"""The drift monitor: a sustained move per skill and per scope, never a single bad run."""

from __future__ import annotations

import pytest

from ops.drift import DriftMonitor
from ops.events import EventBus
from ops.models import DecisionKind, Outcome, RunState
from ops.run_store import SqlRunStore
from tests.p23.conftest import ENGAGEMENT, OTHER_ENGAGEMENT, Script

SKILL = "line-item-tagging@0.1.0"


def decided_run(
    store: SqlRunStore,
    bus: EventBus,
    run_id: str,
    *,
    engagement: str = ENGAGEMENT,
    decided: int = 10,
    overridden: int = 1,
    confidence: float = 0.9,
) -> None:
    s = Script(store, bus, run_id, engagement)
    s.start()
    for n in range(decided):
        s.review(f"li_{n}", SKILL, confidence=confidence)
        kind = DecisionKind.CORRECTED if n < overridden else DecisionKind.ACCEPTED
        s.decide(f"li_{n}", kind, SKILL)
    store.end_run(run_id, RunState.DELIVERED, Outcome.RELEASED_WITH_REVIEW)


def test_a_sustained_rise_in_override_rate_is_flagged_and_a_single_bad_run_is_not(
    store: SqlRunStore, bus: EventBus
) -> None:
    monitor = DriftMonitor(store, recent=3, baseline=5, rise=0.10, sustained=3)
    for n in range(5):
        decided_run(store, bus, f"base_{n}", overridden=1)  # 10%
    decided_run(store, bus, "bad_once", overridden=5)  # 50%, once
    decided_run(store, bus, "fine_again", overridden=1)
    decided_run(store, bus, "fine_still", overridden=1)
    assert monitor.report().flags == (), "one bad run is not drift"

    for n in range(3):
        decided_run(store, bus, f"worse_{n}", overridden=4)  # 40%, three in a row
    report = monitor.report()
    (flag,) = report.flagged("line-item-tagging")
    assert flag.metric == "override_rate" and flag.direction == "up"
    assert flag.scope == "_firm" and flag.runs == 3
    assert flag.recent == pytest.approx(0.4) and 0.09 < flag.baseline < 0.31
    assert "line-item-tagging @ _firm: override_rate up" in report.report()


def test_drift_is_per_scope_so_a_healthy_scope_does_not_hide_a_degrading_one(
    store: SqlRunStore, bus: EventBus
) -> None:
    scope = {ENGAGEMENT: "valuation/esop", OTHER_ENGAGEMENT: "valuation/non-esop"}
    monitor = DriftMonitor(store, scope_of=scope.get, recent=3, baseline=5, rise=0.10, sustained=3)
    for n in range(5):
        decided_run(store, bus, f"esop_{n}", engagement=ENGAGEMENT, overridden=1)
        decided_run(store, bus, f"non_{n}", engagement=OTHER_ENGAGEMENT, overridden=1)
    for n in range(3):
        decided_run(store, bus, f"esop_bad_{n}", engagement=ENGAGEMENT, overridden=5)
        decided_run(store, bus, f"non_ok_{n}", engagement=OTHER_ENGAGEMENT, overridden=1)
    report = monitor.report()
    assert {(f.skill, f.scope) for f in report.flags} == {("line-item-tagging", "valuation/esop")}
    assert {(s.skill, s.scope) for s in report.series} == {
        ("line-item-tagging", "valuation/esop"),
        ("line-item-tagging", "valuation/non-esop"),
    }
    blended = DriftMonitor(store, recent=3, baseline=5, rise=0.10, sustained=3).report()
    (series,) = blended.series
    assert series.scope == "_firm" and len(series.samples) == 16


def test_confidence_and_guard_failure_series_are_read_from_the_stream(
    store: SqlRunStore, bus: EventBus
) -> None:
    monitor = DriftMonitor(store, recent=2, baseline=4, rise=0.10, sustained=2)
    for n in range(4):
        decided_run(store, bus, f"c_{n}", confidence=0.9)
    for n in range(2):
        decided_run(store, bus, f"low_{n}", confidence=0.6)
    report = monitor.report()
    (flag,) = report.flagged("line-item-tagging")
    assert flag.metric == "mean_confidence" and flag.direction == "down"
    sample = report.series[0].samples[-1]
    assert sample.routed == 10 and sample.confidences == (0.6,) * 10
    assert sample.guard_checks == 0 and sample.guard_failure_rate is None


def test_the_monitor_holds_no_state_and_writes_nothing(store: SqlRunStore, bus: EventBus) -> None:
    decided_run(store, bus, "only")
    before = len(store.events("only"))
    DriftMonitor(store).report()
    DriftMonitor(store).report()
    assert len(store.events("only")) == before
    assert DriftMonitor(store).report().as_dict()["flags"] == []
