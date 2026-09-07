"""C13 - The system runs

Proves:
A file landing in a watched folder becomes a deliverable in the outbox, with nothing
in the path that exists only in a test

This checkpoint is not written yet. It is written at the end of P35,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P35")
def test_c13_integration():
    raise NotImplementedError
