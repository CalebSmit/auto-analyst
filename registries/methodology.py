"""Methodology: cleared once by a person, checked by a hash on every run.

`foundations/` is the firm's reference material - how we do this work - and it reaches
every model call unconditionally. That makes it the one input nothing ever checks against
the engagement it is being read for. The outbound payload scan knows only the current
engagement's identifiers, so a worked example quoting a real deal, pasted into a
methodology file by somebody being helpful, would reach every prompt for every client and
nothing in this system would notice.

**A clearance, not a live scan.** A file is scanned once, as a recorded act with a name
attached, and its digest is written here. At run time the Context Builder does a set
lookup on that digest. Both halves of that ordering are deliberate:

- A regex over methodology at run time would mean one broad pattern takes a practice
  group offline in the middle of the working day. A false positive at clearance time is
  somebody re-reading a paragraph; the same false positive at run time is an outage.
- A warning at clearance time is a warning nobody reads. This refuses.

**An edit loses its clearance for free**, because the digest changes and the new bytes are
not in the register. There is no path where a file is cleared, edited, and still attached
- which is the property that makes clearing once safe at all.

The register is append-only, like `skills/registered.yaml`, and for the same reason: what
was cleared, by whom, is a record, and a record you can edit is a record of nothing. It is
not committed. A clone has nothing cleared, which is the honest starting state - nobody at
the firm has read these files yet - and preflight says so before a run finds out.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from registries.errors import (
    METHODOLOGY_UNSAFE,
    DiagnosticError,
    diagnose,
)

__all__ = [
    "CLEARED_FILE",
    "FOUNDATIONS_DIR",
    "ClearanceRefused",
    "ClearedFile",
    "MethodologyFile",
    "MethodologyRegister",
    "digest_of",
]

REPO_ROOT = Path(__file__).resolve().parents[1]
FOUNDATIONS_DIR = REPO_ROOT / "foundations"
CLEARED_FILE = FOUNDATIONS_DIR / "cleared.yaml"

SKIP = frozenset({"readme.md"})
"""Files in the folder that are not methodology. The README describes the folder; it is
not attached to anything, so clearing it would be recording a decision nobody made."""


def digest_of(body: bytes) -> str:
    """The same spelling the Context Builder frames each section with, so the register and
    the assembled bytes agree by construction rather than by convention."""
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


class ClearanceRefused(DiagnosticError):
    """The file carries something that must not reach every prompt, or nobody signed."""


@dataclass(frozen=True)
class ClearedFile:
    """One recorded clearance. The digest is the part that matters at run time; the rest
    is so a person can answer "who decided this, and when" without asking anyone."""

    name: str
    digest: str
    cleared_at: str
    cleared_by: str
    size_bytes: int


@dataclass(frozen=True)
class MethodologyFile:
    """A file on disk, and what the register says about it.

    `state` is one of:

    - `cleared` - this exact content was cleared, and is attached.
    - `edited` - the name was cleared once, but not these bytes. Somebody changed it after
      it was read, which is the case this whole module exists for.
    - `uncleared` - nobody has ever cleared it.
    """

    name: str
    digest: str
    state: str
    cleared_by: str = ""
    cleared_at: str = ""

    @property
    def attachable(self) -> bool:
        return self.state == "cleared"


class MethodologyRegister:
    def __init__(self, path: Path = CLEARED_FILE, root: Path = FOUNDATIONS_DIR) -> None:
        self.path = path
        self.root = root

    # -- reading

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        return list(raw.get("cleared", []))

    def cleared(self) -> tuple[ClearedFile, ...]:
        return tuple(
            ClearedFile(
                name=str(row["name"]),
                digest=str(row["digest"]),
                cleared_at=str(row["cleared_at"]),
                cleared_by=str(row["cleared_by"]),
                size_bytes=int(row["size_bytes"]),
            )
            for row in self._load()
        )

    def digests(self) -> frozenset[str]:
        """The whole run-time interface. A set of hashes, so the check on the hot path
        cannot be slow and cannot be wrong about content it has already seen."""
        return frozenset(row.digest for row in self.cleared())

    def is_cleared(self, digest: str) -> bool:
        return digest in self.digests()

    def entry(self, digest: str) -> ClearedFile | None:
        return next((row for row in self.cleared() if row.digest == digest), None)

    # -- what is on disk, and what the register says about it

    def files(self) -> tuple[Path, ...]:
        """The methodology files, in the order the Context Builder attaches them."""
        return tuple(p for p in sorted(self.root.glob("*.md")) if p.name.lower() not in SKIP)

    def review(self) -> tuple[MethodologyFile, ...]:
        """Every file on disk against the register. What preflight reports, and what an
        admin surface shows somebody deciding whether to clear something."""
        by_name = {row.name for row in self.cleared()}
        out: list[MethodologyFile] = []
        for path in self.files():
            digest = digest_of(path.read_bytes())
            found = self.entry(digest)
            if found is not None:
                out.append(
                    MethodologyFile(
                        name=path.name,
                        digest=digest,
                        state="cleared",
                        cleared_by=found.cleared_by,
                        cleared_at=found.cleared_at,
                    )
                )
            else:
                out.append(
                    MethodologyFile(
                        name=path.name,
                        digest=digest,
                        state="edited" if path.name in by_name else "uncleared",
                    )
                )
        return tuple(out)

    # -- clearing

    def scan(self, body: bytes, name: str) -> tuple[str, ...]:
        """Why this content must not reach every prompt, if it must not.

        Two scanners, the same two a dropped skill draft goes through, for the same two
        reasons: anything shaped like a real engagement's data, and anything shaped like
        an instruction aimed at the model reading it. Methodology is the more dangerous of
        the two documents, because a skill draft is read by one step and this is read by
        every step of every run.
        """
        from governance.conformance import find_client_data
        from guards.untrusted import UntrustedBoundary

        text = body.decode("utf-8", errors="replace")
        reasons = [f"{kind}: {found!r}" for kind, found in find_client_data(text)]
        result = UntrustedBoundary().check(text, source_id=digest_of(body), label=name)
        if not result.passed:
            reasons.extend(result.reasons)
        return tuple(reasons)

    def clear(self, path: Path, *, cleared_by: str) -> ClearedFile:
        """Read a file, scan it, and record that a person cleared this exact content.

        Refuses a blank name. "Cleared by nobody" is the state this register exists to
        make impossible, and a default would quietly reintroduce it.
        """
        if not cleared_by.strip():
            raise ValueError("a clearance names the person who gave it")
        body = path.read_bytes()
        digest = digest_of(body)

        reasons = self.scan(body, path.name)
        if reasons:
            raise ClearanceRefused(
                diagnose(
                    METHODOLOGY_UNSAFE,
                    f"{path.name} carries {len(reasons)} thing(s) that must not reach "
                    f"every prompt: " + "; ".join(reasons[:4]),
                    locator=path.name,
                    expected="methodology with no engagement data and no instructions in it",
                    found="; ".join(reasons[:4]),
                )
            )

        existing = self.entry(digest)
        if existing is not None:
            return existing

        record = ClearedFile(
            name=path.name,
            digest=digest,
            cleared_at=datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            cleared_by=cleared_by.strip(),
            size_bytes=len(body),
        )
        rows = self._load()
        rows.append(
            {
                "name": record.name,
                "digest": record.digest,
                "cleared_at": record.cleared_at,
                "cleared_by": record.cleared_by,
                "size_bytes": record.size_bytes,
            }
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "# Cleared methodology. Written only by registries/methodology.py, only when a\n"
            "# person clears a file that scanned clean. Append-only: an entry is never\n"
            "# edited or removed, and an edited file simply stops matching.\n"
            + yaml.safe_dump({"cleared": rows}, sort_keys=False),
            encoding="utf-8",
        )
        return record
