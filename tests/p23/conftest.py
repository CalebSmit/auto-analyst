"""Fixtures for P23: scripted runs on a real store and bus.

Nothing here mocks the record. `scripted_run` drives the same store and bus a run
uses - sources, steps, guard verdicts, model calls, review items, decisions, a release -
in the shapes the real nodes emit them, so the scorecard, the trace reducer, the stall
detector and the analytics are tested against events that look exactly like production
ones. Three shapes cover what the phase has to prove: a run that delivered clean, a run
that delivered after a person corrected two items, and a run that halted on tie-out
after a repair loop.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import ports
from ops.events import EventBus
from ops.manifest import close_out
from ops.models import DecisionKind, Outcome, RunState, StepStatus
from ops.run_store import SqlRunStore, open_store
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry

ROOT = Path(__file__).resolve().parents[2]
ENGAGEMENT = "HEND-2026-04"
OTHER_ENGAGEMENT = "MERC-2026-02"
PLAN_HASH = "sha256:" + "7c" * 32
VERSIONS = {
    "model_pin": "claude-sonnet-5 @ effort=high",
    "skills": ["timing-normalization@0.1.0", "line-item-tagging@0.1.0"],
    "contracts": "1.0.0",
    "constraints": "1.0.0",
    "taxonomy": "coa-taxonomy@1.0.0",
}
SOURCES = (
    {
        "source_id": "sha256:" + "ab" * 32,
        "filename": "FY2025 trial balance.xlsx",
        "document_type": "trial_balance",
        "source_version": 1,
        "received_at": "2026-04-02T09:15:00Z",
    },
    {
        "source_id": "sha256:" + "cd" * 32,
        "filename": "FY2024 income statement.xlsx",
        "document_type": "financial_statements",
        "source_version": 1,
        "received_at": "2026-04-02T09:15:00Z",
    },
)
STEPS = (
    ("intake", "io", None),
    ("timing", "skill", "timing-normalization@0.1.0"),
    ("tagging", "skill", "line-item-tagging@0.1.0"),
    ("ebitda", "skill", "ebitda-normalization@0.1.0"),
    ("release", "io", None),
)
REVIEWER = "Dana Whitfield"


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def constraints() -> ConstraintRegistry:
    return ConstraintRegistry.load()


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p23.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


@pytest.fixture
def delivery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    root = tmp_path / "outbox"
    root.mkdir()
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(root))
    ports.reset()
    yield ports.get_delivery()
    ports.reset()


class Clock:
    """A clock the tests move by hand, so 'no event for six hours' is a fact."""

    def __init__(self, start: datetime | None = None) -> None:
        # Starts at the real now: the store stamps steps and events with wall time,
        # and silence is measured against those stamps.
        self.now = start or datetime.now(tz=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> datetime:
        self.now = self.now + timedelta(**delta)
        return self.now

    def reset(self) -> datetime:
        """Back to the real now - after the record has been given fresh, wall-stamped
        events that an advanced clock would otherwise read as old."""
        self.now = datetime.now(tz=UTC)
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


# ------------------------------------------------------------------ scripted runs


class Script:
    """Drives one run through the store and the bus the way the real nodes do."""

    def __init__(self, store: SqlRunStore, bus: EventBus, run_id: str, engagement: str) -> None:
        self.store = store
        self.bus = bus
        self.run_id = run_id
        self.engagement = engagement

    def emit(self, node: str, event_type: str, message: str = "", **kw: Any) -> dict[str, Any]:
        return self.bus.emit(
            run_id=self.run_id,
            engagement_id=self.engagement,
            node_id=node,
            type=event_type,
            message=message or event_type,
            **kw,
        )

    def guard(
        self, node: str, guard: str, passed: bool, checked: int, failed: int = 0, **kw: Any
    ) -> None:
        self.bus.emit_guard(
            run_id=self.run_id,
            engagement_id=self.engagement,
            node_id=node,
            guard=guard,
            passed=passed,
            checked=checked,
            failed=failed,
            **kw,
        )

    def start(self) -> None:
        self.store.start_run(
            run_id=self.run_id,
            engagement_id=self.engagement,
            plan_hash=PLAN_HASH,
            versions=dict(VERSIONS),
            tieout_tolerance=1.0,
        )
        for source in SOURCES:
            self.store.record_source(self.run_id, dict(source))
        self.store.transition(self.run_id, RunState.RUNNING)
        self.emit("intake_window", "run.launched", "set complete", payload={"sources": 2})
        for step_id, kind, skill in STEPS:
            self.store.record_step(self.run_id, step_id, self.key(step_id), kind, skill=skill)

    def key(self, step_id: str) -> str:
        """A step key is a ledger primary key across every run, so it carries the run."""
        digest = hashlib.sha256(f"{self.run_id}/{step_id}".encode()).hexdigest()
        return f"sha256:{digest}"

    def step(self, step_id: str, *, complete: bool = True) -> None:
        """Begin an attempt the way the executor does - the step is now started on the
        record - and, with `complete`, commit it at once."""
        attempt = self.store.begin_attempt(self.run_id, step_id)
        self.emit("step_executor", "step.started", f"{step_id}: attempt {attempt}", step_id=step_id)
        if complete:
            self._finish(step_id)

    def intake(self) -> None:
        self.step("intake", complete=False)
        for source in SOURCES:
            self.emit(
                "doc_reader",
                "intake.read",
                source["filename"],
                step_id="intake",
                payload={"source_id": source["source_id"], "rows": 120},
            )
        self.guard("payload_scan", "payload_scan", True, 2, step_id="intake")
        self._finish("intake")

    def skill(self, step_id: str, skill: str, *, summary: dict[str, Any] | None = None) -> None:
        self.step(step_id, complete=False)
        self.emit(
            "skill_dispatcher",
            "skill.dispatched",
            f"{skill}",
            step_id=step_id,
            payload={"skill": skill},
        )
        self.emit("llm_port", "model.called", "sonnet", step_id=step_id)
        self.store.record_model_call(self.run_id, 0.42, input_tokens=18_400, output_tokens=2_100)
        self.emit(
            "cost_meter",
            "model.answered",
            "$0.42",
            step_id=step_id,
            cost_usd=0.42,
            payload={"model": "claude-sonnet-5", "input_tokens": 18_400, "output_tokens": 2_100},
        )
        self.guard("schema_gate", "schema", True, 1, step_id=step_id)
        self.emit(
            "skill_dispatcher",
            "skill.completed",
            f"{skill}: output",
            step_id=step_id,
            payload={"skill": skill, "summary": summary or {}},
        )
        self._finish(step_id)

    def _finish(self, step_id: str) -> None:
        attempt = next(s.attempts for s in self.store.steps(self.run_id) if s.step_id == step_id)
        self.store.commit_step(
            self.run_id, step_id, self.key(step_id), "sha256:" + "e" * 64, attempt
        )
        self.emit("step_executor", "step.completed", f"{step_id}: done", step_id=step_id)

    def review(
        self,
        item_id: str,
        skill: str,
        *,
        confidence: float,
        due_hours: float = 24.0,
        at: datetime | None = None,
    ) -> None:
        when = at or datetime.now(tz=UTC)
        due = (
            (when + timedelta(hours=due_hours)).isoformat(timespec="seconds").replace("+00:00", "Z")
        )
        self.emit(
            "confidence_router",
            "hitl.item.routed",
            f"{item_id}: review",
            level="warn",
            payload={"item_id": item_id, "skill": skill, "confidence": confidence},
        )
        self.store.open_review_item(
            self.run_id,
            item_id,
            "below_threshold",
            f"{item_id}: category?",
            detail={"skill": skill, "confidence": confidence, "severity": "med"},
            owner=REVIEWER,
            due_at=due,
        )
        self.emit(
            "review_queue",
            "hitl.item.queued",
            f"{item_id} queued",
            level="warn",
            payload={"item_id": item_id, "owner": REVIEWER, "due_at": due},
        )

    def auto_accept(self, item_id: str, skill: str, *, confidence: float) -> None:
        self.emit(
            "confidence_router",
            "hitl.item.auto_accepted",
            f"{item_id}: auto",
            payload={"item_id": item_id, "skill": skill, "confidence": confidence},
        )

    def decide(
        self, item_id: str, decision: DecisionKind, skill: str, rationale: str = "because"
    ) -> None:
        item = next(i for i in self.store.review_items(self.run_id) if i.item_id == item_id)
        self.store.record_decision(
            self.run_id,
            item_id,
            decided_by=REVIEWER,
            decision=decision,
            rationale=rationale,
            writes_precedent=decision in (DecisionKind.ACCEPTED, DecisionKind.CORRECTED),
            expected_version=item.version,
            proposal={"category": "x"},
            answer={"category": "y"} if decision is DecisionKind.CORRECTED else {},
            skill=skill,
        )
        self.emit(
            "decision_log",
            "hitl.item.decided",
            f"{item_id}: {decision}",
            payload={"item_id": item_id, "decision": str(decision), "skill": skill},
        )

    def release(self) -> None:
        self.step("release", complete=False)
        self.guard("numeric_lock", "numeric_lock", True, 14, step_id="release")
        self.guard("unmask_verify", "unmask_verify", True, 1, step_id="release")
        self.guard("deliverable_qc", "deliverable_qc", True, 4, step_id="release")
        self.emit(
            "release_gate",
            "release.written",
            "model released",
            step_id="release",
            payload={"name": "HEND_model.xlsx"},
        )
        self._finish("release")


TIMING_SUMMARY = {
    "periods": ["FY2023", "FY2024", "FY2025"],
    "period_gaps": [],
    "unmatched": 0,
}


def clean_run(
    store: SqlRunStore, bus: EventBus, run_id: str = "run_clean", engagement: str = ENGAGEMENT
) -> Script:
    """Everything measured, everything met, nothing excepted."""
    s = Script(store, bus, run_id, engagement)
    s.start()
    s.intake()
    s.skill("timing", "timing-normalization@0.1.0", summary=TIMING_SUMMARY)
    s.guard("provenance_gate", "provenance", True, 318, step_id="timing")
    s.guard("tieout_gate", "tieout", True, 14, step_id="timing")
    s.skill("tagging", "line-item-tagging@0.1.0")
    s.guard("provenance_gate", "provenance", True, 96, step_id="tagging")
    s.guard("reconcile", "reconcile", True, 96, step_id="tagging")
    for n in range(6):
        s.auto_accept(f"li_{n}", "line-item-tagging@0.1.0", confidence=0.93)
    s.skill("ebitda", "ebitda-normalization@0.1.0")
    s.guard("tieout_gate", "tieout", True, 6, step_id="ebitda")
    s.release()
    return s


def reviewed_run(
    store: SqlRunStore,
    bus: EventBus,
    run_id: str = "run_reviewed",
    engagement: str = ENGAGEMENT,
    *,
    at: datetime | None = None,
) -> Script:
    """Delivered after a person corrected one item and accepted another."""
    s = Script(store, bus, run_id, engagement)
    s.start()
    s.intake()
    s.skill(
        "timing",
        "timing-normalization@0.1.0",
        summary={
            **TIMING_SUMMARY,
            "period_gaps": [{"period_label": "FY2022", "why": "not provided by the client"}],
        },
    )
    s.guard("provenance_gate", "provenance", True, 318, step_id="timing")
    s.guard("tieout_gate", "tieout", True, 14, step_id="timing")
    s.skill("tagging", "line-item-tagging@0.1.0")
    s.guard("provenance_gate", "provenance", True, 96, step_id="tagging")
    s.guard("reconcile", "reconcile", True, 96, step_id="tagging")
    for n in range(4):
        s.auto_accept(f"li_{n}", "line-item-tagging@0.1.0", confidence=0.91)
    s.review("li_10", "line-item-tagging@0.1.0", confidence=0.61, at=at)
    s.review("li_11", "line-item-tagging@0.1.0", confidence=0.58, at=at)
    store.transition(run_id, RunState.WAITING, reason="blocked on tagging")
    s.decide("li_10", DecisionKind.CORRECTED, "line-item-tagging@0.1.0", "it is a fee")
    s.decide("li_11", DecisionKind.ACCEPTED, "line-item-tagging@0.1.0")
    store.transition(run_id, RunState.RUNNING, reason="every review item decided")
    s.emit("review_queue", "run.resumed", "resumed at the frontier")
    s.skill("ebitda", "ebitda-normalization@0.1.0")
    s.guard("tieout_gate", "tieout", True, 6, step_id="ebitda")
    s.release()
    return s


def halted_run(
    store: SqlRunStore, bus: EventBus, run_id: str = "run_halted", engagement: str = ENGAGEMENT
) -> Script:
    """Tie-out failed, the repair loop ran once, tie-out failed again, the run stopped."""
    s = Script(store, bus, run_id, engagement)
    s.start()
    s.intake()
    s.skill("timing", "timing-normalization@0.1.0", summary=TIMING_SUMMARY)
    s.guard("provenance_gate", "provenance", True, 318, step_id="timing")
    s.guard("tieout_gate", "tieout", True, 14, step_id="timing")
    s.skill("tagging", "line-item-tagging@0.1.0")
    s.guard("provenance_gate", "provenance", True, 96, step_id="tagging")
    s.guard("reconcile", "reconcile", True, 96, step_id="tagging")
    s.step("ebitda", complete=False)
    s.emit(
        "skill_dispatcher",
        "skill.dispatched",
        "ebitda",
        step_id="ebitda",
        payload={"skill": "ebitda-normalization@0.1.0"},
    )
    s.guard(
        "tieout_gate",
        "tieout",
        False,
        6,
        1,
        step_id="ebitda",
        diagnostic_code="GUARD.TIEOUT_MISMATCH",
    )
    s.emit(
        "loop_controller",
        "loop.tieout_repair.iteration",
        "iteration 1 of 1",
        level="loop",
        step_id="ebitda",
        payload={"iteration": 1, "ceiling": 1},
    )
    s.guard(
        "tieout_gate",
        "tieout",
        False,
        6,
        1,
        step_id="ebitda",
        diagnostic_code="GUARD.TIEOUT_MISMATCH",
    )
    s.emit(
        "loop_controller",
        "loop.tieout_repair.exhausted",
        "exhausted",
        level="error",
        step_id="ebitda",
        diagnostic_code="LOOP.EXHAUSTED",
    )
    store.finish_step(
        run_id, "ebitda", StepStatus.QUARANTINED, reason="tie-out mismatch after repair"
    )
    s.emit(
        "step_executor",
        "step.quarantined",
        "ebitda: tie-out",
        level="error",
        step_id="ebitda",
        diagnostic_code="GUARD.TIEOUT_MISMATCH",
    )
    store.open_review_item(
        run_id, "tieout_ebitda", "tieout", "FY23 officer comp does not tie", owner=REVIEWER
    )
    return s


def close(
    store: SqlRunStore, bus: EventBus, delivery: Any, run_id: str, state: RunState, outcome: Outcome
) -> dict[str, Any]:
    result = close_out(store, run_id, state, outcome, delivery, bus=bus)
    return result.manifest


ScriptFactory = Callable[..., Script]
