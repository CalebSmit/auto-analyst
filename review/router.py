"""The Confidence Router: decides what goes straight through and what a person sees.

Item-level, not run-level. An analyst approves eleven uncertain line-item tags out of
four hundred rather than approving "the run", which is the difference between review that
catches things and review that becomes a rubber stamp.

The one node that reads the Checkpoint Policy. Thresholds are configurable; the skill's
own declaration and the fails-closed guards are not - this node can add review, never
remove it. The rules, in the order they are applied, each with the reason it records:

1. A skill whose effective review level puts its whole output in front of a person
   (rank 30 and above on the ladder) **blocks**: the run stops at that step until the
   person has looked, because nothing downstream may build on an unseen result.
2. An item the skill itself marked `review_required` goes to **review**. Never lowered.
3. A **material** item goes to review, whatever its confidence.
4. An item in an always-review category, one that differs from the prior year, or one
   that binds future years goes to review - the constraint registry's own list.
5. An item with no confidence, or one below the engagement's auto-accept bar, goes to
   review. No bar set means no auto-accept.
6. Everything else is **auto-accepted** - and recorded as such, so the Sampling Audit can
   draw from what nobody was asked to look at.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ops.events import EventBus
from registries.scopes import ScopeRegistry
from review.policy import CheckpointPolicy, Money

__all__ = ["ConfidenceRouter", "Item", "Route", "Routing"]

NODE = "confidence_router"

# The rung from which a skill's whole output goes to a person, not selected items.
WHOLE_OUTPUT_RANK = 30


class Route(StrEnum):
    AUTO_ACCEPT = "auto_accept"
    REVIEW = "review"
    BLOCK = "block"


@dataclass(frozen=True)
class Item:
    """One thing a skill proposed, in the shape the router and the queue read.

    `source_excerpt` and `question` are what a reviewer sees first; `proposal` and
    `confidence` are what they see on request. The router never looks at the excerpt.
    """

    item_id: str
    skill: str
    question: str
    source_excerpt: str
    proposal: dict[str, Any]
    confidence: float | None = None
    amount: Money | None = None
    category: str | None = None
    review_required: bool = False
    changed_from_prior: bool = False
    binds_future_years: bool = False
    locator: str = ""


@dataclass(frozen=True)
class Routing:
    item_id: str
    route: Route
    reasons: tuple[str, ...] = ()
    effective_review: str = ""
    severity: str = "low"

    @property
    def needs_a_person(self) -> bool:
        return self.route is not Route.AUTO_ACCEPT


class ConfidenceRouter:
    def __init__(
        self,
        policy: CheckpointPolicy,
        scopes: ScopeRegistry | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self.policy = policy
        self.scopes = scopes or ScopeRegistry.load()
        self.bus = bus

    def route(
        self,
        item: Item,
        declared_hitl: str,
        *,
        run_id: str = "",
        engagement_id: str = "",
        step_id: str | None = None,
    ) -> Routing:
        """Where this item goes. `declared_hitl` is the skill's own value after its
        scope overlays - the floor this node may raise and never lower."""
        level = self.policy.effective_review(item.skill, declared_hitl, self.scopes)
        rank = self.scopes.review_rank(level)
        reasons: list[str] = []

        if rank >= WHOLE_OUTPUT_RANK:
            reasons.append(f"{item.skill} declares {level}: the whole output goes to a person")
            routing = Routing(item.item_id, Route.BLOCK, tuple(reasons), level, "high")
            return self._record(routing, item, run_id, engagement_id, step_id)

        if item.review_required:
            reasons.append(f"{item.skill} marked this item review_required")
        if self.policy.is_material(item.amount):
            assert item.amount is not None
            reasons.append(
                f"material: {item.amount.amount:,.0f} {item.amount.currency} is at or above "
                f"the engagement threshold of {self.policy.materiality.amount:,.0f} "
                f"{self.policy.materiality.currency}"
            )
        if item.category and item.category in self.policy.always_review_categories:
            reasons.append(f"category {item.category!r} is always reviewed on this engagement")
        if item.changed_from_prior:
            reasons.append("differs from the prior year")
        if item.binds_future_years:
            reasons.append("binds future years")
        if item.confidence is None:
            reasons.append("no confidence stated")
        elif self.policy.auto_accept_confidence is None:
            reasons.append("no auto-accept bar is set for this engagement")
        elif item.confidence < self.policy.auto_accept_confidence:
            reasons.append(
                f"confidence {item.confidence:.2f} is below the bar of "
                f"{self.policy.auto_accept_confidence:.2f}"
            )

        if reasons:
            severity = "high" if any(r.startswith("material") for r in reasons) else "med"
            routing = Routing(item.item_id, Route.REVIEW, tuple(reasons), level, severity)
        else:
            routing = Routing(item.item_id, Route.AUTO_ACCEPT, (), level, "low")
        return self._record(routing, item, run_id, engagement_id, step_id)

    def route_all(self, items: list[Item], declared_hitl: str, **where: Any) -> tuple[Routing, ...]:
        return tuple(self.route(item, declared_hitl, **where) for item in items)

    # -- the record

    def _record(
        self,
        routing: Routing,
        item: Item,
        run_id: str,
        engagement_id: str,
        step_id: str | None,
    ) -> Routing:
        if self.bus is None or not run_id:
            return routing
        auto = routing.route is Route.AUTO_ACCEPT
        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type="hitl.item.auto_accepted" if auto else "hitl.item.routed",
            message=(
                f"{item.skill}/{item.item_id}: {routing.route}"
                + (f" - {'; '.join(routing.reasons)}" if routing.reasons else "")
            ),
            level="info" if auto else "warn",
            step_id=step_id,
            payload={
                "item_id": item.item_id,
                "skill": item.skill,
                "route": str(routing.route),
                "reasons": list(routing.reasons),
                "effective_review": routing.effective_review,
                "confidence": item.confidence,
                "locator": item.locator,
            },
        )
        return routing
