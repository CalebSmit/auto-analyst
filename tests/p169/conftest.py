"""Fixtures for P169, taken from P24: a whole environment behind the real ports, the
synthetic templates registered, a configuration document written through the store.
Re-exported rather than copied."""

from __future__ import annotations

from tests.p24.conftest import (  # noqa: F401 - re-exported as fixtures
    clock,
    config,
    constraints,
    contracts,
    environment,
    roster,
    store,
    templates,
)
