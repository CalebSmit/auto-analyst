"""C37 - The boundary, exercised rather than read

Proves:
A session walked end to end through the commands a person actually runs - status,
session, answers, acknowledgement, scan - reports what the record holds at every point:
the acknowledgement covers what it looked at and nothing logged after it, a standing one
cannot be silently replaced, status and scan never describe the same file differently, a
leaked identifier is named rather than raised on, and no command reaches the
repository's own knowledge folder.

This checkpoint is not written yet. It is written at the end of P66,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P66")
def test_c37_integration():
    raise NotImplementedError
