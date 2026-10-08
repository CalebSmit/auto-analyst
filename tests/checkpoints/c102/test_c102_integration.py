"""C102 - Checks a clean machine can pass

Proves:
Every check this build runs is one a machine with nothing but the tracked files can
pass, and pass again tomorrow: nothing generated under BUILD carries the day it was
generated, the surface collector answers the same thing with no approval register
present as with one, every read of a path the image does not ship is guarded by a
question about that same path rather than about some other absence, and a failure inside
the image names the test that failed.

This checkpoint is not written yet. It is written at the end of P177,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P177")
def test_c102_integration():
    raise NotImplementedError
