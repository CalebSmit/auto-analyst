"""The P24 world - a real admin console over a real configuration - reused, not rebuilt.

The same re-export `tests/p43/setup/conftest.py` makes, and for the same reason: `stage`
goes through `AdminConsole.add_file`, so the thing to test it against is a real console
over a real engagement with a real folder, and there is one of those already.
"""

from __future__ import annotations

from tests.p24 import conftest as p24

clock = p24.clock
config = p24.config
console = p24.console
constraints = p24.constraints
contracts = p24.contracts
environment = p24.environment
henderson = p24.henderson
preflight = p24.preflight
roster = p24.roster
store = p24.store
templates = p24.templates
