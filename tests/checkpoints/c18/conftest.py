"""C18 runs against P17's world: the readers over real bytes, writing a real parse store.

Nothing is rebuilt. The point of a checkpoint is that the pieces meet.
"""

from __future__ import annotations

from tests.p17 import conftest as p17

boundary = p17.boundary
bus = p17.bus
contracts = p17.contracts
parse_store = p17.parse_store
started = p17.started
store = p17.store
