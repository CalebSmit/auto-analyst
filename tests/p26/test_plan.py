"""The Run Plan: the same compiler and the same assertions as a recipe, the named recipe
when a proposal does not survive them, and the whole plan written down before it runs."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from graph.compile import PlanContext, compile_recipe
from graph.recipes import load_recipe
from ops.blobs import LocalContentStore
from ops.console import Console, create_app
from ops.events import EventBus
from ops.run_store import SqlRunStore
from orchestrate import REQUIRED_LOOPS, RunPlanner, recipe_from_proposal
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from tests.p26.conftest import FALLBACK, RUN_INPUTS, events_of, proposal


def with_steps(**changes: Any) -> dict[str, Any]:
    """The composed proposal with one or more steps edited, by id."""
    steps = [dict(s) for s in proposal()["steps"]]
    by_id = {s["id"]: s for s in steps}
    for step_id, fields in changes.items():
        by_id[step_id].update(fields)
    return proposal(steps=steps)


def gated() -> dict[str, Any]:
    """EBITDA normalization placed after the tie-out gate: a plan whose figures would be
    written after the check that verifies them."""
    steps = [dict(s) for s in proposal()["steps"]]
    by_id = {s["id"]: s for s in steps}
    steps.insert(
        4,
        {"id": "tieout_gate", "kind": "guard", "label": "Tie-out gate",
         "needs": ["timing", "tagging"], "on_failure": "halt"},
    )
    by_id["ebitda"]["needs"] = ["tieout_gate"]
    return proposal(steps=steps)


def test_a_proposal_that_violates_a_plan_assertion_is_rejected_and_the_recipe_is_used(
    world: dict[str, Any], context: PlanContext, store: SqlRunStore
) -> None:
    """The exit criterion. The proposal is coherent, compiles as a graph, and is refused
    by the assertion that says a step running after verification may not emit figures -
    the same assertion, in the same suite, that a named recipe goes through."""
    planned = world["planner"].from_proposal(
        gated(), context, world["run_id"], fallback_recipe=FALLBACK, run_inputs=RUN_INPUTS
    )
    assert planned.refusal is not None
    assert planned.refusal.code == "PROCESS.PLAN_REFUSED"
    assert "runs after verification" in planned.refusal.detail
    assert planned.source == "recipe" and not planned.from_proposal
    assert planned.plan.recipe == FALLBACK
    assert planned.plan_hash == compile_recipe(load_recipe(FALLBACK), context).plan_hash

    (refused,) = events_of(store, world["run_id"], "plan.refused")
    assert refused.diagnostic_code == "PROCESS.PLAN_REFUSED" and refused.level == "warn"
    assert refused.payload["fallback_recipe"] == FALLBACK
    assert refused.node_id == "orchestrator"

    document = planned.document
    assert document["source"] == "recipe"
    assert document["refusal"]["code"] == "PROCESS.PLAN_REFUSED"
    assert document["refusal"]["what_now"]
    assert document["rationale"], "what it proposed and why is still on the record"


@pytest.mark.parametrize(
    ("name", "broken", "code"),
    [
        ("a cycle nobody declared", with_steps(timing={"needs": ["mask", "qc"]}),
         "LOOP.UNDECLARED_CYCLE"),
        ("a skill this engagement does not have",
         with_steps(tagging={"skill": "first-year-baseline"}), "SCOPE.RECIPE_INVALID"),
        ("a skill that does not exist at all",
         with_steps(tagging={"skill": "unit-award-valuation"}), "SCOPE.RECIPE_INVALID"),
        ("an input nothing declared",
         with_steps(ebitda={"run_inputs": ["participant_census"]}), "SCOPE.RECIPE_INVALID"),
        ("a step needing one that is not in the plan",
         with_steps(qc={"needs": ["timing", "dcf"]}), "SCOPE.RECIPE_INVALID"),
    ],
)
def test_every_way_a_proposal_can_be_wrong_ends_at_the_same_recipe(
    world: dict[str, Any],
    context: PlanContext,
    store: SqlRunStore,
    name: str,
    broken: dict[str, Any],
    code: str,
) -> None:
    """The compiler refuses and the assertions refuse, and both are ordinary: the run
    proceeds on the recipe it was always going to fall back to, with the reason recorded.
    A model proposing a bad plan is not a way for a run to fail."""
    planned = world["planner"].from_proposal(
        broken, context, world["run_id"], fallback_recipe=FALLBACK, run_inputs=RUN_INPUTS
    )
    assert planned.refusal is not None and planned.refusal.code == code, name
    assert planned.refusal.what_now and planned.refusal.owner
    assert planned.source == "recipe"
    assert planned.plan_hash == compile_recipe(load_recipe(FALLBACK), context).plan_hash
    assert len(events_of(store, world["run_id"], "plan.refused")) == 1
    assert store.artifacts(world["run_id"])[-1].name == "run_plan"


def test_a_surviving_proposal_is_the_plan_and_the_compiler_pinned_everything_in_it(
    world: dict[str, Any], context: PlanContext, contracts: ContractRegistry
) -> None:
    """What the model supplied is which skills run and what each needs. Versions, model
    pins and output contracts are the compiler's, from the resolved scope."""
    planned = world["planner"].from_proposal(
        proposal(), context, world["run_id"], fallback_recipe=FALLBACK, run_inputs=RUN_INPUTS
    )
    assert planned.from_proposal and planned.refusal is None
    assert planned.plan.order == (
        "intake", "mask", "timing", "tagging", "ebitda", "qc", "release"
    )
    tagging = planned.plan.step("tagging")
    assert tagging.skill == "line-item-tagging@0.1.0", "the scope pinned the version"
    assert tagging.model_pin and "effort=" in tagging.model_pin
    assert tagging.output_schema == contracts.skill_output_key("line-item-tagging")
    assert tagging.max_turns == 1 and tagging.timeout_s > 0
    assert all(s.max_turns == 1 for s in planned.plan.steps)
    assert planned.plan_hash != compile_recipe(load_recipe(FALLBACK), context).plan_hash


def test_the_model_has_no_way_to_ask_for_another_iteration(
    world: dict[str, Any], context: PlanContext, constraints: ConstraintRegistry
) -> None:
    """The graph owns every loop. The regions in a composed plan come from a table in
    code and their ceilings from the constraint registry, so a proposal cannot raise one,
    add one or remove one - it has no field to do it in."""
    planned = world["planner"].from_proposal(
        proposal(), context, world["run_id"], fallback_recipe=FALLBACK, run_inputs=RUN_INPUTS
    )
    ceilings = {spec.name: spec.max_iterations for spec in constraints.in_run_loops()}
    assert planned.plan.loops, "a composed plan still gets its declared regions"
    for region in planned.plan.loops:
        assert region.max_iterations == ceilings[region.loop]
        assert region.scope == "in_run"
    assert {r.loop for r in planned.plan.loops} == {loop for loop, _, _ in REQUIRED_LOOPS}

    # The same regions the named recipe declares for the same skills.
    recipe_plan = compile_recipe(load_recipe(FALLBACK), context)
    assert {(r.loop, r.head) for r in planned.plan.loops} == {
        (r.loop, r.head) for r in recipe_plan.loops
    }


def test_a_region_is_dropped_rather_than_forced_when_the_shape_does_not_hold(
    contracts: ContractRegistry, constraints: ConstraintRegistry
) -> None:
    """A guard between tagging and EBITDA means the cross-skill region no longer encloses
    the path between them. It is left out rather than declared wrongly: a loop only ever
    permits an extra iteration, so a plan without one iterates less, never more."""
    recipe = recipe_from_proposal(
        gated(), contracts=contracts, constraints=constraints, run_inputs=RUN_INPUTS
    )
    assert "conflict_resolution" not in {loop.loop for loop in recipe.loops}
    assert {loop.loop for loop in recipe.loops} == {
        "self_verification", "guard_repair", "tieout_repair"
    }


def test_the_run_plan_is_written_down_before_anything_runs(
    world: dict[str, Any],
    context: PlanContext,
    store: SqlRunStore,
    blobs: LocalContentStore,
    bus: EventBus,
    contracts: ContractRegistry,
) -> None:
    """An artifact on the run, valid against its contract, readable on the console -
    before a step exists. 'What is it doing?' has an answer you read in advance."""
    planned = world["planner"].from_proposal(
        proposal(), context, world["run_id"], fallback_recipe=FALLBACK, run_inputs=RUN_INPUTS,
        proposal_ref="sha256:" + "ab" * 32, request_hash="sha256:" + "cd" * 32,
    )
    assert store.steps(world["run_id"]) == (), "nothing has run"

    (artifact,) = [a for a in store.artifacts(world["run_id"]) if a.name == "run_plan"]
    written = json.loads(blobs.get(_ref(artifact.content_hash)).decode("utf-8"))
    assert written == planned.document
    contracts.validate("run_plan@1.0.0", written)
    assert written["plan_hash"] == planned.plan_hash
    assert written["order"] == list(planned.plan.order)
    assert written["source"] == "proposal" and written["refusal"] is None
    assert written["proposal_ref"].startswith("sha256:")
    ebitda = next(s for s in written["steps"] if s["id"] == "ebitda")
    assert ebitda["skill"] == "ebitda-normalization@0.1.0"
    assert sorted(i["name"] for i in ebitda["inputs"]) == [
        "engagement_profile", "tagging", "timing"
    ]
    assert "self_verification:ebitda" in ebitda["loops"]

    (compiled,) = events_of(store, world["run_id"], "plan.compiled")
    assert compiled.node_id == "run_plan" and compiled.payload["source"] == "proposal"
    assert compiled.payload["plan_hash"] == planned.plan_hash

    api = TestClient(create_app(Console(store, bus, blobs=blobs)))
    shown = api.get(f"/api/runs/{world['run_id']}/plan").json()
    assert shown["plan_hash"] == planned.plan_hash
    assert [s["id"] for s in shown["steps"]] == list(planned.plan.order)
    assert shown["rationale"].startswith("Two statements")
    page = api.get(f"/api/runs/{world['run_id']}").json()
    assert page["trace"]["nodes"]["run_plan"] == "passed"


def test_a_named_recipe_still_compiles_to_exactly_what_it_always_did(
    world: dict[str, Any], context: PlanContext, store: SqlRunStore
) -> None:
    """The planner is not a second way to compile a recipe. Every run before this phase
    would get the same plan hash from it."""
    planned = world["planner"].from_recipe(FALLBACK, context, world["run_id"])
    assert planned.source == "recipe" and planned.refusal is None
    assert planned.plan_hash == compile_recipe(load_recipe(FALLBACK), context).plan_hash
    assert planned.document["rationale"] == ""
    assert planned.document["proposal_ref"] is None
    assert events_of(store, world["run_id"], "plan.refused") == []


def test_the_planner_needs_no_model(
    store: SqlRunStore, bus: EventBus, blobs: LocalContentStore, context: PlanContext
) -> None:
    """Compiling, refusing and falling back are deterministic Python. A planner built
    with no door, no port and no key does all of it."""
    import inspect

    import orchestrate.plan as module

    planner = RunPlanner(store, bus, blobs)
    store.start_run(
        run_id="run_no_model",
        engagement_id=context.engagement_id,
        plan_hash="sha256:" + "7c" * 32,
        versions={
            "model_pin": "none",
            "skills": [],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": "coa-taxonomy@1.0.0",
        },
    )
    planned = planner.from_proposal(
        gated(), context, "run_no_model", fallback_recipe=FALLBACK, run_inputs=RUN_INPUTS
    )
    assert planned.refusal is not None and planned.plan.recipe == FALLBACK
    imports = [
        line
        for line in inspect.getsource(module).splitlines()
        if line.startswith(("import ", "from "))
    ]
    assert not [line for line in imports if "ports.llm" in line or "harness.door" in line]


def _ref(content_hash: str) -> Any:
    from ops.blobs import ContentRef

    return ContentRef(content_hash=content_hash, media_type="application/json", name="run_plan")
