"""C41 - The retry path, joined at both ends

Proves:
The class the adapter raises is the class the executor catches and it belongs to the
port so both can see it; something in production raises it, checked the way the gap was
found; the executor's retry loop, its event and its exhaustion code are all still there;
transient and permanent remain different questions; and the fact that no rehearsal could
have caught this - the fake and scripted adapters have no network - is recorded where
somebody trusting a clean rehearsal will meet it.

This checkpoint is not written yet. It is written at the end of P72,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P72")
def test_c41_integration():
    raise NotImplementedError
