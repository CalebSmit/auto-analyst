"""The Analytics Dashboard: across all runs, is this working, and what should we fix?

The live console answers "what is happening right now". This answers the four questions
that decide whether the project continues, and nothing else:

* **Is it healthy?** Outcome mix by week, first-pass yield, where runs stop.
* **What should we fix first?** Failures ranked by frequency, each with the owner the
  diagnostics registry gives it - because the largest class is client trial balances
  that do not foot, and no engineering removes that.
* **Is it getting better?** Auto-accept and override trends, each beside the human
  baseline. The baseline is measured by two analysts on real line items (P24); until it
  is, the dashboard says `unmeasured` rather than inventing one.
* **Is anything stuck?** Quarantined steps, items past SLA, silent runs, drift flags.

Reads the run store; holds no state of its own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from ops.cost import CostMeter
from ops.drift import DriftMonitor
from ops.events import guard_name_and_result
from ops.models import DecisionKind, Outcome, RunState
from ops.run_store import RunRecord, RunStore
from ops.stall import StallDetector
from registries.errors import WHAT_NOW

__all__ = ["Analytics", "Overview"]

OVERRIDES = frozenset({DecisionKind.CORRECTED, DecisionKind.REJECTED})


@dataclass(frozen=True)
class Overview:
    since: str
    head: dict[str, Any]
    outcomes: list[dict[str, Any]]
    funnel: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    trends: dict[str, Any]
    stuck: dict[str, Any]
    skills: list[dict[str, Any]]
    human_baseline_override_rate: float | None = None
    scope_of: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "since": self.since,
            "head": self.head,
            "outcomes": self.outcomes,
            "funnel": self.funnel,
            "failures": self.failures,
            "trends": self.trends,
            "stuck": self.stuck,
            "skills": self.skills,
            "human_baseline_override_rate": self.human_baseline_override_rate,
        }

    def report(self) -> str:
        lines = [f"analytics since {self.since}"]
        lines += [f"  {k:<36} {v}" for k, v in self.head.items()]
        lines.append("  failures, ranked")
        lines += [f"    {f['code']:<32} {f['count']:>4}  [{f['owner']}]" for f in self.failures]
        lines.append("  stuck")
        lines += [f"    {k:<28} {v}" for k, v in self.stuck.items()]
        return "\n".join(lines)


class Analytics:
    def __init__(
        self,
        store: RunStore,
        *,
        meter: CostMeter | None = None,
        drift: DriftMonitor | None = None,
        stall: StallDetector | None = None,
        scope_of: Callable[[str], str | None] | None = None,
        human_baseline_override_rate: float | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.meter = meter or CostMeter(store)
        self.drift = drift or DriftMonitor(store, scope_of=scope_of)
        self.stall = stall
        self._scope_of = scope_of or (lambda _e: "_firm")
        self.human_baseline = human_baseline_override_rate
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    def overview(self, *, days: int = 30) -> Overview:
        now = self._clock()
        since = now - timedelta(days=days)
        since_iso = since.isoformat(timespec="seconds").replace("+00:00", "Z")
        runs = tuple(r for r in self.store.runs() if _parse(r.started_at) >= since)
        finished = tuple(r for r in runs if r.is_finished)
        delivered = tuple(r for r in finished if r.state is RunState.DELIVERED)

        per_run = {r.run_id: self._facts(r) for r in runs}
        return Overview(
            since=since_iso,
            head=self._head(runs, finished, delivered, per_run),
            outcomes=self._outcomes(finished),
            funnel=self._funnel(runs, per_run),
            failures=self._failures(runs, per_run),
            trends=self._trends(runs, per_run),
            stuck=self._stuck(runs, per_run),
            skills=self._skills(runs, per_run),
            human_baseline_override_rate=self.human_baseline,
            scope_of={r.engagement_id: self._scope_of(r.engagement_id) or "_firm" for r in runs},
        )

    # -- one pass over each run's record

    def _facts(self, run: RunRecord) -> dict[str, Any]:
        events = self.store.events(run.run_id)
        items = self.store.review_items(run.run_id)
        decisions = self.store.decisions(run.run_id)
        steps = self.store.steps(run.run_id)
        skill_of_step = {s.step_id: s.skill for s in steps if s.skill}
        guards: dict[str, str] = {}
        routed: dict[str, dict[str, Any]] = {}
        codes: list[str] = []
        released_at: str | None = None
        for e in events:
            if e.level == "guard":
                name, result = guard_name_and_result(e.type)
                guards[name] = result
            if e.diagnostic_code:
                codes.append(e.diagnostic_code)
            if e.type in ("hitl.item.routed", "hitl.item.auto_accepted"):
                skill = _name(str(e.payload.get("skill") or skill_of_step.get(e.step_id or "", "")))
                b = routed.setdefault(skill, {"routed": 0, "auto": 0})
                b["routed"] += 1
                b["auto"] += e.type == "hitl.item.auto_accepted"
            if e.type == "release.written" and released_at is None:
                released_at = e.ts
        corrected_after_release = sum(
            1
            for d in decisions
            if released_at and d.decision is DecisionKind.CORRECTED and d.decided_at > released_at
        )
        return {
            "events": len(events),
            "guards": guards,
            "codes": codes,
            "routed": routed,
            "items": len(items),
            "open_items": sum(1 for i in items if i.state == "open"),
            "decisions": decisions,
            "quarantined": [s for s in steps if str(s.status) == "quarantined"],
            "read": any(e.type == "intake.read" for e in events) or bool(run.sources),
            "dispatched": any(e.type == "skill.completed" for e in events),
            "released": released_at is not None,
            "halted_by_guard": any(e.level == "guard" and e.type.endswith(".fail") for e in events)
            and run.state is RunState.HALTED,
            "corrected_after_release": corrected_after_release,
            "first_event": events[0].ts if events else None,
            "first_review": next((i.created_at for i in items), None),
            "skills": sorted({_name(s) for s in skill_of_step.values()}),
        }

    # -- the four questions

    def _head(
        self,
        runs: tuple[RunRecord, ...],
        finished: tuple[RunRecord, ...],
        delivered: tuple[RunRecord, ...],
        per_run: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        first_pass = [
            r
            for r in delivered
            if not any(
                e
                for e in self.store.events(r.run_id)
                if e.level == "guard" and e.type.endswith(".fail")
            )
        ]
        minutes = [
            (_parse(f["first_review"]) - _parse(r.started_at)).total_seconds() / 60
            for r in runs
            if (f := per_run[r.run_id])["first_review"]
        ]
        spends: dict[str, float] = {}
        for r in runs:
            spends[r.engagement_id] = spends.get(r.engagement_id, 0.0) + r.cost_usd
        return {
            "runs": len(runs),
            "finished": len(finished),
            "first_pass_yield": _ratio(len(first_pass), len(finished)),
            "time_to_first_reviewable_min": round(median(minutes), 1) if minutes else None,
            "review_items_per_run": median(per_run[r.run_id]["items"] for r in runs) if runs else 0,
            "model_spend_per_engagement_usd": round(median(spends.values()), 2) if spends else 0.0,
            "released_then_corrected": sum(f["corrected_after_release"] for f in per_run.values()),
        }

    def _outcomes(self, finished: tuple[RunRecord, ...]) -> list[dict[str, Any]]:
        weeks: dict[str, dict[str, int]] = {}
        for r in finished:
            week = _parse(r.ended_at or r.started_at).strftime("%G-W%V")
            row = weeks.setdefault(
                week, {"clean": 0, "released_with_review": 0, "halted": 0, "blocked": 0}
            )
            row[str(r.outcome or Outcome.BLOCKED)] += 1
        return [{"week": w, **row} for w, row in sorted(weeks.items())]

    def _funnel(
        self, runs: tuple[RunRecord, ...], per_run: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        stages = (
            ("Intake & fingerprint", lambda f: f["read"]),
            ("Mask & payload scan", lambda f: f["guards"].get("payload_scan") == "pass"),
            ("Skills dispatched", lambda f: f["dispatched"]),
            (
                "Guards",
                lambda f: bool(f["guards"]) and all(v == "pass" for v in f["guards"].values()),
            ),
            ("Review resolved", lambda f: f["items"] == 0 or f["open_items"] == 0),
            ("Released", lambda f: f["released"]),
        )
        rows = []
        previous = len(runs)
        for label, reached in stages:
            count = sum(1 for r in runs if reached(per_run[r.run_id]))
            rows.append({"stage": label, "reached": count, "dropped": max(0, previous - count)})
            previous = count
        return rows

    def _failures(
        self, runs: tuple[RunRecord, ...], per_run: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for r in runs:
            for code in per_run[r.run_id]["codes"]:
                counts[code] = counts.get(code, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return [
            {
                "code": code,
                "count": n,
                "owner": WHAT_NOW[code][0] if code in WHAT_NOW else "unknown",
                "what_now": WHAT_NOW[code][1] if code in WHAT_NOW else "",
            }
            for code, n in ranked
        ]

    def _trends(
        self, runs: tuple[RunRecord, ...], per_run: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        routed = sum(b["routed"] for f in per_run.values() for b in f["routed"].values())
        auto = sum(b["auto"] for f in per_run.values() for b in f["routed"].values())
        decided = [d for f in per_run.values() for d in f["decisions"]]
        overridden = sum(1 for d in decided if d.decision in OVERRIDES)
        with_tieout = [f for f in per_run.values() if "tieout" in f["guards"]]
        failed_tieout = [f for f in with_tieout if f["guards"]["tieout"] == "fail"]
        spends: dict[str, float] = {}
        for r in runs:
            spends[r.engagement_id] = spends.get(r.engagement_id, 0.0) + r.cost_usd
        return {
            "auto_accept_rate": _ratio(auto, routed),
            # The denominators, beside the rates they came from. A page that prints a
            # percentage without them is asking to be read as more certain than it is.
            "routed_items": routed,
            "decided_items": len(decided),
            "tieout_checked_runs": len(with_tieout),
            "override_rate": _ratio(overridden, len(decided)),
            "override_rate_human_baseline": (
                self.human_baseline if self.human_baseline is not None else "unmeasured"
            ),
            "tieout_failure_rate": _ratio(len(failed_tieout), len(with_tieout)),
            "cost_per_engagement_usd": round(median(spends.values()), 2) if spends else 0.0,
        }

    def _stuck(
        self, runs: tuple[RunRecord, ...], per_run: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        quarantined = [s for f in per_run.values() for s in f["quarantined"]]
        alerts = self.stall.open_alerts() if self.stall is not None else ()
        overdue = [a for a in alerts if a.kind == "review_overdue"]
        silent = [a for a in alerts if a.kind in ("run_silent", "step_overdue")]
        flags = self.drift.report().flags
        return {
            "quarantined_steps": len(quarantined),
            "review_items_past_sla": len(overdue),
            "review_owners_unassigned": sum(1 for a in overdue if not a.detail.get("assigned_to")),
            "stalled_runs": len({a.run_id for a in silent}),
            "skills_flagged_by_drift": sorted({f"{f.skill} @ {f.scope}" for f in flags}),
        }

    def _skills(
        self, runs: tuple[RunRecord, ...], per_run: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        table: dict[tuple[str, str], dict[str, Any]] = {}
        for r in runs:
            scope = self._scope_of(r.engagement_id) or "_firm"
            f = per_run[r.run_id]
            for skill, b in f["routed"].items():
                row = table.setdefault(
                    (skill, scope),
                    {"items": 0, "auto": 0, "decided": 0, "overridden": 0, "runs": 0},
                )
                row["items"] += b["routed"]
                row["auto"] += b["auto"]
                row["runs"] += 1
            for d in f["decisions"]:
                if not d.skill:
                    continue
                row = table.setdefault(
                    (_name(d.skill), scope),
                    {"items": 0, "auto": 0, "decided": 0, "overridden": 0, "runs": 0},
                )
                row["decided"] += 1
                row["overridden"] += d.decision in OVERRIDES
        return [
            {
                "skill": skill,
                "scope": scope,
                "runs": row["runs"],
                "items": row["items"],
                "auto_accept_rate": _ratio(row["auto"], row["items"]),
                "override_rate": _ratio(row["overridden"], row["decided"]),
                "drift_flags": [f.metric for f in self.drift.report().flagged(skill, scope)],
            }
            for (skill, scope), row in sorted(table.items())
        ]


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else round(numerator / denominator, 4)


def _name(skill: str) -> str:
    return skill.split("@", 1)[0]


def _parse(stamp: str) -> datetime:
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
