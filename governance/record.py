"""The Governance Record: every submission, decision and registration, permanently.

Answers the question a firm should always be able to answer about an automated system:
what does it do, who decided it could, and when.

Append-only, and not by convention. There is no method here that edits or removes an
entry, entries are written with an open-append and a flush, and every entry carries the
hash of the one before it - so an edit made outside this module leaves a break that
`verify()` finds and names. The run store gets the same guarantee from database triggers;
this store is a file in a governance scope, so the chain is what makes the guarantee
survive a text editor.

It lives outside the repo by default, beside the drop folder, for the same reason the
drop folder does: a draft can carry a pasted trial balance, and the scan that catches
that runs *after* the drop. Nothing about governance belongs in a git history.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from governance.candidate import STAGES, Candidate, Stage

__all__ = ["Entry", "GovernanceRecord", "RecordBroken", "intake_root"]

ENV_ROOT = "AA_SKILLS_INTAKE_ROOT"
RECORD_NAME = "governance.jsonl"
GENESIS = "sha256:" + "0" * 64


class RecordBroken(RuntimeError):
    """The hash chain does not hold: an entry was edited or removed outside this module."""


def intake_root(root: Path | str | None = None) -> Path:
    """Where governance keeps its working files. Never inside the repo.

    A dropped draft is untrusted content from outside the system - that is the whole
    premise of the conformance scan - so the one place it must not land is a directory
    somebody might commit.
    """
    if root is not None:
        return Path(root)
    named = os.environ.get(ENV_ROOT)
    if named:
        return Path(named)
    return Path.home() / ".automated-analyst" / "skills-intake"


@dataclass(frozen=True)
class Entry:
    seq: int
    at: str
    candidate: str
    stage: str
    actor: str
    """Who or what did it. A person's name for a decision, a node id for a machine step."""
    ref: str = ""
    """What it produced: a content hash, a scorecard key, a decision id."""
    detail: Mapping[str, Any] = None  # type: ignore[assignment]
    prev: str = GENESIS
    hash: str = ""

    def body(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "at": self.at,
            "candidate": self.candidate,
            "stage": self.stage,
            "actor": self.actor,
            "ref": self.ref,
            "detail": dict(self.detail or {}),
            "prev": self.prev,
        }

    def digest(self) -> str:
        body = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(body).hexdigest()

    def line(self) -> str:
        return f"{self.seq:>4} {self.at} {self.candidate} {self.stage:<11} {self.actor}"


class GovernanceRecord:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = intake_root(root)
        self.path = self.root / "_record" / RECORD_NAME

    def __repr__(self) -> str:
        return f"GovernanceRecord({self.path})"

    # -- writing

    def append(
        self,
        candidate: str,
        stage: Stage | str,
        actor: str,
        ref: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> Entry:
        """One entry. There is no counterpart, here or anywhere else."""
        if not str(actor).strip():
            raise ValueError("a governance entry names who or what did it")
        existing = self.entries()
        entry = Entry(
            seq=len(existing) + 1,
            at=_stamp(),
            candidate=candidate,
            stage=str(stage),
            actor=str(actor).strip(),
            ref=ref,
            detail=dict(detail or {}),
            prev=existing[-1].hash if existing else GENESIS,
        )
        entry = Entry(**{**entry.__dict__, "hash": entry.digest()})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**entry.body(), "hash": entry.hash}) + "\n")
        return entry

    # -- reading

    def entries(self, candidate: str | None = None) -> tuple[Entry, ...]:
        if not self.path.is_file():
            return ()
        rows = [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        found = tuple(
            Entry(
                seq=int(r["seq"]),
                at=str(r["at"]),
                candidate=str(r["candidate"]),
                stage=str(r["stage"]),
                actor=str(r["actor"]),
                ref=str(r.get("ref", "")),
                detail=dict(r.get("detail") or {}),
                prev=str(r.get("prev", GENESIS)),
                hash=str(r.get("hash", "")),
            )
            for r in rows
        )
        return tuple(e for e in found if candidate is None or e.candidate == candidate)

    def verify(self) -> None:
        """Walk the chain. An edited or removed entry breaks it, and this says where."""
        prev = GENESIS
        for n, entry in enumerate(self.entries(), start=1):
            if entry.seq != n:
                raise RecordBroken(f"entry {n} is numbered {entry.seq}: an entry was removed")
            if entry.prev != prev:
                raise RecordBroken(f"entry {entry.seq} does not follow entry {entry.seq - 1}")
            if entry.hash != entry.digest():
                raise RecordBroken(f"entry {entry.seq} was edited after it was written")
            prev = entry.hash

    def evidence(self, candidate: str) -> dict[str, str]:
        """Stage to reference, latest wins. What the chain reads to decide what may
        happen next - so a candidate's position is a fact about the record rather than
        about an object somebody is holding."""
        found: dict[str, str] = {}
        for entry in self.entries(candidate):
            if entry.stage in {str(s) for s in STAGES}:
                found[entry.stage] = entry.ref or entry.hash
        return found

    def candidate(self, candidate_id: str) -> Candidate | None:
        """Rebuild a candidate from the record alone."""
        entries = self.entries(candidate_id)
        if not entries:
            return None
        detail: dict[str, Any] = {}
        for entry in entries:
            detail.update(entry.detail or {})
        return Candidate(
            id=candidate_id,
            name=str(detail.get("name", candidate_id)),
            source_hash=str(detail.get("source_hash", "")),
            version=str(detail.get("version", "")),
            layer=str(detail.get("layer", "")),
            evidence=self.evidence(candidate_id),
            detail=detail,
        )

    def candidates(self) -> tuple[str, ...]:
        seen: list[str] = []
        for entry in self.entries():
            if entry.candidate not in seen:
                seen.append(entry.candidate)
        return tuple(seen)

    def report(self, candidate: str | None = None) -> str:
        return "\n".join(e.line() for e in self.entries(candidate)) or "(nothing recorded)"


def _stamp() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
