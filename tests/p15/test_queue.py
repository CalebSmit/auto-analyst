"""The Review Queue: an inbox of items with an SLA and a named owner."""

from __future__ import annotations

import pytest

from ops.run_store import SqlRunStore
from review import ConfidenceRouter, Money, ReviewQueue, Route, Routing
from tests.p15.conftest import (
    DECLARED,
    EBITDA,
    ENGAGEMENT,
    OWNER,
    SLA_HOURS,
    TAGGING,
    Clock,
    events_of,
    item,
    start,
)


def test_an_item_lands_with_its_owner_and_due_time(
    queue: ReviewQueue, router: ConfidenceRouter, started: str, store: SqlRunStore
) -> None:
    it = item()
    record = queue.enqueue(started, ENGAGEMENT, it, router.route(it, DECLARED[TAGGING]))

    assert record.state == "open" and record.version == 1
    assert record.owner == OWNER
    assert record.due_at == "2026-09-05T09:00:00Z", "T0 plus the 48-hour SLA"
    assert record.kind == "below_threshold"
    assert record.subject == it.question
    assert record.detail["source_excerpt"] == it.source_excerpt
    assert record.detail["proposal"] == it.proposal and record.detail["confidence"] == 0.61
    assert record.detail["reasons"][0].startswith("confidence 0.61 is below")
    queued = events_of(store, started, "hitl.item.queued")
    assert len(queued) == 1 and queued[0].payload["owner"] == OWNER


def test_an_auto_accepted_item_is_not_a_review_item(queue: ReviewQueue, started: str) -> None:
    with pytest.raises(ValueError, match="auto-accepted"):
        queue.enqueue(started, ENGAGEMENT, item(), Routing("li_118", Route.AUTO_ACCEPT))


def test_the_kind_says_why(queue: ReviewQueue, router: ConfidenceRouter, started: str) -> None:
    material = item("ab_1", EBITDA, confidence=0.99, amount=Money(50000, "USD"))
    blocking = item("qc_1", "qc-tieout", confidence=0.9)
    assert (
        queue.enqueue(started, ENGAGEMENT, material, router.route(material, DECLARED[EBITDA])).kind
        == "material"
    )
    assert (
        queue.enqueue(
            started, ENGAGEMENT, blocking, router.route(blocking, DECLARED["qc-tieout"])
        ).kind
        == "blocking"
    )


def test_the_inbox_is_of_items_not_runs(
    queue: ReviewQueue, router: ConfidenceRouter, started: str, store: SqlRunStore, plan
) -> None:
    for n in range(3):
        it = item(f"li_{n}")
        queue.enqueue(started, ENGAGEMENT, it, router.route(it, DECLARED[TAGGING]))
    other = start(store, plan, run_id="run_other")
    it = item("li_x")
    queue.enqueue(other, ENGAGEMENT, it, router.route(it, DECLARED[TAGGING]))

    inbox = queue.open_items(ENGAGEMENT)
    assert [(i.run_id, i.item_id) for i in inbox] == [
        (started, "li_0"),
        (started, "li_1"),
        (started, "li_2"),
        (other, "li_x"),
    ]
    assert queue.open_items("OTHER-ENGAGEMENT") == ()


def test_overdue_and_escalation_to_the_named_owner(
    queue: ReviewQueue, router: ConfidenceRouter, started: str, store: SqlRunStore, clock: Clock
) -> None:
    it = item()
    queue.enqueue(started, ENGAGEMENT, it, router.route(it, DECLARED[TAGGING]))
    assert queue.overdue() == ()
    clock.advance(SLA_HOURS - 0.01)
    assert queue.overdue() == ()
    clock.advance(0.02)
    late = queue.escalate_overdue()

    assert [i.item_id for i in late] == ["li_118"]
    breached = events_of(store, started, "hitl.sla.breached")
    assert len(breached) == 1
    assert breached[0].diagnostic_code == "PROCESS.REVIEW_SLA_BREACH"
    assert breached[0].payload["owner"] == OWNER
    assert breached[0].payload["what_now"]
    assert store.review_items(started)[0].state == "open", "escalation decides nothing"


def test_the_queue_has_no_way_to_close_an_item() -> None:
    for forbidden in ("decide", "close", "resolve", "approve", "accept"):
        assert not any(forbidden in name for name in dir(ReviewQueue)), forbidden
