"""The Review Surface: source and question first, one decision per item, the run resumes."""

from __future__ import annotations

import dataclasses

import pytest

from graph.compile import CompiledGraph
from graph.execute import StepExecutor
from ops.blobs import LocalContentStore
from ops.models import DecisionKind, RunState
from ops.run_store import SqlRunStore
from ports.queue import Job
from ports.queue.in_process import InProcessQueue
from review import ConfidenceRouter, ReviewQueue, ReviewRefused, ReviewSurface, StaleDecision
from review.surface import RESUME_JOB, View
from tests.p15.conftest import (
    CONTEXT_REF,
    DECLARED,
    ENGAGEMENT,
    TAGGING,
    Blocks,
    Recorder,
    events_of,
    item,
)


@pytest.fixture
def queued(queue: ReviewQueue, router: ConfidenceRouter, started: str) -> str:
    it = item()
    queue.enqueue(started, ENGAGEMENT, it, router.route(it, DECLARED[TAGGING]))
    return it.item_id


# ------------------------------------------------------------ reading order


def test_show_gives_the_source_and_the_question_and_not_the_answer(
    surface: ReviewSurface, started: str, queued: str
) -> None:
    view = surface.show(started, queued)
    assert view.question == "Prof fees - Q3 special: category?"
    assert view.source_excerpt.startswith("Professional fees")
    assert view.locator == "TB_FY24!A118" and view.version == 1
    fields = {f.name for f in dataclasses.fields(View)}
    assert "proposal" not in fields and "confidence" not in fields


def test_reveal_is_a_second_click_and_is_recorded(
    surface: ReviewSurface, started: str, queued: str, store: SqlRunStore
) -> None:
    shown = surface.reveal(started, queued, viewer="Dana Whitfield")
    assert shown.proposal["category"] == "non_recurring" and shown.confidence == 0.61
    revealed = events_of(store, started, "hitl.proposal.revealed")
    assert len(revealed) == 1 and revealed[0].payload["viewer"] == "Dana Whitfield"


# --------------------------------------------------------------- deciding


def test_an_accept_closes_the_item_and_may_write_precedent(
    surface: ReviewSurface, started: str, queued: str, store: SqlRunStore
) -> None:
    record = surface.decide(
        started,
        queued,
        decided_by="Dana Whitfield",
        decision=DecisionKind.ACCEPTED,
        expected_version=1,
    )
    assert record.decision is DecisionKind.ACCEPTED and record.writes_precedent
    assert record.proposal["category"] == "non_recurring" and record.skill == TAGGING
    (after,) = store.review_items(started)
    assert after.state == "decided" and after.version == 2
    assert (
        events_of(store, started, "hitl.item.decided")[0].payload["decided_by"] == "Dana Whitfield"
    )


def test_an_edit_needs_a_reason_and_a_value(
    surface: ReviewSurface, started: str, queued: str
) -> None:
    with pytest.raises(ReviewRefused) as refused:
        surface.decide(
            started,
            queued,
            decided_by="Dana Whitfield",
            decision=DecisionKind.CORRECTED,
            expected_version=1,
            answer={"category": "recurring"},
        )
    assert refused.value.diagnostic.code == "PROCESS.RATIONALE_REQUIRED"
    with pytest.raises(ReviewRefused, match="corrected value"):
        surface.decide(
            started,
            queued,
            decided_by="Dana Whitfield",
            decision=DecisionKind.CORRECTED,
            expected_version=1,
            rationale="It recurs every Q3.",
        )
    record = surface.decide(
        started,
        queued,
        decided_by="Dana Whitfield",
        decision=DecisionKind.CORRECTED,
        expected_version=1,
        rationale="It recurs every Q3.",
        answer={"category": "recurring"},
    )
    assert record.answer == {"category": "recurring"} and record.writes_precedent


def test_a_rejection_needs_a_reason_and_writes_no_precedent(
    surface: ReviewSurface, started: str, queued: str
) -> None:
    with pytest.raises(ReviewRefused):
        surface.decide(
            started,
            queued,
            decided_by="Dana Whitfield",
            decision=DecisionKind.REJECTED,
            expected_version=1,
        )
    record = surface.decide(
        started,
        queued,
        decided_by="Dana Whitfield",
        decision=DecisionKind.REJECTED,
        expected_version=1,
        rationale="Not a line item at all - it is a subtotal.",
    )
    assert not record.writes_precedent


def test_the_second_reviewer_sees_the_firsts_decision_rather_than_overwriting_it(
    surface: ReviewSurface, started: str, queued: str, store: SqlRunStore
) -> None:
    """The exit criterion. Both reviewers opened the item at version 1. The first
    decides; the second's decision is refused with the first's attached, and the log
    holds exactly one decision."""
    surface.decide(
        started,
        queued,
        decided_by="Dana Whitfield",
        decision=DecisionKind.ACCEPTED,
        expected_version=1,
    )
    with pytest.raises(StaleDecision) as stale:
        surface.decide(
            started,
            queued,
            decided_by="Marcus Oyelaran",
            decision=DecisionKind.REJECTED,
            expected_version=1,
            rationale="Disagree - this is capex.",
        )
    assert stale.value.diagnostic.code == "PROCESS.STALE_DECISION"
    assert stale.value.existing is not None
    assert stale.value.existing.decided_by == "Dana Whitfield"
    assert stale.value.existing.decision is DecisionKind.ACCEPTED
    assert stale.value.version == 2
    assert "Dana Whitfield recorded accepted" in stale.value.diagnostic.detail
    decisions = store.decisions(started)
    assert len(decisions) == 1 and decisions[0].decided_by == "Dana Whitfield"


def test_the_lock_holds_at_the_store_even_without_the_surface(
    store: SqlRunStore, started: str, queued: str
) -> None:
    from registries.errors import DiagnosticError

    with pytest.raises(DiagnosticError) as refused:
        store.record_decision(
            started, queued, decided_by="x", decision=DecisionKind.ACCEPTED, expected_version=7
        )
    assert refused.value.diagnostic.code == "PROCESS.STALE_DECISION"
    assert store.decisions(started) == ()


# ---------------------------------------------------------------- resuming


def test_a_recorded_decision_reenqueues_the_waiting_run_at_its_frontier(
    executor_with,
    plan: CompiledGraph,
    started: str,
    run_inputs,
    blobs: LocalContentStore,
    store: SqlRunStore,
    surface: ReviewSurface,
    jobs: InProcessQueue,
) -> None:
    """The exit criterion, end to end. The run blocks at tagging and exits; a person
    decides; the run is re-enqueued as a job; the job runs the executor, which satisfies
    intake, mask and timing from the ledger and starts at tagging."""
    blocker = Blocks(blobs, at="tagging")
    first = executor_with(blocker).execute(plan, started, run_inputs, CONTEXT_REF)
    assert first.state is RunState.WAITING and store.run(started).state is RunState.WAITING

    survivor = Recorder(blobs)
    reports = []

    def resume(job: Job) -> None:
        reports.append(
            executor_with(survivor).execute(plan, job.payload["run_id"], run_inputs, CONTEXT_REF)
        )

    jobs.register(RESUME_JOB, resume)
    surface.decide(
        started,
        "item_1",
        decided_by="Dana Whitfield",
        decision=DecisionKind.ACCEPTED,
        expected_version=1,
    )

    assert store.run(started).state is RunState.RUNNING
    resumed = events_of(store, started, "run.resumed")
    assert len(resumed) == 1 and resumed[0].payload["job"] == RESUME_JOB
    jobs.drain()
    (report,) = reports
    assert report.satisfied == ["intake", "mask", "timing"]
    assert survivor.calls == list(plan.order[3:])
    assert report.finished


def test_a_run_with_another_item_open_keeps_waiting(
    executor_with,
    plan: CompiledGraph,
    started: str,
    run_inputs,
    blobs: LocalContentStore,
    store: SqlRunStore,
    surface: ReviewSurface,
    queue: ReviewQueue,
    router: ConfidenceRouter,
    jobs: InProcessQueue,
) -> None:
    executor_with(Blocks(blobs, at="tagging")).execute(plan, started, run_inputs, CONTEXT_REF)
    second = item("li_2")
    queue.enqueue(started, ENGAGEMENT, second, router.route(second, DECLARED[TAGGING]))

    surface.decide(
        started,
        "item_1",
        decided_by="Dana Whitfield",
        decision=DecisionKind.ACCEPTED,
        expected_version=1,
    )
    assert store.run(started).state is RunState.WAITING
    assert events_of(store, started, "run.resumed") == []

    surface.decide(
        started,
        "li_2",
        decided_by="Dana Whitfield",
        decision=DecisionKind.ACCEPTED,
        expected_version=1,
    )
    assert store.run(started).state is RunState.RUNNING
    assert len(events_of(store, started, "run.resumed")) == 1


def test_a_decision_names_a_person(surface: ReviewSurface, started: str, queued: str) -> None:
    with pytest.raises(Exception, match="(?i)person|decided_by"):
        surface.decide(
            started, queued, decided_by="", decision=DecisionKind.ACCEPTED, expected_version=1
        )


def test_the_executor_is_not_needed_to_decide(
    store: SqlRunStore, started: str, queued: str
) -> None:
    """A decision on a run that is not waiting - one still running, say - is recorded and
    resumes nothing. The surface never transitions a running run."""
    surface = ReviewSurface(store, __import__("ops.events", fromlist=["EventBus"]).EventBus(store))
    surface.decide(
        started,
        queued,
        decided_by="Dana Whitfield",
        decision=DecisionKind.ACCEPTED,
        expected_version=1,
    )
    assert store.run(started).state is RunState.RUNNING
    assert events_of(store, started, "run.resumed") == []


def test_the_surface_can_be_built_without_a_job_queue(store: SqlRunStore, bus) -> None:
    assert isinstance(ReviewSurface(store, bus), ReviewSurface)
    assert StepExecutor is not None
