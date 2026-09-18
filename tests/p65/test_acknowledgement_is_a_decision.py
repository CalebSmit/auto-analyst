"""P65: an acknowledgement is a decision, not a default.

Found by running the command, not by reading it. A session probing exit codes ran
`register --none` with no text against this repo and destroyed the acknowledgement that was
there: the code supplied a note of its own, `record_review` replaced the standing line
without a word, and the whole thing exited 0. What was lost was a person's record of what
they had looked at.

Two rules, both of which the repo already applies elsewhere and neither of which was applied
here. A methodology clearance records that a person read a file, so it cannot be written by
the code; an acknowledgement's note is the same thing and was being defaulted. And P57
refuses to re-approve a recipe at bytes already approved, because a second decision that
changed nothing makes a chain nobody can audit; a standing acknowledgement is the same case.

Renewing a *stale* acknowledgement stays allowed, because that is the legitimate act - and
`test_a_stale_acknowledgement_can_still_be_renewed` is what stops this being fixed by making
the command refuse always.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import pytest

from tools import interview

DAY = dt.date(2026, 9, 18)
WORDS = "checked the three sessions; no client, person or entity has been named"


@pytest.fixture
def cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The real `main([...])`, against a knowledge folder of our own.

    Pointing `interview.KNOWLEDGE` is the whole of it, and that is the point of this phase.
    Before it, the CLI handlers called helpers whose `knowledge` default was bound at
    definition and could not follow this patch, so a test that did exactly this still wrote
    to the repo's own `knowledge/` - which is how a session of this build downgraded a real
    topic from covered to partial and destroyed a real acknowledgement.
    `test_no_command_touches_the_real_knowledge_folder` is the one that holds that closed.
    """
    folder = tmp_path / "knowledge"
    interview.init(folder)
    monkeypatch.setattr(interview, "KNOWLEDGE", folder)
    return folder


def session(folder: Path, on: dt.date = DAY) -> Path:
    log = interview.start_session(folder, today=on)
    with log.open("a", encoding="utf-8") as fh:
        fh.write("\n## Q1\n\nAn answer, with no name in it.\n")
    return log


def line(folder: Path) -> str:
    return (folder / "identifiers.txt").read_text(encoding="utf-8")


# ------------------------------------------------- a note is the decision


def test_an_acknowledgement_with_no_words_records_nothing(
    cli: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = line(cli)
    assert interview.main(["register", "--none", "", "--who", "smitc"]) == 2
    assert line(cli) == before, "an acknowledgement was written with no words in it"
    assert "words of your own" in capsys.readouterr().out


def test_whitespace_is_not_words(cli: Path) -> None:
    before = line(cli)
    assert interview.main(["register", "--none", "   ", "--who", "smitc"]) == 2
    assert line(cli) == before


def test_the_words_a_person_gives_are_the_ones_recorded(cli: Path) -> None:
    session(cli)
    assert interview.main(["register", "--none", WORDS, "--who", "smitc"]) == 0
    assert WORDS in line(cli)


# ------------------------------------------------- a standing record is not replaced


def test_a_standing_acknowledgement_is_not_replaced(
    cli: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The failure this phase exists for: one careless invocation destroyed a record."""
    session(cli)
    assert interview.main(["register", "--none", WORDS, "--who", "smitc"]) == 0
    written = line(cli)

    assert interview.main(["register", "--none", "different words", "--who", "someone"]) == 1
    assert line(cli) == written, "a standing acknowledgement was overwritten"
    said = capsys.readouterr().out
    assert "already stands" in said
    assert "smitc" in said and DAY.isoformat() in said, "the refusal does not say whose it is"


def test_a_stale_acknowledgement_can_still_be_renewed(cli: Path) -> None:
    """The other side. A rule that refuses everything is not a rule - and renewing a stale
    acknowledgement is exactly how a person closes the next session."""
    session(cli)
    assert interview.main(["register", "--none", WORDS, "--who", "smitc"]) == 0
    session(cli, DAY + dt.timedelta(days=1))
    renewed = ["register", "--none", "looked again, still nobody", "--who", "smitc"]
    assert interview.main(renewed) == 0
    assert "looked again, still nobody" in line(cli)


def test_only_one_acknowledgement_is_ever_in_the_file(cli: Path) -> None:
    session(cli)
    interview.main(["register", "--none", WORDS, "--who", "smitc"])
    session(cli, DAY + dt.timedelta(days=1))
    interview.main(["register", "--none", "looked again", "--who", "smitc"])
    assert len([ln for ln in line(cli).splitlines() if interview._REVIEWED.match(ln.strip())]) == 1


def test_a_register_with_names_in_it_has_nothing_to_acknowledge(cli: Path) -> None:
    interview.main(["register", "Northgate Dental Partners"])
    assert interview.main(["register", "--none", WORDS, "--who", "smitc"]) == 1


# ------------------------------------------------- refusals are sentences


def test_an_unknown_topic_says_why_rather_than_raising(
    cli: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A traceback in the middle of an interview is noise a person reads past to reach the
    one sentence that matters, and the sentence was already written."""
    assert interview.main(["mark", "not-a-topic", "covered"]) == 2
    said = capsys.readouterr().out
    assert "not-a-topic" in said and "topics.yaml" in said
    assert "Traceback" not in said
    assert "interview.py topics" in said, "the refusal does not say where the topics are"


def test_a_known_topic_still_marks(cli: Path) -> None:
    known = interview.load_topics()[0].id
    assert interview.main(["mark", known, "partial", "--note", "n"]) == 0
    assert interview.load_coverage(cli)[known]["status"] == "partial"


# ------------------------------------------------- and nothing reaches the real folder


def test_no_command_touches_the_real_knowledge_folder(
    cli: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The root cause, held closed.

    Two accidents in this build wrote to the repo's own `knowledge/` from a test that had
    pointed `interview.KNOWLEDGE` somewhere else: one downgraded a topic from covered to
    partial, one destroyed a person's acknowledgement. Neither was noticed by a test,
    because the tests were the thing doing it.

    The cause was two ways of finding the folder - this module attribute, and parameter
    defaults bound at definition that cannot follow it. Every CLI handler now names the
    folder it works on. This runs every command and fingerprints the real directory around
    them, so the next helper called bare fails here rather than in somebody's register.
    """
    real = Path(interview.ROOT) / "knowledge"
    fingerprint = lambda: {  # noqa: E731 - a fingerprint, read twice, is clearer inline
        p.relative_to(real).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(real.rglob("*"))
        if p.is_file()
    }
    before = fingerprint()
    assert before, "the real knowledge/ is empty; this test would pass over anything"

    topic = interview.load_topics()[0].id
    for argv in (
        ["status"],
        ["topics"],
        ["scan"],
        ["suggest"],
        ["session"],
        ["mark", topic, "partial", "--note", "a note"],
        ["register", "Northgate Dental Partners"],
        ["register", "--none", WORDS, "--who", "smitc"],
    ):
        interview.main(argv)
    capsys.readouterr()

    assert fingerprint() == before, "a command reached the repo's own knowledge/ folder"
    assert (cli / "coverage.yaml").read_text(encoding="utf-8").count(topic) == 1
