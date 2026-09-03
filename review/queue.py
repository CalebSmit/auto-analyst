"""The Review Queue: an inbox of items needing a decision - not an inbox of runs.

Each item carries its source excerpt, the proposal, the confidence and the reason it was
queued. Each has a named owner and a due time, from the engagement's Checkpoint Policy,
because "nobody works the queue" is the second-highest risk in the blueprint and it is
not technical: the SLA and the stall alert are the only defences the system itself can
offer.

The queue opens items. It never closes one - a decision does that, in `surface.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from ops.events import EventBus
from ops.models import now_iso
from ops.run_store import ReviewItemRecord, RunStore
from registries.errors import REVIEW_SLA_BREACH, diagnose
from review.policy import CheckpointPolicy
from review.router import Item, Route, Routing

__all__ = ["ReviewQueue"]

NODE = "review_queue"


class ReviewQueue:
    def __init__(
        self,
        store: RunStore,
        bus: EventBus,
        policy_for: Callable[[str], CheckpointPolicy],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.bus = bus
        self.policy_for = policy_for
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    # -- in

    def enqueue(
        self,
        run_id: str,
        engagement_id: str,
        item: Item,
        routing: Routing,
        *,
        step_id: str | None = None,
    ) -> ReviewItemRecord:
        """Open one item, with everything a reviewer needs and the proposal held back
        behind the surface's `reveal`. An auto-accepted routing is refused: the queue
        holds questions, and an auto-accept is not one."""
        if routing.route is Route.AUTO_ACCEPT:
            raise ValueError(f"{item.item_id} was auto-accepted; it is not a review item")
        policy = self.policy_for(engagement_id)
        due = self._clock() + timedelta(hours=policy.sla_hours)
        due_at = due.isoformat(timespec="seconds").replace("+00:00", "Z")
        kind = "blocking" if routing.route is Route.BLOCK else _kind_of(routing)
        self.store.open_review_item(
            run_id,
            item.item_id,
            kind,
            item.question,
            detail={
                "skill": item.skill,
                "source_excerpt": item.source_excerpt,
                "locator": item.locator,
                "proposal": item.proposal,
                "confidence": item.confidence,
                "reasons": list(routing.reasons),
                "route": str(routing.route),
                "effective_review": routing.effective_review,
                "severity": routing.severity,
                "step_id": step_id,
                "queued_at": now_iso(),
            },
            owner=policy.owner,
            due_at=due_at,
        )
        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type="hitl.item.queued",
            message=f"{item.skill}/{item.item_id}: {item.question}",
            level="warn",
            step_id=step_id,
            payload={
                "item_id": item.item_id,
                "kind": kind,
                "owner": policy.owner,
                "due_at": due_at,
                "reasons": list(routing.reasons),
            },
        )
        record = next(i for i in self.store.review_items(run_id) if i.item_id == item.item_id)
        return record

    # -- out

    def open_items(self, engagement_id: str | None = None) -> tuple[ReviewItemRecord, ...]:
        """Everything waiting on a person, oldest first, across runs."""
        return self.store.open_review_items(engagement_id)

    def overdue(self, engagement_id: str | None = None) -> tuple[ReviewItemRecord, ...]:
        now = self._clock()
        return tuple(
            item
            for item in self.open_items(engagement_id)
            if item.due_at and _parse(item.due_at) < now
        )

    def escalate_overdue(self, engagement_id: str | None = None) -> tuple[ReviewItemRecord, ...]:
        """Say so, to the named owner, for every item past its SLA. Escalation is a
        recorded event with a code and an owner; it does not decide the item and it does
        not touch the run."""
        late = self.overdue(engagement_id)
        for item in late:
            run = self.store.run(item.run_id)
            d = diagnose(
                REVIEW_SLA_BREACH,
                f"{item.item_id} has been open since {item.created_at}, due {item.due_at}; "
                f"owner {item.owner or 'unassigned'}",
                locator=f"{item.run_id}/{item.item_id}",
            )
            self.bus.emit(
                run_id=item.run_id,
                engagement_id=run.engagement_id,
                node_id=NODE,
                type="hitl.sla.breached",
                message=f"{item.item_id}: past its review SLA - escalated to {item.owner}",
                level="error",
                diagnostic_code=d.code,
                payload={
                    "item_id": item.item_id,
                    "owner": item.owner,
                    "due_at": item.due_at,
                    "created_at": item.created_at,
                    "what_now": d.what_now,
                    "diagnostic": d.as_dict(),
                },
            )
        return late


def _kind_of(routing: Routing) -> str:
    text = " ".join(routing.reasons)
    if text.startswith("material"):
        return "material"
    if "confidence" in text:
        return "below_threshold"
    if "prior year" in text:
        return "changed_from_prior"
    return "review_required"


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
