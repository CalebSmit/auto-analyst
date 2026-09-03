"""Fixtures for P06.

`recipe_from` writes YAML to a temp directory and loads it back through `load_recipe`,
rather than constructing a `Recipe` object directly. Every refusal this phase is about is
a refusal about a *file* somebody wrote, so the tests go in the same door a recipe does.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from graph.compile import PlanContext
from graph.recipes import Recipe, load_recipe
from graph.resolve import ResolvedScope, ScopeResolver
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry

ROOT = Path(__file__).resolve().parents[2]

ENGAGEMENT = "HEND-2026-04"
SCOPE_PATH = "valuation/esop/repeat"
TAXONOMY = "coa-taxonomy@1.0.0"
SNAPSHOT = "precedent_snapshot_2026_09_01"


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def constraints() -> ConstraintRegistry:
    return ConstraintRegistry.load()


@pytest.fixture(scope="session")
def resolver() -> ScopeResolver:
    return ScopeResolver()


@pytest.fixture(scope="session")
def scope(resolver: ScopeResolver) -> ResolvedScope:
    return resolver.resolve(SCOPE_PATH)


@pytest.fixture
def context(scope: ResolvedScope) -> PlanContext:
    return PlanContext(
        engagement_id=ENGAGEMENT,
        scope=scope,
        taxonomy_version=TAXONOMY,
        precedent_snapshot=SNAPSHOT,
    )


@pytest.fixture(scope="session")
def monthly() -> Recipe:
    return load_recipe("monthly-refresh")


@pytest.fixture(scope="session")
def ddr() -> Recipe:
    return load_recipe("full-ddr-intake")


@pytest.fixture
def recipe_from(tmp_path: Path) -> Callable[[dict[str, Any]], Recipe]:
    """Write a recipe and load it the way the pipeline would."""

    def build(body: dict[str, Any]) -> Recipe:
        name = str(body.get("name", "made-up"))
        path = tmp_path / f"{name}.yaml"
        path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
        return load_recipe(name, tmp_path)

    return build


def skill_step(step_id: str, skill: str, contract: str, **extra: Any) -> dict[str, Any]:
    """A valid skill step. Tests vary one thing about it at a time."""
    return {
        "id": step_id,
        "kind": "skill",
        "label": step_id,
        "skill": skill,
        "output_schema": contract,
        "on_failure": "quarantine",
        **extra,
    }


def two_step_recipe(**extra: Any) -> dict[str, Any]:
    """timing -> tagging. The smallest thing that can hold an edge and a loop."""
    body: dict[str, Any] = {
        "name": "made-up",
        "version": 1,
        "title": "Made up",
        "steps": [
            skill_step("timing", "timing-normalization", "skills/timing-normalization@1.0.0"),
            skill_step(
                "tagging",
                "line-item-tagging",
                "skills/line-item-tagging@1.0.0",
                needs=["timing"],
            ),
        ],
    }
    body.update(extra)
    return body
