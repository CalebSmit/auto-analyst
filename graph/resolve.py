"""Tier 0: the Scope Resolver. Deterministic Python, no model.

Before anything is chosen, the field is narrowed. The engagement says what it is -
Valuation / ESOP / returning client - and that path resolves against a layered library
into one set: the applicable skills, the overlays in force, the template to build into,
and the precedent scope that may be retrieved from.

This is the cheapest control in the system. A Corporate Finance skill is not something
an ESOP run declines to use; it is something that run never had. And it is what keeps
the library viable: as Chartwell adds practice groups the tree grows into the hundreds,
while what the orchestrator reads stays about a dozen descriptions.

Two rules do the work.

**Deeper shadows shallower, and only by declaring the same skill.** A layer never removes
what a shallower layer gave it, so no run loses a firm skill by being specific.

**An overlay may only tighten.** It may raise a review floor, narrow a privacy class,
and take tools away; it may never do the reverse. A loosening raises here rather than
warning, because a review floor that was quietly lowered is indistinguishable from one
nobody set. If the looser setting is genuinely right, it belongs in the skill at the
layer where it is true - reaching up from a deeper layer to relax a shallower promise
means the shallower promise was never worth anything.

Resolution is part of the plan hash, so a run records the exact skill set it was allowed.
`resolution_hash` is what P06 folds in.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from registries.errors import (
    OVERLAY_LOOSENS,
    SKILL_INVALID,
    RegistryError,
    diagnose,
)
from registries.scopes import ScopePath, ScopeRegistry
from registries.skills import Overlay, Skill, SkillIndex, SkillTree

REPO_ROOT = Path(__file__).resolve().parents[1]
BINDINGS_FILE = REPO_ROOT / "templates" / "bindings.yaml"

FIRM_LAYER = "_firm"

# The only dimensions an overlay may tighten, and the only things it may add. Anything
# else is either a typo or a loosening wearing a different word, and both are refused:
# an overlay vocabulary that quietly accepts new keys is one that quietly accepts new
# powers.
TIGHTENABLE = ("hitl", "data_sensitivity", "tools")
ADDABLE = ("references", "scripts", "escalate", "precedent_scope")

__all__ = [
    "ResolvedScope",
    "ResolvedSkill",
    "ScopeResolver",
    "TemplateBinding",
]


@dataclass(frozen=True)
class TemplateBinding:
    """Which Excel model this scope builds into, and which layer said so."""

    layer: str
    file: str
    template_version: str
    why: str = ""


@dataclass(frozen=True)
class ResolvedSkill:
    """One skill as this scope actually gets it: where it came from, and what changed."""

    skill: Skill
    layer: str
    hitl: str
    data_sensitivity: str
    tools: tuple[str, ...]
    references: tuple[str, ...]
    shadowed: tuple[str, ...] = ()
    """Shallower layers that also declared this skill. Recorded rather than discarded:
    "which version of the EBITDA procedure ran" should not be archaeology."""
    overlays: tuple[Overlay, ...] = ()
    escalate_additions: tuple[str, ...] = ()
    precedent_scope: str | None = None

    @property
    def name(self) -> str:
        return self.skill.name

    @property
    def modified(self) -> bool:
        return bool(self.overlays)


@dataclass(frozen=True)
class ResolvedScope:
    """Exactly one skill set for exactly one scope path."""

    scope: ScopePath
    layers: tuple[str, ...]
    skills: tuple[ResolvedSkill, ...]
    overlays: tuple[Overlay, ...]
    template: TemplateBinding | None
    precedent_scope: str
    counts: tuple[tuple[str, int], ...]
    explain: tuple[str, ...]
    scopes_version: str
    resolution_hash: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(r.name for r in self.skills)

    @property
    def firm_layer_only(self) -> bool:
        """True when nothing below the firm layer contributed anything.

        Stated as a property rather than left for a reader to infer from a count,
        because "Consulting has no skills yet" and "Consulting resolved badly" look
        identical from the outside and are not the same situation.
        """
        return all(r.layer == FIRM_LAYER for r in self.skills) and not self.overlays

    def index(self) -> SkillIndex:
        """Tier 1: name and description only, for the skills this scope resolved to."""
        return SkillIndex.of(tuple(r.skill for r in self.skills))

    def skill(self, name: str) -> ResolvedSkill:
        found = next((r for r in self.skills if r.name == name), None)
        if found is None:
            raise KeyError(f"{name!r} did not resolve into {self.scope}")
        return found

    def __len__(self) -> int:
        return len(self.skills)


class ScopeResolver:
    """Walks the layers and returns one answer."""

    def __init__(
        self,
        scopes: ScopeRegistry | None = None,
        tree: SkillTree | None = None,
        bindings_file: Path = BINDINGS_FILE,
    ) -> None:
        self.scopes = scopes or ScopeRegistry.load()
        self.tree = tree or SkillTree.load()
        self.bindings = _read_bindings(bindings_file)

    def resolve(self, scope: ScopePath | str) -> ResolvedScope:
        path = ScopePath.parse(scope) if isinstance(scope, str) else scope
        self.scopes.validate(path)
        layers = self.scopes.layers_for(path)

        resolved: dict[str, ResolvedSkill] = {}
        counts: list[tuple[str, int]] = []
        for layer in layers:
            at_layer = self.tree.at(layer)
            counts.append((layer, len(at_layer)))
            for skill in at_layer:
                previous = resolved.get(skill.name)
                resolved[skill.name] = ResolvedSkill(
                    skill=skill,
                    layer=layer,
                    hitl=skill.hitl,
                    data_sensitivity=skill.data_sensitivity,
                    tools=skill.tools,
                    references=skill.references,
                    shadowed=(*previous.shadowed, previous.layer) if previous else (),
                )

        overlays = tuple(o for layer in layers for o in self.tree.overlays_at(layer))
        disposition = self.scopes.disposition(path.disposition)
        precedent_scope = disposition.precedent_scope
        for overlay in overlays:
            if overlay.target not in resolved:
                # Declared at a layer in force, but its target never resolved here. Not
                # an error: an overlay on a skill this scope does not have simply has
                # nothing to change.
                continue
            resolved[overlay.target] = self._apply(resolved[overlay.target], overlay)

        skills = tuple(resolved[name] for name in sorted(resolved))
        template = self._bind_template(layers)
        explain = _explain(path, layers, counts, skills, overlays, template)

        result = ResolvedScope(
            scope=path,
            layers=layers,
            skills=skills,
            overlays=overlays,
            template=template,
            precedent_scope=precedent_scope,
            counts=tuple(counts),
            explain=explain,
            scopes_version=self.scopes.version,
        )
        return _with_hash(result)

    # -- overlays

    def _apply(self, current: ResolvedSkill, overlay: Overlay) -> ResolvedSkill:
        _reject_unknown_keys(overlay)

        hitl = current.hitl
        sensitivity = current.data_sensitivity
        tools = current.tools

        if "hitl" in overlay.tightens:
            hitl = self._tighten_review(current, overlay)
        if "data_sensitivity" in overlay.tightens:
            sensitivity = self._tighten_sensitivity(current, overlay)
        if "tools" in overlay.tightens:
            tools = _tighten_tools(current, overlay)

        references = current.references + tuple(
            r for r in overlay.adds.get("references", ()) if r not in current.references
        )
        escalate = current.escalate_additions
        if overlay.adds.get("escalate"):
            escalate = (*escalate, " ".join(str(overlay.adds["escalate"]).split()))

        precedent = current.precedent_scope
        if "precedent_scope" in overlay.adds:
            precedent = self._checked_precedent_scope(overlay)

        return ResolvedSkill(
            skill=current.skill,
            layer=current.layer,
            hitl=hitl,
            data_sensitivity=sensitivity,
            tools=tools,
            references=references,
            shadowed=current.shadowed,
            overlays=(*current.overlays, overlay),
            escalate_additions=escalate,
            precedent_scope=precedent,
        )

    def _tighten_review(self, current: ResolvedSkill, overlay: Overlay) -> str:
        proposed = str(overlay.tightens["hitl"])
        was = self.scopes.review_rank(current.hitl)
        now = self.scopes.review_rank(proposed)
        if now <= was:
            raise RegistryError(
                diagnose(
                    OVERLAY_LOOSENS,
                    f"the overlay at {overlay.layer} would move {current.name} from "
                    f"{current.hitl} (rank {was}) to {proposed} (rank {now}). An "
                    f"overlay raises a review floor; it never lowers one, and setting "
                    f"it no higher is not raising it.",
                    locator=f"{overlay.layer} -> {overlay.target}",
                )
            )
        return proposed

    def _tighten_sensitivity(self, current: ResolvedSkill, overlay: Overlay) -> str:
        proposed = str(overlay.tightens["data_sensitivity"])
        was = self.scopes.sensitivity_rank(current.data_sensitivity)
        now = self.scopes.sensitivity_rank(proposed)
        if now <= was:
            raise RegistryError(
                diagnose(
                    OVERLAY_LOOSENS,
                    f"the overlay at {overlay.layer} would move {current.name} from "
                    f"{current.data_sensitivity} to {proposed}, which widens what the "
                    f"skill may be shown. A privacy class narrows from a deeper layer "
                    f"or it does not change.",
                    locator=f"{overlay.layer} -> {overlay.target}",
                )
            )
        return proposed

    def _checked_precedent_scope(self, overlay: Overlay) -> str:
        proposed = str(overlay.adds["precedent_scope"])
        declared = {d.precedent_scope for d in self.scopes.dispositions}
        if proposed not in declared:
            raise RegistryError(
                diagnose(
                    OVERLAY_LOOSENS,
                    f"the overlay at {overlay.layer} asks for precedent scope "
                    f"{proposed!r}, which no disposition declares "
                    f"(have: {', '.join(sorted(declared))}). Retrieval breadth is not "
                    f"something an overlay invents.",
                    locator=f"{overlay.layer} -> {overlay.target}",
                )
            )
        return proposed

    # -- templates

    def _bind_template(self, layers: tuple[str, ...]) -> TemplateBinding | None:
        """Deepest binding wins; a layer bound to nothing falls through.

        The same five-layer walk as the skills, which is the point: "Corporate Finance
        uses a different model" is a row in a registry rather than a branch in the code.
        """
        found: TemplateBinding | None = None
        for layer in layers:
            binding = self.bindings.get(layer)
            if binding is not None and binding.file:
                found = binding
        return found


# ------------------------------------------------------------------- helpers


def _reject_unknown_keys(overlay: Overlay) -> None:
    unknown_tighten = [k for k in overlay.tightens if k not in TIGHTENABLE]
    unknown_add = [k for k in overlay.adds if k not in ADDABLE]
    if unknown_tighten:
        raise RegistryError(
            diagnose(
                SKILL_INVALID,
                f"{', '.join(unknown_tighten)} is not a dimension an overlay may tighten "
                f"(have: {', '.join(TIGHTENABLE)})",
                locator=f"{overlay.layer} -> {overlay.target}",
            )
        )
    if unknown_add:
        raise RegistryError(
            diagnose(
                SKILL_INVALID,
                f"{', '.join(unknown_add)} is not something an overlay may add "
                f"(have: {', '.join(ADDABLE)})",
                locator=f"{overlay.layer} -> {overlay.target}",
            )
        )


def _tighten_tools(current: ResolvedSkill, overlay: Overlay) -> tuple[str, ...]:
    proposed = tuple(overlay.tightens["tools"])
    added = [t for t in proposed if t not in current.tools]
    if added:
        raise RegistryError(
            diagnose(
                OVERLAY_LOOSENS,
                f"the overlay at {overlay.layer} would give {current.name} "
                f"{', '.join(added)}. An overlay takes tools away; a skill that needs a "
                f"new tool needs a review, not a deeper folder.",
                locator=f"{overlay.layer} -> {overlay.target}",
            )
        )
    return proposed


def _explain(
    path: ScopePath,
    layers: tuple[str, ...],
    counts: list[tuple[str, int]],
    skills: tuple[ResolvedSkill, ...],
    overlays: tuple[Overlay, ...],
    template: TemplateBinding | None,
) -> tuple[str, ...]:
    """Why this answer. Read by the console, the manifest and whoever is confused."""
    lines = [
        f"{path} resolved to {len(skills)} skill(s) from "
        f"{len({r.layer for r in skills})} of {len(layers)} layer(s)."
    ]
    lines += [
        f"  {layer}: {count} skill(s)" + ("" if count else "  - declared, empty")
        for layer, count in counts
    ]

    empty_below_firm = [layer for layer, count in counts if layer != FIRM_LAYER and not count]
    if all(r.layer == FIRM_LAYER for r in skills) and not overlays:
        lines.append(
            f"{path.practice} resolves to the firm layer only: nothing is declared at "
            f"{', '.join(empty_below_firm)}. That is the honest state of a scaffolded "
            f"practice group, not a resolution failure - and it is said out loud so the "
            f"two are never confused."
        )
    if overlays:
        lines.append(
            f"{len(overlays)} overlay(s) in force: "
            + ", ".join(f"{o.layer} -> {o.target}" for o in overlays)
        )
    lines.append(
        f"template: {template.file} from {template.layer}"
        if template
        else "template: none bound at any layer in force"
    )
    return tuple(lines)


def _with_hash(result: ResolvedScope) -> ResolvedScope:
    """A content hash over everything resolution decided.

    Folded into plan_hash by P06, which is what makes "a run records the exact skill set
    it was allowed" true rather than aspirational: change a layer, an overlay or a
    template binding and every plan built on it is a different plan.
    """
    payload: dict[str, Any] = {
        "scopes_version": result.scopes_version,
        "scope": str(result.scope),
        "layers": list(result.layers),
        "precedent_scope": result.precedent_scope,
        "template": None
        if result.template is None
        else [result.template.layer, result.template.file, result.template.template_version],
        "skills": [
            {
                "name": r.name,
                "version": r.skill.version,
                "layer": r.layer,
                "hitl": r.hitl,
                "data_sensitivity": r.data_sensitivity,
                "tools": list(r.tools),
                "references": list(r.references),
                "output_contract": r.skill.output_contract,
                "overlays": [f"{o.layer}->{o.target}" for o in r.overlays],
                "precedent_scope": r.precedent_scope,
            }
            for r in result.skills
        ],
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = f"sha256:{hashlib.sha256(body).hexdigest()}"
    return ResolvedScope(**{**result.__dict__, "resolution_hash": digest})


def _read_bindings(path: Path) -> dict[str, TemplateBinding]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        b["layer"]: TemplateBinding(
            layer=b["layer"],
            file=b.get("file") or "",
            template_version=str(b.get("template_version") or ""),
            why=" ".join(str(b.get("why", "")).split()),
        )
        for b in raw.get("bindings") or ()
    }
