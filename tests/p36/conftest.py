"""Fixtures for P36: P29's whole environment, and the console over it.

Nothing new is built. The claim is about who a change is recorded against, so the right
subject is the console every other admin test uses.
"""

from __future__ import annotations

from tests.p29 import conftest as p29

HEND = p29.HEND
WHO = p29.WHO
clock = p29.clock
config = p29.config
console = p29.console
constraints = p29.constraints
contracts = p29.contracts
entry = p29.entry
environment = p29.environment
henderson = p29.henderson
preflight = p29.preflight
profile_for = p29.profile_for
roster = p29.roster
store = p29.store
templates = p29.templates
