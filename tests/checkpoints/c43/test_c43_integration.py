"""C43 - The scan is read here, and read before anything masks it

Proves:
Nothing on the OCR path can reach a model - not the port, not the adapters, not the
document reader that calls them - and privacy/ is still deterministic Python; the eighth
port is chosen by configuration and refuses an unknown name like the other seven; a
machine with no engine reads everything it always could and still reports a scan rather
than reading it as an empty page; and the adapter the analyst confirmed he can install
is registered and buildable without it, so a clone, a container and the work laptop are
the same code with different configuration.

This checkpoint is not written yet. It is written at the end of P74,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P74")
def test_c43_integration():
    raise NotImplementedError
