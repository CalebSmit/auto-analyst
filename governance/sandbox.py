"""The Skill Authoring Sandbox and its Test Harness.

**The sandbox** is where a draft SKILL.md, its references and its output schema are
written, walled off from client work. Its isolation is that the connection does not
exist, not that a permission denies it: the sandbox has its own tree root, and no storage
port binding, so there is no engagement folder to reach and no vault to open. A test walks
this module's imports and asserts the same thing.

**The test harness** runs the draft against seeded synthetic fixtures and produces a
transcript: inputs, outputs, guard results, cost. It uses the same dispatcher and the same
guards as production, pointed at fixture data - a draft skill faces exactly the checks a
live one does, which is the only way the transcript means anything. Testing that runs a
different code path than production tells a reviewer nothing about how the skill will
behave, and the transcript is what the reviewer actually reads.

Fixtures are seeded by a person. Nothing here writes one.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from governance.adapt import Adapted
from governance.candidate import Stage
from governance.record import GovernanceRecord, intake_root
from ops.blobs import ContentStore, put_json
from registries.skills import SkillTree

__all__ = ["SANDBOX_DIR", "Sandbox", "SandboxTest", "Transcript", "TranscriptEntry"]

SANDBOX_DIR = "_sandbox"
NODE_SANDBOX = "skill_sandbox"
NODE_TEST = "sandbox_test"


class Sandbox:
    """A skills tree of its own, outside the repo and outside every engagement."""

    def __init__(self, record: GovernanceRecord, root: Path | str | None = None) -> None:
        self.record = record
        self.root = intake_root(root) / SANDBOX_DIR

    def __repr__(self) -> str:
        return f"Sandbox({self.root})"

    def write(self, adapted: Adapted, *, written_by: str) -> Path:
        """Put the conforming draft in the sandbox tree, at its proposed layer."""
        folder = self.root / adapted.layer / adapted.name
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "SKILL.md"
        path.write_text(adapted.skill_md(), encoding="utf-8")
        self.record.append(
            adapted.candidate_id,
            Stage.DRAFTED,
            actor=written_by,
            ref=adapted.ref,
            detail={
                "node": NODE_SANDBOX,
                "path": str(path.relative_to(self.root)),
                "layer": adapted.layer,
                "name": adapted.name,
                "version": adapted.version,
            },
        )
        return path

    def tree(self) -> SkillTree:
        """The sandbox's own tree. Loading it proves the draft parses as a skill at all,
        which is the first thing the test harness needs and the last thing a draft that
        merely looks right will pass."""
        return SkillTree.load(self.root)

    def reference(self, adapted: Adapted, name: str, text: str) -> Path:
        """A reference file beside the skill. Written by the author, in the sandbox."""
        path = self.root / adapted.layer / adapted.name / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


@dataclass(frozen=True)
class TranscriptEntry:
    """One fixture case, run through the production dispatcher."""

    case: str
    passed: bool
    output_ref: str = ""
    guards: tuple[str, ...] = ()
    cost_usd: float = 0.0
    refusal: str = ""

    def line(self) -> str:
        mark = "ok " if self.passed else "FAIL"
        return f"{mark} {self.case}: {', '.join(self.guards) or 'no guard reported'}{
            '' if self.passed else ' - ' + self.refusal}"


@dataclass(frozen=True)
class Transcript:
    """What the reviewer reads: every case, what it produced, what the guards said."""

    candidate_id: str
    skill: str
    entries: tuple[TranscriptEntry, ...] = ()
    ref: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return bool(self.entries) and all(e.passed for e in self.entries)

    @property
    def cost_usd(self) -> float:
        return round(sum(e.cost_usd for e in self.entries), 6)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "skill": self.skill,
            "passed": self.passed,
            "cases": [
                {
                    "case": e.case,
                    "passed": e.passed,
                    "output_ref": e.output_ref,
                    "guards": list(e.guards),
                    "cost_usd": e.cost_usd,
                    "refusal": e.refusal,
                }
                for e in self.entries
            ],
            "cost_usd": self.cost_usd,
            **self.detail,
        }

    def report(self) -> str:
        head = f"{self.skill}: {len(self.entries)} case(s), ${self.cost_usd:.4f}"
        return "\n".join([head, *(f"  {e.line()}" for e in self.entries)])


class SandboxTest:
    """Runs a draft against seeded fixtures through the production dispatcher.

    `dispatch` is the seam: the caller supplies the same `SkillDispatcher.run` a live step
    uses, bound to the sandbox tree. Keeping it a callable rather than constructing a
    dispatcher here is what lets the harness be the production path instead of a
    reimplementation of it - and what a test can prove, by asserting the callable it was
    given is the dispatcher's own method.
    """

    def __init__(
        self,
        record: GovernanceRecord,
        blobs: ContentStore,
        dispatch: Callable[[str, Any], Any],
    ) -> None:
        self.record = record
        self.blobs = blobs
        self.dispatch = dispatch

    def run(
        self,
        candidate_id: str,
        skill: str,
        cases: Sequence[tuple[str, Any]],
        *,
        run_by: str = NODE_TEST,
    ) -> Transcript:
        """Every case, in order. A case that a guard refuses is recorded as refused, not
        raised: the transcript is the output, and a harness that stops at the first
        failure tells a reviewer about one case."""
        entries: list[TranscriptEntry] = []
        for case, inputs in cases:
            entries.append(self._one(case, inputs))
        transcript = Transcript(candidate_id=candidate_id, skill=skill, entries=tuple(entries))
        ref = put_json(self.blobs, transcript.as_dict(), name=f"transcript:{candidate_id}")
        transcript = Transcript(**{**transcript.__dict__, "ref": ref.content_hash})
        self.record.append(
            candidate_id,
            Stage.EXERCISED,
            actor=run_by,
            ref=ref.content_hash,
            detail={
                "node": NODE_TEST,
                "skill": skill,
                "cases": len(entries),
                "passed": transcript.passed,
                "cost_usd": transcript.cost_usd,
            },
        )
        return transcript

    def _one(self, case: str, inputs: Any) -> TranscriptEntry:
        try:
            dispatched = self.dispatch(case, inputs)
        except Exception as refused:  # noqa: BLE001 - a refusal is a result, not a crash
            return TranscriptEntry(
                case=case,
                passed=False,
                refusal=f"{type(refused).__name__}: {refused}",
                guards=_guards_of(refused),
            )
        return TranscriptEntry(
            case=case,
            passed=True,
            output_ref=getattr(getattr(dispatched, "output_ref", None), "content_hash", ""),
            guards=("schema", "provenance") if hasattr(dispatched, "output") else (),
        )


def _guards_of(refused: Exception) -> tuple[str, ...]:
    result = getattr(refused, "result", None)
    return (str(getattr(result, "guard", "")),) if result is not None else ()
