"""C86 - One reader, two kinds of page

Proves:
A scanned page and the same page's text layer produce the same rows, the same figures
and the same arithmetic cover, the whole filing's measured counts still hold, and every
figure that re-adds does so when its rows are added again independently.

This checkpoint is not written yet. It is written at the end of P155,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P155")
def test_c86_integration():
    raise NotImplementedError
