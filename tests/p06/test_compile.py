"""The compiled graph: typed steps, an order, and what the compiler refuses.

Nothing executes that has not been through here, so most of this file is about what does
not compile. A plan that fails at run time failed here first and was let through.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from graph.compile import RUN_BOUNDARY, PlanContext, compile_recipe
from graph.recipes import Recipe
from registries.contracts import ContractRegistry
from registries.errors import RegistryError
from tests.p06.conftest import skill_step, two_step_recipe


def test_the_monthly_refresh_compiles_to_what_the_blueprint_shows(
    monthly: Recipe, context: PlanContext
) -> None:
    """`8 steps · 5 skill invocations` and `DAG valid · 5 loop regions declared` - the
    fifth is EBITDA's self-verification, which the blueprint says applies always."""
    plan = compile_recipe(monthly, context)
    assert len(plan) == 8
    assert len(plan.steps_where(kind="skill")) == 5
    assert len(plan.loops) == 5
    assert plan.plan_hash.startswith("sha256:")


def test_the_order_is_topological(monthly: Recipe, context: PlanContext) -> None:
    plan = compile_recipe(monthly, context)
    position = {step_id: n for n, step_id in enumerate(plan.order)}
    for step in plan.steps:
        for producer in step.needs:
            assert position[producer] < position[step.id], (
                f"{step.id} is ordered before {producer}, which it needs"
            )


def test_the_order_is_stable_across_compiles(monthly: Recipe, context: PlanContext) -> None:
    """Ties break on the recipe's own order, so a plan reads the way it was written and
    two compiles of one recipe produce the same list rather than the same set."""
    assert compile_recipe(monthly, context).order == compile_recipe(monthly, context).order


def test_parallel_branches_are_identified(ddr: Recipe, context: PlanContext) -> None:
    """The DDR recipe forks after masking: tagging the response and normalizing the
    statements need nothing from each other."""
    plan = compile_recipe(ddr, context)
    assert plan.parallel_branches() == (("ddr", "timing"),)
    assert plan.levels[0] == ("intake",)


def test_a_linear_recipe_has_no_parallel_branches(
    monthly: Recipe, context: PlanContext
) -> None:
    """The other half. A branch finder that finds branches everywhere finds nothing."""
    assert compile_recipe(monthly, context).parallel_branches() == ()


def test_every_edge_carries_the_schema_of_what_crosses_it(
    monthly: Recipe, context: PlanContext, contracts: ContractRegistry
) -> None:
    plan = compile_recipe(monthly, context)
    for edge in plan.forward_edges():
        producer = plan.step(edge.src)
        assert edge.schema == producer.output_schema
        if edge.schema is not None:
            assert edge.schema in contracts.ids()


def test_the_only_untyped_edges_are_the_ones_no_contract_exists_for_yet(
    monthly: Recipe, context: PlanContext
) -> None:
    """The intake manifest is P16's and the delivery record is P21's. Inventing schemas
    for them now would mean pinning something nobody has reviewed - so they are exposed
    and counted rather than quietly typed as `object`."""
    plan = compile_recipe(monthly, context)
    assert [(e.src, e.dst) for e in plan.untyped_edges()] == [
        ("intake", "mask"),
        ("mask", "timing"),
    ]
    for edge in plan.untyped_edges():
        assert plan.step(edge.src).kind == "io"


def test_a_run_input_comes_from_the_run_boundary(
    monthly: Recipe, context: PlanContext
) -> None:
    """Nothing enters a plan undeclared, so an external input is a ref like any other -
    with the boundary as its producer instead of a step."""
    plan = compile_recipe(monthly, context)
    profile = [r for r in plan.step("ebitda").inputs if r.name == "engagement_profile"]
    assert len(profile) == 1
    assert profile[0].producer == RUN_BOUNDARY
    assert profile[0].from_run
    assert profile[0].schema == "engagement_profile@1.0.0"
    assert "engagement_profile" not in plan.step("ebitda").needs


# ------------------------------------------------------- pins and versions


def test_a_skill_step_is_pinned_to_a_version_from_the_resolved_scope(
    monthly: Recipe, context: PlanContext
) -> None:
    """A recipe names a skill; the scope decides which version this engagement has. That
    is what makes the plan hash move when a skill is revised, without editing recipes."""
    plan = compile_recipe(monthly, context)
    for step in plan.steps_where(kind="skill"):
        assert step.skill is not None
        name, _, version = step.skill.partition("@")
        assert context.scope.skill(name).skill.version == version


def test_each_skill_step_carries_the_model_pin_for_its_tier(
    monthly: Recipe, context: PlanContext
) -> None:
    """A workfile that cannot say which model produced a figure is a workfile that
    cannot be defended, and the pin has to be fixed before the run starts, not chosen
    while it is happening."""
    plan = compile_recipe(monthly, context)
    assert plan.step("ebitda").model_pin == "claude-opus-5 @ effort=high"
    assert plan.step("timing").model_pin == "claude-sonnet-5 @ effort=high"
    assert plan.step("intake").model_pin is None


def test_a_step_key_leaves_room_for_the_half_the_compiler_cannot_know(
    monthly: Recipe, context: PlanContext
) -> None:
    """Content hashes and context_ref do not exist until something has run. P08 completes
    the key with them; the compiler exposes the static half rather than pretending to a
    key it cannot compute."""
    material = compile_recipe(monthly, context).step("ebitda").key_material()
    assert material[0] == "ebitda"
    assert material[1].startswith("ebitda-normalization@")
    assert "claude-opus-5" in material[2]
    assert material[3] == "skills/ebitda-normalization@1.0.0"


# --------------------------------------------------------- max_turns == 1


def test_every_compiled_step_takes_one_model_turn(
    monthly: Recipe, ddr: Recipe, context: PlanContext
) -> None:
    for recipe in (monthly, ddr):
        assert {s.max_turns for s in compile_recipe(recipe, context).steps} == {1}


@pytest.mark.parametrize("turns", [2, 3, 10])
def test_a_step_declaring_more_than_one_turn_is_rejected(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext, turns: int
) -> None:
    """The exit criterion. A skill proposes; if it needs a tool result, that is another
    step in the plan - compiled, keyed and visible - not a hidden turn inside one."""
    body = two_step_recipe()
    body["steps"][1]["max_turns"] = turns
    with pytest.raises(RegistryError) as raised:
        compile_recipe(recipe_from(body), context)
    assert raised.value.diagnostic.code == "POLICY.MULTI_TURN_STEP"
    assert "one model turn" in str(raised.value)


def test_zero_turns_is_rejected_as_readily_as_two(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """`max_turns != 1` rather than `> 1`. A step that takes no turn at all is not a
    cheaper skill step, it is a step that cannot do its job."""
    body = two_step_recipe()
    body["steps"][0]["max_turns"] = 0
    with pytest.raises(RegistryError, match="POLICY.MULTI_TURN_STEP"):
        compile_recipe(recipe_from(body), context)


# ------------------------------------------------------------- the refusals


def test_a_step_needing_something_that_does_not_exist_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    body = two_step_recipe()
    body["steps"][1]["needs"] = ["timing", "nonexistent"]
    with pytest.raises(RegistryError, match="nonexistent"):
        compile_recipe(recipe_from(body), context)


def test_a_step_needing_itself_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """A step that repeats is a declared loop region, not a dependency on its own
    output."""
    body = two_step_recipe()
    body["steps"][1]["needs"] = ["tagging"]
    with pytest.raises(RegistryError, match="needs itself"):
        compile_recipe(recipe_from(body), context)


def test_a_skill_step_with_no_output_schema_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """Every edge declares the schema and version of the data crossing it."""
    body = two_step_recipe()
    del body["steps"][0]["output_schema"]
    with pytest.raises(RegistryError, match="output_schema"):
        compile_recipe(recipe_from(body), context)


def test_an_unpinned_output_schema_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """An unpinned version is never resolved to a guess."""
    body = two_step_recipe()
    body["steps"][0]["output_schema"] = "skills/timing-normalization@9.9.9"
    with pytest.raises(RegistryError, match="not pinned"):
        compile_recipe(recipe_from(body), context)


def test_an_undeclared_run_input_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """Nothing enters a plan undeclared."""
    body = two_step_recipe()
    body["steps"][0]["run_inputs"] = ["something_from_nowhere"]
    with pytest.raises(RegistryError, match="does not declare"):
        compile_recipe(recipe_from(body), context)


def test_a_recipe_naming_a_skill_the_scope_did_not_resolve_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe],
    context: PlanContext,
    resolver: Any,
) -> None:
    """The Scope Resolver's control, made real by the compiler. A Corporate Finance run
    is not declining to use the ESOP skills - it never had them, and a recipe that asks
    for one is a recipe for a different engagement."""
    body = two_step_recipe()
    body["steps"][1] = skill_step(
        "dol",
        "dol-adequate-consideration",
        "skills/dol-adequate-consideration@1.0.0",
        needs=["timing"],
    )
    recipe = recipe_from(body)

    compile_recipe(recipe, context)  # valuation/esop/repeat has it

    corpfin = PlanContext(
        engagement_id=context.engagement_id,
        scope=resolver.resolve("corporate-finance/tbd/repeat"),
        taxonomy_version=context.taxonomy_version,
        precedent_snapshot=context.precedent_snapshot,
    )
    with pytest.raises(RegistryError) as raised:
        compile_recipe(recipe, corpfin)
    assert raised.value.diagnostic.code == "SCOPE.RECIPE_INVALID"
    assert "did not resolve into corporate-finance/tbd/repeat" in str(raised.value)
