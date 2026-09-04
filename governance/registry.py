"""The Skill Registry: the only way a skill becomes live, and the single writer to the tree.

Approval is a decision; registration is a deployment. Keeping them as two events means
"someone approved this" and "this is running on client work" can never be the same moment
by accident.

This is the one edge from governance back into the live system, and it carries a
definition - never data, and never a client file. What it writes is a SKILL.md at a scope
layer, and a row in the version ledger. It writes nothing else anywhere, and a test walks
the repo to check that no other module writes into `skills/`.

Registration requires the whole chain, not a subset of it. `SkillRegistration` (P22) is the
version ledger and holds the gate that a scorecard must clear; this adds the rest of the
evidence - the drop, both scans, the bench, the sandbox, the transcript, the replay, the
submission, the board's approval and a sustained shadow run - and refuses if any one of
them is missing. Remove any single gate and the path from the drop folder to the tree
breaks, which is invariant 21 as a property of this function rather than of a diagram.

Versions are immutable. A change is a new version and a new review.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from evals.harness import Scorecard
from evals.registration import RegisteredSkill, SkillRegistration
from governance.candidate import Stage
from governance.record import GovernanceRecord
from registries.skills import SkillTree

__all__ = ["Published", "SkillRegistry"]

NODE = "skill_registry"
SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"


@dataclass(frozen=True)
class Published:
    """A version, live: the ledger row and the file the tree will read."""

    registered: RegisteredSkill
    path: Path
    layer: str

    @property
    def key(self) -> str:
        return self.registered.key


class SkillRegistry:
    """The single write path into the live skills tree."""

    def __init__(
        self,
        record: GovernanceRecord,
        registration: SkillRegistration | None = None,
        skills_dir: Path | str = SKILLS_DIR,
    ) -> None:
        self.record = record
        self.registration = registration or SkillRegistration()
        self.skills_dir = Path(skills_dir)

    def __repr__(self) -> str:
        return f"SkillRegistry(tree={self.skills_dir})"

    def register(
        self,
        candidate_id: str,
        scorecard: Scorecard,
        *,
        definition: str,
        layer: str,
        approved_by: str,
    ) -> Published:
        """Publish the definition into the tree and record the version.

        Order matters: the chain is checked first, then the gate, then the ledger row,
        and only then is anything written into `skills/`. A file in the tree with no row
        behind it would be a live skill nobody registered.
        """
        candidate = self.record.candidate(candidate_id)
        if candidate is None:
            raise ValueError(f"{candidate_id} is not in the governance record")
        candidate.require(Stage.REGISTERED)

        registered = self.registration.register(scorecard, approved_by=approved_by)

        folder = self.skills_dir / layer / registered.skill
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "SKILL.md"
        path.write_text(definition, encoding="utf-8")

        self.record.append(
            candidate_id,
            Stage.REGISTERED,
            actor=approved_by,
            ref=registered.scorecard_hash,
            detail={
                "node": NODE,
                "skill": registered.skill,
                "version": registered.version,
                "layer": layer,
                "path": str(path.relative_to(self.skills_dir)),
                "gates": list(registered.gates),
                "owed": list(registered.owed),
            },
        )
        return Published(registered=registered, path=path, layer=layer)

    # -- reading

    def registered(self) -> tuple[RegisteredSkill, ...]:
        return self.registration.registered()

    def is_registered(self, skill: str, version: str) -> bool:
        return self.registration.is_registered(skill, version)

    def tree(self) -> SkillTree:
        """The live tree, as the Scope Resolver will read it."""
        return SkillTree.load(self.skills_dir)

    def unregistered(self) -> tuple[str, ...]:
        """Every skill in the live tree with no registration behind it.

        The tree is a folder of files and a person can put one there by hand, so this is
        how the claim is checked rather than assumed. P27 reports it; the practice
        decides what to do about the drafts that predate the chain.
        """
        return tuple(
            sorted(
                skill.key
                for skill in self.tree().all()
                if not self.is_registered(skill.name, skill.version)
            )
        )
