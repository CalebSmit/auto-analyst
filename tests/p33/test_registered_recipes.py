"""P33: which workflows may run on client work is a recorded decision with a name on it.

A recipe is the order the work happens in - which skills run, against which inputs, with
which guards between them. P32 made it a property of the engagement, which is what a
practice group wanted and which means a managing director can point an engagement at any
YAML file in `recipes/`. A skill cannot reach client work without a board approval; the
sequence the skills run in could, by editing a file.

Three claims:

1. An unregistered recipe cannot run on client work.
2. A recipe edited after registration loses it, because the digest changes.
3. Registration names the person who approved it, and refuses without one.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from governance.board import Decision, SkillBoard
from graph.recipes import RECIPES_DIR, load_recipe, recipe_names
from registries.recipes import (
    RecipeRegister,
    RegistrationRefused,
    digest_of_recipe,
)

ROOT = Path(__file__).resolve().parents[2]


def approval(candidate_id: str = "cand-monthly-refresh", reviewer: str = "R. Partner") -> Decision:
    return Decision(
        candidate_id=candidate_id,
        decision="approved",
        reviewer=reviewer,
        reason="the sequence is what the practice does, in the order it does it",
        routed_to=("valuation",),
    )


# ------------------------------------------------------------- cannot run


def test_an_unregistered_recipe_cannot_run(register: RecipeRegister, recipes: Path) -> None:
    """The first exit criterion, at the one door every run comes through."""
    with pytest.raises(RegistrationRefused) as refused:
        load_recipe("monthly-refresh", recipes, register)

    diagnostic = refused.value.diagnostic
    assert diagnostic.code == "SCOPE.RECIPE_UNREGISTERED"
    assert diagnostic.owner == "config"
    assert "has never been approved for client work" in diagnostic.detail
    assert diagnostic.what_now and "board" in diagnostic.what_now


def test_a_registered_recipe_runs(
    board: SkillBoard, register: RecipeRegister, recipes: Path
) -> None:
    board.register_recipe(
        recipes / "monthly-refresh.yaml", version=1, decision=approval(), register=register
    )
    recipe = load_recipe("monthly-refresh", recipes, register)
    assert recipe.name == "monthly-refresh" and recipe.steps


def test_registering_one_recipe_does_not_register_another(
    board: SkillBoard, register: RecipeRegister, recipes: Path
) -> None:
    """Approval is per workflow. Two recipes in one folder are two decisions."""
    board.register_recipe(
        recipes / "monthly-refresh.yaml", version=1, decision=approval(), register=register
    )
    load_recipe("monthly-refresh", recipes, register)
    with pytest.raises(RegistrationRefused):
        load_recipe("full-ddr-intake", recipes, register)


# ------------------------------------------------------------- edited


def test_a_recipe_edited_after_registration_loses_it(
    board: SkillBoard, register: RecipeRegister, recipes: Path
) -> None:
    """The second exit criterion. Nobody has to notice, remember or revoke anything: the
    bytes changed, so the digest changed, so the lookup misses."""
    path = recipes / "monthly-refresh.yaml"
    board.register_recipe(path, version=1, decision=approval(), register=register)
    assert [r.state for r in register.review() if r.name == "monthly-refresh"] == ["registered"]

    path.write_text(path.read_text(encoding="utf-8") + "\n# one more thought\n", encoding="utf-8")

    assert [r.state for r in register.review() if r.name == "monthly-refresh"] == ["edited"]
    with pytest.raises(RegistrationRefused) as refused:
        load_recipe("monthly-refresh", recipes, register)
    assert "edited after the board approved it" in refused.value.diagnostic.detail

    # The approval is still on the record. It happened; it just no longer matches a file.
    assert len(register.registered()) == 1


def test_the_check_is_on_the_file_not_the_name(
    board: SkillBoard, register: RecipeRegister, recipes: Path
) -> None:
    """A recipe edited after the board saw it is the same problem wearing the name of
    something that was approved."""
    path = recipes / "monthly-refresh.yaml"
    board.register_recipe(path, version=1, decision=approval(), register=register)
    approved_digest = register.registered()[0].digest

    path.write_text(path.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    assert digest_of_recipe(path) != approved_digest
    assert register.is_registered(approved_digest), "the approved bytes are still approved"
    assert not register.is_registered(digest_of_recipe(path))


# ------------------------------------------------------------- who approved it


def test_registration_names_the_person_and_refuses_without_one(
    register: RecipeRegister, recipes: Path
) -> None:
    """The third exit criterion."""
    path = recipes / "monthly-refresh.yaml"
    for blank in ("", "   "):
        with pytest.raises(ValueError, match="names the person who approved it"):
            register.register(path, version=1, approved_by=blank, decision_ref="cand-1")
    with pytest.raises(ValueError, match="carries the approval it rests on"):
        register.register(path, version=1, approved_by="R. Partner", decision_ref="")
    assert register.registered() == ()


def test_only_an_approval_registers_a_recipe(
    board: SkillBoard, register: RecipeRegister, recipes: Path
) -> None:
    """Returned-for-changes and rejected carry the same fields as an approval and mean
    the opposite, so the board takes the decision itself rather than evidence of one."""
    for outcome in ("returned", "rejected"):
        decision = Decision(
            candidate_id="cand-1",
            decision=outcome,
            reviewer="R. Partner",
            reason="not yet",
            routed_to=("valuation",),
        )
        with pytest.raises(ValueError, match="only an approval registers"):
            board.register_recipe(
                recipes / "monthly-refresh.yaml",
                version=1,
                decision=decision,
                register=register,
            )
    assert register.registered() == ()


def test_what_is_recorded_is_who_when_which_bytes_and_which_approval(
    board: SkillBoard, register: RecipeRegister, recipes: Path
) -> None:
    path = recipes / "monthly-refresh.yaml"
    recorded = board.register_recipe(
        path, version=3, decision=approval(reviewer="  R. Partner  "), register=register
    )

    assert recorded.name == "monthly-refresh" and recorded.version == 3
    assert recorded.key == "monthly-refresh@3"
    assert recorded.approved_by == "R. Partner", "whitespace is not part of a name"
    assert recorded.decision_ref == "cand-monthly-refresh"
    assert recorded.digest == digest_of_recipe(path)
    assert recorded.registered_at.endswith("Z")

    written = register.path.read_text(encoding="utf-8")
    assert "Append-only" in written and "governance/board.py" in written


def test_the_approval_is_in_the_governance_record(
    board: SkillBoard, register: RecipeRegister, recipes: Path, record: Any
) -> None:
    """A registration whose approval cannot be found is a registration nobody can audit."""
    board.register_recipe(
        recipes / "monthly-refresh.yaml", version=1, decision=approval(), register=register
    )
    entries = record.entries("cand-monthly-refresh")
    registered = [e for e in entries if "recipe" in (e.detail or {})]
    assert registered, entries
    assert registered[-1].actor == "R. Partner"
    assert registered[-1].detail["recipe"] == "monthly-refresh"


def test_registering_the_same_bytes_twice_records_it_once(
    board: SkillBoard, register: RecipeRegister, recipes: Path
) -> None:
    path = recipes / "monthly-refresh.yaml"
    first = board.register_recipe(path, version=1, decision=approval(), register=register)
    again = board.register_recipe(path, version=1, decision=approval(), register=register)
    assert again == first
    assert len(register.registered()) == 1


def test_a_version_cannot_be_reused_for_different_bytes(
    board: SkillBoard, register: RecipeRegister, recipes: Path
) -> None:
    """A change to a workflow is a new version and a new review, which is the rule the
    skill register keeps and for the same reason."""
    path = recipes / "monthly-refresh.yaml"
    board.register_recipe(path, version=1, decision=approval(), register=register)
    path.write_text(path.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")

    with pytest.raises(RegistrationRefused) as refused:
        board.register_recipe(path, version=1, decision=approval(), register=register)
    assert "new version and a new review" in refused.value.diagnostic.detail


# ------------------------------------------------------------- the boundary


def test_only_the_board_writes_the_recipe_register() -> None:
    """The register cannot import the board - the board reaches back into the harness, and
    the register sits on the path every run takes - so the constraint is a test rather
    than a type. Docstrings are stripped: prose naming the rule is not breaking it."""

    def code_only(source: str) -> str:
        holds = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, holds):
                text = ast.get_docstring(node, clean=False)
                if text:
                    source = source.replace(text, "")
        return source

    callers = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".venv/", "tests/")) or rel == "registries/recipes.py":
            continue
        for node in ast.walk(ast.parse(code_only(path.read_text(encoding="utf-8")))):
            # `decision_ref` is the argument only a write to this register takes, so this
            # finds the call rather than any file that happens to name the class - the
            # admin surface reads the register and registers templates, and does neither
            # of those here.
            if isinstance(node, ast.Call) and any(
                keyword.arg == "decision_ref" for keyword in node.keywords
            ):
                callers.append(rel)
    assert callers == ["governance/board.py"], callers


def test_every_production_caller_loads_from_the_firms_recipe_folder() -> None:
    """What makes the gate a gate rather than a suggestion.

    `load_recipe` enforces registration for `RECIPES_DIR`, which lets the parser's shape
    checks be tested against deliberately malformed files without an exemption flag. That
    only holds if nothing on the client-work path can ask for a recipe from anywhere else.
    """
    offenders = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".venv/", "tests/")) or rel == "graph/recipes.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            named = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if named == "load_recipe" and (len(node.args) > 1 or node.keywords):
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, offenders


def test_the_register_is_not_a_recipe() -> None:
    """It lives beside the recipes it is about; offering it as one would offer somebody a
    workflow that does not exist."""
    assert "registered" not in recipe_names()
    assert sorted(recipe_names()) == [
        "full-ddr-intake",
        "mature-company-valuation",
        "monthly-refresh",
    ]
    assert (RECIPES_DIR / "registered.yaml").parent == RECIPES_DIR


def test_a_clone_has_nothing_registered() -> None:
    """The register is not committed, for the same reason a clearance is not: it records
    that somebody at the firm approved a workflow."""
    from tests.conftest import needs_a_checkout

    needs_a_checkout("what a clone starts with")
    import subprocess

    tracked = subprocess.run(  # noqa: S603
        ["git", "ls-files", "recipes/"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    assert "recipes/monthly-refresh.yaml" in tracked, "the recipes themselves are tracked"
    assert "recipes/registered.yaml" not in tracked
    assert "recipes/registered.yaml" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "recipes/registered.yaml" in (ROOT / ".dockerignore").read_text(encoding="utf-8")
