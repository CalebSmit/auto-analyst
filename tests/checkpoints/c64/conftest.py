"""Borrow P21's world: the only place a real template, a real mapping and a real workbook
come together.

Imported rather than declared with `pytest_plugins`, which registers the same module as a
plugin twice when both suites run in one session and fails collection outright. An import
into a conftest is what pytest's own documentation suggests for sharing fixtures across
directories, and it is what the checkpoint runs need.
"""

from tests.p21.conftest import *  # noqa: F403
