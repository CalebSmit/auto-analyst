"""P84 fixtures: the real door, with the usage under the test's control.

The first version of this emitted `model.answered` itself, with the payload copied out of
`harness/door.py`. Every assertion about what the event carries then held against the copy
- reverting the door left them green - which is the defect this repo is named for, wearing
a fixture. So the door is the real one, `tests/p11`'s, and the only thing arranged is what
usage the port reports back.
"""

from typing import Any

import pytest

from tests.p11.conftest import *  # noqa: F401,F403
from tests.p11.conftest import Answers, masked_request


@pytest.fixture
def answered(door: Any, port: Answers, identifiers: Any, started: str) -> Any:
    """Send one real request through the real door, reporting the usage this test wants.

    Every call is on the one started run: what the breakdown reads is a run's events, and
    a second run would be a second set of them.
    """

    def call(usage: Any, run_id: str | None = None) -> str:
        port.usage = usage
        door.send(
            masked_request(), identifiers, run_id or started,
            step_id="tagging", estimated_cost_usd=0.01,
        )
        return run_id or started

    return call
