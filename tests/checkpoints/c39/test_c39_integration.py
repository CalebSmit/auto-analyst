"""C39 - The gate reports a failure rather than becoming one

Proves:
A real check that fails with output the console cannot encode is still reported, as a
failure, with its text intact and the unencodable character replaced; the gate runs as a
process under that console encoding without a traceback; a passing check still reads as
passing; and no phase sits past the last checkpoint.

This checkpoint is not written yet. It is written at the end of P70,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P70")
def test_c39_integration():
    raise NotImplementedError
