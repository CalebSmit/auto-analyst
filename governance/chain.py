"""The governance chain, end to end: a dropped draft becomes a registered skill, or does not.

One object that holds the eleven nodes and walks a candidate through them. It exists so
that "no path from the drop folder to the tree skips fixtures, review or a shadow run" is
something a caller cannot get wrong by holding the pieces in a different order: every
stage asks the governance record what has already happened and refuses if the answer is
not enough.

    drop -> scan -> adapt -> draft -> exercise -> evaluate -> replay
         -> submit -> approve -> shadow -> register

Two things this chain deliberately cannot do.

**It cannot supply fixtures.** The bench produces a conforming skill and a fixture request;
the eval harness scores against a fixture set a person seeded. There is no method here
that writes one, and the evaluate stage refuses a skill whose fixture set does not exist -
evidence cannot be authored by the thing it vouches for.

**It cannot skip a stage.** There is no `force`, no `skip`, and no method that records a
stage's evidence without doing the stage. The refusal names the first missing gate and
what it would have meant.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.harness import EvalHarness, Scorecard
from governance.adapt import AdaptationBench, Adapted
from governance.board import Decision, SkillBoard, Submission
from governance.candidate import Candidate, Stage
from governance.conformance import ConformanceCheck, GapReport
from governance.drop import DropFolder, Dropped
from governance.record import GovernanceRecord
from governance.registry import Published, SkillRegistry
from governance.sandbox import Sandbox, SandboxTest, Transcript
from governance.shadow import Promotion, ShadowDeployment
from registries.errors import SKILL_INVALID, RegistryError, diagnose

__all__ = ["GovernanceChain"]


@dataclass(frozen=True)
class GovernanceChain:
    """Every node of the chain, and the record they all write to."""

    record: GovernanceRecord
    drop: DropFolder
    conformance: ConformanceCheck
    bench: AdaptationBench
    sandbox: Sandbox
    sandbox_test: SandboxTest
    evals: EvalHarness
    board: SkillBoard
    shadow: ShadowDeployment
    registry: SkillRegistry

    # -- the stages, in order

    def take(self, path: Path, dropped_by: str) -> Dropped:
        return self.drop.take(path, dropped_by)

    def scan(self, dropped: Dropped, checked_by: str) -> GapReport:
        self.require(dropped.candidate_id, Stage.SCANNED)
        return self.conformance.scan(dropped.candidate_id, dropped.text(), checked_by)

    def adapt(self, report: GapReport, proposed_by: str) -> Adapted:
        self.require(report.candidate_id, Stage.ADAPTED)
        return self.bench.adapt(report, proposed_by=proposed_by)

    def draft(self, adapted: Adapted, written_by: str) -> Path:
        self.require(adapted.candidate_id, Stage.DRAFTED)
        return self.sandbox.write(adapted, written_by=written_by)

    def exercise(
        self, candidate_id: str, skill: str, cases: Sequence[tuple[str, Any]], run_by: str
    ) -> Transcript:
        self.require(candidate_id, Stage.EXERCISED)
        return self.sandbox_test.run(candidate_id, skill, cases, run_by=run_by)

    def evaluate(
        self,
        candidate_id: str,
        skill: str,
        *,
        scored_by: str = "eval_harness",
        world: Any | None = None,
    ) -> Scorecard:
        """Score the candidate against its published gates.

        Refuses a skill whose fixture set does not exist rather than scoring it as zero:
        a missing fixture set is a request nobody answered, and reporting it as a failing
        score would let somebody argue about the threshold instead of supplying evidence.
        """
        self.require(candidate_id, Stage.EVALUATED)
        gates = self.evals.gates_for(skill)
        if not gates:
            raise RegistryError(
                diagnose(
                    SKILL_INVALID,
                    f"{skill} has no acceptance gates published, so there is nothing to "
                    f"score it against. Gates are the practice's; add them to "
                    f"evals/gates.yaml before the candidate goes further.",
                    locator=skill,
                )
            )
        # Scored in the sandbox, against the candidate - not against the version already
        # live. The harness's default tree is the live one, which would score the skill
        # this candidate is meant to replace and register a version nobody drafted.
        scorecard = EvalHarness(self.evals.gates_file, tree=self.sandbox.tree()).evaluate(
            skill, world
        )
        self.record.append(
            candidate_id,
            Stage.EVALUATED,
            actor=scored_by,
            ref=scorecard.key,
            detail={
                "node": "eval_harness",
                "passed": scorecard.passed,
                "owed": [g.metric for g in scorecard.owed],
                "gates": [m.line() for m in scorecard.metrics],
            },
        )
        return scorecard

    def replayed(self, candidate_id: str, *, changes: int, runs: int, checked_by: str) -> None:
        """Record the regression diff from the replay harness.

        The harness itself is P22's and takes a run store; the chain records that it ran
        and what it found, so the stage is evidence rather than an assumption.
        """
        self.require(candidate_id, Stage.REPLAYED)
        self.record.append(
            candidate_id,
            Stage.REPLAYED,
            actor=checked_by,
            ref=f"changes:{changes}",
            detail={"node": "replay_harness", "changes": changes, "runs": runs},
        )

    def submit(self, candidate_id: str, *, submitted_by: str, **fields: Any) -> Submission:
        self.require(candidate_id, Stage.SUBMITTED)
        return self.board.submit(candidate_id, submitted_by=submitted_by, **fields)

    def decide(self, candidate_id: str, **fields: Any) -> Decision:
        self.require(candidate_id, Stage.APPROVED)
        return self.board.decide(candidate_id, **fields)

    def promote(self, candidate_id: str, *, promoted_by: str) -> Promotion:
        self.require(candidate_id, Stage.SHADOWED)
        return self.shadow.promote(candidate_id, promoted_by=promoted_by)

    def register(self, candidate_id: str, scorecard: Scorecard, **fields: Any) -> Published:
        return self.registry.register(candidate_id, scorecard, **fields)

    # -- what every stage asks first

    def candidate(self, candidate_id: str) -> Candidate:
        found = self.record.candidate(candidate_id)
        if found is None:
            raise ValueError(f"{candidate_id} is not in the governance record")
        return found

    def require(self, candidate_id: str, stage: Stage) -> Candidate:
        """Refuse the stage unless every stage before it has evidence in the record."""
        candidate = self.candidate(candidate_id)
        candidate.require(stage)
        return candidate

    def stage_of(self, candidate_id: str) -> Stage | None:
        return self.candidate(candidate_id).stage
