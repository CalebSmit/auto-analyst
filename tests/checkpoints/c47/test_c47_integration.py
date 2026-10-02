"""C47 - Setting up a repeat client, with everything that needs saying

Proves:
The newest configuration version is the one a write produces and every supported version
still loads; no version was edited in place, so 1.1.0 knows nothing of a recipe and
1.2.0 nothing of a prior model; an engagement naming no prior model is not upgraded
because another one was; a repeat engagement is told on the roster that it has not been
pointed at last year's workbook, and stops being told once it has; and the page is
handed which engagements are repeat rather than splitting a scope path itself.

This checkpoint is not written yet. It is written at the end of P79,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P79")
def test_c47_integration():
    raise NotImplementedError
