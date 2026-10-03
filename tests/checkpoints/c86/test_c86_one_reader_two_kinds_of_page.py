"""C86 - one reader, two kinds of page.

P155 changed what a row is, and changed it for both kinds of page at once. The text-layer
path is the one with a hundred and eight pages of measured evidence behind it, and the one
with nothing new asking about it - `tests/p155` is about the scan. So this asks the question
from the other side: is the page that was always read still read the same way?

Three things are checked here and nowhere else.

**The whole filing, not one page.** P155's own evidence is page 56. A change to the band
predicate or the label rule reaches every page, and the counts P151 and P152 measured over
all hundred and eight are what would notice.

**Every footing re-added independently.** A total that re-adds is what lets a figure past a
person unseen. P155 added four by stripping a currency mark off a label, which is a change in
what a person is shown without being asked - so the arithmetic is done again here rather than
the reader asked whether it believes itself.

**The two paths against each other.** Not that each works: that they agree. A reader that
found most of a scanned statement would be worse than one that found none, because the
figures it found would carry locators and arithmetic cover and nothing would say what was
missing.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from intake.readers.documents import _tables_from_layout, read_document
from intake.readers.footing import footings_in, two_sides
from intake.readers.layout import lay_out_words
from ports.ocr import Box, OCRLine, OCRPage, OCRWord

ROOT = Path(__file__).resolve().parents[3]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"
CAPTURE = ROOT / "fixtures" / "public" / "ocr-sec-ars-3d-systems-p56.json"
BALANCE_SHEET = 56


@pytest.fixture(scope="module")
def filing():
    return read_document(FILING.read_bytes(), FILING.name)


@pytest.fixture(scope="module")
def scanned():
    """Page 56 as an engine read it, converted the way an adapter converts it."""
    captured = json.loads(CAPTURE.read_text(encoding="utf-8"))
    scale = 1 / captured["render_scale"]
    words = [
        OCRWord(
            text=f["text"],
            box=Box(
                x0=f["box"][0] * scale,
                top=f["box"][1] * scale,
                x1=f["box"][2] * scale,
                bottom=f["box"][3] * scale,
            ),
            confidence=f["confidence"],
        )
        for f in captured["fragments"]
    ]
    page = OCRPage(
        number=1,
        lines=tuple(OCRLine(text=w.text, confidence=w.confidence) for w in words),
        words=tuple(words),
        geometry="exact",
    )
    return _tables_from_layout(1, lay_out_words(1, page.laid_out()))


def values(built) -> list[tuple[str, float]]:
    return [
        (row.label, row.value)
        for table in built
        for column in table.columns
        for row in column.rows
        if row.value is not None
    ]


# ------------------------------------------------- the page that was always read, unchanged


def test_the_whole_filing_still_reads_as_it_was_measured(filing) -> None:
    """The counts P151 and P152 established over all hundred and eight pages.

    Written as four numbers rather than four tests because they move together: a change to
    what a band is, or to where a label stops, reaches every page at once, and one of these
    moving while the others hold is the interesting case.
    """
    rows = sum(
        1
        for page in filing.pages
        for table in page.tables
        for column in table.columns
        for row in column.rows
        if row.value is not None
    )
    tables = sum(len(page.tables) for page in filing.pages)
    named = sum(
        1
        for page in filing.pages
        for table in page.tables
        if table.headings and all(h for h in table.headings)
    )
    assert rows == 815, f"rows carrying a value moved to {rows}"
    assert tables == 72, f"tables moved to {tables}"
    # Twenty-seven until P163, and forty-five after it - this assertion is the one that
    # noticed, which is what it is for.
    #
    # P163 found that the band carrying a statement's dates was being thrown away: the
    # heading band was the *last* plain band before the figures, and `ASSETS` and
    # `Current assets:` always sit between the dates and the first row. So the years are
    # read from the nearest band above that dates every column, and eighteen more of this
    # filing's tables now say which column is which year. Tables and rows are deliberately
    # unchanged beside it: that phase writes column headings and touches neither the
    # columns nor the rows, and `tools/check_against_filer.py` still reports the same 194.
    #
    # Forty-eight here and forty-five in `tests/p163`, and both are right: this count takes
    # every table, and three single-column ones (p72, p85, p100) were named by the line
    # reader's heading line before this phase and still are. P163's count is over the
    # multi-column tables only, because one column is nothing to tell apart.
    assert named == 48, f"tables whose every column is named moved to {named}"


def test_every_footing_in_the_filing_re_adds_when_added_again(filing) -> None:
    """Given its rows, not asked whether it believes itself.

    P155 added four of these by taking a currency mark off a label, which changed nothing
    about the arithmetic and everything about whether the arithmetic was looked for. The
    arithmetic is what is checked.
    """
    wrong = []
    covered = 0
    for page in filing.pages:
        for table in page.tables:
            for column in table.columns:
                by_ordinal = {row.ordinal: row for row in column.rows}
                for found in footings_in(column.rows).footings:
                    if not found.covered:
                        continue
                    covered += 1
                    parts = [by_ordinal[o].value for o in found.ordinals]
                    assert all(v is not None for v in parts), found.label
                    added = sum(v for v in parts if v is not None)
                    if abs(added - found.value) > 0.005:
                        wrong.append(
                            f"p{page.number}: {found.label} says {found.value:,.2f} and "
                            f"its {len(parts)} rows add to {added:,.2f}"
                        )
    assert wrong == [], "a footing that does not foot:\n" + "\n".join(wrong[:8])
    assert covered == 73, f"{covered} totals re-add, not 73"


def test_the_balance_sheet_is_still_the_only_page_that_states_both_sides(filing) -> None:
    """The label rule is what `two_sides` matches on, and it changed. A page gaining or
    losing a side is how that would show."""
    speaks = []
    for page in filing.pages:
        widest = max((len(t.columns) for t in page.tables), default=0)
        for n in range(widest):
            rows = [
                row
                for table in page.tables
                if n < len(table.columns)
                for row in table.columns[n].rows
            ]
            sides = two_sides(rows)
            if sides.stated:
                speaks.append((page.number, sides.balances))
    assert speaks == [(56, True), (56, True)], speaks


def test_no_label_keeps_a_currency_mark_it_should_not(filing) -> None:
    """What the rule is for, asked of every page rather than of the one that showed it.

    A label that still ends in `$` is a label nothing matches: `is_a_total` asks whether one
    begins with the word total, and `two_sides` matches its two exactly. Four real totals
    were invisible for this reason and it took a scan to notice.
    """
    offenders = []
    for page in filing.pages:
        for table in page.tables:
            for column in table.columns:
                for row in column.rows:
                    label = row.label.strip()
                    if label.endswith(("$", "£", "€")) or label.startswith(("$ ", "£ ", "€ ")):
                        offenders.append(f"p{page.number}: {label[:60]!r}")
    assert offenders == [], "a currency mark is standing in a label:\n" + "\n".join(
        offenders[:8]
    )


# ------------------------------------------------------------- and the two paths agree


def test_the_two_paths_agree_about_the_balance_sheet(filing, scanned) -> None:
    """The claim P155 exists to make, from both ends at once."""
    page = next(p for p in filing.pages if p.number == BALANCE_SHEET)
    printed = values(page.tables)
    read = values(scanned)

    assert len(printed) == len(read) == 61
    assert sorted(v for _, v in read) == sorted(v for _, v in printed)
    assert [len(t.columns) for t in scanned] == [len(t.columns) for t in page.tables]

    def letters(label: str) -> str:
        return "".join(label.split())

    assert [letters(a) for a, _ in read] == [letters(a) for a, _ in printed]


def test_the_two_paths_agree_about_what_covers_a_figure(filing, scanned) -> None:
    """The part that decides what a person is shown. Agreeing about the figures and
    disagreeing about their cover would send a different set of rows to a person depending
    on whether the client scanned the page, which is the difference nobody could see."""
    page = next(p for p in filing.pages if p.number == BALANCE_SHEET)
    for built in (page.tables, scanned):
        rows = [r for t in built for c in t.columns for r in c.rows]
        report = footings_in(rows)
        covered = [(f.label.strip(), f.value) for f in report.footings if f.covered]
        assert len(covered) == 10, f"{len(covered)} footings re-add, not 10"
        assert ("Total assets", 521_728.0) in covered
        assert ("Total liabilities", 279_177.0) in covered
        sides = two_sides(rows)
        assert sides.stated and sides.balances is True
        assert sides.assets == sides.liabilities_and_equity == 521_728.0


def test_a_scan_is_marked_as_a_scan_all_the_way_through(filing, monkeypatch) -> None:
    """A figure a machine recognised is weaker evidence than one copied out of a text layer,
    and the acceptance rule turns on evidence. The two paths agreeing about the figures is
    exactly why which of them it was must not be lost."""
    from pypdf import PdfWriter

    import ports

    captured = json.loads(CAPTURE.read_text(encoding="utf-8"))

    class Replay:
        name = "replay"

        def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
            scale = 1 / captured["render_scale"]
            words = tuple(
                OCRWord(
                    text=f["text"],
                    box=Box(
                        x0=f["box"][0] * scale,
                        top=f["box"][1] * scale,
                        x1=f["box"][2] * scale,
                        bottom=f["box"][3] * scale,
                    ),
                    confidence=f["confidence"],
                )
                for f in captured["fragments"]
            )
            return (
                OCRPage(
                    number=1,
                    lines=tuple(
                        OCRLine(text=w.text, confidence=w.confidence) for w in words
                    ),
                    words=words,
                    geometry="exact",
                ),
            )

    monkeypatch.setattr(ports, "get_ocr", lambda: Replay())
    writer = PdfWriter()
    writer.add_blank_page(width=594, height=774)
    buffer = io.BytesIO()
    writer.write(buffer)

    doc = read_document(buffer.getvalue(), "Balance sheet (scanned).pdf")
    assert doc.pages[0].lines, "the engine's text arrived"
    assert all(line.ocr for line in doc.pages[0].lines), "every line is marked OCR"
    assert any(line.confidence is not None for line in doc.pages[0].lines)

    # And the page it was read from carries no such mark.
    page = next(p for p in filing.pages if p.number == BALANCE_SHEET)
    assert not any(line.ocr for line in page.lines)
