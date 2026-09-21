"""The relay: ShareFile to Box, because somebody pressed Update.

**Power Automate is the thing that does this automatically, and it stays outside the
boundary.** This is the backup - what gets pressed on the morning the automatic one has
not run, or has run and nobody is sure. That framing decides the whole design, because it
means the two will sometimes act on the same files, and the failure worth designing
against is not a copy that did not happen. He would see that. It is **two copiers
fighting**.

So the relay converges rather than competing:

* **Copy, never move.** Nothing is deleted from ShareFile. There is no method to do it
  with - `ShareFileStorage` does not implement `ReceivingStorage`, so the source cannot
  be written to at all, let alone emptied. If the relay is wrong about something, the
  original is still where the client put it.
* **Skip on identical content.** The same bytes already in Box are reported as skipped and
  nothing is written. Pressing Update after Power Automate already ran is a no-op that
  says so, rather than a second copy under a mangled name.
* **A re-send is surfaced, not resolved.** Different bytes under a name that already
  exists means the client sent a second version. That is the one case a person has to
  look at, so it is its own outcome and the destination's versioning keeps both.
* **Per file, and partial failure is named.** Nine of twelve copied is nine of twelve,
  with the three named. A relay that stopped at the first failure would leave somebody
  guessing which files made it, and a relay that reported "an error occurred" would be
  worse than one that did nothing.

**This is not a run.** It writes no run record, releases no deliverable, reaches no skill,
and nothing in a compiled graph can call it - a check in `tests/p90` holds that, because
the moment a graph step could move a client's files the whole argument about what the
graph guarantees would have a hole in it. It is an operator action, and the guarantees do
not apply to it precisely because it produces nothing anyone will rely on. What it leaves
behind is a report of what arrived, which is what the request-list tracker reads (B-054).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ports.storage import COPIED, RESENT, SKIPPED, FileRef
from registries.errors import DiagnosticError

__all__ = ["ARRIVED", "FAILED", "Moved", "RelayReport", "relay"]

FAILED = "failed"
ARRIVED = (COPIED, RESENT)
"""The two outcomes that mean a file is now in Box that was not, in the form it is in now.
`skipped` is not one: nothing arrived, because it was already there."""


@dataclass(frozen=True)
class Moved:
    """One file, and what happened to it."""

    path: str
    outcome: str
    """`copied`, `skipped`, `resent` or `failed`."""

    size_bytes: int = 0
    detail: str = ""

    @property
    def arrived(self) -> bool:
        return self.outcome in ARRIVED

    def line(self) -> str:
        return f"  {self.outcome:<8} {self.path}" + (f" - {self.detail}" if self.detail else "")


@dataclass(frozen=True)
class RelayReport:
    ran_at: str
    source: str
    destination: str
    moves: tuple[Moved, ...]

    @property
    def counts(self) -> dict[str, int]:
        out = {COPIED: 0, SKIPPED: 0, RESENT: 0, FAILED: 0}
        for move in self.moves:
            out[move.outcome] = out.get(move.outcome, 0) + 1
        return out

    @property
    def arrived(self) -> tuple[str, ...]:
        """What is now in Box that was not. The tracker's input."""
        return tuple(m.path for m in self.moves if m.arrived)

    @property
    def failures(self) -> tuple[Moved, ...]:
        return tuple(m for m in self.moves if m.outcome == FAILED)

    @property
    def complete(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, Any]:
        return {
            "ran_at": self.ran_at,
            "source": self.source,
            "destination": self.destination,
            "complete": self.complete,
            "counts": self.counts,
            "arrived": list(self.arrived),
            # Stated where the page can read it, because a screen showing "12 skipped" and
            # nothing else invites the reading that something went wrong.
            "means": "nothing was deleted from the source, and a skipped file was already "
            "there byte for byte - usually because Power Automate had already moved it",
            "moves": [
                {
                    "path": m.path,
                    "outcome": m.outcome,
                    "size_bytes": m.size_bytes,
                    "detail": m.detail,
                }
                for m in self.moves
            ],
        }

    def report(self) -> str:
        counts = self.counts
        head = (
            f"{self.source} -> {self.destination}: "
            f"{counts[COPIED]} copied, {counts[SKIPPED]} already there, "
            f"{counts[RESENT]} re-sent, {counts[FAILED]} failed  ({self.ran_at})"
        )
        return "\n".join([head, *(m.line() for m in self.moves)])


def relay(source: Any, destination: Any, prefix: str = "") -> RelayReport:
    """Copy everything under `prefix` from source to destination.

    `destination` has to satisfy `ReceivingStorage`; `source` only has to be a
    `StoragePort`. That asymmetry is the guarantee - the source is handed to something
    that has no way to write to it.
    """
    _refuse_a_destination_that_cannot_receive(destination)

    moves: list[Moved] = []
    try:
        found = source.list(prefix)
    except DiagnosticError as refused:
        # Listing failing is different from a file failing: there is nothing to report
        # per file, so the report carries the one failure rather than pretending to be a
        # complete pass over an empty folder.
        return RelayReport(
            ran_at=_now(),
            source=str(getattr(source, "name", "source")),
            destination=str(getattr(destination, "name", "destination")),
            moves=(Moved(prefix or "/", FAILED, detail=refused.diagnostic.detail),),
        )

    for ref in found:
        moves.append(_one(source, destination, ref))

    return RelayReport(
        ran_at=_now(),
        source=str(getattr(source, "name", "source")),
        destination=str(getattr(destination, "name", "destination")),
        moves=tuple(moves),
    )


def _one(source: Any, destination: Any, ref: FileRef) -> Moved:
    """One file. A failure here is recorded and the walk goes on.

    Carrying on is the decision worth defending: the alternative leaves somebody guessing
    which of twelve files made it across, and the files that *can* be copied are still
    worth copying. One that cannot is named, and stays named in the report.
    """
    try:
        data = source.read(ref)
    except DiagnosticError as refused:
        return Moved(ref.path, FAILED, detail=refused.diagnostic.detail)
    try:
        landed = destination.deposit(ref.path, data)
    except DiagnosticError as refused:
        return Moved(ref.path, FAILED, len(data), refused.diagnostic.detail)
    return Moved(ref.path, landed.outcome, landed.size_bytes)


def _refuse_a_destination_that_cannot_receive(destination: Any) -> None:
    """Said once, here, rather than as an AttributeError twenty files in.

    A half-finished relay is the worst outcome available: some files copied, the rest not,
    and a traceback instead of a report saying which.
    """
    if not callable(getattr(destination, "deposit", None)):
        raise TypeError(
            f"{type(destination).__name__} cannot receive a relayed copy: it does not "
            f"implement ReceivingStorage. The read side of a store is deliberately not "
            f"writable, which is why ShareFile cannot be a destination."
        )


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")
