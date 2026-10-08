"""C103 - What the remote finally proved

Proves:
The three things only a machine with services on it can check are checked, and the
checks are ones a clean machine can pass: the schema this store creates is the same
schema on both backends it claims, the bounds the jobs run under come from a run in
which nothing was skipped and are stated with their headroom, nothing generated carries
the day it was generated on, the surface collector answers the same thing with no
approval register as with one, and every read of a path the image does not ship asks
about that same path first.

This checkpoint is not written yet. It is written at the end of P178,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P178")
def test_c103_integration():
    raise NotImplementedError
