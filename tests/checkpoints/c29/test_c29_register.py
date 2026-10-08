"""C29 - The register, fillable.

Three phases have now touched the same small check, and each found the previous one's
assumption wrong. P53 made it refuse an empty register rather than lie about one. P54 found
the refusal firing on clones where nobody had been interviewed. P56 found the deeper
assumption underneath both: that answers existing means a name exists. It does not - three
sessions of this interview named no client at all.

What this asks is whether the four commands still tell one story, on the repo as it stands:
that a name gets into the register because a person put it there, that a person is given
everything they need to do that in a minute, and that no path through any of it lets the
check pass without somebody having looked.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.conftest import needs_a_checkout
from tools import interview

ROOT = Path(__file__).resolve().parents[3]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/interview.py", *args], cwd=ROOT, capture_output=True, text=True
    )


def test_the_only_ways_past_the_check_all_require_a_person() -> None:
    """There is no fourth way, and that is the property worth pinning. A name in the
    register, a leak removed from a file, or an acknowledgement someone signed - each is an
    act. None of them is a default, a flag, or something a model can do on its way past."""
    done = run("scan")
    assert done.returncode in (0, 1)
    if done.returncode == 0:
        assert interview.identifiers() or interview.reviewed_empty(), (
            "the scan passed with an empty, unreviewed register - which is the exact "
            "state P53 was written to stop"
        )


def test_suggest_proposes_and_writes_nothing() -> None:
    """It reads real answers, which may hold real names. It must not put them anywhere."""
    needs_a_checkout("the identifier register")
    register = ROOT / "knowledge" / "identifiers.txt"
    before = register.read_text(encoding="utf-8")
    done = run("suggest")
    assert done.returncode == 0, done.stderr
    assert register.read_text(encoding="utf-8") == before


def test_what_it_proposes_here_is_not_a_client() -> None:
    """The finding that produced this phase, kept as a test so it stays true or stops being
    quietly assumed: nothing in three sessions of answers is a client's name. If this starts
    failing, somebody has been interviewed about a real engagement and the register needs
    filling - which is the check doing its job, not this test going wrong."""
    needs_a_checkout("the identifier register")
    candidates = interview.suggest()
    assert all(c.kind == "name-shaped" for c in candidates), (
        "something with the shape of a company or a person is in knowledge/ now; "
        f"register it: {[c.text for c in candidates if c.kind != 'name-shaped']}"
    )


def test_an_acknowledgement_cannot_outlive_the_answers_it_covers() -> None:
    """The one way this could have become an off switch."""
    needs_a_checkout("the identifier register")
    import inspect

    source = inspect.getsource(interview._review_is_current)
    assert "sessions" in source
    assert interview._review_is_current(ROOT / "knowledge", "1999-01-01") is False


def test_the_protocol_and_the_session_rules_say_the_same_thing() -> None:
    protocol = (ROOT / "interview" / "PROTOCOL.md").read_text(encoding="utf-8")
    rules = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for body in (protocol, rules):
        assert "interview.py suggest" in body
        assert "register --none" in body
        assert "invent a name" in body.replace("Never invent", "invent")


def test_every_command_the_protocol_names_exists() -> None:
    """A protocol that names a command the tool does not have is a session that stops."""
    protocol = (ROOT / "interview" / "PROTOCOL.md").read_text(encoding="utf-8")
    for command in ("status", "session", "mark", "scan", "suggest", "register"):
        assert f"interview.py {command}" in protocol
        assert run(command, "--help").returncode == 0, f"{command} is named but not wired"
