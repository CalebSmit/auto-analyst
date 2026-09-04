"""The governance chain: how this system changes, and what a change has to survive.

Skills are how this system changes, and ungoverned change is the main long-term risk. A
dropped draft is a candidate, not a skill.

    drop -> conformance -> bench -> sandbox -> sandbox test -> eval harness
         -> replay -> submit -> board -> shadow run -> registry -> the live tree

Eleven stages, linear, each requiring the evidence of every stage before it. Remove any
one and the path from the drop folder to the tree breaks rather than routing around it.
The governance record is the state: a candidate's position is folded from an append-only,
hash-chained file, so nothing advances because an object in memory said it had.

Two limits are the point of the whole thing. The bench can produce a conforming skill but
never a fixture - evidence cannot be authored by the thing it vouches for. And governance
sees masked payloads or it sees nothing: no engagement credential, no vault, no storage
port binding, and one edge back into the live system that carries a definition.
"""

from governance.adapt import AdaptationBench, Adapted, FixtureRequest
from governance.board import Decision, ReReview, SkillBoard, Submission, reviewers_for
from governance.candidate import NODE_FOR, STAGES, Candidate, GateSkipped, Stage
from governance.chain import GovernanceChain
from governance.conformance import ConformanceCheck, DraftHeld, Gap, GapReport
from governance.drop import DropFolder, Dropped
from governance.record import Entry, GovernanceRecord, RecordBroken, intake_root
from governance.registry import Published, SkillRegistry
from governance.sandbox import Sandbox, SandboxTest, Transcript, TranscriptEntry
from governance.shadow import Observation, Promotion, ShadowDeployment, ShadowRefused

__all__ = [
    "NODE_FOR",
    "STAGES",
    "AdaptationBench",
    "Adapted",
    "Candidate",
    "ConformanceCheck",
    "Decision",
    "DraftHeld",
    "DropFolder",
    "Dropped",
    "Entry",
    "FixtureRequest",
    "Gap",
    "GapReport",
    "GateSkipped",
    "GovernanceChain",
    "GovernanceRecord",
    "Observation",
    "Promotion",
    "Published",
    "ReReview",
    "RecordBroken",
    "Sandbox",
    "SandboxTest",
    "ShadowDeployment",
    "ShadowRefused",
    "SkillBoard",
    "SkillRegistry",
    "Stage",
    "Submission",
    "Transcript",
    "TranscriptEntry",
    "intake_root",
    "reviewers_for",
]
