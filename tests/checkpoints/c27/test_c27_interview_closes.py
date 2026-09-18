"""C27 - The interview can finish again.

A checkpoint asks whether the phases either side of it still agree. This one has a single
phase behind it and a narrow question, because the thing it guards is narrow and was broken
in both directions inside twenty-four hours: the check that keeps a client's name inside
`knowledge/` reported `clean` over an empty register for three sessions, and then refused on
every machine including ones that had never been interviewed.

What is checked here, that P54's own tests do not: the command, the protocol that runs it and
the session it has to close still describe the same thing. P54 proves the behaviour against a
knowledge folder it builds. This proves it against the repo as it actually stands, and against
the documents that tell a model what to do with it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools import interview

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "interview" / "PROTOCOL.md"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    """The command as a person runs it, in its own process - not `main()` in this one."""
    return subprocess.run(
        [sys.executable, "tools/interview.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


# ------------------------------------------------------------------ the command, for real


def test_the_scan_never_reports_a_pass_it_did_not_earn() -> None:
    """Whatever this repo's state, `clean` and exit 0 together mean one of exactly two
    things: a register was checked, or there was nothing to check. Never "a check ran"."""
    done = run("scan")
    assert done.returncode in (0, 1), done.stderr
    if done.returncode == 0:
        assert done.stdout.startswith("clean:")
        checked = interview.identifiers()
        if checked:
            assert f"clean: {len(checked)} identifiers checked" in done.stdout
        else:
            assert "no answers yet" in done.stdout
            assert not interview._knowledge_has_answers()
    else:
        assert "UNCHECKED" in done.stdout or "FAIL:" in done.stdout


def test_an_empty_register_over_real_answers_is_refused_rather_than_waved_through() -> None:
    """The state this repo is in today: three sessions recorded, nothing registered. It must
    refuse, and it must say what to do about it."""
    if interview.identifiers():
        pytest.skip("the register has been filled; the refusal no longer applies here")
    assert interview._knowledge_has_answers(), "knowledge/ should hold three sessions of answers"

    done = run("scan")
    assert done.returncode == 1
    assert "UNCHECKED" in done.stdout
    assert "identifiers.txt" in done.stdout


def test_the_refusal_is_visible_before_the_first_question_and_not_only_after_the_last() -> None:
    """`status` is protocol step 2; `scan` is step 6. A session that only learns at step 6
    that it cannot be closed has already asked everything it was going to ask."""
    if interview.identifiers():
        pytest.skip("the register has been filled")
    done = run("status")
    assert done.returncode == 0, done.stderr
    assert "identifiers kept inside knowledge/: 0" in done.stdout
    assert "will refuse" in done.stdout


# ------------------------------------------------- the documents that drive it still agree


def test_the_protocol_still_makes_the_scan_the_gate() -> None:
    body = PROTOCOL.read_text(encoding="utf-8")
    assert "interview.py scan` must print `clean`" in body
    assert "UNCHECKED" in body, "the protocol must say what to do when it refuses"
    assert "Never invent a name" in body, "the one thing a model must not do to get past it"


def test_the_protocol_does_not_send_a_session_at_a_phase_that_is_not_open() -> None:
    """It offered `gate amend` on "the current interview phase". A session closes the phase
    it opens, so there usually is not one, and `gate extend` is the working path."""
    body = PROTOCOL.read_text(encoding="utf-8")
    assert "gate.py\nextend" in body or "gate.py extend" in body
    assert "amend` on the current interview phase" not in body


def test_the_map_does_not_claim_the_coverage_file_is_ignored() -> None:
    """`knowledge/` is committed to the private repo so the interview travels between
    machines (2026-09-16). A comment saying otherwise is how a session decides it may write
    a client's name somewhere git will not carry - or will."""
    head = (ROOT / "interview" / "topics.yaml").read_text(encoding="utf-8")
    assert "which git ignores" not in head
    probe = subprocess.run(
        ["git", "check-ignore", "-q", "knowledge/coverage.yaml"], cwd=ROOT, capture_output=True
    )
    assert probe.returncode == 1, "coverage.yaml is tracked, whatever the comment says"


# --------------------------------------------------------------- and the boundary it guards


def test_nothing_under_knowledge_has_reached_a_committable_file() -> None:
    """The check itself, run over this repo. Skipped rather than passed when the register is
    empty, because a scan for no names finds no names."""
    names = interview.identifiers()
    if not names:
        pytest.skip("register empty; `scan` refuses for the same reason and says so")
    assert interview.scan(interview.committable_files(), names) == []
