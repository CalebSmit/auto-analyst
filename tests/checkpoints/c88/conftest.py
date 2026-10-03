"""Fixtures for C88, taken from P17 rather than written again.

The real boundary, the real store, a started run - the same machinery every phase that reads
a file through `read_source` uses. Re-exported rather than copied, because two sets of these
would be two things that have to agree about what a run is, and the second would drift.
"""

from __future__ import annotations

import pytest

from tests.p17.conftest import (  # noqa: F401 - re-exported as fixtures
    boundary,
    bus,
    contracts,
    parse_store,
    started,
    store,
)


@pytest.fixture
def kit(store, parse_store, boundary, started, bus) -> dict:  # noqa: F811
    """Everything `read_source` needs, collected: it takes six keyword arguments and every
    test here calls it over every format in the table."""
    return {
        "store": store,
        "parse_store": parse_store,
        "boundary": boundary,
        "started": started,
        "bus": bus,
    }
