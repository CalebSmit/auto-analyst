"""C33 - A run that ends says so

Proves:
Every quarantined step leaves exactly one record whatever ending produced it, a resumed
pass over the same key does not write a second, and the three failure policies every
recipe declares finally mean three different things - review tells a person, quarantine
does not, halt ends the run through the one door that writes a manifest, which is the
driver's and never the executor's.

This checkpoint is not written yet. It is written at the end of P60,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P60")
def test_c33_integration():
    raise NotImplementedError
