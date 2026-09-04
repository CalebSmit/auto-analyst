"""Job recipes: what loads, and what is refused before it reaches the compiler.

A recipe composes skills; it contains no domain logic. The tests that matter here are
the refusals - a recipe that loads with a hole in it is a recipe that fails later, in a
run, where the diagnosis costs more.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from graph.recipes import Recipe, load_recipe, recipe_names
from registries.errors import RegistryError
from tests.p06.conftest import skill_step, two_step_recipe


def test_both_recipes_load(monthly: Recipe, ddr: Recipe) -> None:
    assert recipe_names() == ("full-ddr-intake", "monthly-refresh")
    assert monthly.key == "monthly-refresh@v3"
    assert ddr.key == "full-ddr-intake@v1"


def test_the_monthly_refresh_is_the_one_the_blueprint_runs(monthly: Recipe) -> None:
    """The blueprint's own console line: `8 steps · 5 skill invocations · recipe:
    monthly-refresh v3`."""
    assert len(monthly.steps) == 8
    assert len([s for s in monthly.steps if s.kind == "skill"]) == 5
    assert monthly.version == 3


def test_five_loop_regions_are_declared(monthly: Recipe) -> None:
    """`DAG valid · 5 loop regions declared`: every in-run loop the constraint registry
    knows about, with self-verification declared twice - on tagging and on EBITDA."""
    assert len(monthly.loops) == 5
    assert {loop.loop for loop in monthly.loops} == {
        "self_verification",
        "guard_repair",
        "conflict_resolution",
        "tieout_repair",
    }


def test_every_declared_loop_gives_a_reason(monthly: Recipe, ddr: Recipe) -> None:
    for recipe in (monthly, ddr):
        for loop in recipe.loops:
            assert len(loop.why) > 40, f"{recipe.name}: {loop.loop}"


def test_a_recipe_contains_no_domain_logic(monthly: Recipe, ddr: Recipe) -> None:
    """A recipe composes skills. If domain vocabulary starts appearing here, the same
    knowledge is now in two places and they will drift."""
    for recipe in (monthly, ddr):
        text = " ".join(step.label.lower() for step in recipe.steps)
        for word in ("addback", "multiple", "discount rate", "wacc", "goodwill"):
            assert word not in text, f"{recipe.name} labels mention {word}"


def test_every_step_says_what_happens_when_it_fails(monthly: Recipe, ddr: Recipe) -> None:
    """There is no implicit 'carry on regardless'."""
    for recipe in (monthly, ddr):
        for step in recipe.steps:
            assert step.on_failure in ("halt", "quarantine", "review")


def test_max_turns_defaults_to_one(monthly: Recipe, ddr: Recipe) -> None:
    """Not a default anybody had to choose. Neither recipe mentions max_turns at all."""
    for recipe in (monthly, ddr):
        assert {step.max_turns for step in recipe.steps} == {1}


# ------------------------------------------------------------- the refusals


def test_an_unknown_recipe_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RegistryError) as raised:
        load_recipe("no-such-recipe", tmp_path)
    assert raised.value.diagnostic.code == "SCOPE.RECIPE_INVALID"


def test_a_recipe_with_no_steps_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe]
) -> None:
    with pytest.raises(RegistryError, match="no steps"):
        recipe_from({"name": "made-up", "steps": []})


def test_a_duplicate_step_id_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe]
) -> None:
    """Step ids are stable within a plan and everything keys off them."""
    body = two_step_recipe()
    body["steps"].append(
        skill_step("timing", "timing-normalization", "skills/timing-normalization@1.0.0")
    )
    with pytest.raises(RegistryError, match="twice"):
        recipe_from(body)


def test_an_unknown_kind_is_refused(recipe_from: Callable[[dict[str, Any]], Recipe]) -> None:
    body = two_step_recipe()
    body["steps"][0]["kind"] = "magic"
    with pytest.raises(RegistryError, match="kind"):
        recipe_from(body)


def test_an_unknown_on_failure_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe]
) -> None:
    body = two_step_recipe()
    body["steps"][0]["on_failure"] = "ignore"
    with pytest.raises(RegistryError, match="on_failure"):
        recipe_from(body)


def test_a_skill_step_naming_no_skill_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe]
) -> None:
    body = two_step_recipe()
    del body["steps"][0]["skill"]
    with pytest.raises(RegistryError, match="names no skill"):
        recipe_from(body)


def test_a_non_skill_step_naming_a_skill_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe]
) -> None:
    """An io step that claims a skill would be a model call nothing dispatches."""
    body = two_step_recipe()
    body["steps"][0]["kind"] = "io"
    with pytest.raises(RegistryError, match="only a skill step"):
        recipe_from(body)


def test_a_loop_without_a_ceiling_is_refused(
    recipe_from: Callable[[dict[str, Any]], Recipe]
) -> None:
    """A region without a ceiling is not a declared loop, it is a cycle with a name."""
    body = two_step_recipe(
        loops=[{"loop": "guard_repair", "head": "tagging", "members": ["tagging"]}]
    )
    with pytest.raises(RegistryError, match="max_iterations"):
        recipe_from(body)


def test_a_recipe_whose_name_disagrees_with_its_filename_is_refused(tmp_path: Path) -> None:
    """`load_recipe("monthly-refresh")` has to get the monthly refresh. A file whose
    declared name is something else would be loaded under one name and recorded in the
    run manifest under another."""
    body = two_step_recipe()
    body["name"] = "something-else"
    (tmp_path / "made-up.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")
    with pytest.raises(RegistryError, match="declares name"):
        load_recipe("made-up", tmp_path)