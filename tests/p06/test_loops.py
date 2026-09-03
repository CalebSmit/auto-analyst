"""Declared loop regions, and the cycles that are refused for not being one.

The graph owns every loop. No agent decides for itself whether to try again, and the way
that stays true is that a cycle with no declared ceiling does not compile.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from graph.compile import MAX_IN_RUN_ITERATIONS, PlanContext, compile_recipe
from graph.recipes import Recipe
from registries.constraints import ConstraintRegistry
from registries.errors import RegistryError
from tests.p06.conftest import skill_step, two_step_recipe


def guard_repair(head: str = "tagging", members: list[str] | None = None, **extra: Any) -> dict:
    body: dict[str, Any] = {
        "loop": "guard_repair",
        "head": head,
        "members": members or [head],
        "max_iterations": 2,
        "why": "the guard's structured failure is appended to the step input",
    }
    body.update(extra)
    return body


# --------------------------------------------------- what the recipes declare


def test_each_declared_region_becomes_a_back_edge(
    monthly: Recipe, context: PlanContext
) -> None:
    plan = compile_recipe(monthly, context)
    assert len(plan.back_edges()) == len(plan.loops) == 4
    assert {(e.src, e.dst) for e in plan.back_edges()} == {
        ("tagging", "tagging"),
        ("ebitda", "ebitda"),
        ("ebitda", "tagging"),
        ("qc", "qc"),
    }


def test_a_region_spanning_two_steps_returns_from_the_deepest_one(
    monthly: Recipe, context: PlanContext
) -> None:
    """Conflict resolution re-invokes each disagreeing skill, so its back edge runs from
    ebitda to tagging rather than being a self-loop."""
    plan = compile_recipe(monthly, context)
    conflict = next(r for r in plan.loops if r.loop == "conflict_resolution")
    assert conflict.head == "tagging"
    assert conflict.tail == "ebitda"
    assert conflict.members == ("tagging", "ebitda")


def test_a_step_can_sit_in_two_regions_at_once(
    monthly: Recipe, context: PlanContext
) -> None:
    """Self-verification applies to every EBITDA output; guard repair applies when that
    output fails its schema check. Both are true of the same step, which is why the
    compiled Step carries `loops` rather than the blueprint's single `loop`."""
    plan = compile_recipe(monthly, context)
    assert plan.step("ebitda").loops == ("guard_repair:ebitda", "conflict_resolution:tagging")
    assert plan.step("tagging").loops == (
        "self_verification:tagging",
        "conflict_resolution:tagging",
    )
    assert plan.step("timing").loops == ()


def test_every_region_carries_the_scope_the_constraints_give_it(
    monthly: Recipe, context: PlanContext
) -> None:
    """Only in-run loops are cycles in a plan. A plan containing a run-spanning loop
    would be a plan that never terminates on its own."""
    assert {r.scope for r in compile_recipe(monthly, context).loops} == {"in_run"}


def test_every_ceiling_is_within_what_the_constraints_allow(
    monthly: Recipe, ddr: Recipe, context: PlanContext, constraints: ConstraintRegistry
) -> None:
    allowed = {spec.name: spec.max_iterations for spec in constraints.in_run_loops()}
    for recipe in (monthly, ddr):
        for region in compile_recipe(recipe, context).loops:
            assert region.max_iterations <= allowed[region.loop]
            assert region.max_iterations <= MAX_IN_RUN_ITERATIONS


# ------------------------------------------------------ undeclared cycles


def test_an_undeclared_cycle_is_rejected_with_a_locatable_error(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """The exit criterion. Two steps each needing the other - and the error names them,
    because "there is a cycle somewhere in this plan" is not something anyone can act on.
    """
    body = two_step_recipe()
    body["steps"][0]["needs"] = ["tagging"]
    with pytest.raises(RegistryError) as raised:
        compile_recipe(recipe_from(body), context)
    assert raised.value.diagnostic.code == "LOOP.UNDECLARED_CYCLE"
    assert raised.value.diagnostic.locator == "tagging, timing"
    assert "tagging, timing" in str(raised.value)


def test_a_longer_undeclared_cycle_names_every_step_in_it(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    body = two_step_recipe()
    body["steps"].append(
        skill_step(
            "ebitda",
            "ebitda-normalization",
            "skills/ebitda-normalization@1.0.0",
            needs=["tagging"],
        )
    )
    body["steps"][0]["needs"] = ["ebitda"]  # ebitda -> timing closes it
    with pytest.raises(RegistryError) as raised:
        compile_recipe(recipe_from(body), context)
    assert raised.value.diagnostic.locator == "ebitda, tagging, timing"


def test_declaring_the_region_does_not_make_a_dependency_cycle_legal(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """A back edge is the loop controller feeding a changed input back in. It is not a
    dependency, and declaring a region does not turn one into the other - the plan still
    has to have an order to execute in."""
    body = two_step_recipe(loops=[guard_repair(head="timing", members=["timing", "tagging"])])
    body["steps"][0]["needs"] = ["tagging"]
    with pytest.raises(RegistryError) as raised:
        compile_recipe(recipe_from(body), context)
    assert raised.value.diagnostic.code == "LOOP.UNDECLARED_CYCLE"


# --------------------------------------------------------- bad declarations


def test_a_region_over_steps_that_never_reach_each_other_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """Its back edge would close a cycle over steps that have no path between them,
    which is not a loop - it is a new dependency wearing a ceiling."""
    body = two_step_recipe(loops=[guard_repair(head="tagging", members=["tagging", "timing"])])
    with pytest.raises(RegistryError) as raised:
        compile_recipe(recipe_from(body), context)
    assert raised.value.diagnostic.code == "SCOPE.RECIPE_INVALID"
    assert "nothing in the plan runs from the head to the tail" in str(raised.value)


def test_a_region_with_a_hole_in_it_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """timing -> tagging -> ebitda, declared over timing and ebitda only. Tagging would
    iterate without being inside a declared loop, which is the thing the ceiling exists
    to prevent."""
    body = two_step_recipe(
        loops=[guard_repair(head="timing", members=["timing", "ebitda"])]
    )
    body["steps"].append(
        skill_step(
            "ebitda",
            "ebitda-normalization",
            "skills/ebitda-normalization@1.0.0",
            needs=["tagging"],
        )
    )
    with pytest.raises(RegistryError) as raised:
        compile_recipe(recipe_from(body), context)
    assert "also passes through tagging" in str(raised.value)


def test_a_region_whose_head_is_not_a_member_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """Iteration restarts at the head, so it has to be inside the region."""
    body = two_step_recipe(loops=[guard_repair(head="timing", members=["tagging"])])
    with pytest.raises(RegistryError, match="not among its members"):
        compile_recipe(recipe_from(body), context)


def test_members_must_read_from_the_head_outwards(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """So the back edge is visible in the declaration rather than derived from a rule
    somebody has to remember."""
    body = two_step_recipe(loops=[guard_repair(head="tagging", members=["timing", "tagging"])])
    with pytest.raises(RegistryError, match="lists 'timing' first"):
        compile_recipe(recipe_from(body), context)


def test_a_region_naming_a_step_that_does_not_exist_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    body = two_step_recipe(loops=[guard_repair(head="nonexistent")])
    with pytest.raises(RegistryError, match="no step for"):
        compile_recipe(recipe_from(body), context)


# ------------------------------------------------------------- the ceilings


def test_a_ceiling_above_what_the_constraints_allow_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe],
    context: PlanContext,
    constraints: ConstraintRegistry,
) -> None:
    """Ceilings are raised in constraints.yaml, deliberately, never in the recipe that
    wants the extra go."""
    allowed = next(s for s in constraints.in_run_loops() if s.name == "guard_repair")
    body = two_step_recipe(
        loops=[guard_repair(max_iterations=allowed.max_iterations + 1)]
    )
    with pytest.raises(RegistryError) as raised:
        compile_recipe(recipe_from(body), context)
    assert raised.value.diagnostic.code == "LOOP.CEILING_EXCEEDED"
    assert "constraints.yaml allows" in str(raised.value)


def test_a_loop_that_is_not_an_in_run_loop_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """Human clarification is run-spanning: the run checkpoints, the process exits, and
    a person's answer restarts it at the frontier. It is not a cycle in a plan, and a
    plan that contained one would never terminate on its own."""
    body = two_step_recipe(
        loops=[guard_repair(**{"loop": "human_clarification", "max_iterations": 1})]
    )
    with pytest.raises(RegistryError) as raised:
        compile_recipe(recipe_from(body), context)
    assert raised.value.diagnostic.code == "LOOP.CEILING_EXCEEDED"
    assert "not an in-run loop" in str(raised.value)


def test_an_unknown_loop_name_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    body = two_step_recipe(loops=[guard_repair(**{"loop": "keep_trying"})])
    with pytest.raises(RegistryError, match="LOOP.CEILING_EXCEEDED"):
        compile_recipe(recipe_from(body), context)


def test_a_region_that_cannot_iterate_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """A region declaring zero iterations is not a loop; remove it."""
    body = two_step_recipe(loops=[guard_repair(max_iterations=0)])
    with pytest.raises(RegistryError) as raised:
        compile_recipe(recipe_from(body), context)
    assert raised.value.diagnostic.code == "LOOP.CEILING_EXCEEDED"
    assert "not a loop" in str(raised.value)
