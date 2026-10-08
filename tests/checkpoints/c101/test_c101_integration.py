"""C101 - Both backends, and the time to prove it

Proves:
Every DDL statement create_all would send to either backend is one that backend can
parse - no boolean column compared to a number in anything Postgres is sent, and the
SQLite trigger still comparing that flag the way SQLite compares booleans, so the two
cannot be flattened to one literal; the guarantee that only a human decision writes
precedent is installed as DDL on both backends with the codes the rest of the build
reports; and the job that runs the suite twice against a real server is bounded by what
its own run line asks for, with every flag on that line one the verifier actually takes.

This checkpoint is not written yet. It is written at the end of P176,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P176")
def test_c101_integration():
    raise NotImplementedError
