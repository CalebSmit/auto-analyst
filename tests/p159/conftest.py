"""Fixtures for P159, taken from P17 rather than written again.

The real boundary, the real store, a started run - the same machinery every phase that reads
a file through `read_source` uses. Re-exported rather than copied, because two sets of these
would be two things that have to agree about what a run is, and the second would drift.
"""

from __future__ import annotations

from tests.p17.conftest import (  # noqa: F401 - re-exported as fixtures
    boundary,
    bus,
    contracts,
    parse_store,
    started,
    store,
)
