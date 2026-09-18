"""Fixtures for P60: P08's executor world.

A compiled `monthly-refresh` plan, a run in progress, a content store, and `executor_with`
to put some other runner behind it. What this phase is about is what an ending leaves
behind, and the honest way to ask that is to drive a real executor to each ending.
"""

from __future__ import annotations

from tests.p08.conftest import (  # noqa: F401
    blobs,
    bus,
    contracts,
    executor_with,
    plan,
    run_inputs,
    started,
    store,
)
