"""C30 - A machine that can be started

Proves:
A workflow can be approved from /admin by a named person with a recorded reason, through
the board and into the governance chain, so a clean clone goes from nothing-will-run to
something-will - and the register is still written by nothing but the board, still not
committed, and still refuses a recipe edited since somebody read it.

This checkpoint is not written yet. It is written at the end of P57,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P57")
def test_c30_integration():
    raise NotImplementedError
