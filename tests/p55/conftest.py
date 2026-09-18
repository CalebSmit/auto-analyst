"""Fixtures for P55.

The executor fixtures are P08's, imported rather than copied: a compiled `monthly-refresh`
plan, a run in progress, a content store, and `executor_with` to put some other runner
behind it. One of the three findings in this phase is about what a quarantine records, and
the honest way to ask that is to drive a real `StepExecutor` over a real plan - which is
what P08 built these for.

Imported by name rather than through `pytest_plugins`, which pytest only honours in a
top-level conftest and which silently applied to the whole suite when it was tried here.
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
