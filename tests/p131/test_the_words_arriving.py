"""P131: the prose checks, where the prose actually moves.

`tools/prose_checks.py` was built in P126 and reached from the command line. This joins it
to the one place in this build where prose enters a client deliverable: the moment an
appendix's content is transplanted into the report.

The reason to put it *there* rather than leave it to `/review` is the analyst's own
request - *"checks like when it is actually running"*. Appendix commentary is where a draft
written with a model enters a report, the preview is where somebody is already looking, and
a check nobody has to remember is a check that runs.

Three things it must not do, and each has a test:

* **it must not stop the update.** Whether a sentence should say something else is a
  judgement, and an appendix that failed to move because of an em dash would be the tool
  deciding something that is not its decision.
* **it must not report silence as clean.** A source it could not read says so, with the
  reason, and the appendix still moves.
* **it must not reach Appendix H.** Nothing here changes that - the certification is not
  `updated` and no path in `report/setup.py` writes it - and it is asserted because this
  phase added a field to `Change` and that is the kind of change that erodes a boundary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from docx import Document

from registries.errors import RegistryError
from report import preview, set_up, update
from tests.docs import a_report, appendix_source

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def desk(tmp_path: Path) -> dict[str, Path]:
    """Last year's report, this period's copy, and a source whose words are a problem."""
    last_year = tmp_path / "Valuation 2025.docx"
    a_report().save(str(last_year))

    source = tmp_path / "economic-conditions.docx"
    document = appendix_source()
    document.add_paragraph(
        "In today's economic environment the the outlook improved — a testament to "
        "policy ."
    )
    document.save(str(source))

    return {
        "last_year": last_year,
        "this_year": set_up(last_year, tmp_path / "Valuation 2026.docx"),
        "source": source,
    }


def findings(change: Any) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for one in change.prose.get("findings", []):
        out.setdefault(one["check"], []).append(one)
    return out


# ------------------------------------------------------- the words arriving are read


def test_the_preview_says_what_is_wrong_with_the_words_arriving(desk: dict[str, Path]) -> None:
    """The preview is where somebody is already looking, so it is where the findings go."""
    change = preview(desk["this_year"], "economic", desk["source"])
    found = findings(change)
    assert "em_dash" in found
    assert "repeated_word" in found
    assert "space_before_punctuation" in found
    assert "register_phrase" in found
    assert change.dry_run is True


def test_the_update_says_the_same_thing_as_its_preview(desk: dict[str, Path]) -> None:
    """`preview` takes the same path and stops before the write, so the two cannot
    disagree - and that has to stay true of the half added here."""
    shown = preview(desk["this_year"], "economic", desk["source"])
    done = update(desk["this_year"], "economic", desk["source"])
    assert findings(done).keys() == findings(shown).keys()
    assert done.prose["paragraphs"] == shown.prose["paragraphs"]


def test_the_mechanical_ones_are_counted_apart_from_the_judgements(
    desk: dict[str, Path],
) -> None:
    """A word typed twice is provably a mistake. An em dash is a judgement. A count that
    mixed them would be a number nobody could act on."""
    change = preview(desk["this_year"], "economic", desk["source"])
    assert change.slips >= 2
    assert change.slips < len(change.prose["findings"]), "the tells are not slips"
    assert "mechanical" in change.summary()


def test_a_source_with_nothing_wrong_with_it_says_nothing(tmp_path: Path) -> None:
    """The half that is easy to lose. The appendix source this suite already uses is
    ordinary prose, and the findings on it are the measure of whether this is worth
    having in front of somebody."""
    last_year = tmp_path / "last.docx"
    a_report().save(str(last_year))
    this_year = set_up(last_year, tmp_path / "this.docx")
    source = tmp_path / "plain.docx"
    appendix_source().save(str(source))

    change = preview(this_year, "economic", source)
    assert change.prose["findings"] == [], change.prose["findings"]
    assert change.slips == 0
    assert "to look at" not in change.summary()


# ------------------------------------------------------------- and it changes nothing


def test_the_appendix_still_moves_when_the_words_are_a_problem(desk: dict[str, Path]) -> None:
    """The invariant. An appendix that failed to move because of an em dash would be this
    tool deciding something that is not its decision."""
    from tests.docs import text_of

    change = update(desk["this_year"], "economic", desk["source"])
    assert change.written_to
    assert change.complete
    assert Path(change.written_to).is_file()
    arrived = text_of(Document(change.written_to))
    assert "Economic conditions in the period under review." in arrived
    assert change.prose["findings"], "and it said what was wrong on the way past"


def test_a_source_the_prose_checks_cannot_read_is_reported_rather_than_passed(
    desk: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Absence is never a pass, and it is never a refusal either: the appendix moves and
    the record says the words were not looked at.

    The reader is made to fail at its own call into the prose checks rather than through a
    stand-in for the whole function, so what is exercised is the `try` that is actually in
    `report/setup.py`.
    """
    import tools.prose_checks as prose

    def explode(_path: Path) -> Any:
        raise RuntimeError("python-docx fell over")

    monkeypatch.setattr(prose, "read", explode)
    change = update(desk["this_year"], "economic", desk["source"])

    assert change.written_to, "the appendix still moved"
    assert Path(change.written_to).is_file()
    assert change.prose["findings"] == []
    assert change.prose["skipped"], "and the record says nothing was looked at"
    assert "python-docx fell over" in change.prose["skipped"][0]
    assert "still moved" in change.prose["skipped"][0]


def test_the_reader_itself_turns_a_failure_into_a_skip(tmp_path: Path) -> None:
    """The function, called directly on something that is not a document at all."""
    import report.setup as setup

    broken = tmp_path / "not-a-document.docx"
    broken.write_bytes(b"certainly not a docx")
    out = setup._read_the_words_arriving(broken)
    assert out["findings"] == []
    # The prose checks handle this themselves and say it better than the `except` here
    # would: "Nothing was checked in it - which is not the same as nothing being wrong."
    # So this asserts the message a person sees rather than which layer produced it.
    assert out["skipped"]
    assert "did not open as a Word document" in out["skipped"][0]
    assert "not the same as nothing being wrong" in out["skipped"][0]


def test_nothing_here_reaches_the_certification(desk: dict[str, Path]) -> None:
    """Added as a field to `Change`, which is the kind of change that erodes a boundary.
    The certification is not an appendix this module updates, and that is a property of
    the registry rather than a sentence in a docstring - so it is asked of the registry."""
    from report.appendices import APPENDICES, updatable

    certification = next(a for a in APPENDICES if a.id == "certification")
    assert certification.updated is False
    assert certification not in updatable(APPENDICES)

    with pytest.raises(RegistryError) as refused:
        preview(desk["this_year"], "certification", desk["source"])
    assert "not updated by this tool" in refused.value.diagnostic.detail
