"""P93 - What is owed before any of this is believed.

Everything in P87 to P92 is proved against a transport that replays documented behaviour,
or a document generated for the purpose. That proves the code's use of an API and the
shape of a document. It is **not** evidence that a credential, an app permission, a folder
id or a heading is right at work.

This phase was first written as a blocking human gate - "It really connected", closed by a
signoff from the work machine. That was the wrong instrument. Phases close in order, so a
signoff that can only happen somewhere else halts every unrelated phase behind it: P94 was
finished, tested and unclosable. The other human gates here (P18, P20, P26, P28) are
sign-offs on work that had just been done and could be checked in the same sitting.

`BUILD/OPEN.md` is the repo's designated home for "evidence only the work machine can
produce", and the four steps live there. So what this phase closes on is the part that can
honestly be established here: that the owed evidence is written down where somebody will
find it, and that **nothing in the block claims to have connected**. The connection stays
owed.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def plan() -> dict:
    return json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))


def owed_text() -> str:
    """OPEN.md with its wrapping and emphasis taken out.

    Searching the raw file would make these tests assertions about where somebody put a
    line break, which is not the claim - and prose that has to keep a phrase on one line
    to satisfy a test is prose written for the test.
    """
    import re

    raw = (ROOT / "BUILD" / "OPEN.md").read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", raw.replace("*", "").replace("`", ""))


def p93() -> dict:
    found = next((p for p in plan()["phases"] if p["id"] == "P93"), None)
    assert found is not None, "the phase that proves the connection is not in the plan"
    return found


def test_the_four_things_owed_are_written_where_somebody_will_find_them() -> None:
    """In OPEN.md, which CLAUDE.md names as the place for evidence only the work machine
    can produce - and which a person is told to read before being asked anything.

    Four separate things, because each is a different kind of evidence: credentials Box
    honours, a browser login ShareFile accepts, a file that really moved, and a document
    that really opens in Word.
    """
    owed = owed_text().lower()
    for needed in ("box", "sharefile", "update button", "word"):
        assert needed in owed, needed
    assert "second press" in owed, "pressing twice is the case the relay exists to get right"


def test_what_each_step_needs_configured_first_is_said() -> None:
    """The two settings most likely to be wrong the first time, named where somebody will
    read them rather than discovered from a refusal."""
    owed = owed_text()
    assert "Generate User Access Tokens" in owed
    assert "offline access" in owed
    assert "/api/admin/sharefile/callback" in owed


def test_closing_this_phase_does_not_read_as_having_connected() -> None:
    """The reason it was renamed. A phase called "It really connected", closed by a test,
    would say the opposite of what happened."""
    assert "connected" not in p93()["title"].lower()
    assert "owed" in p93()["title"].lower()


def test_it_asks_what_the_real_report_s_anchors_actually_are() -> None:
    """The appendix registry is six anchor strings guessed from what he named in the
    interview. The first real report is where they are either right or corrected, and if
    nobody writes that down it gets rediscovered every period."""
    tasks = " ".join(p93()["tasks"]).lower()
    assert "anchors" in tasks
    assert "registry" in tasks


def test_every_phase_in_the_block_that_could_not_be_proved_here_is_covered() -> None:
    """P93 is the receipt for the whole block, so it re-runs each phase's own tests. A
    phase left out would be one whose code nothing re-checks when the block is closed
    out."""
    checks = " ".join(p93()["checks"])
    for phase in ("p87", "p88", "p89", "p90", "p91", "p92"):
        assert phase in checks, phase


def test_the_block_says_in_its_own_words_that_it_has_not_run() -> None:
    """Held here as well as in each module, because this is the phase whose whole job is
    that they stay true until somebody has done the work that makes them false.

    Not tied to this phase's status any more - it closes on the evidence being recorded,
    not on the connection being made. `test_the_connection_is_still_owed` watches OPEN.md
    for the day that changes."""
    for module, phrase in (
        ("ports/storage/box.py", "has spoken to a real Box tenant"),
        ("ports/storage/sharefile.py", "has spoken to real ShareFile"),
        ("report/appendices.py", "the real report has not been seen"),
    ):
        assert phrase in (ROOT / module).read_text(encoding="utf-8").replace("\n", " "), module


def test_the_connection_is_still_owed() -> None:
    """The honest state of the build, asserted on OPEN.md rather than on this phase's
    status - because this phase closing says only that the owed thing is recorded.

    Meant to fail one day: when somebody moves that section to Settled, the sentences in
    the adapters saying they have never reached a real service stop being true, and this
    is what makes them notice.
    """
    open_items = (ROOT / "BUILD" / "OPEN.md").read_text(encoding="utf-8")
    section = "## The connections, and the first real report"
    assert section in open_items
    after = open_items.split(section, 1)[1].split("\n## ", 1)[0]
    assert "Settled" not in after, (
        "the connections have been confirmed. Delete this test and the sentences it "
        "guards: the adapters say they have never reached a real service, and that is "
        "no longer true."
    )
