"""C35 - What a session is told, and whether it is still true.

Everything a new session does starts from three documents it is told to read: STATE.md for
where the build is, OPEN.md for what is waiting on a person, and CLAUDE.md for the rules.
Two of the three are generated and cannot drift. The third is written by hand, and it drifted
- four rows outlived their findings, and the guard meant to catch that was itself pinned to
instructions that had expired.

This asks whether the three still agree with the plan and with each other.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def plan() -> dict:
    return json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))


def test_the_state_file_and_the_plan_agree_on_what_is_closed() -> None:
    state = (ROOT / "BUILD" / "STATE.md").read_text(encoding="utf-8")
    phases = plan()["phases"]
    closed = [p for p in phases if p["status"] == "done"]
    assert f"{len(closed)} of {len(phases)} phases closed" in state


def test_the_register_does_not_ask_for_work_the_plan_says_is_done() -> None:
    register = (ROOT / "BUILD" / "OPEN.md").read_text(encoding="utf-8")
    done = {p["id"] for p in plan()["phases"] if p["status"] == "done"}
    green = {c["id"] for c in plan()["checkpoints"] if c["status"] == "done"}

    live = [
        line
        for line in register.splitlines()
        if line.startswith("|") and not line.startswith(("| ~~", "|--", "| |"))
    ]
    for row in live:
        assert not (set(re.findall(r"close (P\d+)", row)) & done), row[:100]
        assert not (set(re.findall(r"checkpoint (C\d+)", row)) & green), row[:100]


def test_every_settled_row_carries_a_date() -> None:
    register = (ROOT / "BUILD" / "OPEN.md").read_text(encoding="utf-8")
    for line in register.splitlines():
        if line.startswith("| ~~"):
            assert re.search(r"20\d\d-\d\d-\d\d", line), line[:100]


def test_the_three_documents_a_session_reads_all_exist_and_point_at_each_other() -> None:
    rules = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for named in ("BUILD/STATE.md", "BUILD/OPEN.md", "BUILD/LEDGER.md", "BUILD/AMENDMENTS.md"):
        assert named in rules, named
        assert (ROOT / named).is_file(), named


def test_a_dead_end_that_was_walked_is_on_the_ledger() -> None:
    """Reopening P01 was tried and cannot work. A session that tries it again has lost an
    hour to something already known."""
    ledger = (ROOT / "BUILD" / "LEDGER.md").read_text(encoding="utf-8")
    assert "P01" in ledger
    assert "reopen" in ledger.lower()
