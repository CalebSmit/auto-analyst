"""A halted run still writes a complete manifest.

That is the phase's criterion and it is the whole point of the module: the run somebody
will actually ask about is the one that stopped, so a record that only exists when things
went well is not a record. It is tested three ways - by driving a halted run end to end,
by parameterising over every way a run can finish, and structurally, because "no branch
on outcome" is a property of the code that is cheap to check and expensive to lose.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from ops.events import EventBus
from ops.manifest import (
    MANIFEST_CONTRACT,
    MANIFEST_NAME,
    ManifestIncomplete,
    assemble,
    close_out,
    manifest_path,
)
from ops.models import DecisionKind, Outcome, RunState, StepStatus
from ops.run_store import SqlRunStore
from registries.contracts import ContractRegistry
from tests.p04.conftest import ENGAGEMENT, VERSIONS, started

ROOT = Path(__file__).resolve().parents[2]

SOURCE = {
    "source_id": "sha256:" + "ab" * 32,
    "filename": "FY2025 trial balance.xlsx",
    "document_type": "trial_balance",
    "source_version": 1,
    "received_at": "2026-04-02T09:15:00Z",
    "bytes": 48231,
}


def halted_run(store: SqlRunStore, bus: EventBus, run_id: str = "run_halt") -> str:
    """A run that got three steps in, failed tie-out twice, and stopped.

    Deliberately the messy case: sources in, some steps done, one quarantined, three
    never reached, a guard that passed and a guard that failed, a review item nobody
    answered and a coverage gap.
    """
    started(store, run_id=run_id)
    store.record_source(run_id, SOURCE)
    store.transition(run_id, RunState.RUNNING)

    plan = [
        ("s1", "io", None, StepStatus.COMPLETED),
        ("s2", "skill", "ddr-tagging", StepStatus.COMPLETED),
        ("s3", "guard", None, StepStatus.FAILED),
        ("s4", "skill", "ebitda-normalization", StepStatus.NOT_REACHED),
        ("s5", "skill", "dcf-build", StepStatus.NOT_REACHED),
        ("s6", "io", None, StepStatus.NOT_REACHED),
    ]
    for index, (step_id, kind, skill, status) in enumerate(plan):
        key = f"sha256:{index:064x}"
        store.record_step(run_id, step_id, key, kind, skill=skill)
        if status is StepStatus.COMPLETED:
            # A step is completed by committing its result, which is the only way to
            # say so - see the one-door note on finish_step.
            store.commit_step(
                run_id, step_id, key, "sha256:" + "e" * 64,
                store.begin_attempt(run_id, step_id),
            )
        elif status is not StepStatus.NOT_REACHED:
            store.finish_step(run_id, step_id, status)

    bus.emit_guard(
        run_id=run_id, engagement_id=ENGAGEMENT, node_id="schema_gate",
        guard="schema", passed=True, checked=27,
    )
    bus.emit_guard(
        run_id=run_id, engagement_id=ENGAGEMENT, node_id="tieout_gate",
        guard="tieout", passed=False, checked=412, failed=2,
        diagnostic_code="GUARD.TIEOUT_MISMATCH",
    )
    store.record_model_call(run_id, 0.41, input_tokens=18_400, output_tokens=2_100)
    store.record_model_call(run_id, 0.19, input_tokens=6_200, output_tokens=900)
    store.open_review_item(run_id, "item_1", "tieout", "Total assets differ by 1,240")
    store.record_gap(run_id, "FY2023 depreciation schedule", "not provided by the client")
    return run_id


# ------------------------------------------------- the criterion, end to end


def test_a_halted_run_writes_a_complete_manifest(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    bus = EventBus(store, contracts=contracts)
    run_id = halted_run(store, bus)

    result = close_out(
        store, run_id, RunState.HALTED, Outcome.HALTED, delivery,
        bus=bus, contracts=contracts, reason="tie-out mismatch after two repair attempts",
    )

    contracts.validate(MANIFEST_CONTRACT, result.manifest)
    manifest = result.manifest
    assert manifest["outcome"] == "halted"
    assert manifest["ended_at"] is not None
    assert manifest["plan_hash"].startswith("sha256:")
    assert manifest["versions"] == VERSIONS
    assert manifest["sources"] == [SOURCE]
    assert manifest["coverage_gaps"] == [
        {"what": "FY2023 depreciation schedule", "why": "not provided by the client"}
    ]
    assert manifest["cost"] == {
        "total_usd": pytest.approx(0.60),
        "model_calls": 2,
        "input_tokens": 24_600,
        "output_tokens": 3_000,
    }


def test_the_halted_manifest_shows_where_the_run_stopped(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    """`not_reached` rather than absent. A manifest that simply omitted the steps that
    never ran would read like a run that finished early on purpose."""
    bus = EventBus(store, contracts=contracts)
    run_id = halted_run(store, bus)
    result = close_out(store, run_id, RunState.HALTED, Outcome.HALTED, delivery,
                       bus=bus, contracts=contracts)

    by_status = {step["step_id"]: step["status"] for step in result.manifest["steps"]}
    assert by_status == {
        "s1": "completed", "s2": "completed", "s3": "failed",
        "s4": "not_reached", "s5": "not_reached", "s6": "not_reached",
    }
    assert len(result.manifest["steps"]) == 6


def test_the_halted_manifest_carries_the_guard_that_passed_as_well_as_the_one_that_failed(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    bus = EventBus(store, contracts=contracts)
    run_id = halted_run(store, bus)
    result = close_out(store, run_id, RunState.HALTED, Outcome.HALTED, delivery,
                       bus=bus, contracts=contracts)

    guards = {g["guard"]: g for g in result.manifest["guard_events"]}
    assert guards["schema"]["result"] == "pass"
    assert guards["schema"]["checked"] == 27
    assert guards["tieout"]["result"] == "fail"
    assert guards["tieout"]["failed"] == 2
    assert guards["tieout"]["diagnostic_code"] == "GUARD.TIEOUT_MISMATCH"


def test_the_manifest_lands_through_the_delivery_port_beside_the_run(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    bus = EventBus(store, contracts=contracts)
    run_id = halted_run(store, bus)
    result = close_out(store, run_id, RunState.HALTED, Outcome.HALTED, delivery,
                       bus=bus, contracts=contracts)

    assert result.path == manifest_path(ENGAGEMENT, run_id)
    on_disk = delivery.root / ENGAGEMENT / run_id / MANIFEST_NAME
    assert on_disk.is_file()
    assert json.loads(on_disk.read_text(encoding="utf-8")) == result.manifest
    assert result.content_hash.startswith("sha256:")
    assert result.version == 1


def test_closing_out_records_the_manifest_and_says_so(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    bus = EventBus(store, contracts=contracts)
    run_id = halted_run(store, bus)
    close_out(store, run_id, RunState.HALTED, Outcome.HALTED, delivery,
              bus=bus, contracts=contracts)

    assert [a.name for a in store.artifacts(run_id)] == [MANIFEST_NAME]
    written = [e for e in store.events(run_id) if e.type == "run.manifest.written"]
    assert len(written) == 1
    assert written[0].node_id == "run_manifest"
    assert written[0].payload["guard_events"] == 2


# ---------------------------------------------- every way a run can finish


@pytest.mark.parametrize(
    ("state", "outcome"),
    [
        (RunState.DELIVERED, Outcome.CLEAN),
        (RunState.DELIVERED, Outcome.RELEASED_WITH_REVIEW),
        (RunState.HALTED, Outcome.HALTED),
        (RunState.HALTED, Outcome.BLOCKED),
        (RunState.SUPERSEDED, Outcome.BLOCKED),
    ],
)
def test_a_manifest_is_written_however_the_run_ends(
    store: SqlRunStore,
    contracts: ContractRegistry,
    delivery: Any,
    state: RunState,
    outcome: Outcome,
) -> None:
    """Written unconditionally: the criterion says halted, and the way to be sure of
    halted is to have no branch to get it wrong in."""
    bus = EventBus(store, contracts=contracts)
    run_id = halted_run(store, bus, run_id=f"run_{state}_{outcome}")

    result = close_out(store, run_id, state, outcome, delivery, bus=bus, contracts=contracts)

    contracts.validate(MANIFEST_CONTRACT, result.manifest)
    assert result.manifest["outcome"] == str(outcome)
    assert store.run(run_id).state is state
    assert (delivery.root / ENGAGEMENT / run_id / MANIFEST_NAME).is_file()


def test_a_human_decision_reaches_the_manifest(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    """The only kind of event that may later write to the Precedent Store, so the
    manifest has to be able to say who decided what."""
    bus = EventBus(store, contracts=contracts)
    run_id = halted_run(store, bus)
    store.record_decision(
        run_id, "item_1", "C. Smit", DecisionKind.CORRECTED,
        rationale="Client confirmed the accrual reversal", writes_precedent=True,
    )
    result = close_out(store, run_id, RunState.DELIVERED, Outcome.RELEASED_WITH_REVIEW,
                       delivery, bus=bus, contracts=contracts)

    assert result.manifest["human_decisions"] == [
        {
            "item_id": "item_1",
            "decided_by": "C. Smit",
            "decided_at": result.manifest["human_decisions"][0]["decided_at"],
            "decision": "corrected",
            "rationale": "Client confirmed the accrual reversal",
            "writes_precedent": True,
        }
    ]


# ------------------------------------------------------------- the refusals


def test_a_run_that_cannot_name_its_versions_is_not_closed_out_quietly(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    """A workfile that cannot say which model produced a figure is a workfile that
    cannot be defended, so this fails rather than writing a manifest with a hole in it."""
    thin = dict(VERSIONS)
    del thin["model_pin"]
    started(store, run_id="run_thin", versions=thin)
    store.transition("run_thin", RunState.RUNNING)

    with pytest.raises(ManifestIncomplete) as raised:
        close_out(store, "run_thin", RunState.HALTED, Outcome.HALTED, delivery,
                  contracts=contracts)
    assert raised.value.diagnostic.code == "PROCESS.MANIFEST_INCOMPLETE"
    assert "model_pin" in str(raised.value)
    assert not (delivery.root / ENGAGEMENT / "run_thin" / MANIFEST_NAME).exists()


def test_assemble_reads_and_writes_nothing(
    store: SqlRunStore, contracts: ContractRegistry
) -> None:
    bus = EventBus(store, contracts=contracts)
    run_id = halted_run(store, bus)
    before = len(store.events(run_id))
    first = assemble(store, run_id, bus=bus)
    second = assemble(store, run_id, bus=bus)
    assert first == second
    assert len(store.events(run_id)) == before
    assert store.run(run_id).state is RunState.RUNNING


# -------------------------------------------------------------- structural


def test_the_write_path_has_no_branch_on_outcome() -> None:
    """The criterion, as a property of the code.

    Behavioural tests above cover the five endings that exist today. This one covers the
    sixth somebody adds in P20 without reading them: `close_out` contains no conditional
    that mentions the state or the outcome, so there is nowhere for "except when it
    halted" to be introduced by accident.
    """
    tree = ast.parse((ROOT / "ops" / "manifest.py").read_text(encoding="utf-8"))
    close = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "close_out"
    )
    conditionals = [
        ast.unparse(node.test)
        for node in ast.walk(close)
        if isinstance(node, ast.If | ast.IfExp)
    ]
    offenders = [
        test for test in conditionals if "outcome" in test or "state" in test
    ]
    assert not offenders, f"close_out branches on how the run ended: {offenders}"
