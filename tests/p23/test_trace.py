"""The console replays a completed run from the event stream alone, and node state comes
from explicit events - never from a log line's severity."""

from __future__ import annotations

import inspect
import re
from typing import Any

from ops.console import NodeState, TraceReducer, state_for
from ops.console import trace as module
from ops.events import EventBus
from ops.manifest import close_out
from ops.models import Outcome, RunState
from ops.run_store import SqlRunStore
from tests.p23.conftest import ENGAGEMENT, STEPS, Script, clean_run, halted_run


def test_live_and_replay_are_the_same_reducer_over_the_same_stream(
    store: SqlRunStore, bus: EventBus, delivery: Any
) -> None:
    """Fold the events as the bus delivers them, then fold the stored stream from
    nothing: the two traces are identical, event for event."""
    live = TraceReducer("run_clean", (s[0] for s in STEPS))
    bus.subscribe(live.apply)
    clean_run(store, bus)
    close_out(store, "run_clean", RunState.DELIVERED, Outcome.CLEAN, delivery, bus=bus)
    bus.unsubscribe(live.apply)

    replayed = TraceReducer("run_clean", (s[0] for s in STEPS)).fold(bus.stream("run_clean"))

    assert replayed.nodes == live.trace.nodes
    assert replayed.steps == live.trace.steps
    assert replayed.diagnostics == live.trace.diagnostics == {}
    assert replayed.events == live.trace.events == len(bus.stream("run_clean"))
    assert replayed.nodes["tieout_gate"] is NodeState.PASSED
    assert replayed.nodes["run_scorecard"] is NodeState.PASSED
    assert replayed.nodes["run_manifest"] is NodeState.PASSED
    assert all(state is NodeState.PASSED for state in replayed.steps.values())
    assert replayed.active_step is None


def test_a_halted_run_paints_the_failure_its_diagnostic_and_what_was_never_reached(
    store: SqlRunStore, bus: EventBus, delivery: Any
) -> None:
    halted_run(store, bus)
    close_out(store, "run_halted", RunState.HALTED, Outcome.HALTED, delivery, bus=bus)
    trace = TraceReducer("run_halted", (s[0] for s in STEPS)).fold(bus.stream("run_halted"))

    assert trace.nodes["tieout_gate"] is NodeState.FAILED
    assert trace.diagnostics["tieout_gate"]["code"] == "GUARD.TIEOUT_MISMATCH"
    assert trace.nodes["loop_controller"] is NodeState.FAILED
    assert trace.nodes["step_executor"] is NodeState.FAILED
    assert trace.steps["ebitda"] is NodeState.FAILED
    assert trace.steps["release"] is NodeState.NOT_REACHED
    assert trace.steps["timing"] is NodeState.PASSED
    assert trace.nodes["run_scorecard"] is NodeState.PASSED, "the verdict was computed"
    assert trace.active_step is None
    assert trace.counts()["failed"] == 3
    assert [e["type"] for e in trace.touched["tieout_gate"]] == [
        "guard.tieout.pass",
        "guard.tieout.fail",
        "guard.tieout.fail",
    ]


def test_node_state_comes_from_the_type_never_the_level(store: SqlRunStore, bus: EventBus) -> None:
    """The exit criterion, as behaviour and as a property of the source."""
    s = Script(store, bus, "run_lvl", ENGAGEMENT)
    s.start()
    # The same types at deliberately wrong levels.
    s.emit("tieout_gate", "guard.tieout.pass", level="error", payload={"checked": 1, "failed": 0})
    s.emit("policy_gate", "policy.allow", level="error")
    s.emit("release_gate", "release.blocked", level="info", diagnostic_code="DELIVER.QC_FAILED")
    trace = TraceReducer("run_lvl").fold(bus.stream("run_lvl"))
    assert trace.nodes["tieout_gate"] is NodeState.PASSED
    assert trace.nodes["policy_gate"] is NodeState.PASSED
    assert trace.nodes["release_gate"] is NodeState.FAILED

    source = inspect.getsource(module)
    assert not re.search(r"\.level\b|\[\s*['\"]level['\"]\s*\]|\"level\"", source), (
        "the reducer must not read an event's level"
    )


def test_the_vocabulary_is_explicit_and_an_unknown_type_only_marks_a_node_touched() -> None:
    assert state_for("guard.tieout.fail") is NodeState.FAILED
    assert state_for("guard.tieout.repair.pass") is NodeState.PASSED
    assert state_for("step.started") is NodeState.ACTIVE
    assert state_for("loop.tieout_repair.iteration") is NodeState.ACTIVE
    assert state_for("loop.tieout_repair.exhausted") is NodeState.FAILED
    assert state_for("alert.run_silent") is NodeState.FAILED
    assert state_for("hitl.item.queued") is NodeState.ACTIVE
    assert state_for("hitl.item.decided") is NodeState.PASSED
    assert state_for("something.nobody.declared") is NodeState.USED


def test_a_later_pass_clears_a_diagnostic_and_the_active_step_follows_the_run(
    store: SqlRunStore, bus: EventBus
) -> None:
    s = Script(store, bus, "run_flow", ENGAGEMENT)
    s.start()
    reducer = TraceReducer("run_flow", (x[0] for x in STEPS))
    bus.subscribe(reducer.apply)
    s.step("timing", complete=False)
    assert reducer.trace.active_step == "timing"
    s.guard(
        "tieout_gate",
        "tieout",
        False,
        3,
        1,
        step_id="timing",
        diagnostic_code="GUARD.TIEOUT_MISMATCH",
    )
    assert (
        reducer.trace.nodes["tieout_gate"] is NodeState.FAILED
        and "tieout_gate" in reducer.trace.diagnostics
    )
    s.guard("tieout_gate", "tieout", True, 3, step_id="timing")
    assert reducer.trace.nodes["tieout_gate"] is NodeState.PASSED
    assert "tieout_gate" not in reducer.trace.diagnostics, "a diagnostic belongs to a failure"
    s._finish("timing")
    assert reducer.trace.active_step is None and reducer.trace.steps["timing"] is NodeState.PASSED
    assert reducer.trace.steps["release"] is NodeState.NOT_REACHED
