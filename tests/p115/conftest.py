"""Borrow P21's world: the only place a real template, a real mapping and a real workbook
come together.

Imported rather than declared with `pytest_plugins`, which registers the same module as a
plugin twice when both suites run in one session and fails collection outright.
"""

from tests.p21.conftest import *  # noqa: F403
