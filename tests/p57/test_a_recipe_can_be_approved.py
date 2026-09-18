"""Approving a workflow on a machine where none has been approved.

`recipes/registered.yaml` is gitignored on purpose: it records that somebody approved a
workflow, so shipping one would ship a decision nobody made. The only writer is
`SkillBoard.register_recipe`, and until now it was called from two test files and nothing
else - no route, no button, no command.

That is not protection, it is absence. On a clean clone no recipe loads, preflight check 10
fails, no engagement activates and no run starts, and there is nothing anywhere to click.
The admin console's own docstring said a button here "would be the shortcut P33 exists to
close", which is right about the shortcut and became an argument for having no door at all.

So: the same act, through the board rather than around it. What these hold down is that the
door leads where the old one would have, and nowhere else.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from admin.console import AdminConsole
from registries.recipes import RecipeRegister, RegistrationRefused, digest_of_recipe

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def console() -> AdminConsole:
    """A console with nothing wired but what approval needs. `approve_recipe` reads no
    config, no roster and no preflight - it is a governance act, not a settings change."""
    return AdminConsole.__new__(AdminConsole)


# ------------------------------------------------------------------ the door opens


def test_a_recipe_can_be_approved_and_then_loads(
    console: AdminConsole, register: RecipeRegister, board: Any, recipes: Path
) -> None:
    """The whole point, end to end: from "nothing will run" to "this will"."""
    from graph.recipes import load_recipe

    with pytest.raises(RegistrationRefused):
        load_recipe("monthly-refresh", recipes, register)

    done = console.approve_recipe(
        "monthly-refresh",
        who="Caleb Smit",
        reason="the sequence is what the practice does, in the order it does it",
        register=register,
        board=board,
    )

    assert done["name"] == "monthly-refresh"
    assert done["approved_by"] == "Caleb Smit"
    assert done["digest"] == digest_of_recipe(recipes / "monthly-refresh.yaml")
    assert load_recipe("monthly-refresh", recipes, register).name == "monthly-refresh"


def test_the_approvers_name_and_reason_reach_the_governance_chain(
    console: AdminConsole, register: RecipeRegister, board: Any, record: Any
) -> None:
    """A registration that did not say who, or why, would be a decision with the deciding
    taken out of it - and this record outlives everybody who remembers the conversation."""
    console.approve_recipe(
        "monthly-refresh",
        who="Caleb Smit",
        reason="historicals, then add-backs, then the model - that is the job",
        register=register,
        board=board,
    )

    entries = [e for e in record.entries() if e.candidate == "recipe:monthly-refresh"]
    assert entries, "nothing reached the chain"
    assert entries[-1].actor == "Caleb Smit"
    assert "that is the job" in entries[-1].detail["reason"]

    (row,) = [r for r in register.registered() if r.name == "monthly-refresh"]
    assert row.approved_by == "Caleb Smit"


# ----------------------------------------------------------------- and only that far


def test_an_approval_without_a_person_is_refused(
    console: AdminConsole, register: RecipeRegister, board: Any
) -> None:
    with pytest.raises(ValueError, match="names a person"):
        console.approve_recipe(
            "monthly-refresh", who="  ", reason="because", register=register, board=board
        )
    assert register.registered() == ()


def test_an_approval_without_a_reason_is_refused(
    console: AdminConsole, register: RecipeRegister, board: Any
) -> None:
    """Methodology clearance needs no reason - it always means the same thing. Approving a
    workflow means "these steps in this order are what we do", and which steps and which
    order is exactly what somebody will want to know in a year."""
    with pytest.raises(ValueError, match="needs a reason"):
        console.approve_recipe(
            "monthly-refresh", who="Caleb Smit", reason="", register=register, board=board
        )
    assert register.registered() == ()


def test_a_recipe_that_is_not_there_is_refused(
    console: AdminConsole, register: RecipeRegister, board: Any
) -> None:
    with pytest.raises(KeyError):
        console.approve_recipe(
            "not-a-workflow", who="Caleb Smit", reason="x", register=register, board=board
        )


def test_approving_one_workflow_does_not_approve_another(
    console: AdminConsole, register: RecipeRegister, board: Any, recipes: Path
) -> None:
    from graph.recipes import load_recipe

    console.approve_recipe(
        "monthly-refresh", who="Caleb Smit", reason="this one", register=register, board=board
    )
    with pytest.raises(RegistrationRefused):
        load_recipe("full-ddr-intake", recipes, register)


# ----------------------------------------------------------------------- over http


def test_the_route_approves_and_refuses_the_way_the_console_does(
    register: RecipeRegister, board: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """From /admin, which is where a person will be when nothing runs.

    The console is where the refusals live; this is here because the exit criterion says
    "from /admin" and a route that took the arguments in the wrong order would satisfy every
    test above.
    """
    from fastapi.testclient import TestClient

    from admin.app import create_admin_app

    console = AdminConsole.__new__(AdminConsole)
    real = console.approve_recipe

    def through(name: str, *, who: str, reason: str) -> dict[str, Any]:
        return real(name, who=who, reason=reason, register=register, board=board)

    monkeypatch.setattr(console, "approve_recipe", through, raising=False)
    client = TestClient(create_admin_app(console))

    refused = client.post("/api/admin/recipes/monthly-refresh/approve", json={"who": "C. Smit"})
    assert refused.status_code >= 400, "a reason is required and the route must not default it"
    assert register.registered() == ()

    done = client.post(
        "/api/admin/recipes/monthly-refresh/approve",
        json={"who": "C. Smit", "reason": "this is the order we work in"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["approved_by"] == "C. Smit"
    assert [r.name for r in register.registered()] == ["monthly-refresh"]


# ---------------------------------------------------------- an edit is not an approval


def test_a_recipe_edited_after_approval_has_to_be_approved_again(
    console: AdminConsole, register: RecipeRegister, board: Any, recipes: Path
) -> None:
    """Nobody has to notice or revoke anything - the bytes changed, so the digest changed.
    What matters here is that re-approving is a second decision with its own version, not
    the first one quietly reused."""
    from graph.recipes import load_recipe

    path = recipes / "monthly-refresh.yaml"
    console.approve_recipe(
        "monthly-refresh", who="Caleb Smit", reason="first read", register=register, board=board
    )
    path.write_text(path.read_text(encoding="utf-8") + "\n# one more step\n", encoding="utf-8")

    with pytest.raises(RegistrationRefused):
        load_recipe("monthly-refresh", recipes, register)

    again = console.approve_recipe(
        "monthly-refresh", who="Caleb Smit", reason="read it again", register=register, board=board
    )
    assert again["version"] == 2, "a re-approval is its own decision"
    assert again["digest"] == digest_of_recipe(path)
    assert load_recipe("monthly-refresh", recipes, register).name == "monthly-refresh"

    versions = sorted(r.version for r in register.registered() if r.name == "monthly-refresh")
    assert versions == [1, 2], "both approvals are kept; neither overwrote the other"


# -------------------------------------------------------- the board is still the only writer


def test_nothing_but_the_board_writes_the_register() -> None:
    """The constraint P33 rests on, re-asserted now that there is a route.

    A route that called `RecipeRegister.register` directly would be the shortcut with a
    coat on: it would produce a registered recipe with no governance chain entry behind it.
    Read as code rather than as text, so a docstring mentioning the call does not fail it.
    """
    callers: dict[str, list[int]] = {}
    for path in ROOT.rglob("*.py"):
        if "tests" in path.parts or ".venv" in path.parts:
            continue
        if path.name == "recipes.py" and path.parent.name == "registries":
            continue  # its own definition
        source = path.read_text(encoding="utf-8")
        if "RecipeRegister" not in source:
            continue  # a module that cannot name it cannot call it
        for node in ast.walk(ast.parse(source)):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr != "register":
                continue
            # `self.roster.register(...)` is the project roster, a different register that
            # happens to share the verb. What is being counted is a call on something this
            # module built or was handed.
            receiver = node.func.value
            if (
                isinstance(receiver, ast.Attribute)
                and isinstance(receiver.value, ast.Name)
                and receiver.value.id == "self"
            ):
                continue
            callers.setdefault(path.relative_to(ROOT).as_posix(), []).append(node.lineno)

    assert callers, "this test found no callers at all, so it is checking nothing"
    assert set(callers) == {"governance/board.py"}, (
        f"something outside the board writes the recipe register: {callers}"
    )
