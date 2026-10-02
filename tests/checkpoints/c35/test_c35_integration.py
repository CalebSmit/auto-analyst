"""C35 - What a session is told, and whether it is still true

Proves:
Nothing in the open register asks a session to close a phase the plan says is closed,
run a checkpoint that is green, or obtain a sign-off that exists; every settled row
carries the date that settled it; and the documents a session is told to read all exist
and point at each other.

This checkpoint is not written yet. It is written at the end of P62,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P62")
def test_c35_integration():
    raise NotImplementedError
