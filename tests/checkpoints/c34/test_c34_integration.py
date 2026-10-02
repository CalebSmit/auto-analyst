"""C34 - The setup surface, used

Proves:
The two records a person creates during setup agree with each other and with the chain
behind them: approving bytes that are already approved says who did and writes nothing,
an edited file is still a second decision, neither register is committed, and the bar
the profile form offers is one somebody chose rather than a default nobody did.

This checkpoint is not written yet. It is written at the end of P61,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P61")
def test_c34_integration():
    raise NotImplementedError
