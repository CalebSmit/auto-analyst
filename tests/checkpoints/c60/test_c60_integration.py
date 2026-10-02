"""C60 - The gate's own arithmetic

Proves:
That the gate orders phases and checkpoints by number wherever it compares two, that its
four safety nets - coverage, closing in order, what is owed, and a red checkpoint
blocking the next phase - all still fire at three digits, and that the tests which check
the gate do not carry the same assumption.

This checkpoint is not written yet. It is written at the end of P100,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P100")
def test_c60_integration():
    raise NotImplementedError
