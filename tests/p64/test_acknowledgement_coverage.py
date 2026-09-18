"""P64: an acknowledgement that says what it looked at.

`interview.py scan` refuses an empty register unless a person has recorded that they looked
and found nobody. That acknowledgement has to expire, or the first person to run it switches
the check off for good - the failure P53 and P54 were both about.

It expired by date, and a session logged on the *same day* counted as covered. That was
deliberate: the legitimate flow is to finish a session and then record that nobody was named,
and both happen on one day, so a strict `<` would refuse the very case the acknowledgement
exists for. But `<=` also covers a session that had not happened when the line was written.
Acknowledge at ten in the morning, interview at two, and the afternoon's answers inherit the
morning's acknowledgement - `scan` prints `clean` over a session full of client names, and
`clean` from this command is what CLAUDE.md offers as the guarantee that no client's name has
left `knowledge/`.

A date cannot tell the two orderings apart, because they share one. So the acknowledgement
records the sessions it was made over, and is current only while those are still all of them.

The two tests that matter are `test_the_legitimate_flow_still_closes_a_session` and
`test_an_acknowledgement_does_not_cover_a_session_that_came_after_it_the_same_day`. Either
one alone is satisfiable by a rule that is wrong in the other direction.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from tools import interview

NAMED = "## Q1\n\nThe client is Northgate Dental Partners; the owner is R. Whitfield.\n"
DAY = dt.date(2026, 9, 18)


def session(folder: Path, on: dt.date, body: str = NAMED) -> Path:
    log = interview.start_session(folder, today=on)
    with log.open("a", encoding="utf-8") as fh:
        fh.write("\n" + body)
    return log


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    interview.init(tmp_path)
    return tmp_path


def current(folder: Path) -> bool:
    on, _ = interview.reviewed_empty(folder)
    return interview._review_is_current(folder, on)


# ------------------------------------------------- the two orderings that share a date


def test_the_legitimate_flow_still_closes_a_session(folder: Path) -> None:
    """Finish a session, look at the register, record that nobody was named. This is the
    case the acknowledgement exists for and it happens on one day."""
    session(folder, DAY)
    interview.record_review("smitc", "no client was named", folder, on=DAY.isoformat())
    assert current(folder), "the flow the acknowledgement exists for was refused"


def test_an_acknowledgement_does_not_cover_a_session_that_came_after_it_the_same_day(
    folder: Path,
) -> None:
    """The hole. The acknowledgement was written before these answers existed, so it says
    nothing about them - and it used to say `clean` about them anyway."""
    interview.record_review("smitc", "no client was named", folder, on=DAY.isoformat())
    assert current(folder), "an acknowledgement over no sessions should hold until one is run"
    session(folder, DAY)
    assert not current(folder), "a session inherited an acknowledgement written before it"


def test_a_later_session_still_expires_it(folder: Path) -> None:
    session(folder, DAY)
    interview.record_review("smitc", "no client was named", folder, on=DAY.isoformat())
    session(folder, DAY + dt.timedelta(days=1))
    assert not current(folder)


def test_acknowledging_again_covers_the_new_session(folder: Path) -> None:
    """The way out is the same act, performed again: a person looks and records it. If this
    did not work the check would be unsatisfiable rather than strict."""
    interview.record_review("smitc", "nobody", folder, on=DAY.isoformat())
    session(folder, DAY)
    assert not current(folder)
    interview.record_review("smitc", "looked again, still nobody", folder, on=DAY.isoformat())
    assert current(folder)


# ------------------------------------------------- what the line records


def test_the_acknowledgement_names_the_sessions_it_was_made_over(folder: Path) -> None:
    first = session(folder, DAY)
    second = session(folder, DAY)
    interview.record_review("smitc", "nobody", folder, on=DAY.isoformat())

    over = interview._reviewed_over(folder)
    assert over is not None, "the acknowledgement records no coverage"
    assert set(over) == {first.stem, second.stem}


def test_a_session_opened_and_never_answered_is_not_something_to_have_reviewed(
    folder: Path,
) -> None:
    """`sessions_with_answers` is the same predicate the refusal uses. A log that never got
    past its own header holds nothing to have looked at, so it neither needs covering nor
    counts as coverage."""
    interview.start_session(folder, today=DAY)
    assert interview.sessions_with_answers(folder) == ()
    interview.record_review("smitc", "nobody", folder, on=DAY.isoformat())
    assert interview._reviewed_over(folder) == ()
    assert current(folder)


def test_who_and_when_still_parse_out_of_the_longer_line(folder: Path) -> None:
    """The line grew a bracketed clause between the name and the colon. `reviewed_empty` is
    what prints "reviewed <date> by <who>" to a person, and it reads the same line."""
    session(folder, DAY)
    interview.record_review("smitc", "no client was named", folder, on=DAY.isoformat())
    assert interview.reviewed_empty(folder) == (DAY.isoformat(), "smitc")


# ------------------------------------------------- an old line is read, not trusted


def legacy(folder: Path, on: str = "2026-09-18") -> None:
    path = folder / "identifiers.txt"
    path.write_text(
        path.read_text(encoding="utf-8") + f"# reviewed {on} by smitc: written before P64\n",
        encoding="utf-8",
    )


def test_an_old_acknowledgement_covers_only_what_was_logged_strictly_before_it(
    folder: Path,
) -> None:
    """It carries no list, and the one thing not known about it is whether the same-day
    session came first. Read conservatively: the cost of being wrong the safe way is running
    `register --none` again."""
    session(folder, DAY - dt.timedelta(days=1))
    legacy(folder)
    assert current(folder), "an old acknowledgement stopped covering what it did cover"

    session(folder, DAY)
    assert not current(folder), "an old acknowledgement was trusted over a same-day session"


def test_an_old_line_reports_no_coverage_rather_than_empty_coverage(folder: Path) -> None:
    """`None` and `()` must not be confused: one is a line that says nothing about what it
    looked at, the other is a line that says it looked at nothing."""
    legacy(folder)
    assert interview._reviewed_over(folder) is None

    interview.record_review("smitc", "nobody", folder, on=DAY.isoformat())
    assert interview._reviewed_over(folder) == ()


# ------------------------------------------------- and the command says which it has


def test_scan_tells_a_person_which_kind_of_acknowledgement_it_read(
    folder: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Only the module attribute, because P65 made every handler name the folder it works
    # on. Patching each helper's __defaults__ was what this had to do before that, and is
    # exactly the fragility P65 removed.
    outside = folder.parent / "outside"
    outside.mkdir()
    monkeypatch.setattr(interview, "KNOWLEDGE", folder)
    monkeypatch.setattr(
        interview, "committable_files", lambda root=None: sorted(outside.rglob("*"))
    )

    session(folder, DAY)
    interview.record_review("smitc", "nobody", folder, on=DAY.isoformat())
    assert interview.main(["scan"]) == 0
    said = capsys.readouterr().out
    assert "clean" in said
    assert "Made over 1 session(s)" in said, said
    assert DAY.isoformat() + "-1" in said, "the person is not told which session was covered"
