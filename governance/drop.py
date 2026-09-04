"""The Skill Drop Folder: the one folder a person touches, and nothing is demanded of it.

Drafts written anywhere - in Claude, in a text editor, in a colleague's notes - land here
exactly as they are. No frontmatter, no schema, no scope, no fixtures. Anything dropped is
copied, hashed and moved into triage; **the original is left untouched**, so nobody loses
work by contributing.

Making the front door frictionless is deliberate. If conforming to the contract were a
prerequisite for contributing, people would stop contributing and start working around the
system, which is worse than a messy inbox. The rigour is applied after the drop.

The folder is not in the repo and its default root is outside it. A draft is untrusted
content from outside the system - somebody will paste a real trial balance into an example
sooner or later - and the scan that catches that runs after the drop, not before it.
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from governance.candidate import Stage
from governance.record import GovernanceRecord, intake_root

__all__ = ["DROP_DIR", "TRIAGE_DIR", "Dropped", "DropFolder"]

DROP_DIR = "_drop"
TRIAGE_DIR = "_triage"
NODE = "skill_drop"
READABLE = {".md", ".markdown", ".txt", ".yaml", ".yml", ".json"}


@dataclass(frozen=True)
class Dropped:
    """One draft, copied out of the drop folder and hashed."""

    candidate_id: str
    filename: str
    source_hash: str
    path: Path
    """Where the copy lives in triage. The original is still in the drop folder."""

    def text(self) -> str:
        return self.path.read_text(encoding="utf-8", errors="replace")


class DropFolder:
    def __init__(self, record: GovernanceRecord, root: Path | str | None = None) -> None:
        self.record = record
        self.root = intake_root(root)
        self.drop = self.root / DROP_DIR
        self.triage = self.root / TRIAGE_DIR

    def __repr__(self) -> str:
        return f"DropFolder({self.drop})"

    def waiting(self) -> tuple[Path, ...]:
        """What is sitting in the drop folder right now."""
        if not self.drop.is_dir():
            return ()
        return tuple(
            sorted(p for p in self.drop.iterdir() if p.is_file() and p.suffix.lower() in READABLE)
        )

    def take(self, path: Path, dropped_by: str) -> Dropped:
        """Copy, hash, record. Never move: the contributor keeps their file."""
        data = path.read_bytes()
        source_hash = "sha256:" + hashlib.sha256(data).hexdigest()
        candidate_id = f"cand_{source_hash.removeprefix('sha256:')[:12]}"
        self.triage.mkdir(parents=True, exist_ok=True)
        target = self.triage / f"{candidate_id}{path.suffix.lower()}"
        shutil.copy2(path, target)
        self.record.append(
            candidate_id,
            Stage.DROPPED,
            actor=dropped_by,
            ref=source_hash,
            detail={
                "name": path.stem,
                "source_hash": source_hash,
                "filename": path.name,
                "bytes": len(data),
                "node": NODE,
            },
        )
        return Dropped(
            candidate_id=candidate_id, filename=path.name, source_hash=source_hash, path=target
        )

    def sweep(self, dropped_by: str) -> tuple[Dropped, ...]:
        """Everything waiting, taken in filename order. Idempotent by content: dropping
        the same bytes twice is the same candidate, and the record shows both drops."""
        return tuple(self.take(path, dropped_by) for path in self.waiting())

    def originals(self) -> Iterator[Path]:
        """What is still in the drop folder. Used by the test that proves nothing here
        moves or deletes a contributor's file."""
        yield from self.waiting()
