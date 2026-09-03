"""The Bounded Loop Controller: input must change, ceilings hold, exhaustion leaves a record."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph.compile import CompiledGraph
from graph.execute import StepOutcome
from harness.loops import LoopController, RepairNeeded
from ops.blobs import LocalContentStore
from ops.events import EventBus
from ops.run_store import SqlRunStore
from registries.errors import SCHEMA_INVALID, diagnose
from tests.p14.conftest import (
    ENGAGEMENT,
    ROOT,
    Repairer,
    events_of,
    loop_events,
    tieout_diagnostic,
)

SAME = {"guard": "tieout", "stated": 332324.0, "recomputed": 331000.0}


def test_a_skill_returning_byte_identical_output_is_stopped_not_retried(
    executor_with,
    blobs: LocalContentStore,
    monthly: CompiledGraph,
    started: str,
    run_inputs,
    store: SqlRunStore,
) -> None:
    """The exit criterion. guard_repair on ebitda allows two iterations. The skill gets
    one - the feedback changed the input - and is refused the second, because the same
    output produced the same feedback, and the same feedback is the same call."""
    runner = Repairer(blobs, "ebitda", "guard_repair", feedback=lambda n: SAME)
    report = executor_with(runner).execute(monthly, started, run_inputs, "context:x")

    assert report.quarantined == ["ebitda"]
    assert len(runner.calls("ebitda")) == 2, "first pass + one admitted iteration, not three"
    refused = events_of(store, started, "loop.refused")
    assert len(refused) == 1
    assert refused[0].diagnostic_code == "LOOP.INPUT_UNCHANGED"
    assert len(loop_events(store, started)) == 1, "one iteration was paid for"
    held = store.quarantines(started)
    assert len(held) == 1 and held[0].code == "LOOP.INPUT_UNCHANGED"


def test_changing_feedback_runs_to_the_ceiling_and_no_further(
    executor_with,
    blobs: LocalContentStore,
    monthly: CompiledGraph,
    started: str,
    run_inputs,
    store: SqlRunStore,
) -> None:
    runner = Repairer(blobs, "ebitda", "guard_repair", feedback=lambda n: {"attempt": n})
    report = executor_with(runner).execute(monthly, started, run_inputs, "context:x")

    assert report.quarantined == ["ebitda"]
    assert len(runner.calls("ebitda")) == 3, "first pass + the ceiling of two"
    assert len(loop_events(store, started)) == 2
    exhausted = events_of(store, started, "loop.exhausted")
    assert len(exhausted) == 1 and exhausted[0].diagnostic_code == "LOOP.EXHAUSTED"


def test_loop_exhaustion_quarantines_and_opens_a_review_item_with_both_positions(
    executor_with,
    blobs: LocalContentStore,
    monthly: CompiledGraph,
    started: str,
    run_inputs,
    store: SqlRunStore,
) -> None:
    """The exit criterion. Two artifacts, always both, and each names the other."""
    runner = Repairer(blobs, "ebitda", "guard_repair", feedback=lambda n: {"attempt": n})
    executor_with(runner).execute(monthly, started, run_inputs, "context:x")

    (held,) = store.quarantines(started)
    assert held.code == "LOOP.EXHAUSTED" and held.owner == "model"
    assert held.loop == "guard_repair"
    assert [a["iteration"] for a in held.attempts] == [1, 2]
    assert len({a["step_key"] for a in held.attempts}) == 2, "each iteration was its own key"
    assert held.guard_output["diagnostic"]["code"] == "GUARD.TIEOUT_MISMATCH"
    assert held.diagnostic["what_now"]

    items = [i for i in store.review_items(started) if i.kind == "loop_exhausted"]
    assert len(items) == 1
    item = items[0]
    assert item.item_id == held.review_item_id
    assert item.state == "open"
    positions = item.detail["positions"]
    assert positions["proposed"]["value"] == 332324.0
    assert positions["recomputed"]["value"] == 331000.0
    assert item.detail["guard"]["expected"] == "331000.0"
    assert item.detail["guard"]["found"] == "332324.0"
    assert item.detail["stopped_by"]["code"] == "LOOP.EXHAUSTED"
    queued = events_of(store, started, "hitl.item.queued")
    assert queued and queued[-1].payload["item_id"] == item.item_id


def test_a_repair_that_works_completes_the_step_under_a_new_key(
    executor_with,
    blobs: LocalContentStore,
    monthly: CompiledGraph,
    started: str,
    run_inputs,
    store: SqlRunStore,
) -> None:
    runner = Repairer(
        blobs, "ebitda", "guard_repair", feedback=lambda n: {"attempt": n}, passes_after=1
    )
    report = executor_with(runner).execute(monthly, started, run_inputs, "context:x")

    assert report.finished
    assert "ebitda" in report.executed
    first, second = runner.calls("ebitda")
    assert first.step_key != second.step_key
    assert second.iteration == 1
    assert store.ledger_entry(second.step_key) is not None
    assert store.ledger_entry(first.step_key) is None, "the rejected pass wrote nothing"


def test_a_repair_may_change_the_input_and_nothing_else(
    executor_with,
    blobs: LocalContentStore,
    monthly: CompiledGraph,
    started: str,
    run_inputs,
) -> None:
    """Never the guard, the tolerance or the schema. The second attempt is the same step
    object with one more input - the feedback - and every original input unchanged."""
    runner = Repairer(
        blobs, "ebitda", "guard_repair", feedback=lambda n: {"attempt": n}, passes_after=1
    )
    executor_with(runner).execute(monthly, started, run_inputs, "context:x")

    first, second = runner.calls("ebitda")
    assert second.step is first.step
    assert second.step.output_schema == first.step.output_schema
    assert second.timeout_s == first.timeout_s
    assert set(second.inputs) == set(first.inputs) | {"feedback"}
    for name, ref in first.inputs.items():
        assert second.inputs[name].content_hash == ref.content_hash


def test_an_undeclared_loop_has_a_ceiling_of_zero(
    executor_with,
    blobs: LocalContentStore,
    monthly: CompiledGraph,
    started: str,
    run_inputs,
    store: SqlRunStore,
) -> None:
    """timing declares no guard_repair region. A guard failure there is exhaustion at
    once - the controller does not improvise a loop the plan did not declare."""
    runner = Repairer(blobs, "timing", "guard_repair", feedback=lambda n: {"attempt": n})
    report = executor_with(runner).execute(monthly, started, run_inputs, "context:x")

    assert report.quarantined == ["timing"]
    assert len(runner.calls("timing")) == 1
    assert loop_events(store, started) == []
    (held,) = store.quarantines(started)
    assert held.code == "LOOP.EXHAUSTED"
    assert "not declared" in held.reason


def test_every_iteration_counts_against_the_run_ceiling(
    executor_with,
    blobs: LocalContentStore,
    monthly: CompiledGraph,
    started: str,
    run_inputs,
    store: SqlRunStore,
    bus: EventBus,
    constraints,
) -> None:
    """Several loops cannot conspire to run long. Eight iterations already on the record
    from other loops; the ninth is refused whatever its own region allows."""
    ceiling = int(constraints.ceilings["per_run"]["loop_iterations_max"])
    for n in range(ceiling):
        bus.emit(
            run_id=started,
            engagement_id=ENGAGEMENT,
            node_id="loop_controller",
            type="loop.self_verification.iteration",
            message=f"seed {n}",
            level="loop",
        )
    runner = Repairer(blobs, "ebitda", "guard_repair", feedback=lambda n: {"attempt": n})
    report = executor_with(runner).execute(monthly, started, run_inputs, "context:x")

    assert report.quarantined == ["ebitda"]
    assert len(runner.calls("ebitda")) == 1
    (held,) = store.quarantines(started)
    assert held.code == "POLICY.BUDGET_EXCEEDED"
    assert len(loop_events(store, started)) == ceiling, "nothing was admitted past it"


def test_the_ceilings_are_the_blueprints_four(
    monthly: CompiledGraph, ddr: CompiledGraph, constraints
) -> None:
    declared = {spec.name: spec.max_iterations for spec in constraints.in_run_loops()}
    assert declared == {
        "guard_repair": 2,
        "tieout_repair": 1,
        "self_verification": 1,
        "conflict_resolution": 1,
    }
    regions = {r.id: r.max_iterations for plan in (monthly, ddr) for r in plan.loops}
    for region, ceiling in regions.items():
        assert ceiling <= declared[region.split(":")[0]]


def test_only_in_run_loops_live_in_a_plan(
    monthly: CompiledGraph, ddr: CompiledGraph, constraints
) -> None:
    """Human clarification is a suspend-and-resume; drift re-review is human-paced. The
    controller never sees either as a region."""
    in_run = {spec.name for spec in constraints.in_run_loops()}
    for plan in (monthly, ddr):
        for region in plan.loops:
            assert region.loop in in_run and region.scope == "in_run"
    assert "human_clarification" not in in_run and "drift_re_review" not in in_run


# --------------------------------------------------------------- the controller alone


def test_the_fixture_fires_input_unchanged(
    controller: LoopController, monthly: CompiledGraph, started: str
) -> None:
    """fixtures/guards/loop_byte_identical_output.json, driven straight at admit()."""
    body = json.loads(
        (ROOT / "fixtures" / "guards" / "loop_byte_identical_output.json").read_text(
            encoding="utf-8"
        )
    )
    step = monthly.step("ebitda")
    trigger = diagnose(SCHEMA_INVALID, "fixture")
    first, second = (a["input_hash"] for a in body["attempts"])
    admitted = controller.admit(
        started, monthly, step, body["loop"], "sha256:" + "0" * 64, first, {}, trigger
    )
    assert admitted.allowed and admitted.iteration == 1
    refused = controller.admit(started, monthly, step, body["loop"], first, second, {}, trigger)
    assert not refused.allowed
    assert refused.code == "LOOP.INPUT_UNCHANGED"
    assert refused.diagnostic is not None and not refused.diagnostic.retryable


def test_the_controller_records_each_admitted_iteration(
    controller: LoopController, monthly: CompiledGraph, started: str
) -> None:
    step = monthly.step("ebitda")
    trigger = tieout_diagnostic("ebitda")
    keys = ["sha256:" + c * 64 for c in "abc"]
    controller.admit(
        started, monthly, step, "guard_repair", keys[0], keys[1], {"feedback": "f1"}, trigger
    )
    controller.admit(
        started, monthly, step, "guard_repair", keys[1], keys[2], {"feedback": "f2"}, trigger
    )
    history = controller.history(started, "guard_repair:ebitda")
    assert [it.number for it in history] == [1, 2]
    assert [it.step_key for it in history] == keys[1:]
    assert all(it.trigger == "GUARD.TIEOUT_MISMATCH" for it in history)
    assert controller.iterations_so_far(started) == 2


def test_the_controller_has_no_way_to_relax_an_exit_condition() -> None:
    """A loop that can relax its own exit condition is not a control."""
    for forbidden in ("tolerance", "schema", "set_ceiling", "raise_ceiling", "relax"):
        assert not any(forbidden in name for name in dir(LoopController))
    assert not any("tolerance" in name or "schema" in name for name in dir(RepairNeeded))


def test_step_outcomes_name_the_endings() -> None:
    assert {o.value for o in StepOutcome} == {
        "executed",
        "satisfied_from_ledger",
        "quarantined",
        "blocked",
        "not_reached",
    }


@pytest.mark.parametrize("path", ["harness/loops.py"])
def test_the_controller_imports_no_tool_and_no_model(path: str) -> None:
    text = (Path(ROOT) / path).read_text(encoding="utf-8")
    assert "from tools" not in text and "import tools" not in text
    assert "anthropic" not in text and "ports.llm" not in text
