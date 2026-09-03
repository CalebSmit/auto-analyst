"""Fixtures for P05.

Two of these read the blueprint HTML. The skill tree is meant to be the blueprint's
tree - same layers, same frontmatter, same descriptions - so "the tree and the blueprint
disagree" is a failing test rather than something noticed in month four.

`synthetic` builds a tree in memory rather than on disk. Every loosening the resolver
must refuse is, by definition, something that cannot be committed to `skills/` without
breaking the real tree, so those cases are constructed here instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from graph.resolve import ScopeResolver
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.scopes import ScopeRegistry
from registries.skills import Overlay, Skill, SkillTree

ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT = ROOT / "docs" / "architecture.html"


@pytest.fixture(scope="session")
def scopes() -> ScopeRegistry:
    return ScopeRegistry.load()


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    """P02's registry. The tree names output contracts and they have to be pinned."""
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def constraints() -> ConstraintRegistry:
    """Also P02's. What a skill declares and what the Policy Gate allows must agree."""
    return ConstraintRegistry.load()


@pytest.fixture(scope="session")
def tree() -> SkillTree:
    return SkillTree.load()


@pytest.fixture(scope="session")
def resolver() -> ScopeResolver:
    return ScopeResolver()


@pytest.fixture(scope="session")
def blueprint_skill_scopes() -> dict[str, str]:
    """Which layer the blueprint says each skill lives at."""
    text = BLUEPRINT.read_text(encoding="utf-8")
    block = text[text.index("const SKILLS = ["):text.index("const PLAN_STEPS")]
    return dict(re.findall(r"\{id:'([a-z-]+)',[^\n]*?scope:'([^']*)'", block))


@pytest.fixture(scope="session")
def blueprint_layer_order() -> tuple[str, ...]:
    """LAYER_ORDER as the blueprint writes it, normalised to the yaml's placeholders."""
    text = BLUEPRINT.read_text(encoding="utf-8")
    start = text.index("const LAYER_ORDER = sc =>")
    block = text[start:text.index("];", start)]
    # The blueprint builds each layer by concatenating literals with scope fields.
    # Turning the fields into literals too makes every entry a plain join.
    layers = []
    for entry in block.split("[", 1)[1].split(",\n"):
        expression = (
            entry.replace("sc.practice", "'{practice}'")
            .replace("sc.segment", "'{segment}'")
            .replace("sc.disp", "'{disposition}'")
        )
        layers.append("".join(re.findall(r"'([^']*)'", expression)))
    return tuple(layers)


def skill(
    name: str,
    layer: str,
    *,
    hitl: str = "material_addbacks_require_review",
    sensitivity: str = "masked_only",
    tools: tuple[str, ...] = ("recompute",),
    references: tuple[str, ...] = (),
) -> Skill:
    """A minimal, valid skill. Only the fields an overlay can touch vary."""
    return Skill(
        name=name,
        version="0.1.0",
        status="skeleton",
        layer=layer,
        title=name,
        description=f"{name} description",
        tier="mid",
        inputs=("normalized_historicals",),
        outputs=("addback_schedule",),
        tools=tools,
        data_sensitivity=sensitivity,
        hitl=hitl,
        output_contract=f"skills/{name}@1.0.0",
        references=references,
        path=f"skills/{layer}/{name}/SKILL.md",
    )


def overlay(layer: str, target: str, **parts: object) -> Overlay:
    return Overlay(
        layer=layer,
        target=target,
        why="constructed by a test",
        adds=dict(parts.get("adds") or {}),  # type: ignore[arg-type]
        tightens=dict(parts.get("tightens") or {}),  # type: ignore[arg-type]
    )


@pytest.fixture
def synthetic(scopes: ScopeRegistry) -> object:
    """Build a resolver over a tree assembled in memory."""

    def build(skills: tuple[Skill, ...], overlays: tuple[Overlay, ...]) -> ScopeResolver:
        return ScopeResolver(scopes=scopes, tree=SkillTree(skills, overlays))

    return build


@pytest.fixture(scope="session")
def blueprint_skill_descriptions() -> dict[str, str]:
    """The one-line description the blueprint gives each skill.

    It is the only skill content the orchestrator ever reads, so drift here changes what
    the system does rather than only what a document says.
    """
    text = BLUEPRINT.read_text(encoding="utf-8")
    block = text[text.index("const SKILLS = ["):text.index("const PLAN_STEPS")]
    found: dict[str, str] = {}
    for record in re.split(r"\n\{id:'", block)[1:]:
        name = re.match(r"[a-z-]+", record)
        described = re.search(r"\n description:'((?:[^'\\]|\\.)*)'", record)
        if name and described:
            raw = described.group(1).replace("\'", "'")
            found[name.group(0)] = raw.encode("latin-1", "backslashreplace").decode(
                "unicode_escape"
            )
    return found
