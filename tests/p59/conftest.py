"""Fixtures for P59: P34's world, which is C07's.

A real store, bus, blobs, vault, meter, governor, guarded runtime, dispatcher, plan, scope
and parse store - not a fixture shaped to fit the question. A loop that only turns against
a double is the state this phase is fixing.
"""

from __future__ import annotations

from tests.p34.conftest import (  # noqa: F401
    CLIENT,
    ENGAGEMENT,
    RUN_ID,
    TAXONOMY,
    case,
    context,
    facts,
    runner_for,
    sources,
    world,
)
