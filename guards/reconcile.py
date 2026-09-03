"""Reconciliation & Conflict Surfacing: where two skills disagree, say so.

Collates outputs across skills and surfaces contradictions: a line item categorised
differently by two skills, a figure two outputs state differently for the same period, a
period present in one and absent from another. Deterministic set comparison over
structured outputs; emits a conflict list with both positions and their sources.

Conflicts route to review. They are never auto-resolved by preferring the later writer,
because "the later writer" is an accident of scheduling and not a reason.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from guards import GuardResult, figures_in, report
from ops.events import EventBus
from registries.errors import RECONCILE_CONFLICT

__all__ = ["Conflict", "Position", "Reconcile"]


@dataclass(frozen=True)
class Position:
    """One skill's claim about one thing."""

    skill: str
    claim: str
    source_id: str = ""
    locator: str = ""


@dataclass(frozen=True)
class Conflict:
    """Two or more positions on one subject that cannot all be right."""

    subject: str
    kind: str
    positions: tuple[Position, ...] = field(default_factory=tuple)


class Reconcile:
    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus

    def check(self, outputs: Mapping[str, Any]) -> GuardResult:
        """`outputs` is skill name to that skill's output. Three comparisons, all sets."""
        conflicts: list[Conflict] = []
        conflicts += _category_conflicts(outputs)
        conflicts += _figure_conflicts(outputs)
        conflicts += _period_conflicts(outputs)
        checked = sum(1 for _ in _subjects(outputs))
        return GuardResult(
            guard="reconcile",
            passed=not conflicts,
            checked=checked,
            failed=len(conflicts),
            code=RECONCILE_CONFLICT if conflicts else None,
            reasons=tuple(
                f"{c.kind} on {c.subject}: "
                + " vs ".join(f"{p.skill}={p.claim}" for p in c.positions)
                for c in conflicts
            ),
            detail={
                "conflicts": [
                    {
                        "subject": c.subject,
                        "kind": c.kind,
                        "positions": [
                            {
                                "skill": p.skill,
                                "claim": p.claim,
                                "source_id": p.source_id,
                                "locator": p.locator,
                            }
                            for p in c.positions
                        ],
                    }
                    for c in conflicts
                ]
            },
        )

    def run(
        self,
        outputs: Mapping[str, Any],
        run_id: str,
        engagement_id: str,
        step_id: str | None = None,
    ) -> GuardResult:
        return report(self.bus, self.check(outputs), "reconcile", run_id, engagement_id, step_id)


# ------------------------------------------------------------ comparisons


def _tagged_items(output: Any) -> dict[str, str]:
    """line_item_ref -> category, wherever an output carries both."""
    found: dict[str, str] = {}
    for item in _objects(output):
        ref = item.get("line_item_ref") or item.get("line_item_id")
        category = item.get("category")
        if isinstance(ref, str) and isinstance(category, str):
            found[ref] = category
    return found


def _category_conflicts(outputs: Mapping[str, Any]) -> list[Conflict]:
    by_ref: dict[str, list[Position]] = {}
    for skill, output in outputs.items():
        for ref, category in _tagged_items(output).items():
            by_ref.setdefault(ref, []).append(Position(skill=skill, claim=category))
    return [
        Conflict(subject=ref, kind="category", positions=tuple(positions))
        for ref, positions in sorted(by_ref.items())
        if len({p.claim for p in positions}) > 1
    ]


def _figure_conflicts(outputs: Mapping[str, Any]) -> list[Conflict]:
    """The same source, locator and period, stated as different values."""
    by_key: dict[tuple[str, str, str], list[Position]] = {}
    for skill, output in outputs.items():
        for _, figure in figures_in(output):
            period = figure.get("period") or {}
            key = (
                figure["source_id"],
                figure["locator"],
                f"{period.get('type')}:{period.get('end')}",
            )
            by_key.setdefault(key, []).append(
                Position(
                    skill=skill,
                    claim=f"{float(figure['value']):g}",
                    source_id=figure["source_id"],
                    locator=figure["locator"],
                )
            )
    return [
        Conflict(subject=f"{locator} @ {period}", kind="figure", positions=tuple(positions))
        for (_, locator, period), positions in sorted(by_key.items())
        if len({p.claim for p in positions}) > 1
    ]


def _period_conflicts(outputs: Mapping[str, Any]) -> list[Conflict]:
    """A period one output covers and another, covering the same source, does not."""
    covered: dict[str, dict[str, set[str]]] = {}
    for skill, output in outputs.items():
        for _, figure in figures_in(output):
            period = figure.get("period") or {}
            covered.setdefault(figure["source_id"], {}).setdefault(skill, set()).add(
                f"{period.get('type')}:{period.get('end')}"
            )
    conflicts: list[Conflict] = []
    for source_id, by_skill in sorted(covered.items()):
        if len(by_skill) < 2:
            continue
        union = set().union(*by_skill.values())
        for period in sorted(union):
            have = [s for s, periods in by_skill.items() if period in periods]
            lack = [s for s in by_skill if s not in have]
            if lack:
                conflicts.append(
                    Conflict(
                        subject=f"{source_id[:19]}... @ {period}",
                        kind="period",
                        positions=tuple(
                            [Position(skill=s, claim="present") for s in sorted(have)]
                            + [Position(skill=s, claim="absent") for s in sorted(lack)]
                        ),
                    )
                )
    return conflicts


def _objects(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(value, dict):
        out.append(value)
        for inner in value.values():
            out.extend(_objects(inner))
    elif isinstance(value, list):
        for inner in value:
            out.extend(_objects(inner))
    return out


def _subjects(outputs: Mapping[str, Any]) -> set[str]:
    subjects: set[str] = set()
    for output in outputs.values():
        subjects.update(_tagged_items(output))
        subjects.update(f"{f['source_id']}:{f['locator']}" for _, f in figures_in(output))
    return subjects
