"""Filling the register from what was already said, and the empty register that is honest.

P53 made the leak scan refuse an empty register. P54 made the refusal correct about which
machines it applies to. Both assumed the thing that turned out not to be true here: that
answers existing means names exist.

Running `suggest` over this repo's three sessions found six candidates and not one client
among them - "Gordon Growth", "Managing Director", "Claude Code". The interview had been
conducted generically throughout, about how the work is done rather than whose work it was.
So the register was empty because nothing had needed to go in it, and the check was raising
a false alarm at the close of every session.

The answer is not a cleverer detector. It is the move methodology clearance already makes: a
person reads something and records that they did, under their own name - and the record
expires, because an acknowledgement covers the answers that existed when it was written.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import interview


def knowledge(root: Path) -> Path:
    """`<root>/knowledge`, beside a `<root>/outside` standing in for the committable tree.
    Separate directories on purpose: `suggest` asks both, and a fixture where they were the
    same path made "does this also appear outside knowledge/" unanswerable."""
    here = root / "knowledge"
    here.mkdir()
    interview.init(here)
    real = Path(interview.ROOT) / "knowledge" / "README.md"
    (here / "README.md").write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    return here


def answered(folder: Path, stem: str = "2026-09-16-1", body: str = "We do it this way.") -> Path:
    log = folder / "sessions" / f"{stem}.md"
    log.write_text(
        f"# Session {stem}\n\n{interview.SESSION_HEADER}\n## Q1\n\n{body}\n", encoding="utf-8"
    )
    return log


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    here = knowledge(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    for fn in (
        interview.init,
        interview.identifiers,
        interview._knowledge_has_answers,
        interview.reviewed_empty,
        interview.add_identifiers,
    ):
        monkeypatch.setattr(fn, "__defaults__", (here,))
    monkeypatch.setattr(interview.record_review, "__defaults__", (here, None))
    monkeypatch.setattr(interview.suggest, "__defaults__", (here, tmp_path))
    monkeypatch.setattr(interview, "KNOWLEDGE", here)
    monkeypatch.setattr(interview, "ROOT", tmp_path)
    monkeypatch.setattr(
        interview, "committable_files", lambda root=tmp_path: sorted(outside.rglob("*"))
    )
    return here


# ---------------------------------------------------------------- what it proposes


def test_it_proposes_a_company_and_a_person_from_an_answer(folder: Path) -> None:
    answered(
        folder,
        body="The client is Northgate Dental Partners. R. Whitfield is the owner and we "
        "tested his compensation against the benchmark.",
    )
    proposed = {c.text: c for c in interview.suggest(folder, folder.parent)}

    assert "Northgate Dental Partners" in proposed
    assert proposed["Northgate Dental Partners"].kind == "entity"
    assert "R. Whitfield" in proposed
    assert proposed["R. Whitfield"].kind == "person"
    assert proposed["Northgate Dental Partners"].first_seen.startswith("sessions/2026-09-16-1.md:")


def test_it_does_not_propose_what_is_already_registered(folder: Path) -> None:
    answered(folder, body="The client is Northgate Dental Partners.")
    interview.add_identifiers(["Northgate Dental Partners"], folder)
    proposed = {c.text for c in interview.suggest(folder, folder.parent)}
    assert "Northgate Dental Partners" not in proposed


def test_ordinary_prose_is_not_proposed(folder: Path) -> None:
    """A list a person has to read is only useful if most of it is worth reading."""
    answered(
        folder,
        body="We normalise the historicals first, then the add-backs. The associate "
        "reviews it before it goes up. This usually takes about a day.",
    )
    assert [c.text for c in interview.suggest(folder, folder.parent)] == []


def test_it_writes_nothing(folder: Path) -> None:
    """It proposes. A name enters the register because a person put it there - the same
    reason nothing in privacy/ lets a model decide who somebody is."""
    answered(folder, body="The client is Northgate Dental Partners.")
    register = folder / "identifiers.txt"
    before = register.read_text(encoding="utf-8")

    assert interview.main(["suggest"]) == 0

    assert register.read_text(encoding="utf-8") == before
    assert interview.identifiers(folder) == []


def test_a_candidate_already_outside_knowledge_is_marked_not_dropped(folder: Path) -> None:
    """Usually it means the phrase is this build's own vocabulary. The other reading is that
    a client's name has already reached a committable file, which is the one case the
    register exists to catch - so it is flagged rather than filtered away."""
    answered(folder, body="The client is Northgate Dental Partners.")
    leaked = folder.parent / "outside" / "SKILL.md"
    leaked.write_text("Worked example: Northgate Dental Partners.\n", encoding="utf-8")

    (candidate,) = [c for c in interview.suggest(folder, folder.parent) if "Northgate" in c.text]
    assert candidate.outside is True


# ------------------------------------------------- an empty register that has been looked at


def test_an_acknowledged_empty_register_scans_clean(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    answered(folder)
    assert interview.main(["scan"]) == 1, "before anybody has looked"
    capsys.readouterr()

    interview.record_review("caleb", "no client has been named yet", folder, on="2026-09-17")
    assert interview.main(["scan"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("clean:")
    assert "caleb" in out and "2026-09-17" in out


def test_the_acknowledgement_expires_when_a_newer_session_is_recorded(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The half that keeps this from being an off switch. An acknowledgement is about the
    answers that existed when it was written; the next session's answers are not covered by
    somebody having read the ones before them."""
    answered(folder)
    interview.record_review("caleb", "nothing named yet", folder, on="2026-09-17")
    assert interview.main(["scan"]) == 0
    capsys.readouterr()

    answered(folder, stem="2026-09-18-1", body="The client is Northgate Dental Partners.")

    assert interview.main(["scan"]) == 1
    out = capsys.readouterr().out
    assert "UNCHECKED" in out
    assert "reviewed on 2026-09-17" in out
    assert "recorded since" in out


def test_an_acknowledgement_is_not_an_identifier(folder: Path) -> None:
    """It is a comment. `scan` must not start searching every committable file for the
    reviewer's own name."""
    interview.record_review("caleb", "nothing named yet", folder, on="2026-09-17")
    assert interview.identifiers(folder) == []


def test_recording_one_over_a_filled_register_is_refused(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    interview.add_identifiers(["Northgate Dental Partners"], folder)
    assert interview.main(["register", "--none", "nothing here"]) == 1
    assert "not empty" in capsys.readouterr().out


def test_a_second_review_replaces_the_first(folder: Path) -> None:
    """One line, not a pile. The current answer to "when did somebody last look" has to be
    a single unambiguous date."""
    interview.record_review("caleb", "first", folder, on="2026-09-17")
    interview.record_review("caleb", "second", folder, on="2026-09-18")
    body = (folder / "identifiers.txt").read_text(encoding="utf-8")
    assert body.count("# reviewed") == 1
    assert interview.reviewed_empty(folder) == ("2026-09-18", "caleb")


# ------------------------------------------------------------------------ adding names


def test_register_adds_names_and_skips_duplicates(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert interview.main(["register", "Northgate Dental Partners", "R. Whitfield"]) == 0
    assert interview.identifiers(folder) == ["Northgate Dental Partners", "R. Whitfield"]

    capsys.readouterr()
    assert interview.main(["register", "R. Whitfield"]) == 0
    assert "already registered" in capsys.readouterr().out
    assert interview.identifiers(folder) == ["Northgate Dental Partners", "R. Whitfield"]


def test_registering_a_name_makes_the_scan_check_for_it(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The point of the whole exercise, end to end: a name goes in, and a file outside
    knowledge/ that carries it is found."""
    answered(folder, body="The client is Northgate Dental Partners.")
    leaked = folder.parent / "outside" / "SKILL.md"
    leaked.write_text("Worked example: Northgate Dental Partners added back rent.\n", "utf-8")

    interview.main(["register", "Northgate Dental Partners"])
    capsys.readouterr()

    assert interview.main(["scan"]) == 1
    out = capsys.readouterr().out
    assert "SKILL.md:1" in out
    assert "FAIL: 1 identifier(s) outside knowledge/" in out
