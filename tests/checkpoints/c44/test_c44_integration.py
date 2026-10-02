"""C44 - Two engines, one real document, and a rule widened on purpose

Proves:
Every registered OCR engine is local, reaches no model and no network, and can be built
on a machine that has installed none of them; none of them silently falls back to
another, so a scan is never read by an engine nobody chose; the real filing is still
read and the comparative-column defect it found is pinned along with the escalation that
is the only thing stopping a run on it; and widening the fixtures rule to allow a public
document did not loosen what it always forbade - no client data, a named public source,
and the identifier register checking the fixture like anything else.

This checkpoint is not written yet. It is written at the end of P76,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P76")
def test_c44_integration():
    raise NotImplementedError
