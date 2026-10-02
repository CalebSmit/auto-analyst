"""C50 - The check that can be believed

Proves:
The reachability scan's verdict matches what actually happens: a module it calls
reachable really is reached, and one it excuses is noticed the moment production touches
it.

This checkpoint is not written yet. It is written at the end of P82,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P82")
def test_c50_integration():
    raise NotImplementedError
