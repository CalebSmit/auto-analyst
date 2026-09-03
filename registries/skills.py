"""The Skill Tree and the Skill Index: two tiers, and the line between them.

**Tier 0** is the Scope Resolver (`graph.resolve`), which narrows the library before
anything is chosen.

**Tier 1 is the Skill Index** - name and one-line description, roughly forty tokens
each, and nothing else. It is the entire skill footprint in the orchestrator's context.
Procedures, references and worked examples stay on disk until a skill is actually
selected, which is what keeps a library growing into the hundreds from eating the
context window before any work starts.

**Tier 2 is the SKILL.md body**, loaded on dispatch and never through here.

`SkillIndex` therefore carries no body and no reference content, and a test asserts it -
the boundary is worth an assertion because the failure is invisible. An index that
quietly grew a `body` field would work perfectly and cost more every run.

The tree is a folder per layer, a folder per skill, a SKILL.md inside it. Adding a
practice group is one folder; adding a skill is one folder at whichever layer it belongs
to. Nothing else changes, which is the whole argument for layering over a flat library:
the shared eighty per cent is written once and reviewed once.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from registries.errors import (
    AMBIGUOUS_SKILL,
    SKILL_INVALID,
    RegistryError,
    diagnose,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
OVERLAY_FILE = "overlays.yaml"

# What a SKILL.md must declare to be dispatchable at all. Each one is something the
# Policy Gate or the dispatcher enforces later; a skill missing any of them is not a
# skill with a gap, it is a skill nothing can be enforced against.
REQUIRED_FRONTMATTER = (
    "name",
    "version",
    "status",
    "scope",
    "title",
    "description",
    "tier",
    "inputs",
    "outputs",
    "tools",
    "data_sensitivity",
    "hitl",
    "output_contract",
)

__all__ = [
    "IndexEntry",
    "Overlay",
    "Skill",
    "SkillIndex",
    "SkillTree",
]


@dataclass(frozen=True)
class Skill:
    """One SKILL.md, as its frontmatter declares it. The body is not held here."""

    name: str
    version: str
    status: str
    layer: str
    title: str
    description: str
    tier: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    tools: tuple[str, ...]
    data_sensitivity: str
    hitl: str
    output_contract: str
    references: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()
    path: str = ""

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass(frozen=True)
class Overlay:
    """A change to an inherited skill, declared at a deeper layer.

    `adds` extends: references, scripts, a narrowed precedent scope. `tightens` raises a
    floor. Neither may loosen, and `graph.resolve` is where that is checked - an overlay
    on its own is a declaration, not yet a decision.
    """

    layer: str
    target: str
    why: str
    adds: dict[str, Any] = field(default_factory=dict)
    tightens: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IndexEntry:
    """Tier 1. Name and description, and deliberately nothing else.

    `layer` and `tier` are here because they are routing facts about the skill rather
    than content from it - which layer answered, and how expensive the call is. Neither
    is a procedure, a reference or an example.
    """

    name: str
    description: str
    layer: str
    tier: str

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"


class SkillTree:
    """Every skill the firm has, laid out in layers."""

    def __init__(self, skills: tuple[Skill, ...], overlays: tuple[Overlay, ...]) -> None:
        self._skills = skills
        self._overlays = overlays
        self._by_layer: dict[str, list[Skill]] = {}
        for skill in skills:
            self._by_layer.setdefault(skill.layer, []).append(skill)

    @classmethod
    def load(cls, skills_dir: Path = SKILLS_DIR) -> SkillTree:
        skills = tuple(sorted(_read_skills(skills_dir), key=lambda s: (s.layer, s.name)))
        overlays = tuple(sorted(_read_overlays(skills_dir), key=lambda o: (o.layer, o.target)))
        tree = cls(skills, overlays)
        tree.self_check()
        return tree

    def __len__(self) -> int:
        return len(self._skills)

    def all(self) -> tuple[Skill, ...]:
        return self._skills

    def at(self, layer: str) -> tuple[Skill, ...]:
        """The skills declared at exactly this layer. Empty is a normal answer."""
        return tuple(self._by_layer.get(layer, ()))

    def overlays(self) -> tuple[Overlay, ...]:
        return self._overlays

    def overlays_at(self, layer: str) -> tuple[Overlay, ...]:
        return tuple(o for o in self._overlays if o.layer == layer)

    def layers(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_layer))

    def self_check(self) -> None:
        """No duplicate at a layer, and no overlay pointing at nothing."""
        seen: dict[tuple[str, str], Skill] = {}
        for skill in self._skills:
            key = (skill.layer, skill.name)
            if key in seen:
                raise RegistryError(
                    diagnose(
                        AMBIGUOUS_SKILL,
                        f"{skill.name!r} is declared twice at {skill.layer}",
                        locator=skill.path,
                    )
                )
            seen[key] = skill
        declared = {s.name for s in self._skills}
        for overlay in self._overlays:
            if overlay.target not in declared:
                raise RegistryError(
                    diagnose(
                        SKILL_INVALID,
                        f"the overlay at {overlay.layer} targets {overlay.target!r}, "
                        f"which no layer declares",
                        locator=f"{overlay.layer}/{OVERLAY_FILE}",
                    )
                )


class SkillIndex:
    """Tier 1, built from a resolved set. Name and description, nothing further."""

    def __init__(self, entries: tuple[IndexEntry, ...]) -> None:
        self._entries = entries

    @classmethod
    def of(cls, skills: tuple[Skill, ...]) -> SkillIndex:
        return cls(
            tuple(
                IndexEntry(
                    name=skill.name,
                    description=skill.description,
                    layer=skill.layer,
                    tier=skill.tier,
                )
                for skill in skills
            )
        )

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[IndexEntry]:
        return iter(self._entries)

    def entries(self) -> tuple[IndexEntry, ...]:
        return self._entries

    def names(self) -> tuple[str, ...]:
        return tuple(entry.name for entry in self._entries)

    def as_prompt(self) -> str:
        """What actually goes into the orchestrator's context. One line per skill."""
        return "\n".join(f"- {entry}" for entry in self._entries)

    def __repr__(self) -> str:
        return f"<SkillIndex {len(self._entries)} skills>"


# ------------------------------------------------------------------- reading


def _locate(path: Path) -> str:
    """A path a reader can act on. Relative to the repo when it is inside it, absolute
    when it is not - a locator that raises while building an error message is worse
    than a long one."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _read_skills(skills_dir: Path) -> Iterator[Skill]:
    for path in sorted(skills_dir.rglob("SKILL.md")):
        frontmatter = _frontmatter(path)
        layer = path.parent.parent.relative_to(skills_dir).as_posix()
        missing = [f for f in REQUIRED_FRONTMATTER if not frontmatter.get(f)]
        if missing:
            raise RegistryError(
                diagnose(
                    SKILL_INVALID,
                    f"frontmatter is missing {', '.join(missing)}",
                    locator=_locate(path),
                )
            )
        if frontmatter["scope"] != layer:
            raise RegistryError(
                diagnose(
                    SKILL_INVALID,
                    f"declares scope {frontmatter['scope']!r} but sits at {layer!r}. A "
                    f"skill moved without updating its declaration would resolve from "
                    f"one layer and claim another.",
                    locator=_locate(path),
                )
            )
        if frontmatter["name"] != path.parent.name:
            raise RegistryError(
                diagnose(
                    SKILL_INVALID,
                    f"declares name {frontmatter['name']!r} in a folder called "
                    f"{path.parent.name!r}",
                    locator=_locate(path),
                )
            )
        yield Skill(
            name=frontmatter["name"],
            version=str(frontmatter["version"]),
            status=frontmatter["status"],
            layer=layer,
            title=frontmatter["title"],
            description=" ".join(str(frontmatter["description"]).split()),
            tier=frontmatter["tier"],
            inputs=tuple(frontmatter["inputs"]),
            outputs=tuple(frontmatter["outputs"]),
            tools=tuple(frontmatter["tools"]),
            data_sensitivity=frontmatter["data_sensitivity"],
            hitl=frontmatter["hitl"],
            output_contract=frontmatter["output_contract"],
            references=tuple(frontmatter.get("references") or ()),
            scripts=tuple(frontmatter.get("scripts") or ()),
            path=_locate(path),
        )


def _frontmatter(path: Path) -> dict[str, Any]:
    """The YAML block between the first two `---` lines, and not one byte of the body."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise RegistryError(
            diagnose(
                SKILL_INVALID,
                "no frontmatter block; a SKILL.md starts with ---",
                locator=_locate(path),
            )
        )
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise RegistryError(
            diagnose(
                SKILL_INVALID,
                "the frontmatter block is not closed",
                locator=_locate(path),
            )
        )
    loaded = yaml.safe_load(parts[1])
    if not isinstance(loaded, dict):
        raise RegistryError(
            diagnose(
                SKILL_INVALID,
                "frontmatter is not a mapping",
                locator=_locate(path),
            )
        )
    return loaded


def _read_overlays(skills_dir: Path) -> Iterator[Overlay]:
    for path in sorted(skills_dir.rglob(OVERLAY_FILE)):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        layer = path.parent.relative_to(skills_dir).as_posix()
        if raw.get("scope") != layer:
            raise RegistryError(
                diagnose(
                    SKILL_INVALID,
                    f"declares scope {raw.get('scope')!r} but sits at {layer!r}",
                    locator=_locate(path),
                )
            )
        for entry in raw.get("overlays") or ():
            if not entry.get("why"):
                raise RegistryError(
                    diagnose(
                        SKILL_INVALID,
                        f"the overlay on {entry.get('target')!r} gives no reason. An "
                        f"overlay without one is indistinguishable from a mistake six "
                        f"months later.",
                        locator=_locate(path),
                    )
                )
            yield Overlay(
                layer=layer,
                target=entry["target"],
                why=" ".join(str(entry["why"]).split()),
                adds=dict(entry.get("adds") or {}),
                tightens=dict(entry.get("tightens") or {}),
            )
