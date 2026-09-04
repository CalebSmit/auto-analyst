"""A stalled review item raises an alert against its SLA - and a silent run, an overdue
step and a guard that keeps failing each raise one too, once per episode."""

from __future__ import annotations

from datetime import UTC, datetime

from ops.events import EventBus
from ops.models import DecisionKind, RunState
from ops.run_store import SqlRunStore
from ops.stall import StallDetector
from tests.p23.conftest import ENGAGEMENT, Clock, Script, reviewed_run


def detector(store: SqlRunStore, bus: EventBus, clock: Clock, **kw: object) -> StallDetector:
    return StallDetector(store, bus, clock=clock, **kw)  # type: ignore[arg-type]


def test_a_review_item_past_its_sla_raises_an_alert_to_its_owner(
    store: SqlRunStore, bus: EventBus, clock: Clock
) -> None:
    s = Script(store, bus, "run_sla", ENGAGEMENT)
    s.start()
    s.review("li_10", "line-item-tagging@0.1.0", confidence=0.6, due_hours=24, at=clock())
    store.transition("run_sla", RunState.WAITING, reason="blocked on tagging")
    stalls = detector(store, bus, clock)

    assert stalls.scan() == (), "not yet due"
    clock.advance(hours=25)
    (alert,) = stalls.scan()
    assert alert.kind == "review_overdue" and alert.subject == "li_10"
    assert alert.code == "PROCESS.REVIEW_SLA_BREACH" and alert.owner == "process"
    assert alert.detail["assigned_to"] == "Dana Whitfield" and alert.emitted
    raised = [e for e in store.events("run_sla") if e.type == "alert.review_overdue"]
    assert len(raised) == 1
    assert raised[0].diagnostic_code == "PROCESS.REVIEW_SLA_BREACH"
    assert raised[0].node_id == "stall_alert" and raised[0].payload["owner"] == "process"
    assert "what to do" not in raised[0].message and raised[0].message.startswith("li_10")

    # Raised once per item: a second scan finds it still overdue and says nothing new.
    clock.advance(hours=1)
    (again,) = stalls.scan()
    assert again.kind == "review_overdue" and not again.emitted
    assert len([e for e in store.events("run_sla") if e.type == "alert.review_overdue"]) == 1

    # A person decides it, and it is no longer anybody's alert.
    s.decide("li_10", DecisionKind.ACCEPTED, "line-item-tagging@0.1.0")
    assert stalls.scan() == ()


def test_a_running_run_that_goes_quiet_is_a_visible_fact(
    store: SqlRunStore, bus: EventBus, clock: Clock
) -> None:
    s = Script(store, bus, "run_quiet", ENGAGEMENT)
    s.start()
    s.step("timing", complete=False)
    stalls = detector(store, bus, clock, silence_s=1800)
    assert not [a for a in stalls.scan() if a.kind == "run_silent"]

    clock.advance(hours=2)
    kinds = {a.kind: a for a in stalls.scan()}
    assert (
        kinds["run_silent"].code == "PROCESS.RUN_STALLED" and kinds["run_silent"].owner == "system"
    )
    assert kinds["step_overdue"].subject == "timing"
    assert kinds["step_overdue"].code == "PROCESS.RUN_STALLED"
    silent = [e for e in store.events("run_quiet") if e.type == "alert.run_silent"]
    assert len(silent) == 1

    # The alert itself is not activity: another scan raises nothing new...
    clock.advance(hours=1)
    stalls.scan()
    assert len([e for e in store.events("run_quiet") if e.type == "alert.run_silent"]) == 1
    # ...but the run speaking again ends the episode, and a new silence is a new alert.
    s.emit("step_executor", "step.completed", "timing: done", step_id="timing")
    clock.reset()
    assert not [a for a in stalls.scan() if a.kind == "run_silent"]
    clock.advance(hours=2)
    stalls.scan()
    assert len([e for e in store.events("run_quiet") if e.type == "alert.run_silent"]) == 2


def test_a_waiting_run_is_not_silent_and_a_finished_run_is_not_watched(
    store: SqlRunStore, bus: EventBus, clock: Clock
) -> None:
    reviewed = reviewed_run(store, bus, "run_w", at=clock())
    store.transition("run_w", RunState.WAITING, reason="a question")
    stalls = detector(store, bus, clock)
    clock.advance(days=3)
    assert not [a for a in stalls.scan() if a.kind in ("run_silent", "step_overdue")]
    store.end_run(
        "run_w", RunState.HALTED, __import__("ops.models", fromlist=["Outcome"]).Outcome.BLOCKED
    )
    assert reviewed.run_id == "run_w"
    assert stalls.scan() == ()


def test_a_guard_that_keeps_failing_is_an_alert_with_the_guards_own_code(
    store: SqlRunStore, bus: EventBus, clock: Clock
) -> None:
    s = Script(store, bus, "run_rep", ENGAGEMENT)
    s.start()
    for _ in range(3):
        s.guard(
            "tieout_gate",
            "tieout",
            False,
            6,
            1,
            step_id="ebitda",
            diagnostic_code="GUARD.TIEOUT_MISMATCH",
        )
    stalls = detector(store, bus, clock, repeated_failures=3)
    (alert,) = [a for a in stalls.scan() if a.kind == "guard_repeating"]
    assert alert.subject == "tieout" and alert.code == "GUARD.TIEOUT_MISMATCH"
    assert alert.owner == "client-data", "the trial balance does not foot; not our defect"
    assert alert.detail["failures"] == 3
    assert [e for e in store.events("run_rep") if e.type == "alert.guard_repeating"]


def test_the_detector_decides_nothing_about_the_run(
    store: SqlRunStore, bus: EventBus, clock: Clock
) -> None:
    s = Script(store, bus, "run_hands_off", ENGAGEMENT)
    s.start()
    s.review("li_1", "line-item-tagging@0.1.0", confidence=0.5, due_hours=1, at=clock())
    clock.advance(hours=2)
    before = store.run("run_hands_off")
    detector(store, bus, clock).scan()
    after = store.run("run_hands_off")
    assert after.state is before.state and after.ended_at is None
    assert [i.state for i in store.review_items("run_hands_off")] == ["open"]
    assert datetime.now(tz=UTC) is not None
