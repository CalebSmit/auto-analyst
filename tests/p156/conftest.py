"""Fixtures for P156, taken from P17 rather than written again.

P17 built the machinery for reading a file through the real boundary - a store, a started
run, a parse store and an `UntrustedBoundary` - and this phase asks a question about the
same path. Re-exported rather than copied, because two sets of these would be two things
that have to agree about what a run is, and the second would drift.

The one thing added is `kit`, which collects them. `read_source` takes six keyword
arguments and every test here calls it; six parameters repeated down a file is how the one
that matters gets lost.
"""

from __future__ import annotations

import pytest

from tests.p17.conftest import boundary as boundary  # noqa: PLC0414 - same
from tests.p17.conftest import (  # noqa: F401 - re-exported as fixtures
    bus,
    contracts,
    parse_store,
    started,
    store,
)


@pytest.fixture
def kit(store, parse_store, boundary, started, bus) -> dict:  # noqa: F811
    return {
        "store": store,
        "parse_store": parse_store,
        "boundary": boundary,
        "started": started,
        "bus": bus,
    }
