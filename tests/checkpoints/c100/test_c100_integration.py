"""C100 - Run rather than read

Proves:
Every tool in this repository reaches uv by asking which one is installed rather than
assuming, the image ships no compiled file from the machine that built it, and every
test that asks a question about the repository says so before it reads anything - with
the skip proved to fire only where there is no checkout, so the same tests still run on
a developer machine and in the verify job.

This checkpoint is not written yet. It is written at the end of P175,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P175")
def test_c100_integration():
    raise NotImplementedError
