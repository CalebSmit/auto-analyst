"""Quarantine: full context held, independent branches finish, nothing partial released."""

from __future__ import annotations

import pytest

from graph.compile import CompiledGraph
from graph.execute import StepExecutor, StepOutcome, dependents
from ops.blobs import LocalContentStore
from ops.models import TRANSITIONS, Outcome, RunState
from ops.run_store import QuarantineRecord, SqlRunStore
from registries.errors import DiagnosticError
from tests.p14.conftest import Repairer


def test_the_fork_is_what_the_test_needs(ddr: CompiledGraph) -> None:
    """ddr-tagging and timing both hang off mask; only qc joins them. If that ever
    changes, the independence tests below would be testing nothing."""
    assert dependents(ddr, "ddr") == {"qc", "release"}
    assert "timing" not in dependents(ddr, "ddr") and "tagging" not in dependents(ddr, "ddr")


def test_independent_branches_finish_and_dependent_ones_halt(
    executor_with,
    blobs: LocalContentStore,
    ddr: CompiledGraph,
    started_ddr: str,
    run_inputs,
    store: SqlRunStore,
) -> None:
    runner = Repairer(blobs, "ddr", "self_verification", feedback=lambda n: {"attempt": n})
    report = executor_with(runner).execute(ddr, started_ddr, run_inputs, "context:x")

    assert report.quarantined == ["ddr"]
    assert report.outcomes["timing"] is StepOutcome.EXECUTED
    assert report.outcomes["tagging"] is StepOutcome.EXECUTED
    assert report.outcomes["qc"] is StepOutcome.NOT_REACHED
    assert report.outcomes["release"] is StepOutcome.NOT_REACHED
    assert report.halted == ["qc", "release"]
    assert report.state is RunState.QUARANTINED
    statuses = {s.step_id: s.status for s in store.steps(started_ddr)}
    assert statuses["timing"] == "completed" and statuses["tagging"] == "completed"
    assert statuses["ddr"] == "quarantined"
    # A step that never started has no key and so no row; the manifest records it as
    # not_reached from the plan. What matters here is that nothing ran it.
    assert "qc" not in statuses and "release" not in statuses


def test_nothing_partial_is_ever_released_from_a_quarantined_run(
    executor_with,
    blobs: LocalContentStore,
    ddr: CompiledGraph,
    started_ddr: str,
    run_inputs,
    store: SqlRunStore,
) -> None:
    """The exit criterion, from three sides: the report is not finished, the run state
    has no transition to delivered, and the release step never started."""
    runner = Repairer(blobs, "ddr", "self_verification", feedback=lambda n: {"attempt": n})
    report = executor_with(runner).execute(ddr, started_ddr, run_inputs, "context:x")

    assert not report.finished
    assert RunState.DELIVERED not in TRANSITIONS[RunState.QUARANTINED]
    with pytest.raises(DiagnosticError) as refused:
        store.end_run(started_ddr, RunState.DELIVERED, Outcome.CLEAN)
    assert refused.value.diagnostic.code == "PROCESS.ILLEGAL_TRANSITION"
    assert report.outcomes["release"] is StepOutcome.NOT_REACHED
    assert all(a.name != "release" for a in store.artifacts(started_ddr))


def test_the_record_holds_the_full_context(
    executor_with,
    blobs: LocalContentStore,
    ddr: CompiledGraph,
    started_ddr: str,
    run_inputs,
    store: SqlRunStore,
) -> None:
    runner = Repairer(blobs, "ddr", "self_verification", feedback=lambda n: {"attempt": n})
    executor_with(runner).execute(ddr, started_ddr, run_inputs, "context:x")

    (held,) = store.quarantines(started_ddr)
    step = ddr.step("ddr")
    assert set(held.inputs) == {ref.name for ref in step.inputs} | {"feedback"}
    assert all(h.startswith("sha256:") for h in held.inputs.values())
    assert len(held.attempts) == 1 and held.attempts[0]["loop"] == "self_verification"
    assert held.guard_output["diagnostic"]["code"] == "GUARD.TIEOUT_MISMATCH"
    assert held.guard_output["mismatches"][0]["stated"] == 332324.0
    assert held.diagnostic["code"] == "LOOP.EXHAUSTED"
    assert held.diagnostic["owner"] == "model"
    assert held.diagnostic["what_now"]
    assert held.review_item_id and held.held_at.endswith("Z")


def test_a_quarantined_step_can_be_rerun_by_key_once_the_cause_is_fixed(
    executor_with,
    blobs: LocalContentStore,
    ddr: CompiledGraph,
    started_ddr: str,
    run_inputs,
    store: SqlRunStore,
) -> None:
    """Resume is replay. The four steps that finished are satisfied from the ledger; the
    quarantined one runs; what it halted now runs too. Nothing is re-executed."""
    broken = Repairer(blobs, "ddr", "self_verification", feedback=lambda n: {"attempt": n})
    executor_with(broken).execute(ddr, started_ddr, run_inputs, "context:x")

    store.transition(started_ddr, RunState.RUNNING, reason="cause fixed; re-run by key")
    fixed = Repairer(blobs, "ddr", "self_verification", feedback=lambda n: {}, passes_after=0)
    report = executor_with(fixed).execute(ddr, started_ddr, run_inputs, "context:x")

    assert report.finished
    assert sorted(report.satisfied) == ["intake", "mask", "tagging", "timing"]
    assert sorted(report.executed) == ["ddr", "qc", "release"]
    assert [a.step_id for a in fixed.attempts] == ["ddr", "qc", "release"]
    assert len(store.quarantines(started_ddr)) == 1, "the record is kept, not deleted"


def test_the_record_is_write_once_per_key(store: SqlRunStore, started: str) -> None:
    record = QuarantineRecord(
        step_id="ebitda",
        step_key="sha256:" + "a" * 64,
        code="LOOP.EXHAUSTED",
        owner="model",
        reason="test",
    )
    store.hold(started, record)
    with pytest.raises(Exception, match="(?i)unique|integrity"):
        store.hold(started, record)
    assert len(store.quarantines(started)) == 1


def test_the_executor_builds_its_own_controller_when_given_none(
    store: SqlRunStore, bus, blobs: LocalContentStore
) -> None:
    """A step executor without a loop controller would have to improvise a loop policy
    of its own. It cannot: the controller is part of the executor's own construction."""
    executor = StepExecutor(store, bus, lambda attempt: None, blobs=blobs)
    assert executor.loops is not None
    assert executor.loops.constraints is executor.constraints
