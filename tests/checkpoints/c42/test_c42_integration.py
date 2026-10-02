"""C42 - Two scans for one defect, and the shape they share

Proves:
Both scans are quiet on the tree, so a failure means something new; neither has stopped
finding anything to look at; every excuse in either carries a reason; the two never
excuse the same thing, which would let a defect hide behind whichever was read first;
and the findings that paid for the scans - P55's precedent wiring, P60's on_failure,
P72's retry - are all still fixed.

This checkpoint is not written yet. It is written at the end of P73,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P73")
def test_c42_integration():
    raise NotImplementedError
