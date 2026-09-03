"""plan_hash: what it covers, and what it promises.

Two runs with the same hash had identical inputs and identical configuration - same
skill versions, same model pins and effort, same schemas, same constraints, same
retrieved precedents. It does **not** promise identical output. Models are not
deterministic, and the current generation does not expose sampling controls that would
make them so.

What the hash promises is that a difference between two runs is attributable to the
model rather than to something that quietly changed underneath. Claiming more than that
would not survive the first time two runs of one job disagreed, and they will.

So the tests come in pairs: the same inputs hash the same, and every input that can
change under a run without the recipe changing moves the hash. A field left out of the
hash is a pair of runs that can share a name, differ underneath, and legitimately
disagree - which is exactly what a review found with the precedent snapshot before it
was added.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

import pytest

from graph.compile import PlanContext, compile_recipe
from graph.recipes import Recipe, load_recipe
from graph.resolve import ScopeResolver
from tests.p06.conftest import ENGAGEMENT, SNAPSHOT, TAXONOMY, two_step_recipe


def hash_of(recipe: Recipe, context: PlanContext) -> str:
    return compile_recipe(recipe, context).plan_hash


def changed(context: PlanContext, **fields: Any) -> PlanContext:
    return dataclasses.replace(context, **fields)


# ------------------------------------------------------------ the same twice


def test_identical_inputs_give_an_identical_plan_hash(
    monthly: Recipe, context: PlanContext
) -> None:
    """The exit criterion."""
    assert hash_of(monthly, context) == hash_of(monthly, context)


def test_the_hash_is_of_content_not_of_objects(monthly: Recipe) -> None:
    """Everything rebuilt from scratch - a second registry load, a second resolver, a
    second read of the YAML - and the hash still matches. Otherwise it would be a
    property of one process rather than of the plan."""
    first = compile_recipe(
        load_recipe("monthly-refresh"),
        PlanContext(
            engagement_id=ENGAGEMENT,
            scope=ScopeResolver().resolve("valuation/esop/repeat"),
            taxonomy_version=TAXONOMY,
            precedent_snapshot=SNAPSHOT,
        ),
    )
    second = compile_recipe(
        load_recipe("monthly-refresh"),
        PlanContext(
            engagement_id=ENGAGEMENT,
            scope=ScopeResolver().resolve("valuation/esop/repeat"),
            taxonomy_version=TAXONOMY,
            precedent_snapshot=SNAPSHOT,
        ),
    )
    assert first.plan_hash == second.plan_hash


def test_the_hash_is_a_sha256(monthly: Recipe, context: PlanContext) -> None:
    digest = hash_of(monthly, context)
    assert digest.startswith("sha256:")
    assert len(digest) == 71


# ------------------------------------------------- everything that moves it


def test_changing_the_precedent_snapshot_changes_the_plan_hash(
    monthly: Recipe, context: PlanContext
) -> None:
    """The exit criterion, and the one a review added after noticing that retrieved
    precedents change with every approved correction. Without it two runs could share a
    hash, see different examples, and both be right."""
    moved = changed(context, precedent_snapshot="precedent_snapshot_2026_10_01")
    assert hash_of(monthly, context) != hash_of(monthly, moved)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("engagement_id", "NOVK-2026-11"),
        ("taxonomy_version", "coa-taxonomy@2.0.0"),
        ("precedent_snapshot", "another_snapshot"),
        ("effort", "low"),
        ("contracts_version", "9.9.9"),
        ("constraints_version", "9.9.9"),
    ],
)
def test_every_context_field_is_in_the_hash(
    monthly: Recipe, context: PlanContext, field: str, value: str
) -> None:
    """Parameterised over the whole dataclass rather than over a chosen few, so a field
    added later without being hashed fails here."""
    assert hash_of(monthly, context) != hash_of(monthly, changed(context, **{field: value}))


def test_the_context_has_no_field_this_test_forgot(context: PlanContext) -> None:
    """The guard over the guard. A new field on PlanContext that nobody added to the
    list above would leave a hole nothing notices."""
    covered = {
        "engagement_id",
        "taxonomy_version",
        "precedent_snapshot",
        "effort",
        "contracts_version",
        "constraints_version",
        "scope",  # covered by its own tests below
    }
    assert {f.name for f in dataclasses.fields(context)} == covered


def test_a_different_scope_changes_the_hash(
    monthly: Recipe, context: PlanContext, resolver: ScopeResolver
) -> None:
    """Resolution is part of the plan hash, which is what makes "a run records the exact
    skill set it was allowed" true rather than aspirational. The same recipe under
    non-ESOP gets different overlays and a different template."""
    non_esop = changed(context, scope=resolver.resolve("valuation/non-esop/repeat"))
    assert hash_of(monthly, context) != hash_of(monthly, non_esop)


def test_a_different_recipe_version_changes_the_hash(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    first = recipe_from(two_step_recipe(version=1))
    second = recipe_from(two_step_recipe(version=2))
    assert hash_of(first, context) != hash_of(second, context)


def test_a_changed_structure_changes_the_hash(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    plain = two_step_recipe()
    reordered = two_step_recipe()
    reordered["steps"][1]["needs"] = []  # tagging no longer depends on timing
    assert hash_of(recipe_from(plain), context) != hash_of(recipe_from(reordered), context)


def test_a_changed_timeout_changes_the_hash(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    """Configuration, not structure - and still in the hash. Two runs that differ only
    in how long a step was allowed are not the same run."""
    plain = two_step_recipe()
    slower = two_step_recipe()
    slower["steps"][0]["timeout_s"] = 600
    assert hash_of(recipe_from(plain), context) != hash_of(recipe_from(slower), context)


def test_a_changed_loop_ceiling_changes_the_hash(
    recipe_from: Callable[[dict[str, Any]], Recipe], context: PlanContext
) -> None:
    region = {
        "loop": "guard_repair",
        "head": "tagging",
        "members": ["tagging"],
        "why": "why",
    }
    one = recipe_from(two_step_recipe(loops=[{**region, "max_iterations": 1}]))
    two = recipe_from(two_step_recipe(loops=[{**region, "max_iterations": 2}]))
    assert hash_of(one, context) != hash_of(two, context)


def test_the_recipe_name_is_in_the_hash(
    monthly: Recipe, ddr: Recipe, context: PlanContext
) -> None:
    assert hash_of(monthly, context) != hash_of(ddr, context)


# --------------------------------------------------------- what it does not


def test_the_hash_does_not_change_when_nothing_did(
    monthly: Recipe, context: PlanContext
) -> None:
    """The negative case for the whole set above. A hash that changed on every compile
    would pass every "X changes the hash" test and be worthless."""
    hashes = {hash_of(monthly, context) for _ in range(5)}
    assert len(hashes) == 1
