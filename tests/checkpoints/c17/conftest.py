"""C17 runs against P20's world: the EBITDA skill through a real dispatcher.

Nothing is rebuilt. The point of a checkpoint is that the pieces meet.
"""

from __future__ import annotations

from tests.p20 import conftest as p20

blobs = p20.blobs
bus = p20.bus
case = p20.case
constraints = p20.constraints
contracts = p20.contracts
controller = p20.controller
ebitda_step = p20.ebitda_step
parse_store = p20.parse_store
plan = p20.plan
policy = p20.policy
precedents = p20.precedents
queue = p20.queue
router = p20.router
scope = p20.scope
scopes = p20.scopes
started = p20.started
store = p20.store
surface = p20.surface
tree = p20.tree
world = p20.world
