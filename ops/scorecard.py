"""The Run Scorecard: did this run actually work, and against what bar?

Guards answer "did this particular check pass". Nothing was answering "did the run
work", which left it a matter of opinion formed by scrolling a log. This module computes
the answer from the record - the event stream, the review items, the run's own counters
- against a versioned criteria file, and names every criterion that failed.

Three things are deliberate:

* **Five verdicts, not two.** `pass`, `pass_with_exceptions`, `halted`, `blocked` and
  `partial`. A run blocked waiting on a person is a staffing signal and a run halted by
  a guard is an engineering one, and a pass rate makes them look identical.
* **Silence is never a pass.** A criterion with nothing in the record to measure is
  `not_measured`. It does not fail the run, but it keeps the verdict off `pass`: a run
  whose deliverable QC never ran did not pass deliverable QC, it never reached it.
* **The claim is checked against the computation.** Close-out says how the run ended;
  the scorecard says what the record supports; `check_claim` refuses the pair when they
  disagree. That is the fail-closed edge on the map: the outcome in the manifest is
  computed, not asserted.

The criteria live in `ops/criteria/`, one file per version, and the manifest records
which version judged the run.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from ops.events import EventBus, guard_name_and_result
from ops.models import DecisionKind, Outcome, RunState
from ops.run_store import EventRecord, RunRecord, RunStore
from registries.constraints import ConstraintRegistry
from registries.errors import (
    OUTCOME_CONTRADICTED,
    UNKNOWN_CRITERIA,
    DiagnosticError,
    RegistryError,
    diagnose,
)

__all__ = [
    "CURRENT_CRITERIA",
    "Criteria",
    "Criterion",
    "CriterionResult",
    "OutcomeContradicted",
    "RunScorecard",
    "Scorecard",
    "Verdict",
    "criteria_versions",
    "load_criteria",
    "verdict_for",
]

ROOT = Path(__file__).resolve().parents[1]
CRITERIA_DIR = ROOT / "ops" / "criteria"
CURRENT_CRITERIA = "run_criteria@1.0.0"
NODE = "run_scorecard"

OVERRIDES = frozenset({DecisionKind.CORRECTED, DecisionKind.REJECTED, DecisionKind.ESCALATED})


class Verdict(StrEnum):
    PASS = "pass"
    PASS_WITH_EXCEPTIONS = "pass_with_exceptions"
    HALTED = "halted"
    BLOCKED = "blocked"
    PARTIAL = "partial"


# Which verdicts each recorded outcome may sit beside. Superseded runs are absent on
# purpose: they keep whatever they had reached, and their verdict is always `partial`.
SUPPORTS: dict[Outcome, frozenset[Verdict]] = {
    Outcome.CLEAN: frozenset({Verdict.PASS}),
    Outcome.RELEASED_WITH_REVIEW: frozenset({Verdict.PASS_WITH_EXCEPTIONS, Verdict.PARTIAL}),
    Outcome.HALTED: frozenset({Verdict.HALTED}),
    Outcome.BLOCKED: frozenset({Verdict.BLOCKED}),
}


# Events that mean something refused the run rather than waited on it: with any of
# these on the record a run that ended undelivered was halted, not blocked. Explicit
# types, never a level.
REFUSALS = frozenset(
    {
        "budget.ceiling_crossed",
        "step.quarantined",
        "lock.timeout",
        "release.blocked",
        "tool.cap_exceeded",
    }
)


class OutcomeContradicted(DiagnosticError):
    """The outcome claimed at close-out is not the one the record supports."""


# ------------------------------------------------------------------ criteria


@dataclass(frozen=True)
class Criterion:
    id: str
    label: str
    bar: str
    guards: tuple[str, ...] = ()
    resolved_by: tuple[str, ...] = ()
    max_failed: int = 0

    def reads_guard(self, name: str) -> bool:
        return any(name == g or name.startswith(g + "_") for g in self.guards)


@dataclass(frozen=True)
class Criteria:
    version: str
    criteria: tuple[Criterion, ...]
    verdicts: dict[str, str] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"run_criteria@{self.version}"

    def get(self, criterion_id: str) -> Criterion:
        return next(c for c in self.criteria if c.id == criterion_id)


def criteria_versions() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in CRITERIA_DIR.glob("run_criteria@*.yaml")))


def load_criteria(version: str = CURRENT_CRITERIA) -> Criteria:
    """The criteria at exactly this version. No 'latest': a run scored against whatever
    file happened to be newest could not say what bar it was judged by."""
    path = CRITERIA_DIR / f"{version}.yaml"
    if not version.startswith("run_criteria@") or not path.is_file():
        raise RegistryError(
            diagnose(
                UNKNOWN_CRITERIA,
                f"{version!r} is not a criteria version on disk; known: "
                f"{', '.join(criteria_versions()) or 'none'}",
                locator=str(path),
            )
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if f"run_criteria@{raw.get('version')}" != version:
        raise RegistryError(
            diagnose(
                UNKNOWN_CRITERIA,
                f"{path.name} declares version {raw.get('version')!r}",
                locator=str(path),
            )
        )
    criteria = tuple(
        Criterion(
            id=str(row["id"]),
            label=str(row["label"]),
            bar=str(row["bar"]),
            guards=tuple(row.get("guards") or ()),
            resolved_by=tuple(row.get("resolved_by") or ()),
            max_failed=int(row.get("max_failed", 0)),
        )
        for row in raw["criteria"]
    )
    unmeasurable = [c.id for c in criteria if c.id not in MEASURES]
    if unmeasurable:
        raise RegistryError(
            diagnose(
                UNKNOWN_CRITERIA,
                f"{version} names criteria this scorecard cannot measure: "
                f"{', '.join(unmeasurable)}. A criterion that is skipped is a criterion "
                f"that quietly stopped applying.",
                locator=str(path),
            )
        )
    return Criteria(
        version=str(raw["version"]),
        criteria=criteria,
        verdicts={str(k): str(v) for k, v in (raw.get("verdicts") or {}).items()},
    )


# ------------------------------------------------------------------ results


@dataclass(frozen=True)
class CriterionResult:
    id: str
    label: str
    bar: str
    status: str
    """`pass`, `fail` or `not_measured`."""
    measured: str
    exceptions: tuple[str, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "bar": self.bar,
            "status": self.status,
            "measured": self.measured,
            "exceptions": list(self.exceptions),
        }


@dataclass(frozen=True)
class Scorecard:
    run_id: str
    criteria_version: str
    verdict: Verdict | None
    """None while the run is still going: criteria so far, no verdict yet."""
    results: tuple[CriterionResult, ...]
    state: RunState
    outcome: Outcome | None

    @property
    def failed(self) -> tuple[str, ...]:
        return tuple(r.id for r in self.results if r.status == "fail")

    @property
    def not_measured(self) -> tuple[str, ...]:
        return tuple(r.id for r in self.results if r.status == "not_measured")

    @property
    def exceptions(self) -> tuple[str, ...]:
        return tuple(f"{r.id}: {e}" for r in self.results for e in r.exceptions)

    @property
    def in_progress(self) -> bool:
        return self.verdict is None

    def as_dict(self) -> dict[str, Any]:
        """The manifest shape, plus the run's own state for the console."""
        return {
            "criteria_version": self.criteria_version,
            "verdict": str(self.verdict) if self.verdict else None,
            "failed": list(self.failed),
            "criteria": [r.as_dict() for r in self.results],
        }

    def manifest_entry(self) -> dict[str, Any]:
        if self.verdict is None:
            raise ValueError(f"{self.run_id} has not ended; a manifest needs a verdict")
        return self.as_dict()

    def report(self) -> str:
        head = (
            f"{self.run_id}  IN PROGRESS"
            if self.verdict is None
            else f"{self.run_id}  {str(self.verdict).upper()}"
            + (f" · failed: {', '.join(self.failed)}" if self.failed else "")
        )
        marks = {"pass": "PASS", "fail": "FAIL", "not_measured": "n/a "}
        lines = [head, f"  criteria {self.criteria_version}"]
        for r in self.results:
            lines.append(f"  {marks[r.status]}  {r.label:<20} {r.measured}")
            lines += [f"          - {e}" for e in r.exceptions]
        return "\n".join(lines)


def verdict_for(
    state: RunState | None,
    outcome: Outcome | None,
    results: tuple[CriterionResult, ...],
    human_decisions: int = 0,
    *,
    refused: bool = False,
) -> Verdict | None:
    """The verdict, from how the run ended and what the criteria measured.

    A run that ended without delivering was *halted* if something refused it - a guard,
    a quarantine, a ceiling - and *blocked* if nothing did and it was simply waiting on
    a person who never answered. A delivered run passes only when every criterion was
    measured and met and nothing was excepted - a reported gap, a corrected item, a
    repaired tie-out, a criterion never reached - and it is partial the moment one
    criterion failed.
    """
    if state is None or state not in (RunState.DELIVERED, RunState.HALTED, RunState.SUPERSEDED):
        return None
    if state is RunState.HALTED:
        return Verdict.HALTED if refused else Verdict.BLOCKED
    if state is RunState.SUPERSEDED:
        return Verdict.PARTIAL
    if any(r.status == "fail" for r in results):
        return Verdict.PARTIAL
    excepted = any(r.status == "not_measured" or r.exceptions for r in results)
    if excepted or human_decisions:
        return Verdict.PASS_WITH_EXCEPTIONS
    return Verdict.PASS


# ------------------------------------------------------------------ the record


@dataclass(frozen=True)
class Record:
    """Everything a criterion may read, fetched once."""

    run: RunRecord
    events: tuple[EventRecord, ...]
    steps: tuple[Any, ...]
    review_items: tuple[Any, ...]
    decisions: tuple[Any, ...]
    ceilings: Mapping[str, float]

    def latest_guards(self, criterion: Criterion) -> dict[tuple[str, str | None], EventRecord]:
        """The last verdict of each guard the criterion reads, per step. A repair loop
        that failed and then passed counts as a pass with an exception, not a failure."""
        latest: dict[tuple[str, str | None], EventRecord] = {}
        for e in self.events:
            if e.level != "guard":
                continue
            name, _ = guard_name_and_result(e.type)
            if criterion.reads_guard(name):
                latest[(name, e.step_id)] = e
        return latest

    def earlier_failures(self, criterion: Criterion) -> dict[tuple[str, str | None], int]:
        counts: dict[tuple[str, str | None], int] = {}
        for e in self.events:
            if e.level != "guard":
                continue
            name, result = guard_name_and_result(e.type)
            if criterion.reads_guard(name) and result == "fail":
                counts[(name, e.step_id)] = counts.get((name, e.step_id), 0) + 1
        return counts

    def summaries(self, skill_prefix: str) -> tuple[dict[str, Any], ...]:
        """What a skill said about its own output on `skill.completed`."""
        return tuple(
            dict(e.payload.get("summary") or {})
            for e in self.events
            if e.type == "skill.completed"
            and str(e.payload.get("skill", "")).startswith(skill_prefix)
            and e.payload.get("summary")
        )


def _guard_criterion(
    criterion: Criterion, record: Record, *, unit: str, not_reached: str
) -> CriterionResult:
    latest = record.latest_guards(criterion)
    if not latest:
        return CriterionResult(
            criterion.id, criterion.label, criterion.bar, "not_measured", not_reached
        )
    checked = sum(int(e.payload.get("checked", 0)) for e in latest.values())
    failed = sum(int(e.payload.get("failed", 0)) for e in latest.values())
    failing = [e for e in latest.values() if guard_name_and_result(e.type)[1] == "fail"]
    repaired = [
        f"{name} on {step or 'the run'} passed after {n} failed attempt(s)"
        for (name, step), n in record.earlier_failures(criterion).items()
        if guard_name_and_result(latest[(name, step)].type)[1] == "pass"
    ]
    status = "pass" if not failing and failed <= criterion.max_failed else "fail"
    codes = sorted({e.diagnostic_code for e in failing if e.diagnostic_code})
    return CriterionResult(
        criterion.id,
        criterion.label,
        criterion.bar,
        status,
        f"{checked - failed} / {checked} {unit}"
        if checked
        else f"{len(latest)} check(s), 0 {unit}",
        tuple(repaired),
        {"checked": checked, "failed": failed, "codes": codes},
    )


def _document_coverage(criterion: Criterion, record: Record) -> CriterionResult:
    sources = record.run.sources
    gaps = record.run.coverage_gaps
    read = {
        str(e.payload.get("source_id"))
        for e in record.events
        if e.type == "intake.read" and e.payload.get("source_id")
    }
    if not sources and not gaps:
        return CriterionResult(
            criterion.id, criterion.label, criterion.bar, "not_measured", "no sources recorded"
        )
    processed = [s for s in sources if s.get("source_id") in read]
    exceptions = tuple(f"gap reported: {g['what']} - {g['why']}" for g in gaps)
    status = "pass" if len(processed) == len(sources) else "fail"
    unread = [s.get("filename", s.get("source_id")) for s in sources if s not in processed]
    return CriterionResult(
        criterion.id,
        criterion.label,
        criterion.bar,
        status,
        f"{len(processed)} / {len(sources)} documents"
        + (f", {len(gaps)} gap(s) reported" if gaps else ""),
        exceptions,
        {"unprocessed": unread},
    )


def _period_coverage(criterion: Criterion, record: Record) -> CriterionResult:
    summaries = record.summaries("timing-normalization")
    if not summaries:
        return CriterionResult(
            criterion.id, criterion.label, criterion.bar, "not_measured", "not normalized"
        )
    latest = summaries[-1]
    periods = [str(p) for p in latest.get("periods") or ()]
    gaps = list(latest.get("period_gaps") or ())
    unexplained = [g for g in gaps if not str(g.get("why", "")).strip()]
    status = "pass" if periods and not unexplained else "fail"
    span = f"{periods[0]}-{periods[-1]}" if periods else "no periods"
    return CriterionResult(
        criterion.id,
        criterion.label,
        criterion.bar,
        status,
        span + (f", {len(gaps)} gap(s) reported" if gaps else ""),
        tuple(f"gap reported: {g.get('period_label')} - {g.get('why')}" for g in gaps),
        {"periods": periods, "unexplained": len(unexplained)},
    )


def _conflicts(criterion: Criterion, record: Record) -> CriterionResult:
    base = _guard_criterion(criterion, record, unit="conflicts", not_reached="not reconciled")
    if base.status != "fail":
        return base
    # A surfaced conflict is not a failure if a person resolved it: the loop controller
    # queues both positions when a resolution loop exhausts, and a decision closes it.
    kinds = set(criterion.resolved_by)
    decided_items = {d.item_id for d in record.decisions}
    resolved = [i for i in record.review_items if i.kind in kinds and i.item_id in decided_items]
    open_conflicts = max(0, int(base.detail["failed"]) - len(resolved))
    status = "pass" if open_conflicts <= criterion.max_failed else "fail"
    return CriterionResult(
        criterion.id,
        criterion.label,
        criterion.bar,
        status,
        f"{open_conflicts} open of {base.detail['failed']} surfaced",
        tuple(f"{i.item_id} resolved by a person" for i in resolved),
        {**base.detail, "resolved": len(resolved)},
    )


def _budget(criterion: Criterion, record: Record) -> CriterionResult:
    run = record.run
    crossed = [e for e in record.events if e.type == "budget.ceiling_crossed"]
    loops = sum(1 for e in record.events if e.level == "loop")
    position = {
        "usd_max": run.cost_usd,
        "tokens_max": run.input_tokens + run.output_tokens,
        "wall_clock_s": run.active_seconds,
        "loop_iterations_max": loops,
    }
    over = [k for k, v in position.items() if v > float(record.ceilings.get(k, float("inf")))]
    status = "pass" if not crossed and not over else "fail"
    usd_max = float(record.ceilings.get("usd_max", 0.0))
    return CriterionResult(
        criterion.id,
        criterion.label,
        criterion.bar,
        status,
        f"${run.cost_usd:.2f} / ${usd_max:.0f}, {loops} loop iteration(s)",
        (),
        {"position": position, "crossed": [e.payload.get("ceiling") for e in crossed] + over},
    )


def _review_outstanding(criterion: Criterion, record: Record) -> CriterionResult:
    open_items = [i for i in record.review_items if i.state == "open"]
    overridden = [d for d in record.decisions if d.decision in OVERRIDES]
    status = "pass" if len(open_items) <= criterion.max_failed else "fail"
    return CriterionResult(
        criterion.id,
        criterion.label,
        criterion.bar,
        status,
        f"{len(open_items)} open, {len(record.decisions)} decided",
        tuple(f"{d.item_id}: {d.decision} by {d.decided_by}" for d in overridden),
        {"open": [i.item_id for i in open_items]},
    )


def _provenance(criterion: Criterion, record: Record) -> CriterionResult:
    return _guard_criterion(criterion, record, unit="figures", not_reached="no figures checked")


def _tieout(criterion: Criterion, record: Record) -> CriterionResult:
    return _guard_criterion(criterion, record, unit="totals", not_reached="no totals checked")


def _residual_masking(criterion: Criterion, record: Record) -> CriterionResult:
    return _guard_criterion(criterion, record, unit="payloads", not_reached="nothing scanned")


def _numeric_integrity(criterion: Criterion, record: Record) -> CriterionResult:
    return _guard_criterion(criterion, record, unit="figures", not_reached="nothing locked")


def _deliverable_qc(criterion: Criterion, record: Record) -> CriterionResult:
    return _guard_criterion(criterion, record, unit="checks", not_reached="not reached")


MEASURES: dict[str, Callable[[Criterion, Record], CriterionResult]] = {
    "document_coverage": _document_coverage,
    "period_coverage": _period_coverage,
    "provenance": _provenance,
    "tieout": _tieout,
    "conflicts": _conflicts,
    "residual_masking": _residual_masking,
    "numeric_integrity": _numeric_integrity,
    "budget": _budget,
    "review_outstanding": _review_outstanding,
    "deliverable_qc": _deliverable_qc,
}


# ------------------------------------------------------------------ the scorecard


class RunScorecard:
    """Deterministic, computed from the record. Reads; writes nothing."""

    def __init__(
        self,
        store: RunStore,
        bus: EventBus | None = None,
        constraints: ConstraintRegistry | None = None,
        criteria: Criteria | None = None,
    ) -> None:
        self.store = store
        self.bus = bus
        self.constraints = constraints or ConstraintRegistry.load()
        self.criteria = criteria or load_criteria()

    def score(
        self,
        run_id: str,
        *,
        ending: tuple[RunState, Outcome] | None = None,
    ) -> Scorecard:
        """Every criterion, and the verdict if the run has ended.

        `ending` scores a run as if it had just ended that way - what close-out asks
        before it ends the run, so a contradiction is refused before anything is
        written rather than discovered after.
        """
        run = self.store.run(run_id)
        record = Record(
            run=run,
            events=self.store.events(run_id),
            steps=self.store.steps(run_id),
            review_items=self.store.review_items(run_id),
            decisions=self.store.decisions(run_id),
            ceilings={k: float(v) for k, v in self.constraints.ceilings["per_run"].items()},
        )
        results = tuple(MEASURES[c.id](c, record) for c in self.criteria.criteria)
        state, outcome = ending if ending else (run.state, run.outcome)
        if ending is None and not run.is_finished:
            state = RunState.RUNNING
        refused = (
            any(r.status == "fail" and self.criteria.get(r.id).guards for r in results)
            or any(str(s.status) == "quarantined" for s in record.steps)
            or any(
                e.type in REFUSALS or e.type.endswith((".exhausted", ".refused"))
                for e in record.events
            )
        )
        return Scorecard(
            run_id=run_id,
            criteria_version=self.criteria.key,
            verdict=verdict_for(state, outcome, results, len(record.decisions), refused=refused),
            results=results,
            state=state,
            outcome=outcome,
        )

    def check_claim(self, run_id: str, state: RunState, outcome: Outcome) -> Scorecard:
        """Score the run as ending this way, and refuse if the record disagrees.

        The one place the outcome in the manifest is made a computed fact: `clean` has
        to be earned by every criterion, `released_with_review` by a delivered run with
        something excepted or failed, and halted or blocked by having ended that way.
        """
        card = self.score(run_id, ending=(state, outcome))
        supported = SUPPORTS.get(outcome)
        if state is not RunState.SUPERSEDED and supported and card.verdict not in supported:
            why = f"close-out claims {outcome} but the record supports {card.verdict}"
            if card.failed:
                why += f" (failed: {', '.join(card.failed)})"
            if card.verdict is Verdict.PASS_WITH_EXCEPTIONS:
                parts = []
                if card.not_measured:
                    parts.append(f"{', '.join(card.not_measured)} not measured")
                if card.exceptions:
                    parts.append(f"{len(card.exceptions)} exception(s)")
                why += f" (excepted: {'; '.join(parts)})"
            raise OutcomeContradicted(
                diagnose(
                    OUTCOME_CONTRADICTED,
                    why,
                    locator=run_id,
                    expected=" or ".join(sorted(str(v) for v in supported)),
                    found=str(card.verdict),
                )
            )
        return card

    def emit(self, card: Scorecard, engagement_id: str) -> None:
        """Say the verdict on the bus, for the console. The manifest is the record."""
        if self.bus is None or card.verdict is None:
            return
        self.bus.emit(
            run_id=card.run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type="run.scored",
            message=f"{card.verdict}"
            + (f" - failed: {', '.join(card.failed)}" if card.failed else ""),
            level="error" if card.verdict in (Verdict.HALTED, Verdict.PARTIAL) else "info",
            payload={
                "verdict": str(card.verdict),
                "criteria_version": card.criteria_version,
                "failed": list(card.failed),
                "not_measured": list(card.not_measured),
                "exceptions": len(card.exceptions),
            },
        )
