"""What a skill is before it is a skill, and the eleven stages it has to pass.

A dropped draft is a candidate, not a skill. The chain from the drop folder to the live
tree is the blueprint's, node for node, and it is linear on purpose: every stage requires
the evidence of every stage before it, so removing any one gate breaks the path rather
than routing around it. That is invariant 21 as a property of the code, and the graph
assertion is the same claim about the design.

    dropped -> scanned -> adapted -> drafted -> exercised -> evaluated
            -> replayed -> submitted -> approved -> shadowed -> registered

Nothing here holds state. A candidate's position in the chain is folded from the
governance record, the same way a run's trace is folded from its event stream: the record
is the state, so a candidate cannot be advanced by an object somebody kept a reference to.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from registries.errors import GATE_SKIPPED, DiagnosticError, diagnose

__all__ = [
    "NODE_FOR",
    "STAGES",
    "Candidate",
    "GateSkipped",
    "Stage",
    "required_before",
]


class Stage(StrEnum):
    DROPPED = "dropped"
    SCANNED = "scanned"
    ADAPTED = "adapted"
    DRAFTED = "drafted"
    EXERCISED = "exercised"
    EVALUATED = "evaluated"
    REPLAYED = "replayed"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    SHADOWED = "shadowed"
    REGISTERED = "registered"


STAGES: tuple[Stage, ...] = tuple(Stage)

# Which blueprint node does each stage. The names are the graph's, so a stage and the
# node it implements cannot drift apart without a test noticing.
NODE_FOR: Mapping[Stage, str] = {
    Stage.DROPPED: "skill_drop",
    Stage.SCANNED: "skill_conformance",
    Stage.ADAPTED: "skill_adapt",
    Stage.DRAFTED: "skill_sandbox",
    Stage.EXERCISED: "sandbox_test",
    Stage.EVALUATED: "eval_harness",
    Stage.REPLAYED: "replay_harness",
    Stage.SUBMITTED: "skill_submit",
    Stage.APPROVED: "skill_board",
    Stage.SHADOWED: "shadow_run",
    Stage.REGISTERED: "skill_registry",
}

# What each stage says about itself, for the refusal a person reads.
MEANS: Mapping[Stage, str] = {
    Stage.DROPPED: "the draft was copied and hashed out of the drop folder",
    Stage.SCANNED: "the draft was scanned for injection and for client data, and diffed "
    "against the skill contract",
    Stage.ADAPTED: "the gaps the scan named were filled and a scope layer proposed",
    Stage.DRAFTED: "a conforming SKILL.md exists in the sandbox",
    Stage.EXERCISED: "the draft ran against synthetic fixtures through the production "
    "dispatcher and produced a transcript",
    Stage.EVALUATED: "the eval harness scored it against its published gates",
    Stage.REPLAYED: "recorded steps were replayed against the candidate and the "
    "regression diff recorded",
    Stage.SUBMITTED: "a person packaged it and asked for review",
    Stage.APPROVED: "a named reviewer at the right scope approved it",
    Stage.SHADOWED: "it ran beside the registered version on real runs and held its "
    "agreement threshold",
    Stage.REGISTERED: "the registry published the definition into the live tree",
}


class GateSkipped(DiagnosticError):
    """A stage was reached without the evidence of one before it."""


def required_before(stage: Stage) -> tuple[Stage, ...]:
    """Every stage that must already have evidence. Linear, and that is the point: a
    chain with a shortcut in it is a chain with a gate that does not hold."""
    return STAGES[: STAGES.index(stage)]


@dataclass(frozen=True)
class Candidate:
    """A draft on its way through the chain, and where it has got to.

    `evidence` maps a stage to the reference recorded for it - a content hash, a
    scorecard key, a decision id. Folded from the governance record; never assigned.
    """

    id: str
    name: str
    """The skill name it will register as. Proposed by the bench, confirmed by a person."""
    source_hash: str
    """The hash of exactly what was dropped, before anything touched it."""
    version: str = ""
    layer: str = ""
    """The scope layer it is proposed for: the shallowest layer where the skill is true."""
    evidence: Mapping[str, str] = field(default_factory=dict)
    detail: Mapping[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}" if self.version else self.name

    def has(self, stage: Stage) -> bool:
        return str(stage) in self.evidence

    @property
    def stage(self) -> Stage | None:
        """The furthest stage with evidence. None for a candidate nothing has recorded."""
        reached = [s for s in STAGES if self.has(s)]
        return reached[-1] if reached else None

    def missing(self, stage: Stage) -> tuple[Stage, ...]:
        return tuple(s for s in required_before(stage) if not self.has(s))

    def require(self, stage: Stage) -> None:
        """Refuse to reach `stage` while anything before it has no evidence.

        The refusal names the first missing gate and what it would have meant, because
        "governance refused" is not something anybody can act on.
        """
        missing = self.missing(stage)
        if not missing:
            return
        first = missing[0]
        raise GateSkipped(
            diagnose(
                GATE_SKIPPED,
                f"{self.key} cannot reach {stage} - there is no record that {first} "
                f"happened, so nothing shows that {MEANS[first]}"
                + (
                    f" (also missing: {', '.join(str(s) for s in missing[1:])})"
                    if len(missing) > 1
                    else ""
                ),
                locator=f"{self.id}/{first}",
                skill=self.key,
                expected=f"evidence for {', '.join(str(s) for s in required_before(stage))}",
                found=", ".join(str(s) for s in STAGES if self.has(s)) or "nothing",
            )
        )
