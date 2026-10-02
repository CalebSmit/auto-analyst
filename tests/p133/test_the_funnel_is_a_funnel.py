"""P133: "Where runs stop" was not a funnel.

Found on the Analytics page, running against a store of eighteen real runs. It read:

    Intake & fingerprint   18 of 18
    Mask & payload scan    11 of 18   -7 here
    Skills dispatched       0 of 18   -11 here
    Guards                 17 of 18
    Review resolved        16 of 18   -1 here
    Released                0 of 18   -16 here

Seventeen runs got through the guards and none of them ran a skill. The panel's own
sentence is *every run passes through these in order*, and those numbers cannot be that.

**What was wrong.** Each stage counted every run matching its own predicate, with no
reference to whether that run got through the stages before it. A run can have a passing
payload scan as its only guard and never dispatch a skill, so it counted under "Guards"
without having counted under the stage before. The `dropped` column was
`max(0, previous - count)`, which clamped the impossible negative to zero - so the panel
hid its own contradiction instead of showing it.

**And one label was for a different measure.** "Skills dispatched" counted
`skill.completed`, so a run whose skill was dispatched and then quarantined read as not
having dispatched one. That is the difference between *the work never started* and *the
work started and stopped*, and on a bad day it is the state most runs are in.

What the panel says now, on the same eighteen runs: 18 intake, 11 past the mask, 0 ran a
skill. The work stops at the skills, which is the truth and is what somebody opens this
panel to find out.
"""

from __future__ import annotations

from typing import Any

from ops.analytics import Analytics
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.events import EventBus
from ops.run_store import SqlRunStore
from ops.stall import StallDetector
from tests.p23.conftest import Clock, Script, clean_run


def view(store: SqlRunStore, bus: EventBus, clock: Clock) -> Any:
    return Analytics(store, stall=StallDetector(store, bus, clock=clock), clock=clock).overview()


def a_run_that_passed_a_late_stage_and_not_an_early_one(
    store: SqlRunStore, bus: EventBus, run_id: str
) -> None:
    """The shape that broke it, built on purpose.

    Intake, then a guard that passes - and no skill. Under the old counting this run
    counted under "Guards" (it has a guard and all of them passed) without counting under
    the stage before it, which is how a later stage came to report more than an earlier.
    """
    s = Script(store, bus, run_id, "BAT-ODD")
    s.start()
    s.intake()
    s.guard("payload_scan", "payload_scan", True, 1, step_id="mask")
    s.guard("provenance_gate", "provenance", True, 4, step_id="timing")


# ------------------------------------------------------------------ it is a funnel now


def test_a_stage_never_reports_more_than_the_stage_before_it(
    store: SqlRunStore, bus: EventBus, clock: Clock
) -> None:
    """The property that makes it a funnel, held against the shape that broke it."""
    a_run_that_passed_a_late_stage_and_not_an_early_one(store, bus, "run_odd")
    stages = view(store, bus, clock).funnel

    reached = [s["reached"] for s in stages]
    assert reached == sorted(reached, reverse=True), (
        f"a later stage reports more than an earlier one: "
        f"{[(s['stage'], s['reached']) for s in stages]}"
    )


def test_the_run_that_broke_it_is_counted_where_it_actually_stopped(
    store: SqlRunStore, bus: EventBus, clock: Clock
) -> None:
    """Not just monotonic - correct. This run reached intake and the mask and never ran a
    skill, so it is in the first two stages and in none after."""
    a_run_that_passed_a_late_stage_and_not_an_early_one(store, bus, "run_odd")
    stages = {s["stage"]: s for s in view(store, bus, clock).funnel}

    assert stages["Intake & fingerprint"]["reached"] == 1
    assert stages["Mask & payload scan"]["reached"] == 1
    assert stages["Skills ran"]["reached"] == 0
    assert stages["Guards"]["reached"] == 0, (
        "it has passing guards, and it never got past the stage before them"
    )
    assert stages["Released"]["reached"] == 0


def test_the_drop_is_a_plain_subtraction_with_nothing_clamped(
    store: SqlRunStore, bus: EventBus, clock: Clock
) -> None:
    """`max(0, ...)` is what let the contradiction through silently. With a real funnel
    there is nothing to clamp, and the drops add up to the runs that fell out."""
    a_run_that_passed_a_late_stage_and_not_an_early_one(store, bus, "run_odd")
    stages = view(store, bus, clock).funnel

    previous = 1
    for stage in stages:
        assert stage["dropped"] == previous - stage["reached"], stage
        previous = stage["reached"]
    assert sum(s["dropped"] for s in stages) == 1 - stages[-1]["reached"]


def test_a_run_that_got_all_the_way_through_is_in_every_stage(
    store: SqlRunStore, bus: EventBus, clock: Clock
) -> None:
    """The other half. Making the funnel strict must not drop a run that really did pass
    everything - which is the way a fix like this goes wrong."""
    clean_run(store, bus)
    stages = view(store, bus, clock).funnel
    assert [s["reached"] for s in stages] == [1, 1, 1, 1, 1, 1], (
        [(s["stage"], s["reached"]) for s in stages]
    )
    assert all(s["dropped"] == 0 for s in stages)


def test_two_runs_that_stop_in_different_places_are_each_counted_once(
    store: SqlRunStore, bus: EventBus, clock: Clock
) -> None:
    clean_run(store, bus)
    a_run_that_passed_a_late_stage_and_not_an_early_one(store, bus, "run_odd")
    stages = {s["stage"]: s for s in view(store, bus, clock).funnel}

    assert stages["Intake & fingerprint"]["reached"] == 2
    assert stages["Skills ran"]["reached"] == 1, "only the clean run ran a skill"
    assert stages["Skills ran"]["dropped"] == 1


# --------------------------------------------------- and the label says what it measures


def test_the_stage_is_named_for_what_it_counts(
    store: SqlRunStore, bus: EventBus, clock: Clock
) -> None:
    """It counts `skill.completed`. Calling that "dispatched" made a run whose skill was
    dispatched and then quarantined read as one that never started."""
    clean_run(store, bus)
    names = [s["stage"] for s in view(store, bus, clock).funnel]
    assert "Skills ran" in names
    assert "Skills dispatched" not in names


def test_the_panel_says_a_stage_counts_only_what_got_through_the_ones_before() -> None:
    """The sentence a person reads the numbers against. It claimed an order the numbers
    did not keep; now the numbers keep it and the sentence says how."""
    assert "got through every stage before it" in ANALYTICS
    assert "Every run passes through these in order" in ANALYTICS
