"""The Analyst Review Surface: shows the source and the question before the answer.

The API behind the review UI. Judgment-first ordering is a deliberate default, not a
preference: `show` returns the source excerpt and the question and nothing else;
`reveal` returns the proposal and the confidence, and records that it was asked for.
Shown a confident answer first, a reviewer tends to look for reasons it is right.

A decision needs a reason on edits and rejections, and it is written under optimistic
locking: the reviewer says which version of the item they looked at, and a decision made
against a version that has since changed is refused *with the decision that changed it*.
Two reviewers cannot silently overwrite each other; the second sees the first.

A recorded decision re-enqueues the waiting run at its frontier. The run had checkpointed
and exited; once nothing is left open on it, it goes back to running and a resume job is
submitted, and the executor satisfies every completed step from the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ops.events import EventBus
from ops.models import DecisionKind, RunState
from ops.run_store import DecisionRecord, ReviewItemRecord, RunStore
from ports.queue import QueuePort
from registries.errors import RATIONALE_REQUIRED, STALE_DECISION, DiagnosticError, diagnose

__all__ = ["Proposal", "ReviewRefused", "ReviewSurface", "StaleDecision", "View"]

NODE = "review_surface"
RESUME_JOB = "run.resume"

# Which decisions may later write a precedent. A rejection records that the proposal was
# wrong and nothing about what is right; it teaches nothing a future run should copy.
WRITES_PRECEDENT = frozenset({DecisionKind.ACCEPTED, DecisionKind.CORRECTED})
NEEDS_A_REASON = frozenset({DecisionKind.CORRECTED, DecisionKind.REJECTED, DecisionKind.ESCALATED})


class ReviewRefused(DiagnosticError):
    """The surface would not record that."""


class StaleDecision(ReviewRefused):
    """Somebody else got there first. Carries what they decided."""

    def __init__(self, diagnostic: Any, existing: DecisionRecord | None, version: int) -> None:
        super().__init__(diagnostic)
        self.existing = existing
        self.version = version


@dataclass(frozen=True)
class View:
    """What a reviewer sees first. No proposal, no confidence."""

    run_id: str
    item_id: str
    kind: str
    question: str
    source_excerpt: str
    locator: str
    skill: str
    reasons: tuple[str, ...]
    severity: str
    owner: str | None
    due_at: str | None
    version: int
    state: str


@dataclass(frozen=True)
class Proposal:
    """What a reviewer sees on request - the second click."""

    item_id: str
    proposal: dict[str, Any]
    confidence: float | None


class ReviewSurface:
    def __init__(self, store: RunStore, bus: EventBus, queue: QueuePort | None = None) -> None:
        self.store = store
        self.bus = bus
        self.queue = queue

    # -- reading, in the right order

    def show(self, run_id: str, item_id: str) -> View:
        item = self._item(run_id, item_id)
        d = item.detail
        return View(
            run_id=run_id,
            item_id=item.item_id,
            kind=item.kind,
            question=item.subject,
            source_excerpt=str(d.get("source_excerpt", "")),
            locator=str(d.get("locator", "")),
            skill=str(d.get("skill", "")),
            reasons=tuple(d.get("reasons") or ()),
            severity=str(d.get("severity", "")),
            owner=item.owner,
            due_at=item.due_at,
            version=item.version,
            state=item.state,
        )

    def reveal(self, run_id: str, item_id: str, *, viewer: str) -> Proposal:
        """The proposal and the confidence. Recorded, so "approved without ever revealing
        the proposal" and "approved four seconds after revealing it" are both visible in
        the data later."""
        item = self._item(run_id, item_id)
        run = self.store.run(run_id)
        self.bus.emit(
            run_id=run_id,
            engagement_id=run.engagement_id,
            node_id=NODE,
            type="hitl.proposal.revealed",
            message=f"{item_id}: proposal revealed to {viewer}",
            payload={"item_id": item_id, "viewer": viewer, "version": item.version},
        )
        return Proposal(
            item_id=item_id,
            proposal=dict(item.detail.get("proposal") or {}),
            confidence=item.detail.get("confidence"),
        )

    # -- writing, once

    def decide(
        self,
        run_id: str,
        item_id: str,
        *,
        decided_by: str,
        decision: DecisionKind,
        expected_version: int,
        rationale: str = "",
        answer: dict[str, Any] | None = None,
    ) -> DecisionRecord:
        """Record a person's answer. Refuses without a reason on an edit, a rejection or
        an escalation; refuses if the item is not at the version the reviewer saw."""
        decision = DecisionKind(decision)
        if not decided_by.strip():
            raise ValueError("a decision names a person; decided_by is empty")
        if decision in NEEDS_A_REASON and not rationale.strip():
            raise ReviewRefused(
                diagnose(
                    RATIONALE_REQUIRED,
                    f"{decision} on {item_id} needs a reason; there is no silent override",
                    locator=f"{run_id}/{item_id}",
                )
            )
        if decision is DecisionKind.CORRECTED and not answer:
            raise ReviewRefused(
                diagnose(
                    RATIONALE_REQUIRED,
                    f"corrected on {item_id} needs the corrected value; a correction with "
                    f"no answer is a rejection",
                    locator=f"{run_id}/{item_id}",
                )
            )

        item = self._item(run_id, item_id)
        if item.version != expected_version or item.state != "open":
            existing = next((d for d in self.store.decisions(run_id) if d.item_id == item_id), None)
            raise StaleDecision(
                diagnose(
                    STALE_DECISION,
                    (
                        f"{item_id} is at version {item.version}, not {expected_version}"
                        + (
                            f"; {existing.decided_by} recorded {existing.decision} at "
                            f"{existing.decided_at}"
                            if existing
                            else ""
                        )
                    ),
                    locator=f"{run_id}/{item_id}",
                    expected=f"version {expected_version}",
                    found=f"version {item.version}",
                ),
                existing,
                item.version,
            )

        self.store.record_decision(
            run_id,
            item_id,
            decided_by=decided_by,
            decision=decision,
            rationale=rationale,
            writes_precedent=decision in WRITES_PRECEDENT,
            expected_version=expected_version,
            proposal=dict(item.detail.get("proposal") or {}),
            answer=dict(answer or {}),
            skill=str(item.detail.get("skill", "")),
        )
        record = next(d for d in self.store.decisions(run_id) if d.item_id == item_id)
        run = self.store.run(run_id)
        self.bus.emit(
            run_id=run_id,
            engagement_id=run.engagement_id,
            node_id="decision_log",
            type="hitl.item.decided",
            message=f"{item_id}: {decision} by {decided_by}",
            payload={
                "item_id": item_id,
                "decision": str(decision),
                "decided_by": decided_by,
                "writes_precedent": record.writes_precedent,
                "skill": record.skill,
            },
        )
        self._maybe_resume(run_id)
        return record

    # -- the run

    def _maybe_resume(self, run_id: str) -> str | None:
        """Once nothing on the run is waiting on a person, the run goes back to running
        and a resume job is submitted. The executor picks it up at the frontier."""
        run = self.store.run(run_id)
        if run.state is not RunState.WAITING:
            return None
        if any(i.state == "open" for i in self.store.review_items(run_id)):
            return None
        self.store.transition(run_id, RunState.RUNNING, reason="every review item decided")
        job_id = (
            self.queue.submit(RESUME_JOB, {"run_id": run_id}, engagement_id=run.engagement_id)
            if self.queue is not None
            else None
        )
        self.bus.emit(
            run_id=run_id,
            engagement_id=run.engagement_id,
            node_id="review_queue",
            type="run.resumed",
            message="every review item decided; re-enqueued at the frontier",
            payload={"job_id": job_id, "job": RESUME_JOB},
        )
        return job_id

    # -- plumbing

    def _item(self, run_id: str, item_id: str) -> ReviewItemRecord:
        found = next((i for i in self.store.review_items(run_id) if i.item_id == item_id), None)
        if found is None:
            raise KeyError(f"{run_id} has no review item {item_id!r}")
        return found
