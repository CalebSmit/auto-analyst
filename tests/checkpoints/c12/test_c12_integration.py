"""Checkpoint C12 - a group's workflow, and only approved ones.

Proves: an engagement runs its own group's workflow, and a workflow nobody approved does
not run at all.

Two phases meet here, and each one alone is a worse system than neither. P32 made the
recipe a property of the engagement, so a practice group can say what order its work
happens in - and, on its own, that means a managing director can point an engagement at any
YAML file in the folder. P33 made a recipe something the board approves, with a name on it
and a digest that stops matching when somebody edits the file - and, on its own, that is
ceremony around a setting nobody could vary.

Together they are the thing that was wanted: a group chooses its workflow, and only from
the workflows the firm approved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from admin.console import AdminConsole, AdminRefused
from governance.board import Decision, SkillBoard
from graph.recipes import load_recipe
from registries.recipes import RecipeRegister, RegistrationRefused
from tests.p32.conftest import HEND, NOVK, WHO


def approval(candidate_id: str, reviewer: str = "R. Partner") -> Decision:
    return Decision(
        candidate_id=candidate_id,
        decision="approved",
        reviewer=reviewer,
        reason="the sequence is what the practice does, in the order it does it",
        routed_to=("valuation",),
    )


def test_two_engagements_run_their_own_approved_workflows(
    console: AdminConsole,
    board: SkillBoard,
    register: RecipeRegister,
    recipes: Path,
    both: tuple[str, str],
) -> None:
    """The checkpoint itself.

    Henderson and Novak are the same practice group under the same watch. One is a
    returning client and refreshes monthly; the other is first-year work and needs the
    whole intake. Both workflows were approved by a named person, and both engagements
    run their own.
    """
    for name in ("monthly-refresh", "full-ddr-intake"):
        board.register_recipe(
            recipes / f"{name}.yaml",
            version=1,
            decision=approval(f"cand-{name}"),
            register=register,
        )

    console.set_recipe(HEND, "monthly-refresh", who=WHO, reason="a returning client")
    console.set_recipe(NOVK, "full-ddr-intake", who=WHO, reason="first year, full intake")

    hend = load_recipe("monthly-refresh", recipes, register)
    novk = load_recipe("full-ddr-intake", recipes, register)
    assert hend.name != novk.name
    assert [s.id for s in hend.steps] != [s.id for s in novk.steps], "different work"

    setup = {r["engagement_id"]: r["recipe"] for r in console.setup()["roster"]}
    assert setup[HEND] == "monthly-refresh" and setup[NOVK] == "full-ddr-intake"


def test_a_workflow_nobody_approved_does_not_run(
    console: AdminConsole, register: RecipeRegister, recipes: Path, henderson: Any
) -> None:
    """The other half. The engagement can name it, the configuration will hold it, and
    the run stops at the door - which is where it should stop, because that is the only
    place that knows the file has not changed since somebody read it."""
    console.set_recipe(HEND, "monthly-refresh", who=WHO, reason="chosen")

    with pytest.raises(RegistrationRefused) as refused:
        load_recipe("monthly-refresh", recipes, register)
    assert refused.value.diagnostic.code == "SCOPE.RECIPE_UNREGISTERED"
    assert "never been approved for client work" in refused.value.diagnostic.detail


def test_editing_an_approved_workflow_stops_the_engagement_that_runs_it(
    console: AdminConsole,
    board: SkillBoard,
    register: RecipeRegister,
    recipes: Path,
    henderson: Any,
) -> None:
    """The case both phases exist for, and the one neither catches alone.

    A workflow is approved, an engagement is pointed at it, and then somebody improves it.
    The approval is still on the record and the file is no longer the file that was
    approved - so the run stops, naming the recipe, rather than running a sequence nobody
    reviewed on a client's numbers.
    """
    path = recipes / "monthly-refresh.yaml"
    board.register_recipe(
        path, version=1, decision=approval("cand-monthly-refresh"), register=register
    )
    console.set_recipe(HEND, "monthly-refresh", who=WHO, reason="chosen")
    assert load_recipe("monthly-refresh", recipes, register).name == "monthly-refresh"

    path.write_text(
        path.read_text(encoding="utf-8") + "\n# tightened after review\n", encoding="utf-8"
    )

    with pytest.raises(RegistrationRefused) as refused:
        load_recipe("monthly-refresh", recipes, register)
    assert "edited after the board approved it" in refused.value.diagnostic.detail

    states = {r.name: r.state for r in register.review()}
    assert states["monthly-refresh"] == "edited"
    assert len(register.registered()) == 1, "the approval that happened is still recorded"


def test_the_engagement_cannot_be_pointed_at_a_recipe_that_does_not_exist(
    console: AdminConsole, henderson: Any
) -> None:
    """Choosing and approving are different gates and both are here: a name that resolves
    to no file is refused where the person typing it is still reading."""
    with pytest.raises(AdminRefused) as refused:
        console.set_recipe(HEND, "the-one-we-talked-about", who=WHO, reason="a guess")
    assert refused.value.diagnostics[0].code == "SCOPE.RECIPE_INVALID"


def test_the_surface_shows_which_workflows_are_approved_and_by_whom(
    console: AdminConsole, henderson: Any
) -> None:
    """Answering "why did that engagement not run" without reading a register by hand.

    This reads the repo's own register, which the suite populates the way a firm would
    populate it - so what it shows here is what it would show there.
    """
    listed = {r["name"]: r for r in console.recipes()["recipes"]}
    assert set(listed) == {"monthly-refresh", "full-ddr-intake", "mature-company-valuation"}
    for row in listed.values():
        assert row["state"] == "registered"
        assert row["approved_by"], "a registration names somebody"
        assert row["digest"].startswith("sha256:")
