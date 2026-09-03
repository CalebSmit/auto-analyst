"""The Delivery Port: the write side, mirror of storage.

`ensure_folder()`, `put()`, `version()`. Two inbound edges only - released artifacts,
and the run manifest. The manifest goes through the same port as the deliverable, so
the record lands beside the work it describes rather than somewhere else entirely.

Between this and the Storage Port, moving from a laptop to whatever infrastructure work
eventually sanctions is two config lines and no changed logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PutResult:
    """What a write produced. Enough to prove it happened and to not repeat it."""

    path: str
    content_hash: str
    version: int
    """Destination-side versioning. Writing the same path twice does not destroy the
    first copy - immutability of the record comes from the destination, not from
    everyone remembering not to overwrite."""

    already_present: bool = False
    """True when the identical bytes were already at that path. A keyed retry after a
    transport failure lands here rather than producing a duplicate."""


@runtime_checkable
class DeliveryPort(Protocol):
    name: str

    def ensure_folder(self, path: str) -> None:
        """Make the destination exist. Idempotent."""
        ...

    def put(self, path: str, data: bytes) -> PutResult:
        """Write bytes and return what was written. Never silently overwrites: a repeat
        write of identical bytes is reported as already_present, and different bytes at
        the same path take a new version."""
        ...

    def version(self, path: str) -> int:
        """How many versions exist at that path. Zero if nothing has been written."""
        ...
