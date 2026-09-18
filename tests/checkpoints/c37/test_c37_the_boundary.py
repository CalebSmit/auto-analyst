"""C37 - The boundary, exercised rather than read.

P64, P65 and P66 were all found by running `tools/interview.py`, and all three are about the
one check `CLAUDE.md` names as what keeps a client's name inside `knowledge/`. Two of them
destroyed real records in this repo before they were fixed.

A checkpoint asks whether they hold together. What they have in common is that each was
invisible to the suite because the suite exercised the functions and not the command. So
this walks a whole session the way the protocol describes one - status, session, answers,
acknowledgement, scan - and asks at each point whether the command a person runs says what
the record actually holds.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import pytest

from tools import interview

ROOT = Path(interview.ROOT)
DAY = dt.date(2026, 9, 18)


@pytest.fixture
def machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    knowledge = tmp_path / "knowledge"
    interview.init(knowledge)
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(interview, "KNOWLEDGE", knowledge)
    monkeypatch.setattr(
        interview, "committable_files", lambda root=None: sorted(outside.rglob("*"))
    )
    return knowledge, outside


def answer(knowledge: Path, text: str, on: dt.date = DAY) -> Path:
    log = interview.start_session(knowledge, today=on)
    with log.open("a", encoding="utf-8") as fh:
        fh.write("\n## Q\n\n" + text + "\n")
    return log


def test_a_whole_session_walked_the_way_the_protocol_describes_it(
    machine: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    knowledge, outside = machine

    # Step 2: status, before the first question. Nothing recorded, nothing to warn about.
    interview.main(["status"])
    assert "will refuse" not in capsys.readouterr().out

    # An answer that names a client, as a real session's first answer well might.
    answer(knowledge, "We are valuing Northgate Dental Partners this year.")

    # Now the close-out must refuse: there are answers and nothing in the register.
    assert interview.main(["scan"]) == 1
    assert "UNCHECKED" in capsys.readouterr().out

    # The name is registered, and the scan becomes a real search rather than an excuse.
    interview.main(["register", "Northgate Dental Partners"])
    capsys.readouterr()
    assert interview.main(["scan"]) == 0

    # And it finds that name if it reaches a file outside knowledge/.
    (outside / "skill.md").write_text(
        "Worked example: Northgate Dental Partners.", encoding="utf-8"
    )
    assert interview.main(["scan"]) == 1
    said = capsys.readouterr().out
    assert "Northgate Dental Partners" in said and "skill.md" in said


def test_an_acknowledgement_covers_what_it_saw_and_nothing_after_it(
    machine: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """P64 and P65 together: the acknowledgement expires by what it looked at, and the
    command will not quietly replace one that still stands."""
    knowledge, _ = machine
    answer(knowledge, "A general answer about how the work is done. No names.")

    assert interview.main(["register", "--none", "nobody named", "--who", "smitc"]) == 0
    capsys.readouterr()
    assert interview.main(["scan"]) == 0

    # Replacing a standing one is refused, and the record is untouched.
    written = (knowledge / "identifiers.txt").read_text(encoding="utf-8")
    assert interview.main(["register", "--none", "other words", "--who", "someone"]) == 1
    assert (knowledge / "identifiers.txt").read_text(encoding="utf-8") == written
    capsys.readouterr()

    # A second session the same day is not covered by it - the defect P64 fixed.
    answer(knowledge, "A second answer, later the same day.", DAY)
    assert interview.main(["scan"]) == 1
    capsys.readouterr()

    # And renewing it is the way through, because that is the act.
    assert interview.main(["register", "--none", "looked again", "--who", "smitc"]) == 0
    capsys.readouterr()
    assert interview.main(["scan"]) == 0


def test_status_and_scan_agree_at_every_point_of_that_session(
    machine: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """P66. The two commands the protocol tells a session to run must not describe the same
    file differently."""
    knowledge, _ = machine
    for step in range(4):
        interview.main(["status"])
        warned = "will refuse to close this session" in capsys.readouterr().out
        refuses = interview.main(["scan"]) != 0
        capsys.readouterr()
        assert warned == refuses, f"status and scan disagreed at step {step}"
        if step == 0:
            answer(knowledge, "An answer with no name.")
        elif step == 1:
            interview.main(["register", "--none", "nobody", "--who", "smitc"])
            capsys.readouterr()
        elif step == 2:
            answer(knowledge, "A later answer.", DAY + dt.timedelta(days=1))


def test_no_command_writes_to_the_repositorys_own_knowledge_folder(
    machine: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """P65's root cause, asked once more at the level of the whole tool. Two accidents in
    this build wrote to the real folder from a test that had pointed the module elsewhere."""
    knowledge, _ = machine
    real = ROOT / "knowledge"
    before = {
        p.relative_to(real).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(real.rglob("*"))
        if p.is_file()
    }
    assert before, "the real knowledge/ is empty; this would pass over anything"

    answer(knowledge, "An answer.")
    topic = interview.load_topics()[0].id
    for argv in (
        ["status"],
        ["topics"],
        ["scan"],
        ["suggest"],
        ["session"],
        ["mark", topic, "partial", "--note", "a note"],
        ["register", "Northgate Dental Partners"],
    ):
        interview.main(argv)
    capsys.readouterr()

    after = {
        p.relative_to(real).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(real.rglob("*"))
        if p.is_file()
    }
    assert after == before, "a command reached the repository's own knowledge/ folder"
