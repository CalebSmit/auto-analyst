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
