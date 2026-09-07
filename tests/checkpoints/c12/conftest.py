"""C12 runs against P32's environment and P33's governance fixtures.

Nothing is rebuilt: the same admin console a person sets an engagement up through, the same
board that approves a workflow, and the same register `load_recipe` consults on every run.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from governance.board import SkillBoard
from registries.recipes import RecipeRegister
from tests.p27 import conftest as p27
from tests.p32 import conftest as p32
from tests.p33 import conftest as p33

HEND = p32.HEND
NOVK = p32.NOVK
WHO = p32.WHO
both = p32.both
clock = p32.clock
config = p32.config
console = p32.console
constraints = p32.constraints
contracts = p32.contracts
environment = p32.environment
henderson = p32.henderson
novak = p32.novak
preflight = p32.preflight
roster = p32.roster
store = p32.store
templates = p32.templates

blobs = p27.blobs
record = p27.record
root = p27.root

recipes = p33.recipes
register = p33.register
board = p33.board

__all__ = ["Path", "RecipeRegister", "SkillBoard", "pytest", "shutil"]
