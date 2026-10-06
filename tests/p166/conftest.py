"""Fixtures for P166, taken from P156 and P17 rather than written again."""

from __future__ import annotations

from tests.p156.conftest import kit  # noqa: F401 - re-exported as a fixture
from tests.p17.conftest import (  # noqa: F401 - re-exported as fixtures
    boundary,
    bus,
    contracts,
    parse_store,
    started,
    store,
)
