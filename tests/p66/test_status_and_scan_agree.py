"""P66: two commands, one answer about the register.

The protocol has a session run `status` before the first question and `scan` before the
last. Both read `knowledge/identifiers.txt`. `status` decided what to say from "the register
is empty and there are answers" and never looked at the acknowledgement, so a person running
both in one minute was told the close-out would refuse *and* that the register was clean,
about the same file, by the two commands `CLAUDE.md` tells them to trust.

Both sentences were true of different moments - the acknowledgement stands now and goes stale
when this session records an answer - which is what makes it worth saying properly rather
than picking one.

`test_status_and_scan_never_report_opposite_states` is the one that matters: it runs both
commands over one folder in each state the register can be in, and fails if they disagree.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from tools import interview

DAY = dt.date(2026, 9, 18)
WORDS = "checked this session; nobody was named"


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    knowledge = tmp_path / "knowledge"
    interview.init(knowledge)
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(interview, "KNOWLEDGE", knowledge)
    monkeypatch.setattr(
        interview, "committable_files", lambda root=None: sorted(outside.rglob("*"))
    )
    return knowledge


def answered(knowledge: Path, on: dt.date = DAY) -> Path:
    log = interview.start_session(knowledge, today=on)
    with log.open("a", encoding="utf-8") as fh:
        fh.write("\n## Q1\n\nAn answer, with no name in it.\n")
    return log


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = interview.main(argv)
    return code, capsys.readouterr().out


# ------------------------------------------------------------------ each state


def test_with_no_acknowledgement_status_still_warns_before_the_first_question(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """P54 put this warning at step 2 rather than step 6 so it is a note to act on while
    asking. That must survive."""
    answered(folder)
    _, said = run(["status"], capsys)
    assert "will refuse to close this session" in said

    code, _ = run(["scan"], capsys)
    assert code == 1, "status warned of a refusal that scan does not make"


def test_with_a_standing_acknowledgement_status_says_so_and_what_expires_it(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    answered(folder)
    interview.main(["register", "--none", WORDS, "--who", "smitc"])
    capsys.readouterr()

    _, said = run(["status"], capsys)
    assert "An acknowledgement stands" in said
    assert "smitc" in said and DAY.isoformat() in said
    assert "stale" in said
    assert "will refuse to close this session" not in said, "it warned of a refusal not happening"


def test_the_advice_is_offered_in_both_states(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Whichever state it is in, the register is still empty and names still have to go in
    as they come up. The way to do that must not disappear with the warning."""
    answered(folder)
    for _ in range(2):
        _, said = run(["status"], capsys)
        assert "interview.py suggest" in said
        assert "register --none" in said
        interview.main(["register", "--none", WORDS, "--who", "smitc"])
        capsys.readouterr()


# ------------------------------------------------------------------ and they cannot disagree


def test_status_and_scan_never_report_opposite_states(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Over one folder, in every state the register reaches during a session."""

    def both() -> tuple[bool, bool]:
        _, said = run(["status"], capsys)
        code, _ = run(["scan"], capsys)
        warned = "will refuse to close this session" in said
        refuses = code != 0
        return warned, refuses

    # 1. Nothing recorded at all: nothing to check, nothing to warn about.
    warned, refuses = both()
    assert not warned and not refuses

    # 2. Answers, empty register, no acknowledgement: both say it will not close.
    answered(folder)
    warned, refuses = both()
    assert warned and refuses, "status and scan disagree with answers and no acknowledgement"

    # 3. Acknowledged: both are satisfied.
    interview.main(["register", "--none", WORDS, "--who", "smitc"])
    capsys.readouterr()
    warned, refuses = both()
    assert not warned and not refuses, "status warned while scan passed"

    # 4. A further session: the acknowledgement is stale and both say so again.
    answered(folder, DAY + dt.timedelta(days=1))
    warned, refuses = both()
    assert warned and refuses, "an acknowledgement went stale and status did not notice"

    # 5. A name registered instead: both satisfied, by the other route.
    interview.main(["register", "Northgate Dental Partners"])
    capsys.readouterr()
    warned, refuses = both()
    assert not warned and not refuses


# ------------------------------------------------------------------ the reporting line


def test_scan_reports_a_hit_it_finds_outside_the_repository(
    folder: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Found by C37. `relative_to` raises rather than falling back, and this is the line
    that reports a client's name having reached a file outside `knowledge/` - so the one
    moment the check had something to say was the one moment it could raise instead of
    saying it. Nothing `committable_files()` returns is outside the repository today, which
    is why it never happened; a landmine that has not gone off is still a landmine."""
    interview.main(["register", "Northgate Dental Partners"])
    capsys.readouterr()
    leaked = tmp_path / "outside" / "skill.md"
    leaked.write_text("Worked example: Northgate Dental Partners.", encoding="utf-8")

    code, said = run(["scan"], capsys)
    assert code == 1
    assert "Northgate Dental Partners" in said
    assert "skill.md" in said


def test_a_path_inside_the_repository_is_still_shown_relative(folder: Path) -> None:
    assert interview._shown(Path(interview.ROOT) / "skills" / "x.md") == "skills/x.md"
