"""P151: a text line is not a statement row, and reading it as one loses and invents.

Measured on `fixtures/public/sec-ars-3d-systems-2025.pdf`, a real annual report nobody here
wrote. Page 56 is its consolidated balance sheet. Read as a stream of text lines it gave:

| the filing says | the reader produced |
|---|---|
| Total assets **521,728** | *no row at all* |
| Total liabilities **279,177** | *no row at all* |
| Common stock **146** | **220,000** |

**The two that vanished.** An audited statement sets its grand total on a ruled row, and the
PDF emits the label and the figures as separate runs:

    Total assets
    $ 521,728 $ 608,846

so the run of figure-carrying lines broke at the label, the label became a plain line, and
the row was built by nothing. Those are the two figures a balance sheet exists to state.

**The one that was wrong.** The Common stock line wraps, and its first line reads `Common
stock, $0.001 par value, authorized 220,000 shares; shares issued 145,581 and`. Taking the
last figures on that line stored the *authorized share count* as the common stock balance.
It passed every guard: provenance, because 220,000 really is at that locator; footing,
because the row is not a total and nothing re-adds it. A confidently wrong figure in the
equity section of a balance sheet is the failure this build says it most cares about, and it
was there.

**Why coordinates and not another line rule.** Both failures are the same assumption, and no
reading of the text can fix either: the information needed is where the words are. A row is a
band of the page; a column is a band too. On page 56 the figure columns sit within three
points of x=482 and x=549 and the 220,000 inside that label sits at x=234.

**What it cost elsewhere: nothing, and it gained.** Over the whole 108-page filing the rows
carrying a value went from 674 to 815, and the tables whose every column is named from 21 to
28. The table count fell from 88 to 72 because a statement no longer breaks into four tables
at the rows that lost their figures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intake.readers.documents import read_document
from intake.readers.layout import lay_out

ROOT = Path(__file__).resolve().parents[2]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"

BALANCE_SHEET = 56
INCOME_STATEMENT = 57


@pytest.fixture(scope="module")
def filing():
    return read_document(FILING.read_bytes(), FILING.name)


def _starting(prefix: str, rows: dict[str, float | None]) -> float | None:
    """The one row whose label starts this way.

    Matched by prefix because the filing writes `stockholders’ equity` with a curly
    apostrophe, and writing that into a test is a way to be wrong about which character it
    is. The reader gets it right - there is no replacement character anywhere in this
    document - and an earlier version of this note said the PDF did not encode it, which
    was a Windows console that could not print it rather than anything about the file.
    """
    found = [value for label, value in rows.items() if label.startswith(prefix)]
    assert len(found) == 1, f"{prefix!r} matched {len(found)} rows"
    return found[0]


def values_on(document, page_number: int) -> dict[str, float | None]:
    """Every row of a page, by label, from the first column - the current year."""
    page = next(p for p in document.pages if p.number == page_number)
    return {row.label: row.value for table in page.tables for row in table.rows}


# ------------------------------------------------- the three, against what the filing says


def test_the_grand_totals_are_read_with_their_figures(filing) -> None:
    """Each of these is a label on one text line and its figures on the next. Both are the
    sum of the rows above them, so losing them loses the only figure that can be checked."""
    rows = values_on(filing, BALANCE_SHEET)
    assert rows["Total assets"] == 521_728
    assert rows["Total liabilities"] == 279_177
    assert rows["Total current assets"] == 346_707
    assert rows["Total current liabilities"] == 120_623
    assert _starting("Total stockholders", rows) == 240_358


def test_a_number_inside_a_label_is_not_that_rows_value(filing) -> None:
    """The Common stock row. Its label carries an authorized share count and an issued share
    count, and its value is a balance of 146 printed in the column."""
    rows = values_on(filing, BALANCE_SHEET)
    common = next(label for label in rows if label.startswith("Common stock"))
    assert "220,000" in common, "the share count should still be in the label, where it is"
    assert rows[common] == 146, f"common stock read as {rows[common]}"


def test_the_balance_sheet_balances(filing) -> None:
    """The check a reader makes first, and the one the old reader could not have made at all
    because two of its three terms were missing.

    The filing states both sides, so this compares what it says against what it says: the
    assets total and the line that totals liabilities, the redeemable interest and equity.
    """
    rows = values_on(filing, BALANCE_SHEET)
    both_sides = _starting("Total liabilities, redeemable", rows)
    assert rows["Total assets"] == both_sides == 521_728


def test_what_it_already_read_correctly_it_still_does(filing) -> None:
    """A change this size has to be shown not to have moved anything else."""
    rows = values_on(filing, BALANCE_SHEET)
    for label, value in (
        ("Cash and cash equivalents", 95_635),
        ("Inventories", 127_496),
        ("Goodwill", 15_575),
        ("Accounts payable", 41_017),
        ("Additional paid-in capital", 1_620_399),
        ("Accumulated deficit", -1_332_360),
    ):
        assert rows[label] == value, f"{label} read as {rows[label]}"


# --------------------------------------------------- and the properties underneath them


def test_a_column_is_a_column_of_its_own_table(filing) -> None:
    """Clustering a page at once gave page 30 nine columns, because it carries two tables
    whose columns are in different places - and then neither table's headings lined up."""
    page = next(p for p in filing.pages if p.number == 30)
    assert len(page.tables) == 2
    assert page.tables[0].headings == ("2025", "2024", "Change")
    assert all(len(t.columns) == 3 for t in page.tables)


def test_a_heading_is_the_word_printed_over_its_column(filing) -> None:
    """Page 30's heading line is `(in thousands) 2025 2024 Change` - five tokens over three
    columns, which a count can make nothing of. The page says plainly which word is above
    which column: each year sits about twenty points left of its column's right edge, and
    the `(in thousands)` prefix is three hundred and sixty away."""
    page = next(p for p in filing.pages if p.number == 30)
    assert page.tables[0].headings == ("2025", "2024", "Change")
    laid_out = lay_out(FILING.read_bytes())[30]
    assert laid_out[0].heading_line == "(in thousands) 2025 2024 Change"


def test_a_column_nobody_named_is_still_not_guessed(filing) -> None:
    """Page 34 heads its columns over six lines, the last reading `2024 $ %`. The word
    nearest the third column is `$`, which is not a name - so the table stays unnamed and a
    person is asked, which is what this build decided to do about it."""
    page = next(p for p in filing.pages if p.number == 34)
    assert page.tables[0].headings == ("", "", "")


def test_a_page_with_no_columns_is_read_the_way_it_always_was() -> None:
    """A PDF whose lines are each one drawn string has no column geometry: the figures end
    where the text ends. Whatever clusters out of that is a coincidence, and the line reader
    already reads such a page correctly.
    """
    from tests.p17.conftest import build_pdf

    simple = build_pdf(
        [
            ("Henderson Manufacturing - Officer Compensation", 12.0),
            ("Officer salary  240,000", 10.0),
            ("Auto allowance  18,400", 10.0),
            ("Club dues  5,000", 10.0),
            ("Health premium  12,600", 10.0),
            ("Total officer comp  331,000", 10.0),
        ]
    )
    assert lay_out(simple) == {1: []}, "a page with no columns should offer no table"
    doc = read_document(simple, "comp.pdf")
    rows = {row.label: row.value for row in doc.pages[0].tables[0].rows}
    assert rows["Officer salary"] == 240_000
    assert rows["Total officer comp"] == 331_000


def test_a_pdf_that_cannot_be_laid_out_says_so_rather_than_saying_nothing() -> None:
    """`None` and `{}` have to be different answers. A caller that cannot tell "no columns
    here" from "I could not look" will quietly lose a document."""
    assert lay_out(b"not a pdf at all") is None
    assert lay_out(b"") is None


def test_a_figure_further_right_does_not_leak_into_the_label(filing) -> None:
    """The label stops where the first column starts.

    Page 30's second table carries percentages to the right of its figure columns. Without
    that boundary the `Volume` row's label reads `Volume (20.1)% 0.3 % (12.7)%` - three
    numbers from columns this table does not have, welded onto the name of the row. Removing
    the boundary changes fourteen pages of this filing, which is how it earned its place.
    """
    page = next(p for p in filing.pages if p.number == 30)
    volume = next(
        row for table in page.tables for row in table.rows if row.label.startswith("Volume")
    )
    assert volume.label == "Volume", f"the label picked up {volume.label!r}"
    assert volume.value == -56_138


def test_a_column_runs_down_its_table_rather_than_appearing_twice() -> None:
    """What makes a cluster of right edges a column and not a coincidence.

    Asserted as the property rather than as the constant: every column of every table this
    reader builds from the filing is filled on at least three of that table's rows. Allowing
    two changes sixteen pages of this document, and page 57 grows from four tables to six -
    thinner evidence, more tables, each of them a claim about structure that is not there.
    """
    thin = []
    for page_number, tables in lay_out(FILING.read_bytes()).items():
        for table in tables:
            for position in range(len(table.columns)):
                filled = sum(1 for row in table.rows if row.cells[position] is not None)
                if filled < 3:
                    thin.append(f"p{page_number}: a column filled on {filled} row(s)")
    assert thin == [], "a column that does not run down its table:\n" + "\n".join(thin[:8])
