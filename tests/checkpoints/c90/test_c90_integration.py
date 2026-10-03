"""C90 - Accuracy, measured and acted on

Proves:
Every figure the readers extract off three real filings is a figure the filer reported
at that column's own date, no row that was currency stopped being currency, and a row
whose label declares another unit reaches a figure at its own scale rather than the
statement's.

This checkpoint is not written yet. It is written at the end of P162,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P162")
def test_c90_integration():
    raise NotImplementedError
