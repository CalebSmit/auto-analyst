"""P76: a real filing, kept as the document that finds things.

Every other fixture here is synthetic, and a synthetic document is written by whoever wrote
the code that reads it - so it agrees with that code. The first time the Document Reader
met a real financial statement it took the wrong column of a comparative balance sheet.

`Cash and cash equivalents $ 95,635 $ 171,324` is one line of a real annual report. The
reader matched one figure per row, anchored to the end of the line, so it took **171,324**
- the prior year - and swallowed the current year into the label. Both guards passed:
provenance because the number really was at that locator, and footing because every row
was consistently prior-year so the totals still re-added. On page 34 it was worse than a
year out: `Revenue` stored -53,219, the *Change* column, and `Loss from operations` stored
+181,317 in a year the company lost 96,083.

That was B-030, written in the backlog as a prediction and never demonstrated until a real
document was put in front of it. **P85 closed it**, and the tests that pinned the defect
now say what the answer is instead - which is what pinning it was for.

What this file is still for is the same thing: a document nobody here wrote. It is where
the modal-width rule was found (`net of reserves - $3,608 and $2,433  83,806  101,471`
carries four figures and two columns), and where the guarded header fallback was found (a
header split over six lines whose last line reads `2024 $ %`, three tokens over three
columns, which would have labelled the 2025 column 2024).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intake.readers.documents import read_document
from intake.readers.periods import detect_periods

ROOT = Path(__file__).resolve().parents[2]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"

BALANCE_SHEET = 56
COMPARATIVE = (56, 57, 58)
IMAGE_ONLY = (107, 108)


@pytest.fixture(scope="module")
def filing():
    return read_document(FILING.read_bytes(), FILING.name)


# ------------------------------------------------------------------ it is what it says


def test_the_filing_is_here_with_its_provenance() -> None:
    """A public document is only public if somebody can check where it came from."""
    assert FILING.is_file()
    readme = (FILING.parent / "README.md").read_text(encoding="utf-8")
    assert "https://www.sec.gov/Archives/edgar/data/910638/" in readme
    assert "Retrieved" in readme and "2026-09-19" in readme


def test_the_fixtures_rule_permits_it_everywhere_the_rule_is_written() -> None:
    """Three places say what a fixture may be. A rule widened in one of them is a rule that
    disagrees with itself the next time somebody reads a different copy."""
    for where in ("CLAUDE.md", "fixtures/README.md", "tools/bootstrap_scaffold.py"):
        text = (ROOT / where).read_text(encoding="utf-8")
        assert "public" in text and "synthetic" in text, where
        assert "masked or synthetic, always" not in text, f"{where} still says the old rule"


# ------------------------------------------------------------------ what the reader does


def test_it_reads_a_hundred_page_filing(filing) -> None:
    assert len(filing.pages) == 108
    assert sum(len(p.tables) for p in filing.pages) > 40
    assert sum(len(t.rows) for p in filing.pages for t in p.tables) > 150


def test_the_image_only_pages_are_reported_as_scanned(filing) -> None:
    """Real scanned pages, in a real filing - not one manufactured for a test."""
    scanned = {p.number for p in filing.pages if p.scanned}
    assert scanned == set(IMAGE_ONLY), scanned


def test_a_page_of_prose_is_not_mistaken_for_a_scan(filing) -> None:
    blank = next(p for p in filing.pages if p.number == 106)
    assert not blank.scanned
    assert "INTENTIONALLY LEFT BLANK" in blank.text


def test_the_balance_sheet_rows_are_recovered(filing) -> None:
    page = next(p for p in filing.pages if p.number == BALANCE_SHEET)
    labels = [row.label for table in page.tables for row in table.rows]
    assert any("Cash and cash equivalents" in label for label in labels)
    assert any("Total current assets" in label for label in labels)


# ------------------------------------------------------- the defect, and its closing


def test_both_columns_are_read_and_the_label_is_the_label(filing) -> None:
    """B-030, closed by P85, measured on the document that demonstrated it.

    This used to assert the defect, so that closing it would fail here and whoever closed
    it would have to come back and say what the new answer was. This is that answer.

    Before: the reader anchored on the last figure, so this row stored a label of
    `Cash and cash equivalents $ 95,635 $` and a value of 171,324 - the prior year, with
    the current year swallowed into the label. On page 34 of this same filing it was worse
    than a year out: `Revenue` stored -53,219, the *Change* column, and `Loss from
    operations` stored +181,317 in a year the company lost 96,083.
    """
    page = next(p for p in filing.pages if p.number == BALANCE_SHEET)
    line = next(line for line in page.lines if line.text.startswith("Cash and cash equivalents"))
    assert line.text == "Cash and cash equivalents $ 95,635 $ 171,324", line.text

    table = next(t for t in page.tables if any(
        r.label.startswith("Cash and cash equivalents") for r in t.rows))
    assert len(table.columns) == 2, "a comparative page read as one column"
    first, second = (
        next(r for r in c.rows if r.label.startswith("Cash and cash equivalents"))
        for c in table.columns
    )
    assert first.value == 95635.0, "the current year, which used to be in the label"
    assert second.value == 171324.0, "the prior year, which used to be the only value"
    assert first.label == "Cash and cash equivalents", first.label
    assert first.label == second.label, "one row, two columns, one label"


def test_a_figure_inside_a_label_is_not_a_column(filing) -> None:
    """`Accounts receivable, net of reserves - $3,608 and $2,433  83,806  101,471` carries
    four figures and two columns. Counting every figure on the line made this row four
    wide, which broke the run it belonged to and dropped the cash line above it - so the
    width is what most rows in the run agree on, and each row gives up its last two."""
    page = next(p for p in filing.pages if p.number == BALANCE_SHEET)
    table = next(t for t in page.tables if any(
        r.label.startswith("Accounts receivable") for r in t.rows))
    row = next(r for r in table.columns[0].rows if r.label.startswith("Accounts receivable"))
    assert row.value == 83806.0
    assert "3,608" in row.label and "2,433" in row.label, "the reserves belong to the label"


def test_each_column_is_written_under_its_own_locator(filing) -> None:
    """Which is what leaves the guards alone: one value per row, as before, and the column
    in the locator. Provenance resolves a block, tie-out foots one, and neither had to
    learn what a column is."""
    blocks = filing.blocks()
    page = next(p for p in filing.pages if p.number == BALANCE_SHEET)
    table = next(t for t in page.tables if len(t.columns) == 2)
    assert f"{table.locator}/c1" in blocks
    assert f"{table.locator}/c2" in blocks
    assert blocks[f"{table.locator}/c1"] != blocks[f"{table.locator}/c2"]


def test_the_change_column_is_read_as_the_change_column(filing) -> None:
    """Page 30's MD&A table is the one that made this dangerous: three columns headed
    `2025 2024 Change`, where the old reader took the third and called it revenue."""
    page = next(p for p in filing.pages if p.number == 30)
    table = page.tables[0]
    assert table.headings == ("2025", "2024", "Change")
    revenue = [next(r for r in c.rows if r.label == "Revenue") for c in table.columns]
    assert [r.value for r in revenue] == [386902.0, 440121.0, -53219.0]


def test_a_column_nobody_named_is_escalated_rather_than_guessed(filing) -> None:
    """Page 34's header is split over six lines by the extraction, so the last line above
    the figures reads `2024 $ %`. Three tokens over three columns - and taking them would
    have labelled the 2025 column 2024. The figures are still read; the periods are not
    claimed, and the run stops for a person."""
    page = next(p for p in filing.pages if p.number == 34)
    table = page.tables[0]
    assert table.headings == ("", "", ""), table.headings
    assert [c.rows[0].value for c in table.columns] == [95635.0, 171324.0, -75689.0]

    found = detect_periods(page.text, tables=page.tables)
    assert [a for a in found.ambiguous if a.startswith("columns:")]


def test_the_escalation_fires_where_the_columns_are_unnamed(filing) -> None:
    """Narrowed from what it was. It used to fire on every comparative page, which is
    every audited page, so nothing ever reached a model; now it asks whether the columns
    can be told apart."""
    for number in COMPARATIVE[:2]:
        page = next(p for p in filing.pages if p.number == number)
        found = detect_periods(page.text, tables=page.tables)
        columns = [a for a in found.ambiguous if a.startswith("columns:")]
        assert columns, f"page {number} has unnamed columns and did not escalate"
        assert "no header row names them" in columns[0]


def test_the_escalation_says_which_table_to_look_at(filing) -> None:
    """Narrowed twice over. It used to fire on every comparative page - which is every
    audited page, so nothing reached a model - and say only that rows carried more than
    one figure. Now it fires on the tables whose columns nobody named, and names them.

    Page 30 is the case worth having: its first table *is* named, `2025 2024 Change`, and
    read correctly. The page still stops, because a second table on it is not - and one
    unnamed table is enough, since a figure under an unnamed column is a figure nobody can
    put a year on. What changed is that a person is now told which one.
    """
    page = next(p for p in filing.pages if p.number == 30)
    assert page.tables[0].headings == ("2025", "2024", "Change")

    found = detect_periods(page.text, tables=page.tables)
    (columns,) = [a for a in found.ambiguous if a.startswith("columns:")]
    assert "p30/t2" in columns, columns
    assert "p30/t1" not in columns, "the named table is not what stopped the page"


def test_a_document_whose_columns_are_all_named_is_not_stopped() -> None:
    """The other end of it, on a document small enough to be certain about. Every audited
    statement is comparative, so an escalation that fires on all of them is an escalation
    that stops all of them - which is what this was before P85."""
    statement = "\n".join(
        [
            "CONSOLIDATED STATEMENTS OF OPERATIONS",
            "(in thousands of US dollars)",
            "                          2025          2024",
            "Revenue                1,482,113     1,391,204",
            "Cost of sales            912,004       880,117",
            "Gross profit             570,109       511,087",
        ]
    )
    doc = read_document(statement.encode("utf-8"), "is.txt")
    tables = [t for page in doc.pages for t in page.tables]
    assert tables[0].headings == ("2025", "2024")
    found = detect_periods(doc.as_text(), tables=tables)
    assert not [a for a in found.ambiguous if a.startswith("columns:")]
    assert doc.blocks()["p1/t1/c1"][0].value == 1482113.0
    assert doc.blocks()["p1/t1/c2"][0].value == 1391204.0
