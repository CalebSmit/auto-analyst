"""The Scope Registry: the declared taxonomy, and what "tighter" means.

Two jobs, and the second one is the load-bearing half.

**Validate a scope path.** An engagement scoped to a practice group nobody declared
fails here, at the start of a run, rather than resolving to an empty skill set that
looks like a considered answer. The taxonomy is declarative rather than implicit in
folder names precisely so this check can exist.

**Rank the two dimensions an overlay may tighten.** "An overlay may only tighten" is
only enforceable if tighter is defined, so `review_ladder` and `sensitivity_ladder` in
scopes.yaml give every value an integer rank. Comparing the strings instead would work
right up until somebody adds a value, which is the moment the check is needed. Placing
a new value on the ladder is a decision, and it should look like one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from registries.errors import (
    UNKNOWN_DISPOSITION,
    UNKNOWN_PRACTICE,
    UNKNOWN_REVIEW_LEVEL,
    UNKNOWN_SEGMENT,
    UNRESOLVED_SCOPE,
    RegistryError,
    diagnose,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCOPES_FILE = REPO_ROOT / "scope" / "scopes.yaml"

__all__ = [
    "Disposition",
    "Practice",
    "ScopePath",
    "ScopeRegistry",
    "Segment",
]


@dataclass(frozen=True)
class Segment:
    id: str
    name: str
    defined: bool = False
    parked: bool = False
    """Kept and tested, but not where the work is pointed today. A label, not a gate:
    a parked segment still resolves, and an engagement may still be scoped into it."""


@dataclass(frozen=True)
class Practice:
    id: str
    name: str
    defined: bool
    segments: tuple[Segment, ...]
    note: str = ""

    def segment(self, segment_id: str) -> Segment | None:
        return next((s for s in self.segments if s.id == segment_id), None)


@dataclass(frozen=True)
class Disposition:
    id: str
    name: str
    precedent_scope: str
    note: str = ""


@dataclass(frozen=True)
class ScopePath:
    """practice / segment / disposition. The whole of what an engagement declares."""

    practice: str
    segment: str
    disposition: str

    def __str__(self) -> str:
        return f"{self.practice}/{self.segment}/{self.disposition}"

    @classmethod
    def parse(cls, path: str) -> ScopePath:
        parts = path.strip().split("/")
        if len(parts) != 3 or not all(parts):
            raise RegistryError(
                diagnose(
                    UNRESOLVED_SCOPE,
                    f"{path!r} is not a scope path; it reads practice/segment/disposition",
                    locator=path,
                )
            )
        return cls(*parts)


class ScopeRegistry:
    """scopes.yaml, loaded and answerable."""

    def __init__(
        self,
        version: str,
        layer_order: tuple[str, ...],
        practices: tuple[Practice, ...],
        dispositions: tuple[Disposition, ...],
        review_ranks: dict[str, int],
        sensitivity_ranks: dict[str, int],
        source: Path = SCOPES_FILE,
        focus: tuple[str, str] | None = None,
    ) -> None:
        self.source = source
        self.focus = focus
        """(practice, segment) the build and the dashboards are pointed at, or None."""
        self.version = version
        self.layer_order = layer_order
        self.practices = practices
        self.dispositions = dispositions
        self.review_ranks = review_ranks
        self.sensitivity_ranks = sensitivity_ranks

    @classmethod
    def load(cls, scopes_file: Path = SCOPES_FILE) -> ScopeRegistry:
        raw = _read(scopes_file)
        practices = tuple(
            Practice(
                id=p["id"],
                name=p["name"],
                defined=bool(p.get("defined", False)),
                note=p.get("note", ""),
                segments=tuple(
                    Segment(
                        id=s["id"],
                        name=s["name"],
                        defined=bool(s.get("defined", False)),
                        parked=bool(s.get("parked", False)),
                    )
                    for s in p.get("segments", [])
                ),
            )
            for p in raw["practices"]
        )
        dispositions = tuple(
            Disposition(
                id=d["id"],
                name=d["name"],
                precedent_scope=d["precedent_scope"],
                note=d.get("note", ""),
            )
            for d in raw["dispositions"]
        )
        focus_raw = raw.get("focus")
        focus = (
            (str(focus_raw["practice"]), str(focus_raw["segment"]))
            if isinstance(focus_raw, dict)
            else None
        )
        registry = cls(
            focus=focus,
            version=str(raw["version"]),
            layer_order=tuple(raw["layer_order"]),
            practices=practices,
            dispositions=dispositions,
            review_ranks={r["value"]: int(r["rank"]) for r in raw["review_ladder"]},
            sensitivity_ranks={r["value"]: int(r["rank"]) for r in raw["sensitivity_ladder"]},
            source=scopes_file,
        )
        registry.self_check()
        return registry

    # -- the taxonomy

    def practice(self, practice_id: str) -> Practice:
        found = next((p for p in self.practices if p.id == practice_id), None)
        if found is None:
            raise RegistryError(
                diagnose(
                    UNKNOWN_PRACTICE,
                    f"{practice_id!r} is not a declared practice group "
                    f"(have: {', '.join(p.id for p in self.practices)})",
                    locator=practice_id,
                )
            )
        return found

    def disposition(self, disposition_id: str) -> Disposition:
        found = next((d for d in self.dispositions if d.id == disposition_id), None)
        if found is None:
            raise RegistryError(
                diagnose(
                    UNKNOWN_DISPOSITION,
                    f"{disposition_id!r} is not a declared client disposition "
                    f"(have: {', '.join(d.id for d in self.dispositions)})",
                    locator=disposition_id,
                )
            )
        return found

    def validate(self, scope: ScopePath) -> None:
        """Every part of the path exists. Called before anything resolves."""
        practice = self.practice(scope.practice)
        self.disposition(scope.disposition)
        if practice.segment(scope.segment) is None:
            raise RegistryError(
                diagnose(
                    UNKNOWN_SEGMENT,
                    f"{scope.segment!r} is not a segment of {practice.id} "
                    f"(have: {', '.join(s.id for s in practice.segments)})",
                    locator=str(scope),
                )
            )

    def combinations(self) -> tuple[ScopePath, ...]:
        """Every scope path the declared taxonomy admits.

        The cross product, in declaration order. Used by preflight and by the tests: a
        combination that resolves to nothing is a gap somebody should have to look at,
        not something discovered when an engagement is scoped into it.
        """
        return tuple(
            ScopePath(practice.id, segment.id, disposition.id)
            for practice in self.practices
            for segment in practice.segments
            for disposition in self.dispositions
        )

    def in_focus(self, scope: ScopePath) -> bool:
        """Whether a path sits in the declared focus. False when nothing is declared."""
        return self.focus == (scope.practice, scope.segment)

    def layers_for(self, scope: ScopePath) -> tuple[str, ...]:
        """The five layers, shallowest first. The one place the order is expanded."""
        self.validate(scope)
        return tuple(
            layer.format(
                practice=scope.practice,
                segment=scope.segment,
                disposition=scope.disposition,
            )
            for layer in self.layer_order
        )

    # -- the ladders

    def review_rank(self, value: str) -> int:
        if value not in self.review_ranks:
            raise RegistryError(
                diagnose(
                    UNKNOWN_REVIEW_LEVEL,
                    f"{value!r} is not on the review ladder in scopes.yaml. Place it "
                    f"deliberately - an unranked review level cannot be compared, and "
                    f"an overlay that cannot be compared cannot be refused.",
                    locator=value,
                )
            )
        return self.review_ranks[value]

    def sensitivity_rank(self, value: str) -> int:
        if value not in self.sensitivity_ranks:
            raise RegistryError(
                diagnose(
                    UNKNOWN_REVIEW_LEVEL,
                    f"{value!r} is not on the sensitivity ladder in scopes.yaml "
                    f"(have: {', '.join(sorted(self.sensitivity_ranks))})",
                    locator=value,
                )
            )
        return self.sensitivity_ranks[value]

    # -- internals

    def self_check(self) -> None:
        """Everything about scopes.yaml that has to hold before it is worth reading."""
        problems: list[str] = []
        if not self.layer_order:
            problems.append("layer_order is empty")
        if self.layer_order and self.layer_order[0] != "_firm":
            problems.append("layer_order must start at _firm - the firm layer is the floor")
        for field in ("{practice}", "{segment}", "{disposition}"):
            if not any(field in layer for layer in self.layer_order):
                problems.append(f"no layer in layer_order uses {field}")
        if not self.practices:
            problems.append("no practice groups declared")
        if not self.dispositions:
            problems.append("no client dispositions declared")
        for practice in self.practices:
            if not practice.segments:
                problems.append(f"{practice.id} declares no segments, not even a placeholder")
        if self.focus is not None:
            practice_id, segment_id = self.focus
            declared = next((p for p in self.practices if p.id == practice_id), None)
            segment = declared.segment(segment_id) if declared else None
            if segment is None:
                problems.append(f"focus names {practice_id}/{segment_id}, which is not declared")
            elif segment.parked:
                problems.append(f"focus names {practice_id}/{segment_id}, which is parked")
        for name, ranks in (
            ("review_ladder", self.review_ranks),
            ("sensitivity_ladder", self.sensitivity_ranks),
        ):
            if len(set(ranks.values())) < 2:
                problems.append(f"{name} has no distinct ranks, so nothing can tighten")
        if problems:
            raise RegistryError(
                diagnose(
                    UNRESOLVED_SCOPE,
                    "; ".join(problems),
                    locator=str(self.source),
                )
            )


def _read(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RegistryError(
            diagnose(UNRESOLVED_SCOPE, str(exc), locator=str(path))
        ) from exc
    if not isinstance(loaded, dict):
        raise RegistryError(
            diagnose(UNRESOLVED_SCOPE, "scopes.yaml is not a mapping", locator=str(path))
        )
    return loaded
