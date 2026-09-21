"""The Storage Port: one interface, three sources.

`list()`, `read()`, `stat()`. Nothing downstream knows or cares where a file came from,
which is what lets phase 1 run on a laptop with no credentials and the same code run
against ShareFile later without a rewrite.

This is the portability argument in one module. No cloud has been sanctioned at work
yet, so the only responsible move is to make the choice reversible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class FileRef:
    """Where a file is, in terms this port understands.

    A path relative to the port's root, never an absolute one: an absolute path is a
    fact about this machine, and the whole point of the port is that downstream code
    holds no such facts.
    """

    path: str

    def __post_init__(self) -> None:
        if not self.path or self.path.startswith("/") or ".." in self.path.split("/"):
            raise ValueError(f"not a port-relative path: {self.path!r}")


@dataclass(frozen=True)
class FileStat:
    """What is known about a file without reading it."""

    ref: FileRef
    size_bytes: int
    modified_at: datetime
    content_hash: str
    """sha256:... - the id every figure read from this file will cite."""


@dataclass(frozen=True)
class Deposit:
    """What a relayed copy did. Three outcomes, and they are not the same thing."""

    path: str
    content_hash: str
    outcome: str
    """`copied` - nothing was there. `skipped` - these exact bytes already were, so
    nothing was written. `resent` - something else was there under that name, which is a
    client sending a second version and the one case a person has to look at."""

    size_bytes: int = 0


COPIED = "copied"
SKIPPED = "skipped"
RESENT = "resent"


@runtime_checkable
class ReceivingStorage(Protocol):
    """A store the relay may copy *into*. Deliberately not part of `StoragePort`.

    The read side is three methods and stays three methods: a port that could write would
    make "this is the read side of intake" a comment rather than a fact. So the ability to
    receive is a second, separate protocol, and an adapter has it only if it says so.

    The useful consequence is structural. `ShareFileStorage` does not implement this, so
    the relay - which reads ShareFile and writes Box - **cannot** write back to its own
    source even by mistake. "Nothing is ever deleted from ShareFile" stops being a rule
    somebody has to keep and becomes a thing there is no method for.

    This is not the Delivery Port and must not become it. Delivery has two inbound edges,
    released artifacts and the run manifest, and a client's trial balance is neither. What
    arrives here is material on its way *into* intake, which is the opposite direction.
    """

    name: str

    def deposit(self, path: str, data: bytes) -> Deposit:
        """Put these bytes at that path, and say what that turned out to mean.

        Never a silent overwrite. Identical bytes already there are `skipped` and nothing
        is written; different bytes under the same name are `resent` and the destination's
        own versioning keeps both, because a client re-sending a statement is information
        rather than a collision to resolve.
        """
        ...


@runtime_checkable
class StoragePort(Protocol):
    """The read side of intake.

    Deliberately three methods. Every source can implement these; anything richer would
    be a fact about one source leaking into the interface.
    """

    name: str

    def list(self, prefix: str = "") -> tuple[FileRef, ...]:
        """Every file under prefix, in a stable order. Order matters: a sweep that
        returns files in filesystem order produces a different run every time."""
        ...

    def read(self, ref: FileRef) -> bytes:
        """The bytes. Unreadable is INTAKE.UNREADABLE_FILE, never an empty result."""
        ...

    def stat(self, ref: FileRef) -> FileStat:
        """Size, mtime and content hash, without reading the file into the caller."""
        ...
