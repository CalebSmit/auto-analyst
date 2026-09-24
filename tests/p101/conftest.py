"""Fixtures for P101.

P35's, reused whole. Standing a second copy of the run harness up beside it would be a
second place to be wrong about how a run is wired, and what this phase asks is whether a
run can finish rather than whether a test can build one.
"""

from __future__ import annotations

from tests.p35.conftest import constraints, driver_for, wiring, world

__all__ = ["constraints", "driver_for", "wiring", "world"]
