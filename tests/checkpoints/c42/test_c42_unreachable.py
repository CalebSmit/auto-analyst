"""C42 - Two scans for one defect, and the shape they share.

P71 and P73 look for the same thing from two directions: something built, correct and
unreachable. A public function nothing calls; an exception class nothing can raise. The
build has paid for that shape four times - P55 three, P60 once, P72 once more - and every
one was found by a person reading.

A checkpoint asks whether the two together still cover it, and whether they stay honest:
each has an allowlist, and an allowlist is where a check goes to die quietly.
"""

from __future__ import annotations

from pathlib import Path

from tests.p71.test_nothing_is_unwired import ALLOWED as UNWIRED_OK
from tests.p71.test_nothing_is_unwired import key, unwired
from tests.p73.test_an_exception_nobody_raises import ALLOWED as UNRAISED_OK
from tests.p73.test_an_exception_nobody_raises import exception_classes, never_raised

ROOT = Path(__file__).resolve().parents[3]


def test_both_scans_are_quiet_so_a_failure_means_something_new() -> None:
    functions = [f"{w}:{n}" for w, _, n in unwired() if key(w, n) not in UNWIRED_OK]
    exceptions = [n for n in never_raised() if n not in UNRAISED_OK]
    assert not functions, functions
    assert not exceptions, exceptions


def test_neither_scan_has_quietly_stopped_looking() -> None:
    """The way a check of this kind dies: it keeps passing because it stopped finding
    anything to look at."""
    assert len(exception_classes()) > 20
    from tests.p71.test_nothing_is_unwired import public_functions

    assert len(public_functions()) > 100


def test_every_excuse_in_either_scan_carries_a_reason() -> None:
    for name, why in {**UNWIRED_OK, **UNRAISED_OK}.items():
        assert len(why.split()) >= 12, f"{name} is excused without saying why"


def test_the_two_scans_do_not_excuse_the_same_thing_twice() -> None:
    """An entry in both lists would let a defect hide behind whichever check somebody
    looked at first."""
    shared = {k.rsplit(".", 1)[-1] for k in UNWIRED_OK} & set(UNRAISED_OK)
    assert not shared, shared


def test_the_findings_that_paid_for_these_scans_are_still_fixed() -> None:
    """P55's precedent wiring, P60's on_failure, P72's retry. If any regressed, one of the
    two scans should be what says so."""
    assert "PrecedentStore" in (ROOT / "tools" / "serve.py").read_text(encoding="utf-8")
    assert "on_failure" in (ROOT / "graph" / "execute.py").read_text(encoding="utf-8")
    assert "TransportFailure" not in never_raised()
