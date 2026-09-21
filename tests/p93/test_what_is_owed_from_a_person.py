"""P93 - It really connected.

A phase a test cannot close, which still needs a test directory - so this holds the part
of P93 that *is* checkable: that the phase asks for the right things, and that nothing in
the block quietly claims what only P93 can establish.

The distinction matters. Everything in P87 to P92 is proved against a transport that
replays documented behaviour or a document generated for the purpose. That proves the
code's use of an API and the shape of a document. It is not evidence that a credential, an
app permission, a folder id or a heading is right at work, and a phase that closed on it
while implying otherwise would be this build's signature defect with a network adapter
attached.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def plan() -> dict:
    return json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))


def p93() -> dict:
    found = next((p for p in plan()["phases"] if p["id"] == "P93"), None)
    assert found is not None, "the phase that proves the connection is not in the plan"
    return found


def test_a_person_closes_this_one_and_not_a_test() -> None:
    """If P93 ever closes on a machine with no credentials, something has gone wrong with
    the gate rather than with the connection."""
    assert p93()["gate"] == "human"
    assert p93()["human_check"], "a judgment gate that does not say what is judged"


def test_what_is_asked_for_covers_all_three_connections_and_a_real_report() -> None:
    """Four separate things, because each is a different kind of evidence: credentials
    that Box honours, a browser login ShareFile accepts, a file that really moved, and a
    document that really opens in Word."""
    asked = p93()["human_check"].lower()
    for needed in ("box", "sharefile", "update button", "word"):
        assert needed in asked, needed
    assert "second press" in asked, "pressing twice is the case the relay exists to get right"


def test_it_asks_what_the_real_report_s_anchors_actually_are() -> None:
    """The appendix registry is six anchor strings guessed from what he named in the
    interview. The first real report is where they are either right or corrected, and if
    nobody writes that down it gets rediscovered every period."""
    tasks = " ".join(p93()["tasks"]).lower()
    assert "anchors" in tasks
    assert "registry" in tasks


def test_every_phase_in_the_block_that_could_not_be_proved_here_is_covered() -> None:
    """P93 is the receipt for the whole block, so it re-runs each phase's own tests as
    well as asking a person. A phase left out would be one whose code nothing re-checks on
    the day the connections are confirmed."""
    checks = " ".join(p93()["checks"])
    for phase in ("p87", "p88", "p89", "p90", "p91", "p92"):
        assert phase in checks, phase


def test_the_block_says_in_its_own_words_that_it_has_not_run() -> None:
    """Held here as well as in each module, because this is the phase that discharges it.
    When P93 closes these sentences become false, and the person closing it is the one who
    should be made to notice."""
    for module, phrase in (
        ("ports/storage/box.py", "has spoken to a real Box tenant"),
        ("ports/storage/sharefile.py", "has spoken to real ShareFile"),
        ("report/appendices.py", "the real report has not been seen"),
    ):
        assert phrase in (ROOT / module).read_text(encoding="utf-8").replace("\n", " "), module


def test_it_is_still_open() -> None:
    """The honest state of the build. This is a test that is meant to fail one day - on
    the day a person signs it off - and failing then is the signal to delete it rather
    than a defect."""
    assert p93()["status"] != "done", (
        "P93 has been signed off. Delete this test and the sentences it guards: the "
        "modules say they have never reached a real service, and that is no longer true."
    )
