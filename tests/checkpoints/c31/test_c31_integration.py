"""C31 - What a person is told to type

Proves:
Every command the guide and the session rules give works from a fresh shell, the one
tool that must not need the environment still does not, and a tool run without it names
the command to type instead of raising somebody else's ImportError five hundred lines
in.

This checkpoint is not written yet. It is written at the end of P58,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P58")
def test_c31_integration():
    raise NotImplementedError
