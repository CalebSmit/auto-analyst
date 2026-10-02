"""C70 - The same payload, spelled smaller

Proves:
That compacting every procedure's payload changed nothing a run depends on: the
assembled context still passes the guards, the scripted analyst still reads every
payload, the review loop still resumes, and the workbook still comes out - while the
context that was nearest the ceiling is measurably further from it.

This checkpoint is not written yet. It is written at the end of P124,
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of P124")
def test_c70_integration():
    raise NotImplementedError
