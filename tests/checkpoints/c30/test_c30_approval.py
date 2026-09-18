"""C30 - A machine that can be started.

The question behind this phase was not "is the register protected" - it was protected to
the point of being unreachable. On a clean clone nothing loaded, nothing activated, nothing
ran, and there was no door anywhere. Refusing to do it badly had quietly become refusing to
do it at all.

What this checks is that the door exists, that it leads through the board, and that the
things it was protecting are still protected.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_the_approval_exists_on_every_layer_the_clearance_does() -> None:
    """Four layers, because a route with no button is a feature only its author can use,
    and a button with no route is a page that lies."""
    console = (ROOT / "admin" / "console.py").read_text(encoding="utf-8")
    app = (ROOT / "admin" / "app.py").read_text(encoding="utf-8")
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")

    assert "def approve_recipe" in console
    assert "/api/admin/recipes/{name}/approve" in app
    assert "approveRecipe" in page
    assert 'data-act="approveRecipe"' in page, "reached through ACTIONS, never an inline handler"


def test_the_approval_goes_through_the_board_and_not_around_it() -> None:
    console = (ROOT / "admin" / "console.py").read_text(encoding="utf-8")
    assert "register_recipe" in console, "the board's method, not the register's"
    assert "SkillBoard" in console


def test_the_page_still_builds_and_offers_it_only_where_it_is_needed() -> None:
    from admin.page import PAGE

    assert "approveRecipe" in PAGE
    # Offered on a recipe that is not approved, and not on one that is: a button that
    # re-approved what was already approved would write a second decision nobody made.
    assert "x.state === 'registered' ? '' :" in PAGE


def test_a_recipe_still_cannot_run_unapproved(tmp_path: Path) -> None:
    """The thing the whole arrangement is for, unchanged by there being a door.

    Asked by loading one against an empty register rather than by looking for the name of
    the exception in a file - a door was just added to this, and what matters is that the
    lock still works, not that the word is still written down somewhere.
    """
    import shutil

    import pytest

    from graph.recipes import load_recipe
    from registries.recipes import RecipeRegister, RegistrationRefused

    folder = tmp_path / "recipes"
    folder.mkdir()
    shutil.copy2(ROOT / "recipes" / "monthly-refresh.yaml", folder / "monthly-refresh.yaml")
    empty = RecipeRegister(path=tmp_path / "registered.yaml", root=folder)

    with pytest.raises(RegistrationRefused) as refused:
        load_recipe("monthly-refresh", folder, empty)
    assert refused.value.diagnostic.code == "SCOPE.RECIPE_UNREGISTERED"


def test_the_register_is_still_not_committed() -> None:
    """It records that somebody approved a workflow. Shipping one ships a decision nobody
    made - which is exactly why there had to be a way to make one instead."""
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "recipes/registered.yaml" in ignored


def test_the_route_is_reachable_only_from_this_machine() -> None:
    """Every admin route is behind the request gate; an approval is not an exception."""
    app = (ROOT / "admin" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(app)
    approve = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "approve_recipe"
    ]
    assert approve, "the route function is not there"
    assert "_guard" in ast.unparse(approve[0]), "it must refuse what every other write refuses"
