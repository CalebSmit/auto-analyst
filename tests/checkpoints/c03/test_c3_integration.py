"""C3 - A run survives being killed

Proves:
Kill mid-flight, resume, zero completed steps re-execute, and plan assertions gate the
resume

This checkpoint is not written yet. It is written at the end of P09,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P09")
def test_c3_integration():
    raise NotImplementedError
