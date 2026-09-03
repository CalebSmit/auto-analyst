"""The Decision Log: who decided what, when, and why.

An append-only record of every human decision - item, decision, reason, reviewer,
timestamp, and the model proposal that was accepted or overridden. Written into the run
manifest at the end of the run.

Two audiences. A reviewer six months later asking why a line was treated a particular
way, and the system itself: an override rate that climbs on one skill is the clearest
possible signal that the skill needs work, and it is what the Drift Monitor reads.

The table itself is append-only three ways, like the event table: the API has no update,
the ORM refuses a flush that modifies a decision, and the database has triggers. This
module is the read side.
"""

from __future__ import annotations

from dataclasses import dataclass

from ops.models import DecisionKind
from ops.run_store import DecisionRecord, RunStore

__all__ = ["DecisionLog", "OverrideRate"]

OVERRIDES = frozenset({DecisionKind.CORRECTED, DecisionKind.REJECTED})


@dataclass(frozen=True)
class OverrideRate:
    skill: str
    decided: int
    overridden: int

    @property
    def rate(self) -> float:
        return 0.0 if self.decided == 0 else self.overridden / self.decided


class DecisionLog:
    def __init__(self, store: RunStore) -> None:
        self.store = store

    def entries(self, run_id: str) -> tuple[DecisionRecord, ...]:
        return self.store.decisions(run_id)

    def for_item(self, run_id: str, item_id: str) -> DecisionRecord | None:
        return next((d for d in self.entries(run_id) if d.item_id == item_id), None)

    def override_rate(self, run_id: str, skill: str | None = None) -> OverrideRate:
        """Corrected or rejected, over everything decided - per skill or overall."""
        decided = [d for d in self.entries(run_id) if skill is None or d.skill == skill]
        return OverrideRate(
            skill=skill or "*",
            decided=len(decided),
            overridden=sum(1 for d in decided if d.decision in OVERRIDES),
        )

    def precedent_candidates(self, run_id: str) -> tuple[DecisionRecord, ...]:
        """The only decisions that may ever reach the Precedent Store: a person's
        accept or correction. P19 reads this; nothing else writes precedent."""
        return tuple(d for d in self.entries(run_id) if d.writes_precedent)
