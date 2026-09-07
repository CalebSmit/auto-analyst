"""Fixtures for P33: a recipe folder and a register under the test's control, and the
governance record the board writes its approvals into.

Nothing here touches `recipes/` in the repo. A registration records that somebody approved
a workflow, and a test that wrote one into the firm's own register would be recording a
decision nobody made.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from governance.board import SkillBoard
from registries.recipes import RecipeRegister
from tests.p27 import conftest as p27

blobs = p27.blobs
record = p27.record
root = p27.root

REPO_RECIPES = Path(__file__).resolve().parents[2] / "recipes"


@pytest.fixture
def recipes(tmp_path: Path) -> Path:
    """A copy of the recipes the repo ships, so what is registered here is a real recipe
    that really loads - and editing one is editing a file nothing else reads."""
    folder = tmp_path / "recipes"
    folder.mkdir()
    for name in ("monthly-refresh", "full-ddr-intake"):
        shutil.copy2(REPO_RECIPES / f"{name}.yaml", folder / f"{name}.yaml")
    return folder


@pytest.fixture
def register(tmp_path: Path, recipes: Path) -> RecipeRegister:
    return RecipeRegister(path=tmp_path / "registered.yaml", root=recipes)


@pytest.fixture
def board(record: object, blobs: object) -> SkillBoard:
    return SkillBoard(record, blobs)  # type: ignore[arg-type]
