"""C2 - A plan compiles and hashes.

Proves: a recipe compiles; identical inputs give an identical plan_hash and a changed
precedent snapshot changes it; and the store conformance suite passes against Postgres
as well as SQLite. The Postgres half runs as a separate check on this checkpoint
(`pytest tests/p04 -q --postgres`) because it needs a server, not a fixture.

A checkpoint exists because phases that each pass alone can still disagree. What this one
catches is everything that only shows up when P05 and P06 meet P04: a compiler that
resolves a scope the store cannot record, a plan hash the manifest schema will not
accept, a compiled step whose shape does not survive being written down. Each of those
is cheap now and expensive in P08, where the executor starts trusting all three.

So this is one run end to end, through the real objects: resolve a scope, compile a
recipe, open a run, walk the compiled order, emit a guard event per step, halt on the
tie-out, and close out with a manifest that carries the plan hash the compiler produced.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import ports
from graph.compile import CompiledGraph, PlanContext, compile_recipe
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver
from ops.events import EventBus
from ops.manifest import MANIFEST_CONTRACT, close_out
from ops.models import Outcome, RunState, StepStatus
from ops.run_store import SqlRunStore, open_store
from registries.contracts import ContractRegistry

ENGAGEMENT = "HEND-2026-04"
SCOPE = "valuation/esop/repeat"
RUN_ID = "run_c2"
TAXONOMY = "coa-taxonomy@1.0.0"
SNAPSHOT = "precedent_snapshot_2026_09_01"
SOURCE_ID = "sha256:" + "ab" * 32


@pytest.fixture(scope="module")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture
def store(tmp_path: Path) -> SqlRunStore:
    opened = open_store(f"sqlite:///{(tmp_path / 'c2.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def delivery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    root = tmp_path / "outbox"
    root.mkdir()
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(root))
    ports.reset()
    yield ports.get_delivery()
    ports.reset()


def plan_for(snapshot: str = SNAPSHOT, scope_path: str = SCOPE) -> CompiledGraph:
    """Scope resolution and compilation, through the real registries every time."""
    resolved = ScopeResolver().resolve(scope_path)
    context = PlanContext(
        engagement_id=ENGAGEMENT,
        scope=resolved,
        taxonomy_version=TAXONOMY,
        precedent_snapshot=snapshot,
    )
    return compile_recipe(load_recipe("monthly-refresh"), context)


def provisional_step_key(plan: CompiledGraph, step_id: str) -> str:
    """The idempotency key over what the compiler knows.

    P08 completes it with the input content hashes and the context_ref. Hashed here
    rather than faked, so what this checkpoint writes into a manifest is the real static
    half rather than a placeholder that would stop meaning anything the moment P08 lands.
    """
    material = "|".join(plan.step(step_id).key_material())
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def halted_run(store: SqlRunStore, bus: EventBus, plan: CompiledGraph) -> str:
    """One run, walked in the compiler's order, stopping where the tie-out fails.

    Halted rather than delivered on purpose: the run somebody actually asks about is the
    one that stopped, and it is the case where a record is most needed.
    """
    store.start_run(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
        plan_hash=plan.plan_hash,
        versions={
            "model_pin": plan.step("ebitda").model_pin,
            "skills": sorted(
                f"{s.skill.split('@')[0]}@1.0.0" for s in plan.steps_where(kind="skill")
            ),
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": TAXONOMY,
        },
        tieout_tolerance=1.0,
    )
    store.record_source(
        RUN_ID,
        {
            "source_id": SOURCE_ID,
            "filename": "FY2025 trial balance.xlsx",
            "document_type": "trial_balance",
            "source_version": 1,
            "received_at": "2026-04-02T09:15:00Z",
        },
    )
    store.transition(RUN_ID, RunState.RUNNING)

    for step_id in plan.order:
        store.record_step(
            RUN_ID,
            step_id,
            provisional_step_key(plan, step_id),
            plan.step(step_id).kind,
            skill=plan.step(step_id).skill,
            loop=plan.step(step_id).loops[0] if plan.step(step_id).loops else None,
        )
        bus.emit(
            run_id=RUN_ID,
            engagement_id=ENGAGEMENT,
            node_id="graph_compiler" if step_id == plan.order[0] else "step_executor",
            type="step.started",
            message=f"{step_id} ({plan.step(step_id).kind})",
            step_id=step_id,
            payload={"plan_hash": plan.plan_hash, "loops": list(plan.step(step_id).loops)},
        )

    # Everything up to the tie-out completes. The tie-out fails, its repair loop is
    # exhausted, and the steps after it are never reached.
    for step_id in ("intake", "mask", "timing", "tagging", "ebitda", "model"):
        store.commit_step(
            RUN_ID,
            step_id,
            provisional_step_key(plan, step_id),
            "sha256:" + hashlib.sha256(step_id.encode()).hexdigest(),
            store.begin_attempt(RUN_ID, step_id),
        )
        bus.emit_guard(
            run_id=RUN_ID,
            engagement_id=ENGAGEMENT,
            node_id="schema_gate",
            guard="schema",
            passed=True,
            checked=1,
            step_id=step_id,
        )
    store.finish_step(RUN_ID, "qc", StepStatus.FAILED)
    bus.emit_guard(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
        node_id="tieout_gate",
        guard="tieout",
        passed=False,
        checked=412,
        failed=2,
        step_id="qc",
        diagnostic_code="GUARD.TIEOUT_MISMATCH",
    )
    bus.emit(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
        node_id="loop_controller",
        type="loop.tieout_repair.exhausted",
        message="tieout_repair exhausted after 1 iteration",
        step_id="qc",
        payload={"loop": "tieout_repair:qc", "max_iterations": 1},
    )
    store.open_review_item(RUN_ID, "item_1", "tieout", "Total assets differ by 1,240")
    store.record_gap(RUN_ID, "FY2023 depreciation schedule", "not provided by the client")
    store.record_model_call(RUN_ID, 0.41, input_tokens=18_400, output_tokens=2_100)
    return RUN_ID


# ------------------------------------------------------ a recipe compiles


def test_a_recipe_compiles() -> None:
    plan = plan_for()
    assert len(plan) == 8
    assert len(plan.steps_where(kind="skill")) == 5
    assert len(plan.loops) == 4
    assert plan.order[0] == "intake"
    assert plan.order[-1] == "release"


def test_the_compiled_plan_only_names_skills_the_scope_resolved(
    contracts: ContractRegistry,
) -> None:
    """P05 and P06 meeting. The compiler will not build a plan for skills the engagement
    was never given, which is what makes the scope a control rather than a filter."""
    plan = plan_for()
    resolved = set(plan.context.scope.names)
    for step in plan.steps_where(kind="skill"):
        assert step.skill is not None
        assert step.skill.split("@")[0] in resolved
        assert step.output_schema in contracts.ids()


# --------------------------------------------------------------- the hash


def test_identical_inputs_give_an_identical_plan_hash() -> None:
    """Everything rebuilt from scratch both times - registries, resolver, recipe file."""
    assert plan_for().plan_hash == plan_for().plan_hash


def test_a_changed_precedent_snapshot_changes_the_plan_hash() -> None:
    """Retrieved precedents change with every approved correction. Without this in the
    hash, two runs could share one, see different examples, and legitimately disagree."""
    assert plan_for().plan_hash != plan_for(snapshot="precedent_snapshot_2026_10_01").plan_hash


def test_a_changed_scope_changes_the_plan_hash() -> None:
    assert plan_for().plan_hash != plan_for(scope_path="valuation/non-esop/repeat").plan_hash


# ------------------------------------------- the plan reaches the record


def test_a_halted_run_records_the_plan_it_was_compiled_from(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    """The whole point of the checkpoint. A plan hash the compiler produced has to
    survive being written to the store and validated by the manifest contract - three
    phases that were each green on their own."""
    plan = plan_for()
    bus = EventBus(store, contracts=contracts)
    halted_run(store, bus, plan)

    result = close_out(
        store, RUN_ID, RunState.HALTED, Outcome.HALTED, delivery,
        bus=bus, contracts=contracts, reason="tie-out mismatch, repair loop exhausted",
    )

    contracts.validate(MANIFEST_CONTRACT, result.manifest)
    assert result.manifest["plan_hash"] == plan.plan_hash
    assert result.manifest["outcome"] == "halted"


def test_every_compiled_step_appears_in_the_manifest(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    """Including the one that failed and the one that was never reached. A manifest that
    omitted the steps after a halt would read like a run that finished early on purpose.
    """
    plan = plan_for()
    bus = EventBus(store, contracts=contracts)
    halted_run(store, bus, plan)
    result = close_out(store, RUN_ID, RunState.HALTED, Outcome.HALTED, delivery,
                       bus=bus, contracts=contracts)

    recorded = {s["step_id"]: s["status"] for s in result.manifest["steps"]}
    assert set(recorded) == set(plan.ids)
    assert recorded["qc"] == "failed"
    assert recorded["release"] == "not_reached"
    for step in result.manifest["steps"]:
        assert step["step_key"].startswith("sha256:")


def test_a_step_in_a_declared_loop_says_which_one(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    """The manifest's `loop` field, filled from the compiled graph rather than from a
    second list somebody has to keep in step."""
    plan = plan_for()
    bus = EventBus(store, contracts=contracts)
    halted_run(store, bus, plan)
    result = close_out(store, RUN_ID, RunState.HALTED, Outcome.HALTED, delivery,
                       bus=bus, contracts=contracts)

    by_id = {s["step_id"]: s for s in result.manifest["steps"]}
    assert by_id["qc"]["loop"] == "tieout_repair:qc"
    assert by_id["tagging"]["loop"] == "self_verification:tagging"
    assert by_id["timing"]["loop"] is None


def test_the_guard_that_passed_is_in_the_record_beside_the_one_that_failed(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    """Silence is never ambiguous. Six schema passes and one tie-out failure, all from
    the event stream rather than from a table somebody remembered to write."""
    plan = plan_for()
    bus = EventBus(store, contracts=contracts)
    halted_run(store, bus, plan)
    result = close_out(store, RUN_ID, RunState.HALTED, Outcome.HALTED, delivery,
                       bus=bus, contracts=contracts)

    guards = result.manifest["guard_events"]
    assert [g["result"] for g in guards].count("pass") == 6
    failures = [g for g in guards if g["result"] == "fail"]
    assert len(failures) == 1
    assert failures[0]["guard"] == "tieout"
    assert failures[0]["diagnostic_code"] == "GUARD.TIEOUT_MISMATCH"


def test_the_manifest_lands_through_the_delivery_port(
    store: SqlRunStore, contracts: ContractRegistry, delivery: Any
) -> None:
    plan = plan_for()
    bus = EventBus(store, contracts=contracts)
    halted_run(store, bus, plan)
    result = close_out(store, RUN_ID, RunState.HALTED, Outcome.HALTED, delivery,
                       bus=bus, contracts=contracts)

    on_disk = delivery.root / ENGAGEMENT / RUN_ID / "run_manifest.json"
    assert on_disk.is_file()
    written = json.loads(on_disk.read_text(encoding="utf-8"))
    assert written["plan_hash"] == plan.plan_hash
    assert result.content_hash.startswith("sha256:")


def test_the_event_stream_carries_the_plan_hash_from_the_first_step(
    store: SqlRunStore, contracts: ContractRegistry
) -> None:
    """So the console can tie a live run to the plan it is executing without asking the
    compiler again."""
    plan = plan_for()
    bus = EventBus(store, contracts=contracts)
    halted_run(store, bus, plan)

    started = [e for e in store.events(RUN_ID) if e.type == "step.started"]
    assert len(started) == len(plan)
    assert {e.payload["plan_hash"] for e in started} == {plan.plan_hash}
