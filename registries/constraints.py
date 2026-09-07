"""The Constraint Registry: load the predicates, pin the version, refuse the rest.

Contracts say what shapes are legal; constraints say what actions are legal. This
module loads and pins `constraints/constraints.yaml` and answers structural questions
about it — which tools a skill declared, what a loop's ceiling is, what the firm
materiality floor is.

It deliberately does not *evaluate* anything. The Policy Gate decides and the Guarded
Tool Runtime enforces, and both arrive in P10. Splitting the decision from its data is
what lets the gate be tested against a table of proposed actions with no tools present.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from registries.errors import UNKNOWN_CONSTRAINTS, RegistryError, diagnose

REPO_ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS_FILE = REPO_ROOT / "constraints" / "constraints.yaml"

IN_RUN = "in_run"


@dataclass(frozen=True)
class ToolSpec:
    """One name in the tool namespace, and the caps that apply at call time."""

    name: str
    kind: str
    node: str
    read_only: bool
    caps: dict[str, Any]

    @property
    def computes(self) -> bool:
        return self.kind == "computes"


@dataclass(frozen=True)
class Predicate:
    """One rule the Policy Gate evaluates against a proposed action's arguments."""

    id: str
    applies_to: tuple[str, ...]
    rule: str
    diagnostic: str
    why: str = ""


@dataclass(frozen=True)
class LoopSpec:
    """A declared loop and its integer ceiling. The compiler rejects any cycle that is
    not one of these, which is what stops an agent deciding for itself to try again."""

    name: str
    scope: str
    max_iterations: int | None


class ConstraintRegistry:
    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self.version: str = raw["version"]
        self.tools: dict[str, ToolSpec] = {
            name: ToolSpec(
                name=name,
                kind=spec["kind"],
                node=spec["node"],
                read_only=spec["read_only"],
                caps=dict(spec.get("caps") or {}),
            )
            for name, spec in raw["tools"].items()
        }
        self.tool_allowlists: dict[str, tuple[str, ...]] = {
            skill: tuple(tools) for skill, tools in raw["tool_allowlists"].items()
        }
        self.predicates: tuple[Predicate, ...] = tuple(
            Predicate(
                id=p["id"],
                applies_to=tuple(p["applies_to"]),
                rule=p["rule"],
                diagnostic=p["diagnostic"],
                why=p.get("why", ""),
            )
            for p in raw["predicates"]
        )
        self.loops: dict[str, LoopSpec] = {
            name: LoopSpec(name=name, scope=spec["scope"], max_iterations=spec["max_iterations"])
            for name, spec in raw["loops"].items()
        }
        self.rules: tuple[str, ...] = tuple(raw.get("rules") or ())
        self.ceilings: dict[str, Any] = raw["ceilings"]
        self.materiality: dict[str, Any] = raw["materiality"]
        self.immutability: dict[str, Any] = raw["immutability"]

    @classmethod
    def load(cls, path: Path = CONSTRAINTS_FILE) -> ConstraintRegistry:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        registry = cls(raw)
        registry._self_check()
        return registry

    def require_version(self, expected: str) -> None:
        """A run pins the constraint version it compiled against. A different one is a
        refusal, not a shrug — the plan hash was computed over these predicates."""
        if expected != self.version:
            raise RegistryError(
                diagnose(
                    UNKNOWN_CONSTRAINTS,
                    f"run pinned constraints {expected}, registry is {self.version}",
                )
            )

    # ------------------------------------------------------------------ questions

    def tools_for(self, skill: str) -> tuple[str, ...]:
        if skill not in self.tool_allowlists:
            raise RegistryError(
                diagnose(UNKNOWN_CONSTRAINTS, f"{skill!r} has no declared tool allowlist")
            )
        return self.tool_allowlists[skill]

    def may_call(self, skill: str, tool: str) -> bool:
        """Structural check only. The Policy Gate still has three more questions to ask."""
        return tool in self.tool_allowlists.get(skill, ())

    def skills_using(self, tool: str) -> tuple[str, ...]:
        return tuple(sorted(s for s, tools in self.tool_allowlists.items() if tool in tools))

    def in_run_loops(self) -> tuple[LoopSpec, ...]:
        """The only loops that are cycles in a plan graph, and so the only ones the
        compiler's bounded-loop assertion applies to."""
        return tuple(loop for loop in self.loops.values() if loop.scope == IN_RUN)

    def loop_ceiling(self) -> int:
        return int(self.ceilings["per_run"]["loop_iterations_max"])

    def methodology_ceiling(self) -> int:
        """Bytes of methodology one layer may add to every prompt that walks through it."""
        return int(self.ceilings["per_methodology_layer"]["bytes_max"])

    def materiality_floor(self) -> tuple[float, str]:
        floor = self.materiality["firm_floor"]
        return float(floor["amount"]), str(floor["currency"])

    # ------------------------------------------------------------------ integrity

    def _self_check(self) -> None:
        for skill, tools in self.tool_allowlists.items():
            for tool in tools:
                if tool not in self.tools:
                    raise RegistryError(
                        diagnose(
                            UNKNOWN_CONSTRAINTS,
                            f"{skill} declares {tool!r}, which is not in the tool namespace",
                        )
                    )
        for predicate in self.predicates:
            for target in predicate.applies_to:
                if target != "all" and target not in self.tools:
                    raise RegistryError(
                        diagnose(
                            UNKNOWN_CONSTRAINTS,
                            f"predicate {predicate.id} applies to unknown tool {target!r}",
                        )
                    )
        for loop in self.in_run_loops():
            if not isinstance(loop.max_iterations, int) or loop.max_iterations < 1:
                raise RegistryError(
                    diagnose(
                        UNKNOWN_CONSTRAINTS,
                        f"in-run loop {loop.name!r} has no integer maximum the compiler can check",
                    )
                )
