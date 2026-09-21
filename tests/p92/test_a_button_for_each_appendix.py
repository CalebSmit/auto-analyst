"""P92 - A button for each appendix that changes.

Three buttons. The tests are mostly about what an update must *not* do: touch another
appendix, touch the file it read, or reach Appendix H.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from docx import Document

from registries.errors import RegistryError
from report import APPENDICES, preview, set_up, update, what_would_change
from report.appendices import updatable
from tests.docs import a_report, appendix_source, text_of

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def desk(tmp_path: Path) -> dict[str, Path]:
    """Last year's report, this period's copy of it, and a source document."""
    last_year = tmp_path / "Valuation 2025.docx"
    a_report().save(str(last_year))
    source = tmp_path / "economic-conditions.docx"
    appendix_source().save(str(source))
    this_year = set_up(last_year, tmp_path / "Valuation 2026.docx")
    return {"last_year": last_year, "this_year": this_year, "source": source}


def read(path: Path | str) -> str:
    return text_of(Document(str(path)))


# ============================================================ starting from last year


def test_the_report_starts_as_a_copy_of_last_year_s(tmp_path: Path) -> None:
    """Everything that carries forward does so by being copied rather than regenerated -
    the boilerplate, Appendix G, the certification, the qualifications. Nothing is
    regenerated that nobody asked to change."""
    last_year = tmp_path / "last.docx"
    a_report().save(str(last_year))
    this_year = set_up(last_year, tmp_path / "out" / "this.docx")
    assert this_year.read_bytes() == last_year.read_bytes()


def test_a_report_that_is_not_there_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(RegistryError) as refused:
        set_up(tmp_path / "nothing.docx", tmp_path / "out.docx")
    assert refused.value.diagnostic.code == "CONFIG.PATH_UNREADABLE"


# ============================================================ one appendix, not the report


def test_updating_one_appendix_replaces_its_content(desk: dict[str, Path]) -> None:
    change = update(desk["this_year"], "economic", desk["source"])
    after = read(change.written_to)
    assert "Economic conditions in the period under review." in after
    assert "Last year's economic conditions, still in place." not in after


def test_every_other_appendix_is_left_exactly_as_it_was(desk: dict[str, Path]) -> None:
    """An update that touched a second appendix would be a bug rather than a convenience:
    each one's source becomes ready at its own moment, and the others are not ready."""
    before = read(desk["this_year"])
    change = update(desk["this_year"], "economic", desk["source"])
    after = read(change.written_to)

    for kept in (
        "Appendix E - Summary of Major Market Indices",
        "Last year's summary of major market indices, still in place.",
        "Appendix F - Summary of M&A Markets",
        "Appendix H - Certification",
        "Last year's certification, still in place.",
        "The body of the report, which nothing here touches.",
    ):
        assert kept in before and kept in after, kept


def test_the_same_appendix_can_be_updated_a_second_time(desk: dict[str, Path]) -> None:
    """The defect C55 found, and it was fatal: the update used to remove the anchor's own
    block, so the first press deleted the heading it had bound to and no later press could
    find the appendix again. Pressing twice is the ordinary case - the data is corrected,
    or the quarter turns."""
    first = update(desk["this_year"], "economic", desk["source"])
    second = update(first.written_to, "economic", desk["source"])
    after = read(second.written_to)
    assert "Appendix C - Economic Conditions" in after
    assert after.count("Economic conditions in the period under review.") == 1


def test_a_bookmark_survives_being_updated(desk: dict[str, Path]) -> None:
    """A bookmark is what somebody marked deliberately, and it lives on the heading. An
    update that took the heading took the bookmark with it, silently - and the appendix
    then bound to nothing."""
    from tests.docs import bookmark

    document = Document(str(desk["this_year"]))
    heading = next(
        p for p in document.paragraphs if p.text == "Appendix C - Economic Conditions"
    )
    bookmark(heading, "Appendix C - Economic Conditions", number=30)
    document.save(str(desk["this_year"]))

    change = update(desk["this_year"], "economic", desk["source"])
    from report.anchors import find_anchor

    assert find_anchor(Document(change.written_to), "Appendix C - Economic Conditions").kind == (
        "bookmark"
    )


def test_a_source_that_repeats_the_heading_does_not_produce_two(
    desk: dict[str, Path],
) -> None:
    """The report keeps its own heading, so a source document that also starts with the
    appendix title would give two. Some of these documents carry their title and some do
    not, and neither is wrong."""
    document = Document(str(desk["source"]))
    title = document.add_paragraph("Appendix C - Economic Conditions")
    document.element.body.insert(0, title._p)
    document.save(str(desk["source"]))

    change = update(desk["this_year"], "economic", desk["source"])
    assert read(change.written_to).count("Appendix C - Economic Conditions") == 1


def test_the_appendix_s_own_sub_heading_goes_with_it(desk: dict[str, Path]) -> None:
    """A sub-heading inside Appendix C is Appendix C's. Leaving it behind would put last
    year's structure above this year's content."""
    change = update(desk["this_year"], "economic", desk["source"])
    assert read(change.written_to).count("A sub-heading inside the appendix") == 3


def test_two_appendices_can_be_updated_one_after_the_other(desk: dict[str, Path]) -> None:
    """The point of a button each: he presses industry when the industry data is ready,
    and economic later, without the first update being undone."""
    first = update(desk["this_year"], "economic", desk["source"])
    second = update(first.written_to, "indices", desk["source"])
    after = read(second.written_to)
    assert after.count("Economic conditions in the period under review.") == 2
    assert "Last year's economic conditions, still in place." not in after
    assert "Last year's summary of major market indices, still in place." not in after


# ============================================================ never in place


def test_the_report_it_read_is_not_modified(desk: dict[str, Path]) -> None:
    """The input is usually the only copy of last year's work, and an in-place edit is
    unrecoverable the moment it is wrong."""
    before = desk["this_year"].read_bytes()
    update(desk["this_year"], "economic", desk["source"])
    assert desk["this_year"].read_bytes() == before


def test_the_result_is_a_new_file_beside_the_report(desk: dict[str, Path]) -> None:
    change = update(desk["this_year"], "economic", desk["source"])
    written = Path(change.written_to)
    assert written.is_file()
    assert written != desk["this_year"]
    assert written.parent == desk["this_year"].parent


def test_pressing_it_twice_leaves_two_files(desk: dict[str, Path]) -> None:
    """Rather than one overwritten one. Somebody who pressed it twice wants to be able to
    look at both."""
    first = update(desk["this_year"], "economic", desk["source"])
    second = update(desk["this_year"], "economic", desk["source"])
    assert first.written_to != second.written_to
    assert Path(first.written_to).is_file() and Path(second.written_to).is_file()


# ============================================================ showing before doing


def test_a_preview_writes_nothing(desk: dict[str, Path]) -> None:
    before = sorted(p.name for p in desk["this_year"].parent.iterdir())
    change = preview(desk["this_year"], "economic", desk["source"])
    assert change.dry_run and not change.written_to
    assert sorted(p.name for p in desk["this_year"].parent.iterdir()) == before


def test_a_preview_reports_the_same_change_the_write_makes(desk: dict[str, Path]) -> None:
    """They take the same path and the preview stops before the write, so the two cannot
    disagree - which is the only thing that makes a preview worth looking at."""
    shown = preview(desk["this_year"], "economic", desk["source"]).as_dict()
    done = update(desk["this_year"], "economic", desk["source"]).as_dict()
    for field in ("replaced_blocks", "arriving_blocks", "styles", "numbering", "left_behind"):
        assert shown[field] == done[field], field


def test_the_panel_says_whether_an_anchor_is_even_there(desk: dict[str, Path]) -> None:
    """Asked on load rather than on press: a missing anchor is worth knowing about while
    there is still time to bookmark it."""
    rows = what_would_change(desk["this_year"])
    assert [r["appendix"] for r in rows] == ["economic", "indices", "ma"]
    assert all(r["found"] for r in rows)
    assert all(r["owns"] > 0 for r in rows)


def test_a_missing_anchor_is_reported_rather_than_hidden(tmp_path: Path) -> None:
    """A report without the heading this binds to is the ordinary case for a firm that
    words its appendices differently - and it must say so, not fail at the press."""
    thin = tmp_path / "thin.docx"
    document = Document()
    document.add_heading("Appendix C - Economic Conditions", 1)
    document.save(str(thin))

    rows = {r["appendix"]: r for r in what_would_change(thin)}
    assert rows["economic"]["found"] is True
    assert rows["ma"]["found"] is False
    assert "Appendix F" in rows["ma"]["detail"]


# ============================================================ the line


def test_no_button_exists_for_the_certification() -> None:
    """The hardest non-negotiable, satisfied by there being no code path.

    Appendix H is not in `updatable()`, so nothing the page offers reaches it, and the
    update refuses it outright if anybody constructs the call by hand.
    """
    assert "certification" not in {a.id for a in updatable()}
    assert {a.letter for a in updatable()} == {"C", "E", "F"}


def test_updating_a_carried_forward_appendix_is_refused(desk: dict[str, Path]) -> None:
    for carried in ("certification", "assumptions", "qualifications"):
        with pytest.raises(RegistryError) as refused:
            update(desk["this_year"], carried, desk["source"])
        detail = refused.value.diagnostic.detail
        assert "carries forward" in detail
        assert "economic" in detail, "and it names what can be updated"


def test_the_certification_survives_every_update_untouched(desk: dict[str, Path]) -> None:
    """The property, checked on the document rather than on the registry."""
    at = desk["this_year"]
    for which in ("economic", "indices", "ma"):
        at = Path(update(at, which, desk["source"]).written_to)
    after = read(at)
    assert "Appendix H - Certification" in after
    assert "Last year's certification, still in place." in after


def test_nothing_in_the_report_package_writes_a_conclusion() -> None:
    """Said as a property of the code: the update path reaches an appendix only through
    `appendix()`, and refuses one that is not `updated`. There is no second door."""
    source = (ROOT / "report" / "setup.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    guarded = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "updated"
    ]
    assert guarded, "the check that stops a carried-forward appendix being written is gone"


# ============================================================ what it says it did


def test_the_result_names_what_could_not_be_carried(desk: dict[str, Path]) -> None:
    """Silently losing an exhibit is how a report goes out with a hole in it."""
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    document = Document(str(desk["source"]))
    paragraph = document.add_paragraph("A chart lives here.")
    holder = paragraph._p.makeelement(f"{W}object", {})
    holder.set(f"{R}id", "rIdMissing")
    paragraph._p.append(holder)
    document.save(str(desk["source"]))

    change = update(desk["this_year"], "economic", desk["source"])
    assert not change.complete
    assert any("rIdMissing" in note for note in change.as_dict()["left_behind"])


def test_updating_twice_does_not_leave_two_parts_at_one_name(desk: dict[str, Path]) -> None:
    """A .docx is a zip, and two entries under one name is a corrupt file.

    An image part carries its own partname - `/word/media/image1.png` - from the document
    it came from. Relating it straight across puts a second part at a name the destination
    already uses, and python-docx writes that file with a warning rather than an error.
    Found by updating two appendices from the same source, which is the ordinary case;
    asserted here because a warning nobody turns into a failure is not a test.
    """
    import zipfile

    first = update(desk["this_year"], "economic", desk["source"])
    second = update(first.written_to, "indices", desk["source"])

    with zipfile.ZipFile(second.written_to) as package:
        names = package.namelist()
    assert len(names) == len(set(names)), sorted(
        n for n in names if names.count(n) > 1
    )
    assert Document(second.written_to) is not None


def test_the_same_image_in_two_appendices_is_stored_once(desk: dict[str, Path]) -> None:
    """And the other half of the same fix: a chart that appears in two appendices is one
    part, not two copies of the same bytes."""
    import zipfile

    first = update(desk["this_year"], "economic", desk["source"])
    second = update(first.written_to, "indices", desk["source"])
    with zipfile.ZipFile(second.written_to) as package:
        media = [n for n in package.namelist() if n.startswith("word/media/")]
    assert len(media) == 1, media


def test_the_result_says_how_much_it_took_out(desk: dict[str, Path]) -> None:
    """An appendix that owns forty blocks when it should own four means the anchor is
    bound to the wrong place, and that is visible here before it is visible in Word."""
    change = update(desk["this_year"], "economic", desk["source"])
    # Three, not four: the anchor's own heading stays, so what comes out is the content
    # under it. The count is shown because an appendix that takes forty blocks out when it
    # should take three means the anchor is bound to the wrong place.
    assert change.replaced_blocks == 3
    assert "block(s) out" in change.summary()


def test_a_source_document_that_is_not_there_is_refused_by_name(
    desk: dict[str, Path],
) -> None:
    with pytest.raises(RegistryError) as refused:
        update(desk["this_year"], "economic", desk["this_year"].parent / "nope.docx")
    assert refused.value.diagnostic.code == "CONFIG.PATH_UNREADABLE"
    assert "source document" in refused.value.diagnostic.detail


# ============================================================ the buttons


def test_the_page_offers_a_button_for_each_appendix_that_changes() -> None:
    from admin.page import PAGE

    for action in ("pickReport", "updateAppendix", "previewAppendix"):
        assert f"ACTIONS.{action}" in PAGE, action
        assert f'data-act="{action}"' in PAGE or f"data-act=\"{action}\"" in PAGE, action
    assert "grid-area:report" in PAGE


def test_the_page_explains_why_there_are_three_and_not_six() -> None:
    """A missing button is a question somebody will ask, and the answer belongs where
    they would look for it rather than in a docstring nobody opens."""
    from admin.page import PAGE

    assert "no part of this system writes the certification" in PAGE
    assert "carry forward in the copy of last year's report" in PAGE


def test_the_report_package_is_reached_by_something_a_person_can_press() -> None:
    """P91 built it and nothing called it, which is the defect this build keeps finding.
    This is the join, asserted rather than assumed."""
    console = (ROOT / "admin" / "console.py").read_text(encoding="utf-8")
    for named in ("what_would_change", "set_up", "preview", "update"):
        assert f"from report import {named}" in console or f", {named}" in console, named
    assert "def update_appendix" in console


def test_the_registry_the_page_shows_is_the_registry_the_update_uses() -> None:
    """Two lists of appendices would drift, and the drift would look like a button that
    does nothing."""
    assert {a.id for a in updatable()} == {
        row["appendix"] for row in _rows_for_a_full_report()
    }


def _rows_for_a_full_report() -> list[dict[str, Any]]:
    import tempfile

    folder = Path(tempfile.mkdtemp())
    path = folder / "r.docx"
    a_report().save(str(path))
    return what_would_change(path)


def test_the_default_registry_is_the_six_he_named() -> None:
    assert [a.letter for a in APPENDICES] == ["C", "E", "F", "G", "H", "I"]
