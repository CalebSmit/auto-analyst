"""C45 - The documents a person arrives at, agreeing with each other

Proves:
CLAUDE.md, the interview protocol, the using guide, the handoff packet and .env.example
still say the same thing about how to run it, about the setting that decides whether a
scanned page can be read, and about what version 1 is for; every adapter they name is
one the ports actually register; the shared vocabulary the protocol guard stands on
survived the rewrite; and every document a session is sent to read still exists.

This checkpoint is not written yet. It is written at the end of P77,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P77")
def test_c45_integration():
    raise NotImplementedError
