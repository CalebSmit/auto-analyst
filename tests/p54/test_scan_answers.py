"""The scan that keeps a client's name inside `knowledge/`, asked rather than read.

`CLAUDE.md` names `interview.py scan` as the one check standing between a client's name and
a skill, a methodology file or a fixture. It has never done that job. Until P53 it returned
early on an empty register and printed `clean` unconditionally. P53 made it refuse instead -
and refuse is where it stayed, because `_knowledge_has_answers()` counted any `.md` over 400
bytes and `knowledge/README.md` ships with the repo at 522. There was no state of this repo
in which the command could return 0.

Both defects survived a test suite. The P53 test read the *source* of `_scan` for the string
`"UNCHECKED"`; the P37 test called `scan()` with a register that was empty, so it asserted
that finding nothing in nothing is nothing. Neither ever ran the command.

So these do. Every test here calls `main(["scan"])` and reads what a person would see.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import interview

ANSWER = "## Q1\n\nThe client is Northgate Dental Partners; Priya Raman is the owner.\n"


def knowledge(tmp_path: Path) -> Path:
    """A knowledge folder as a fresh clone has it: the skeleton `init()` lays down, plus the
    repo's own `knowledge/README.md`.

    That README is copied rather than invented, because its *size* is the whole point. It is
    committed and 533 bytes, and the predicate this phase replaced asked whether any `.md`
    under knowledge/ was over 400 - so the README alone answered yes on a machine where
    nobody had been interviewed. A fixture that wrote a shorter one would pass against the
    bug it exists to catch.
    """
    interview.init(tmp_path)
    real = Path(interview.ROOT) / "knowledge" / "README.md"
    (tmp_path / "README.md").write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    assert (tmp_path / "README.md").stat().st_size > 400, "the README must still be the trap"
    return tmp_path


def session(folder: Path, stem: str = "2026-09-17-1", body: str = "") -> Path:
    log = interview.start_session(folder, today=None)
    log.rename(log.with_name(f"{stem}.md"))
    log = folder / "sessions" / f"{stem}.md"
    if body:
        with log.open("a", encoding="utf-8") as fh:
            fh.write("\n" + body)
    return log


@pytest.fixture
def scanning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`scan` against a knowledge folder of our own, over files of our own.

    `committable_files()` is the real thing in production - every file git would commit
    outside `knowledge/`. Here it is the one file each test hands it, so a test says what
    it means: this text, that register.
    """
    folder = knowledge(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()

    # `reviewed_empty` is here because P56 added a call to it inside `_scan`, and its
    # default is the real `knowledge/`. Without this the scan under test reads this repo's
    # own register: these tests stayed green for exactly as long as nobody had recorded an
    # acknowledgement in it, and started failing the hour somebody did. A test that depends
    # on the state of the machine it runs on is a test that will be green when it matters.
    for fn in (
        interview.init,
        interview.identifiers,
        interview._knowledge_has_answers,
        interview.reviewed_empty,
    ):
        monkeypatch.setattr(fn, "__defaults__", (folder,))
    monkeypatch.setattr(interview, "KNOWLEDGE", folder)
    monkeypatch.setattr(interview, "ROOT", tmp_path)
    monkeypatch.setattr(
        interview, "committable_files", lambda root=tmp_path: sorted(outside.rglob("*"))
    )
    return folder, outside


# ------------------------------------------------------- the three states, each run for real


def test_a_clone_where_no_interview_has_happened_has_nothing_to_check(
    scanning, capsys: pytest.CaptureFixture[str]
) -> None:
    """The honest empty case, and the one the old predicate could not express.

    `knowledge/README.md` is committed and 522 bytes, so "any `.md` over 400 bytes" was
    true on a clone that had never been interviewed. Somebody setting this up on the work
    machine would have been told to add names they did not have yet.
    """
    assert interview.main(["scan"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("clean:")
    assert "no answers yet" in out
    assert "UNCHECKED" not in out


def test_answers_with_an_empty_register_refuses(
    scanning, capsys: pytest.CaptureFixture[str]
) -> None:
    """One recorded answer is enough. A name can appear in the first one."""
    folder, _ = scanning
    session(folder, body=ANSWER)

    assert interview.main(["scan"]) == 1
    out = capsys.readouterr().out
    assert "UNCHECKED" in out
    assert "clean" not in out


def test_answers_with_a_register_scans_for_real(
    scanning, capsys: pytest.CaptureFixture[str]
) -> None:
    folder, outside = scanning
    session(folder, body=ANSWER)
    (folder / "identifiers.txt").write_text(
        "# names\nNorthgate Dental Partners\nPriya Raman\n", encoding="utf-8"
    )
    (outside / "how-we-work.md").write_text("The client's owner is paid above market.\n", "utf-8")

    assert interview.main(["scan"]) == 0
    out = capsys.readouterr().out
    assert "clean: 2 identifiers checked" in out


def test_a_name_that_reached_a_committable_file_is_found_and_named(
    scanning, capsys: pytest.CaptureFixture[str]
) -> None:
    """The case the whole command exists for: an answer's name in a file that reaches every
    prompt for every client."""
    folder, outside = scanning
    session(folder, body=ANSWER)
    (folder / "identifiers.txt").write_text("Northgate Dental Partners\n", encoding="utf-8")
    leaked = outside / "SKILL.md"
    leaked.write_text("Worked example: Northgate Dental Partners added back rent.\n", "utf-8")

    assert interview.main(["scan"]) == 1
    out = capsys.readouterr().out
    assert "SKILL.md:1" in out
    assert "FAIL: 1 identifier(s) outside knowledge/" in out


# --------------------------------------------------- what counts as an answer, and what does not


def test_the_skeleton_is_not_an_answer(scanning) -> None:
    """Everything `init()` writes, plus the repo's own README. If laying the folder down
    counted as learning something, the refusal would fire before the first question."""
    folder, _ = scanning
    assert not interview._knowledge_has_answers(folder)


def test_a_session_opened_and_never_used_is_not_an_answer(scanning) -> None:
    """`interview.py session` runs at step 3 of the protocol, before the first question is
    asked. A log with nothing appended to it is a session that has learned nothing yet."""
    folder, _ = scanning
    session(folder)
    assert not interview._knowledge_has_answers(folder)


def test_one_appended_answer_is(scanning) -> None:
    folder, _ = scanning
    session(folder, body=ANSWER)
    assert interview._knowledge_has_answers(folder)


def test_a_document_a_client_sent_is(scanning) -> None:
    """`knowledge/projects/<codename>/docs/` is where real client documents are allowed to
    live. A folder holding one has certainly seen a name, whatever the session logs say."""
    folder, _ = scanning
    docs = folder / "projects" / "oakmont" / "docs"
    docs.mkdir(parents=True)
    (docs / "historicals.xlsx").write_bytes(b"\x50\x4b\x03\x04")
    assert interview._knowledge_has_answers(folder)


def test_the_projects_readme_is_not(scanning) -> None:
    folder, _ = scanning
    assert (folder / "projects" / "README.md").exists()
    assert not interview._knowledge_has_answers(folder)


# ------------------------------------------------------------ found at the start, not the end


def test_status_says_the_close_out_will_refuse_before_the_first_question(
    scanning, capsys: pytest.CaptureFixture[str]
) -> None:
    """The protocol runs `status` at step 2 and `scan` at step 6. Discovering at step 6 that
    the session cannot be closed is discovering it after every answer has been given."""
    folder, _ = scanning
    session(folder, body=ANSWER)

    assert interview.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "identifiers kept inside knowledge/: 0" in out
    assert "will refuse" in out
    # And it says what to do about it, which is the difference between a warning and a
    # nag. P56 added the two commands; naming them here keeps the two phases honest.
    assert "interview.py suggest" in out
    assert "interview.py register" in out


def test_status_stays_quiet_when_there_is_nothing_to_warn_about(
    scanning, capsys: pytest.CaptureFixture[str]
) -> None:
    folder, _ = scanning
    session(folder, body=ANSWER)
    (folder / "identifiers.txt").write_text("Northgate Dental Partners\n", encoding="utf-8")

    assert interview.main(["status"]) == 0
    assert "will refuse" not in capsys.readouterr().out
