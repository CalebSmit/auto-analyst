"""Submit for Review, and the Skill Review Board that reads it.

**Submission is its own act.** Building and testing a skill never, by itself, ships
anything: `submit` packages the definition, its schema, its references and its sandbox
transcript into one record and opens a review task, and it happens because a person asked
for it. There is no automatic path into this queue and nothing here fires on save. That
separation is most of the governance.

**The board is routed by scope.** A skill written at `valuation/esop/_segment` goes to the
ESOP reviewers, not to whoever is free. Outcomes are approved, returned for changes, or
rejected, each with a reason and a named reviewer. This queue is separate from the
engagement review queue on purpose: the question there is "is this output right", and the
question here is "should this procedure exist and run unattended on client data". Those
need different reviewers.

**A sustained drift flag reopens a review.** The drift monitor computes and reports; it
writes nothing and decides nothing. This is where its cross-run loop lands: a flag that
has held for the monitor's sustained window opens a re-review on the board, once per
episode, with the numbers attached. The loop is human-paced - there is no iteration count,
because the ceiling is a person's attention rather than a counter.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from governance.candidate import Stage
from governance.record import GovernanceRecord
from ops.blobs import ContentStore, put_json
from registries.scopes import ScopeRegistry

__all__ = [
    "DECISIONS",
    "Decision",
    "ReReview",
    "SkillBoard",
    "Submission",
    "reviewers_for",
]

NODE_SUBMIT = "skill_submit"
NODE_BOARD = "skill_board"
DECISIONS = ("approved", "returned", "rejected")
LOOP = "drift_re_review"


@dataclass(frozen=True)
class Submission:
    """One package: what it is, what it declares, and what it did on the fixtures."""

    candidate_id: str
    skill: str
    version: str
    layer: str
    submitted_by: str
    transcript_ref: str
    scorecard_key: str = ""
    references: tuple[str, ...] = ()
    ref: str = ""

    @property
    def key(self) -> str:
        return f"{self.skill}@{self.version}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "skill": self.skill,
            "version": self.version,
            "layer": self.layer,
            "submitted_by": self.submitted_by,
            "transcript_ref": self.transcript_ref,
            "scorecard_key": self.scorecard_key,
            "references": list(self.references),
        }


@dataclass(frozen=True)
class Decision:
    """What a named reviewer decided, and why."""

    candidate_id: str
    decision: str
    reviewer: str
    reason: str
    routed_to: str
    """The reviewer group the submission's scope routed it to."""

    @property
    def approved(self) -> bool:
        return self.decision == "approved"


@dataclass(frozen=True)
class ReReview:
    """A review reopened because a registered skill drifted."""

    skill: str
    scope: str
    metric: str
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def episode(self) -> str:
        """One per (skill, scope, metric). A flag that is still true tomorrow is the same
        episode, not a second one."""
        return f"{self.skill}|{self.scope}|{self.metric}"


def reviewers_for(layer: str, scopes: ScopeRegistry | None = None) -> str:
    """Which group reads it, from the scope layer it was written at.

    The rule is the layer's own practice and segment, so a firm-layer skill goes to the
    firm reviewers and an ESOP-segment skill goes to the ESOP ones. Deliberately derived
    rather than configured: a routing table beside the scope registry is a second place
    for the same fact to be wrong.
    """
    if not layer or layer == "_firm":
        return "firm"
    parts = [p for p in layer.split("/") if not p.startswith("_")]
    return "/".join(parts) if parts else layer.strip("_")


class SkillBoard:
    def __init__(
        self,
        record: GovernanceRecord,
        blobs: ContentStore,
        scopes: ScopeRegistry | None = None,
    ) -> None:
        self.record = record
        self.blobs = blobs
        self.scopes = scopes or ScopeRegistry.load()

    # -- submission

    def submit(
        self,
        candidate_id: str,
        *,
        skill: str,
        version: str,
        layer: str,
        submitted_by: str,
        transcript_ref: str,
        scorecard_key: str = "",
        references: Sequence[str] = (),
    ) -> Submission:
        """An explicit send-it-in. Never automatic, never on save."""
        if not submitted_by.strip():
            raise ValueError("a submission names the person who sent it in")
        submission = Submission(
            candidate_id=candidate_id,
            skill=skill,
            version=version,
            layer=layer,
            submitted_by=submitted_by.strip(),
            transcript_ref=transcript_ref,
            scorecard_key=scorecard_key,
            references=tuple(references),
        )
        ref = put_json(self.blobs, submission.as_dict(), name=f"submission:{candidate_id}")
        submission = Submission(**{**submission.__dict__, "ref": ref.content_hash})
        self.record.append(
            candidate_id,
            Stage.SUBMITTED,
            actor=submission.submitted_by,
            ref=ref.content_hash,
            detail={
                "node": NODE_SUBMIT,
                "name": skill,
                "version": version,
                "layer": layer,
                "routed_to": reviewers_for(layer, self.scopes),
                "transcript_ref": transcript_ref,
            },
        )
        return submission

    # -- the queue

    def queue(self, routed_to: str | None = None) -> tuple[dict[str, Any], ...]:
        """Everything submitted and not yet decided, newest last, optionally for one
        reviewer group."""
        submitted: dict[str, dict[str, Any]] = {}
        for entry in self.record.entries():
            if entry.stage == str(Stage.SUBMITTED):
                submitted[entry.candidate] = {
                    "candidate_id": entry.candidate,
                    "at": entry.at,
                    "submitted_by": entry.actor,
                    **dict(entry.detail or {}),
                }
            elif entry.stage in (str(Stage.APPROVED), "returned", "rejected"):
                submitted.pop(entry.candidate, None)
        rows = tuple(submitted.values())
        if routed_to is None:
            return rows
        return tuple(r for r in rows if r.get("routed_to") == routed_to)

    def decide(
        self,
        candidate_id: str,
        *,
        decision: str,
        reviewer: str,
        reason: str,
        layer: str = "",
    ) -> Decision:
        """Approved, returned for changes, or rejected - each with a reason and a name.

        Only an approval carries the candidate forward: the other two are recorded under
        their own name, so nothing downstream can mistake them for evidence of approval.
        """
        if decision not in DECISIONS:
            raise ValueError(f"{decision!r} is not one of {', '.join(DECISIONS)}")
        if not reviewer.strip():
            raise ValueError("a decision names the reviewer who made it")
        if not reason.strip():
            raise ValueError("a decision carries its reason; 'approved' on its own is not one")
        routed = reviewers_for(layer or self._layer_of(candidate_id), self.scopes)
        recorded = Decision(
            candidate_id=candidate_id,
            decision=decision,
            reviewer=reviewer.strip(),
            reason=reason.strip(),
            routed_to=routed,
        )
        self.record.append(
            candidate_id,
            Stage.APPROVED if recorded.approved else decision,
            actor=recorded.reviewer,
            ref=decision,
            detail={
                "node": NODE_BOARD,
                "decision": decision,
                "reason": recorded.reason,
                "routed_to": routed,
            },
        )
        return recorded

    # -- recipes

    def register_recipe(
        self,
        path: Path,
        *,
        version: int,
        decision: Decision,
        register: Any | None = None,
    ) -> Any:
        """Put an approved recipe into the register, and refuse anything else.

        The decision is the object the board produced, not a name and a date somebody
        typed: an approval that was returned for changes or rejected carries the same
        fields and means the opposite, so it is the approval itself that is required
        here rather than evidence of one.

        This is the only place the recipe register is written. `registries.recipes`
        cannot import the board - the board reaches back into the harness, and the
        register sits on the path every run takes - so the constraint is held by a test
        that asserts nothing else calls `register`.
        """
        from registries.recipes import RecipeRegister

        if not decision.approved:
            raise ValueError(
                f"{path.stem} was {decision.decision}, not approved; only an approval "
                f"registers a recipe"
            )
        recorded = (register or RecipeRegister()).register(
            path,
            version=version,
            approved_by=decision.reviewer,
            decision_ref=decision.candidate_id,
        )
        self.record.append(
            decision.candidate_id,
            Stage.REGISTERED,
            actor=decision.reviewer,
            ref=recorded.digest,
            detail={
                "node": NODE_BOARD,
                "recipe": recorded.name,
                "version": recorded.version,
                "reason": decision.reason,
            },
        )
        return recorded

    # -- the cross-run loop

    def reopen_from_drift(self, report: Any, *, opened_by: str = "drift_monitor") -> tuple[
        ReReview, ...
    ]:
        """Open a re-review for every sustained flag the drift monitor raises.

        The monitor writes nothing; this is the one place its cross-run loop becomes an
        action. Once per episode: a flag still true next week is the same episode until
        somebody decides, which is what "human-paced" means for a loop with no counter.
        """
        opened: list[ReReview] = []
        seen = self._episodes()
        for flag in getattr(report, "flags", ()):
            review = ReReview(
                skill=str(getattr(flag, "skill", "")),
                scope=str(getattr(flag, "scope", "")),
                metric=str(getattr(flag, "metric", "")),
                detail={
                    "recent": getattr(flag, "recent", None),
                    "baseline": getattr(flag, "baseline", None),
                    "direction": str(getattr(flag, "direction", "")),
                    "runs": getattr(flag, "runs", None),
                    "detail": flag.line() if hasattr(flag, "line") else str(flag),
                },
            )
            if review.episode in seen:
                continue
            self.record.append(
                f"rereview:{review.skill}",
                "re_review",
                actor=opened_by,
                ref=review.episode,
                detail={
                    "node": NODE_BOARD,
                    "loop": LOOP,
                    "skill": review.skill,
                    "scope": review.scope,
                    "metric": review.metric,
                    "routed_to": reviewers_for(review.scope, self.scopes),
                    **review.detail,
                },
            )
            opened.append(review)
        return tuple(opened)

    def re_reviews(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {"candidate_id": e.candidate, "at": e.at, "episode": e.ref, **dict(e.detail or {})}
            for e in self.record.entries()
            if e.stage == "re_review"
        )

    # -- plumbing

    def _episodes(self) -> set[str]:
        return {e.ref for e in self.record.entries() if e.stage == "re_review"}

    def _layer_of(self, candidate_id: str) -> str:
        for entry in reversed(self.record.entries(candidate_id)):
            layer = (entry.detail or {}).get("layer")
            if layer:
                return str(layer)
        return ""
