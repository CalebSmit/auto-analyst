"""Which workflows may run on client work, and who said so.

A recipe is the order the work happens in: which skills, against which inputs, with which
guards between them. P32 made it a property of the engagement, which is what a practice
group wanted - and which means a managing director can now point an engagement at any YAML
file in `recipes/`. That is the right amount of control and the wrong amount of ceremony:
a skill cannot reach client work without a board approval with a name on it, and the
sequence the skills run in was reachable by editing a file.

So a recipe is registered the way a skill version is. Same shape, same reason: **approval
is a decision, registration is a deployment.** A recipe that nobody approved does not run,
and a recipe edited after it was approved is not the recipe that was approved.

**Only the board writes here.** `register` takes the reference of an approval recorded in
the governance chain, not a name somebody typed, and a test asserts that the only module
which calls it is `governance/board.py`. The register is append-only for the same reason
the skill register is: what was approved, by whom, is a record, and a record you can edit
is a record of nothing.

The file is not committed. A clone has nothing registered, which is the honest state -
nobody at the firm has approved a workflow yet - and `load_recipe` says so rather than
running something on a client's numbers because it happened to be in the repo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from registries.digests import digest_of, text_bytes
from registries.errors import RECIPE_UNREGISTERED, DiagnosticError, diagnose

__all__ = [
    "REGISTERED_FILE",
    "RecipeRegister",
    "RecipeState",
    "RegisteredRecipe",
    "RegistrationRefused",
    "digest_of_recipe",
]

REPO_ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = REPO_ROOT / "recipes"
REGISTERED_FILE = RECIPES_DIR / "registered.yaml"


def digest_of_recipe(path: Path) -> str:
    """The digest of a recipe file, over the same normalised bytes every registry uses."""
    return digest_of(text_bytes(path))


class RegistrationRefused(DiagnosticError):
    """No approval, no approver, or a version already registered."""


@dataclass(frozen=True)
class RegisteredRecipe:
    name: str
    version: int
    digest: str
    registered_at: str
    approved_by: str
    decision_ref: str
    """Where the approval is in the governance record. A registration whose approval
    cannot be found is a registration nobody can audit."""

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass(frozen=True)
class RecipeState:
    """A recipe on disk, and what the register says about it.

    `registered` - this exact file was approved and may run.
    `edited` - the name was approved once, but not these bytes. Somebody changed the
    workflow after the board saw it, which is the case this exists for.
    `unregistered` - nobody has approved it.
    """

    name: str
    digest: str
    state: str
    approved_by: str = ""
    unbuilt: tuple[str, ...] = ()
    """Skills this recipe names that have no mechanical half yet.

    Approval and buildability are different questions and this build kept only the first.
    Three of the four recipes on disk end at `qc-tieout`, which is frontmatter and no
    procedure, so a run reaches it, raises "the skill has no mechanical half yet" and
    stops - after paying a real provider for every step before it. The admin surface
    offered them beside the one that works, labelled identically, and pre-selected one of
    them.

    Derived from `PROCEDURES` rather than listed, because a list of what is not built yet
    is a list that is wrong the day somebody builds one."""

    @property
    def can_finish(self) -> bool:
        return not self.unbuilt
    registered_at: str = ""

    @property
    def runnable(self) -> bool:
        return self.state == "registered"


def unbuilt_skills(path: Path) -> tuple[str, ...]:
    """The skills a recipe names that nothing can dispatch.

    Read from the file rather than from a compiled plan: this answers a question the admin
    surface asks about every recipe on disk, including ones no engagement has resolved and
    ones that would not compile for any scope. A recipe that cannot even be parsed has no
    skills to check and is somebody else's refusal.
    """
    from harness.procedures import PROCEDURES  # noqa: PLC0415

    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 - an unreadable recipe is `load_recipe`'s refusal
        return ()
    named = [
        str(step["skill"])
        for step in (doc.get("steps") or [])
        if step.get("kind") == "skill" and step.get("skill")
    ]
    return tuple(dict.fromkeys(s for s in named if s.split("@", 1)[0] not in PROCEDURES))


class RecipeRegister:
    def __init__(self, path: Path = REGISTERED_FILE, root: Path = RECIPES_DIR) -> None:
        self.path = path
        self.root = root

    # -- reading

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        return list(raw.get("registered", []))

    def registered(self) -> tuple[RegisteredRecipe, ...]:
        return tuple(
            RegisteredRecipe(
                name=str(row["name"]),
                version=int(row["version"]),
                digest=str(row["digest"]),
                registered_at=str(row["registered_at"]),
                approved_by=str(row["approved_by"]),
                decision_ref=str(row["decision_ref"]),
            )
            for row in self._load()
        )

    def digests(self) -> frozenset[str]:
        """The run-time interface: a set of hashes, so the check on the path every run
        takes cannot be slow and cannot be wrong about a file it has already seen."""
        return frozenset(row.digest for row in self.registered())

    def is_registered(self, digest: str) -> bool:
        return digest in self.digests()

    def entry(self, digest: str) -> RegisteredRecipe | None:
        return next((row for row in self.registered() if row.digest == digest), None)

    def files(self) -> tuple[Path, ...]:
        return tuple(
            p for p in sorted(self.root.glob("*.yaml")) if p.stem != REGISTERED_FILE.stem
        )

    def review(self) -> tuple[RecipeState, ...]:
        """Every recipe on disk against the register. What an admin surface shows, and
        what preflight reads."""
        approved = {row.name for row in self.registered()}
        out: list[RecipeState] = []
        for path in self.files():
            digest = digest_of_recipe(path)
            found = self.entry(digest)
            if found is not None:
                out.append(
                    RecipeState(
                        name=path.stem,
                        digest=digest,
                        state="registered",
                        approved_by=found.approved_by,
                        registered_at=found.registered_at,
                        unbuilt=unbuilt_skills(path),
                    )
                )
            else:
                out.append(
                    RecipeState(
                        name=path.stem,
                        digest=digest,
                        state="edited" if path.stem in approved else "unregistered",
                        unbuilt=unbuilt_skills(path),
                    )
                )
        return tuple(out)

    def require(self, name: str, digest: str) -> RegisteredRecipe:
        """The gate. Refuses with what to do rather than with what is missing."""
        found = self.entry(digest)
        if found is not None:
            return found
        approved_before = [row for row in self.registered() if row.name == name]
        detail = (
            f"{name} was registered at version "
            f"{', '.join(str(r.version) for r in approved_before)}, but this is not that "
            f"file - it was edited after the board approved it"
            if approved_before
            else f"{name} has never been approved for client work"
        )
        raise RegistrationRefused(
            diagnose(
                RECIPE_UNREGISTERED,
                detail,
                locator=f"recipes/{name}.yaml",
                expected="a digest recorded in the recipe register",
                found=digest,
            )
        )

    # -- writing, which only the board does

    def register(
        self,
        path: Path,
        *,
        version: int,
        approved_by: str,
        decision_ref: str,
    ) -> RegisteredRecipe:
        """Record that the board approved this exact file.

        Called by `governance.board.SkillBoard.register_recipe` and by nothing else, which
        a test holds to. `decision_ref` is where the approval sits in the governance
        record: a registration whose approval cannot be found is a registration nobody can
        audit, and an approver typed into a form is not an approval.
        """
        if not approved_by.strip():
            raise ValueError("a registration names the person who approved it")
        if not decision_ref.strip():
            raise ValueError("a registration carries the approval it rests on")

        digest = digest_of_recipe(path)
        existing = self.entry(digest)
        if existing is not None:
            return existing

        name = path.stem
        if any(r.name == name and r.version == version for r in self.registered()):
            raise RegistrationRefused(
                diagnose(
                    RECIPE_UNREGISTERED,
                    f"{name}@{version} is already registered against different bytes; a "
                    f"change to a workflow is a new version and a new review",
                    locator=f"recipes/{name}.yaml",
                    expected="a version nobody has registered",
                    found=f"{name}@{version}",
                )
            )

        record = RegisteredRecipe(
            name=name,
            version=version,
            digest=digest,
            registered_at=datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            approved_by=approved_by.strip(),
            decision_ref=decision_ref.strip(),
        )
        rows = self._load()
        rows.append(
            {
                "name": record.name,
                "version": record.version,
                "digest": record.digest,
                "registered_at": record.registered_at,
                "approved_by": record.approved_by,
                "decision_ref": record.decision_ref,
            }
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "# Registered recipes: the workflows approved to run on client work. Written\n"
            "# only by governance/board.py, only from a recorded approval. Append-only: an\n"
            "# entry is never edited or removed, and an edited recipe stops matching.\n"
            + yaml.safe_dump({"registered": rows}, sort_keys=False),
            encoding="utf-8",
        )
        return record
