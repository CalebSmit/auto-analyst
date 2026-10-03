"""C87 - What a run says it did with a file

Proves:
A document that cannot be opened ends the run with the file named rather than a library
exception, a format that is routed and not read still says to save it as something else,
and the rehearsal reports any case whose own file no reader ever looked at.

This checkpoint is not written yet. It is written at the end of P157,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P157")
def test_c87_integration():
    raise NotImplementedError
