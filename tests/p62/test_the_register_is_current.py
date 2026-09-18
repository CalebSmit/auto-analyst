"""The register, held to being current rather than to particular sentences.

`BUILD/OPEN.md` is what a new session reads to find out what is waiting on a person. It had
four rows that outlived their findings: two things P55 and P57 had built, and a P28 sign-off
given on 2026-09-05. A register that lists finished work teaches you to skim it, which is
the one thing it cannot afford.

The test meant to keep it honest asserted that the register contained the strings
`gate close P28` and `gate checkpoint C10`. Both commands had been run. So the guard was
pinning the register to instructions that had expired - and when the register was corrected,
the guard failed and argued for putting the stale text back.

What a session needs is not that particular words appear. It is that nothing in the register
is telling it to do something already done.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "BUILD" / "OPEN.md"


def text() -> str:
    return REGISTER.read_text(encoding="utf-8")


def plan() -> dict:
    return json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))


def open_rows() -> list[str]:
    """Every table row that is not struck through and not a header separator.

    A struck-through row is one somebody has marked settled; it stays for the history, and
    it is deliberately not held to the same test as a live one.
    """
    return [
        line
        for line in text().splitlines()
        if line.startswith("|")
        and not line.startswith("| ~~")
        and not line.startswith("|--")
        and not line.startswith("| |")
    ]


# ------------------------------------------------- nothing open asks for work already done


def test_no_live_row_asks_for_a_phase_that_is_closed() -> None:
    """`gate close P28` sat in the register for thirteen days after P28 was signed off."""
    closed = {p["id"] for p in plan()["phases"] if p["status"] == "done"}
    for row in open_rows():
        for phase in re.findall(r"gate(?:\.py)? close (P\d+)", row):
            assert phase not in closed, (
                f"the register tells a session to close {phase}, which closed on "
                f"{next(p.get('closed') for p in plan()['phases'] if p['id'] == phase)}"
            )


def test_no_live_row_asks_for_a_checkpoint_that_is_green() -> None:
    green = {c["id"] for c in plan()["checkpoints"] if c["status"] == "done"}
    for row in open_rows():
        for checkpoint in re.findall(r"gate(?:\.py)? checkpoint (C\d+)", row):
            assert checkpoint not in green, (
                f"the register tells a session to run {checkpoint}, which is already green"
            )


def test_no_live_row_asks_for_a_signoff_that_exists() -> None:
    """A phase with a recorded sign-off is not waiting on one, whatever the register says."""
    signed = {p["id"] for p in plan()["phases"] if str(p.get("signoff", "")).strip()}
    for row in open_rows():
        if "sign-off" not in row and "signoff" not in row:
            continue
        for phase in re.findall(r"\b(P\d+)\b", row):
            if phase in signed and "--reopen" not in row:
                raise AssertionError(
                    f"{phase} is listed as waiting on a sign-off and already has one: "
                    f"{next(p['signoff'] for p in plan()['phases'] if p['id'] == phase)[:80]}"
                )


# ------------------------------------------------------- and it still names what is owed


def test_the_things_this_build_is_waiting_on_are_still_named() -> None:
    """The four from this build specifically, so a new session picks them up without
    reading the whole history. Named, whether live or settled - a settled item that
    vanished would be a question somebody asks again."""
    register = text()
    for item in ("P28", "container proof", "P26 sign-off", "Redis"):
        assert item in register, item


def test_what_p28_still_owes_is_the_clone_and_it_says_so() -> None:
    """The sign-off was given. What is still owed is evidence only the work machine can
    produce, and that belongs in §4 rather than in "waiting on your word"."""
    register = text()
    assert "work-machine clone" in register
    assert "Evidence only the work machine can produce" in register


def test_a_settled_row_says_when_and_what_settled_it() -> None:
    """Struck through is not enough - a row that says only "done" is one nobody can check."""
    for line in text().splitlines():
        if not line.startswith("| ~~"):
            continue
        assert re.search(r"\b(Done|Signed|done)\b", line), line[:90]
        assert re.search(r"20\d\d-\d\d-\d\d", line), f"no date on a settled row: {line[:90]}"


def test_the_register_is_pointed_at_from_the_rules_a_session_reads() -> None:
    rules = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "OPEN.md" in rules
