"""Shared fixtures for P02.

Two of these read the blueprint HTML directly. That is deliberate: the blueprint is the
design of record, so "the contracts and the blueprint disagree" should be a failing test
rather than something somebody notices in month four.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry

ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT = ROOT / "docs" / "architecture.html"

SHA = "sha256:" + "9f" * 32


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def constraints() -> ConstraintRegistry:
    return ConstraintRegistry.load()


@pytest.fixture
def figure() -> dict[str, Any]:
    """The worked example from the blueprint's Runtime tab, as data."""
    return {
        "value": 486200.00,
        "unit": "currency",
        "currency": "USD",
        "scale": 1,
        "period": {"type": "FY", "end": "2023-12-31"},
        "source_id": SHA,
        "locator": "TB_FY23!B44:B51",
        "source_version": 1,
        "derivation": {"op": "sum", "of": ["TB_FY23!B44", "TB_FY23!B45"]},
        "masked": True,
        "confidence": 0.83,
        "produced_by": "ebitda-normalization@0.1.0",
        "model_pin": "claude-sonnet-5 @ effort=high",
    }


# ------------------------------------------------------------------ blueprint


def _skills_block() -> str:
    text = BLUEPRINT.read_text(encoding="utf-8")
    return text[text.index("const SKILLS = ["):text.index("const PLAN_STEPS")]


@pytest.fixture(scope="session")
def blueprint_skills() -> dict[str, dict[str, tuple[str, ...]]]:
    """Every skill the blueprint declares, with its inputs, outputs and tools."""
    block = _skills_block()
    entries: dict[str, dict[str, tuple[str, ...]]] = {}
    # Each skill record starts at its id and runs to the next one.
    starts = [m.start() for m in re.finditer(r"\{id:'[a-z-]+', ?name:", block)]
    starts.append(len(block))
    for begin, end in zip(starts, starts[1:], strict=False):
        record = block[begin:end]
        name = re.search(r"\{id:'([a-z-]+)'", record).group(1)
        entries[name] = {
            field: tuple(re.findall(r"'([a-z_]+)'", match.group(1)))
            for field in ("inputs", "outputs", "tools")
            if (match := re.search(rf"{field}:\[([^\]]*)\]", record))
        }
    return entries


def walk_schemas(schema: Any) -> list[dict[str, Any]]:
    """Every object subschema in a schema document, the root included."""
    found: list[dict[str, Any]] = []
    if isinstance(schema, dict):
        found.append(schema)
        for value in schema.values():
            found.extend(walk_schemas(value))
    elif isinstance(schema, list):
        for item in schema:
            found.extend(walk_schemas(item))
    return found


@pytest.fixture(scope="session")
def blueprint_tool_namespace() -> dict[str, dict[str, str]]:
    """The blueprint's own tool table: name, node, kind, and how many skills use it."""
    text = BLUEPRINT.read_text(encoding="utf-8")
    start = text.index("const TOOLNS = [")
    block = text[start:text.index("];", start)]
    rows = re.findall(r"\['([a-z_]+)','([a-z_]+)','(\w+)','([^']*)','(\d+) skills?'\]", block)
    return {
        name: {"node": node, "kind": kind, "description": desc, "used_by": int(count)}
        for name, node, kind, desc, count in rows
    }


@pytest.fixture(scope="session")
def blueprint_repo_listing() -> str:
    """The repo tree the Runtime tab shows. It is documentation people build from, so a
    directory that exists and is not on it is a divergence like any other."""
    text = BLUEPRINT.read_text(encoding="utf-8")
    start = text.index("const REPO = [")
    return text[start:text.index("].join('')", start)]
