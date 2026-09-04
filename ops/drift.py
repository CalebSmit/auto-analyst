"""The Drift Monitor: watches whether a skill is quietly getting worse.

Model providers update models. Clients change their chart of accounts. A skill edit has
an effect nobody predicted. None announce themselves and none show in a single run. The
override rate is the one number that moves when any of them does - and it is split by
scope, because the same skill can be healthy in non-ESOP work and degrading in ESOP work,
which a single blended number would hide.

Derived from the decision log and the event stream, per skill and per scope, over the
runs that have ended. Three series per pair: human override rate, confidence at the
routing gate, and guard failure rate. A flag needs a **sustained** move - each of the
last few runs above the earlier baseline by the margin - never a single bad run.

This is the outermost loop on the map and it is a static node: never part of any run,
never emitting into one. A flag is a report the analytics view shows and the governance
chain (P27) opens a re-review from. It changes nothing on its own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ops.events import guard_name_and_result
from ops.models import DecisionKind
from ops.run_store import RunStore

__all__ = ["DriftMonitor", "DriftReport", "Flag", "Sample", "Series"]

OVERRIDES = frozenset({DecisionKind.CORRECTED, DecisionKind.REJECTED})
FIRM_SCOPE = "_firm"
METRICS = ("override_rate", "guard_failure_rate", "mean_confidence")


@dataclass(frozen=True)
class Sample:
    """One run's numbers for one skill in one scope."""

    run_id: str
    ended_at: str
    skill: str
    scope: str
    decided: int = 0
    overridden: int = 0
    routed: int = 0
    auto_accepted: int = 0
    confidences: tuple[float, ...] = ()
    guard_checks: int = 0
    guard_failures: int = 0

    @property
    def override_rate(self) -> float | None:
        return None if self.decided == 0 else self.overridden / self.decided

    @property
    def guard_failure_rate(self) -> float | None:
        return None if self.guard_checks == 0 else self.guard_failures / self.guard_checks

    @property
    def mean_confidence(self) -> float | None:
        return None if not self.confidences else sum(self.confidences) / len(self.confidences)

    def value(self, metric: str) -> float | None:
        found: float | None = getattr(self, metric)
        return found


@dataclass(frozen=True)
class Flag:
    skill: str
    scope: str
    metric: str
    recent: float
    baseline: float
    runs: int
    """How many consecutive recent runs sat past the margin."""
    direction: str
    """`up` for a rate that rose, `down` for a confidence that fell."""

    def line(self) -> str:
        return (
            f"{self.skill} @ {self.scope}: {self.metric} {self.direction} "
            f"{self.baseline:.1%} -> {self.recent:.1%} over the last {self.runs} run(s)"
        )


@dataclass(frozen=True)
class Series:
    skill: str
    scope: str
    samples: tuple[Sample, ...]
    """Oldest first."""

    def rate(self, metric: str, window: tuple[Sample, ...]) -> float | None:
        values = [v for v in (s.value(metric) for s in window) if v is not None]
        return None if not values else sum(values) / len(values)


@dataclass(frozen=True)
class DriftReport:
    series: tuple[Series, ...]
    flags: tuple[Flag, ...]
    recent: int
    baseline: int
    rise: float
    sustained: int

    def flagged(self, skill: str, scope: str | None = None) -> tuple[Flag, ...]:
        return tuple(
            f for f in self.flags if f.skill == skill and (scope is None or f.scope == scope)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "window": {
                "recent": self.recent,
                "baseline": self.baseline,
                "rise": self.rise,
                "sustained": self.sustained,
            },
            "series": [
                {
                    "skill": s.skill,
                    "scope": s.scope,
                    "runs": len(s.samples),
                    "override_rate": s.rate("override_rate", s.samples[-self.recent :]),
                    "guard_failure_rate": s.rate("guard_failure_rate", s.samples[-self.recent :]),
                    "mean_confidence": s.rate("mean_confidence", s.samples[-self.recent :]),
                }
                for s in self.series
            ],
            "flags": [
                {
                    "skill": f.skill,
                    "scope": f.scope,
                    "metric": f.metric,
                    "recent": f.recent,
                    "baseline": f.baseline,
                    "runs": f.runs,
                    "direction": f.direction,
                }
                for f in self.flags
            ],
        }

    def report(self) -> str:
        lines = [f"drift monitor: {len(self.series)} skill/scope series, {len(self.flags)} flag(s)"]
        lines += [f"  FLAG  {f.line()}" for f in self.flags]
        return "\n".join(lines)


class DriftMonitor:
    def __init__(
        self,
        store: RunStore,
        *,
        scope_of: Callable[[str], str | None] | None = None,
        recent: int = 5,
        baseline: int = 10,
        rise: float = 0.05,
        sustained: int = 3,
    ) -> None:
        """`scope_of(engagement_id)` names the scope a run belongs to - the roster knows;
        without one every run is scored at the firm scope. `recent` runs are compared to
        the `baseline` runs before them; a flag needs the last `sustained` runs each past
        the baseline by `rise`."""
        self.store = store
        self._scope_of = scope_of or (lambda _engagement: FIRM_SCOPE)
        self.recent = recent
        self.baseline = baseline
        self.rise = rise
        self.sustained = sustained

    # -- reading the record

    def samples(self) -> tuple[Sample, ...]:
        """Every (run, skill) pair with anything to say, oldest run first."""
        found: list[Sample] = []
        runs = sorted(
            (r for r in self.store.runs() if r.is_finished), key=lambda r: r.ended_at or ""
        )
        for run in runs:
            scope = self._scope_of(run.engagement_id) or FIRM_SCOPE
            per_skill: dict[str, dict[str, Any]] = {}

            def bucket(skill: str, table: dict[str, dict[str, Any]] = per_skill) -> dict[str, Any]:
                return table.setdefault(
                    skill,
                    {
                        "decided": 0,
                        "overridden": 0,
                        "routed": 0,
                        "auto": 0,
                        "conf": [],
                        "checks": 0,
                        "fails": 0,
                    },
                )

            for d in self.store.decisions(run.run_id):
                if not d.skill:
                    continue
                b = bucket(_name(d.skill))
                b["decided"] += 1
                b["overridden"] += d.decision in OVERRIDES
            skill_of_step = {s.step_id: s.skill for s in self.store.steps(run.run_id) if s.skill}
            for e in self.store.events(run.run_id):
                if e.type in ("hitl.item.routed", "hitl.item.auto_accepted"):
                    skill = e.payload.get("skill")
                    if not skill:
                        continue
                    b = bucket(_name(str(skill)))
                    b["routed"] += 1
                    b["auto"] += e.type == "hitl.item.auto_accepted"
                    confidence = e.payload.get("confidence")
                    if isinstance(confidence, int | float):
                        b["conf"].append(float(confidence))
                elif e.level == "guard" and e.step_id in skill_of_step:
                    b = bucket(_name(str(skill_of_step[e.step_id])))
                    _, result = guard_name_and_result(e.type)
                    b["checks"] += 1
                    b["fails"] += result == "fail"
            for skill, b in sorted(per_skill.items()):
                found.append(
                    Sample(
                        run_id=run.run_id,
                        ended_at=run.ended_at or "",
                        skill=skill,
                        scope=scope,
                        decided=b["decided"],
                        overridden=b["overridden"],
                        routed=b["routed"],
                        auto_accepted=b["auto"],
                        confidences=tuple(b["conf"]),
                        guard_checks=b["checks"],
                        guard_failures=b["fails"],
                    )
                )
        return tuple(found)

    def series(self) -> tuple[Series, ...]:
        grouped: dict[tuple[str, str], list[Sample]] = {}
        for sample in self.samples():
            grouped.setdefault((sample.skill, sample.scope), []).append(sample)
        return tuple(
            Series(skill, scope, tuple(samples))
            for (skill, scope), samples in sorted(grouped.items())
        )

    # -- the judgement

    def report(self) -> DriftReport:
        flags: list[Flag] = []
        series = self.series()
        for s in series:
            for metric in METRICS:
                flag = self._flag(s, metric)
                if flag is not None:
                    flags.append(flag)
        return DriftReport(
            series=series,
            flags=tuple(flags),
            recent=self.recent,
            baseline=self.baseline,
            rise=self.rise,
            sustained=self.sustained,
        )

    def _flag(self, series: Series, metric: str) -> Flag | None:
        """Sustained: every one of the last `sustained` runs past the margin against
        the runs before the recent window. One bad run flags nothing."""
        with_values = tuple(s for s in series.samples if s.value(metric) is not None)
        if len(with_values) < self.sustained + 1:
            return None
        recent = with_values[-self.recent :]
        earlier = with_values[: -self.recent][-self.baseline :] or with_values[:1]
        if earlier is recent or not earlier:
            return None
        base = series.rate(metric, earlier)
        now = series.rate(metric, recent)
        if base is None or now is None:
            return None
        worse_is_down = metric == "mean_confidence"
        tail = with_values[-self.sustained :]
        if worse_is_down:
            sustained = all((s.value(metric) or 0.0) <= base - self.rise for s in tail)
            moved = now <= base - self.rise
        else:
            sustained = all((s.value(metric) or 0.0) >= base + self.rise for s in tail)
            moved = now >= base + self.rise
        if not (moved and sustained):
            return None
        return Flag(
            skill=series.skill,
            scope=series.scope,
            metric=metric,
            recent=now,
            baseline=base,
            runs=len(tail),
            direction="down" if worse_is_down else "up",
        )


def _name(skill: str) -> str:
    return skill.split("@", 1)[0]
