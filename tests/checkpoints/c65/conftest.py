"""Borrow P21's world. Imported rather than declared with `pytest_plugins`, which
registers the same module twice when both suites run in one session."""

from tests.p21.conftest import *  # noqa: F403
