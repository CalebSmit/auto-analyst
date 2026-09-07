"""Fixtures for P32. The whole environment from P24/P29, and a second engagement under
the same watch - because "two engagements under one watch run different recipes" is not a
claim you can make with one."""

from __future__ import annotations

from typing import Any

import pytest

from intake.roster import ProjectRoster, RosterEntry
from tests.p29 import conftest as p29

HEND = p29.HEND
NOVK = p29.NOVK
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


@pytest.fixture
def novak(console: Any, henderson: Any) -> RosterEntry:
    """A second engagement on the same watch as Henderson, in the same practice group.
    Nothing distinguishes them but the folder they arrive in."""
    return console.register_engagement(
        p29.entry(
            NOVK,
            client="Novak Industrial",
            folder="Novak Industrial/2026 ESOP",
        ),
        profile=p29.profile_for(NOVK),
        who=WHO,
        reason="second engagement on the same watch",
    )


@pytest.fixture
def both(roster: ProjectRoster, henderson: Any, novak: Any) -> tuple[str, str]:
    return (HEND, NOVK)
