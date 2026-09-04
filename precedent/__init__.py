"""The Precedent Store and its one writer.

`store.py` is the resource: approved, masked tagging decisions, retrieved scope-built.
`writeback.py` is the step: the only code path that puts a row in it, and it starts from
a decision id and nothing else.
"""

from __future__ import annotations

from precedent.store import PrecedentRecord, PrecedentStore
from precedent.writeback import PrecedentWriteback, WritebackRefused

__all__ = ["PrecedentRecord", "PrecedentStore", "PrecedentWriteback", "WritebackRefused"]
