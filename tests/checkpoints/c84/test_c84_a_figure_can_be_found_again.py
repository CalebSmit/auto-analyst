"""C84 - every figure these readers store is in the file they read it from.

Two phases changed how a figure comes into existence.

* **P151.** A PDF's rows are built from where the words are rather than from how the text
  stream is chunked. `Total assets 521,728` and `Total liabilities 279,177` had been built by
  nothing at all, and `Common stock` had been built as 220,000 - the authorized share count
  - where the balance is 146.
* **P152.** A CSV and an `.xls` are converted to a workbook at the door, so two of the four
  spreadsheet types this build accepts stopped being refused with `BadZipFile`. A CSV has no
  types, so every figure in one is now the result of a decision about what a comma means.

What a checkpoint can ask that neither could.

Both phases make figures. The property underneath both is the one CLAUDE.md states as a
non-negotiable: **a figure is proved by arithmetic, or it is seen.** Seeing it means finding
it again in the source, at the place it says it is - so the question here is not whether
either reader is clever but whether **anything it emits was invented**.

Asked over the whole of a real filing and over a converted CSV, because that is the only way
to ask it: a reader that invents on one page of a hundred is a reader nobody can trust, and a
spot check on page 56 would not find it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from intake.readers.documents import read_document
from intake.readers.tabular import as_workbook
from intake.readers.workbook import normalize_workbook, survey_workbook

ROOT = Path(__file__).resolve().parents[3]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"


@pytest.fixture(scope="module")
def filing():
    return read_document(FILING.read_bytes(), FILING.name)


def written(value: float) -> set[str]:
    """How a statement could have printed this figure.

    A page writes `521,728`, `(4.7)`, `1.3` and `95,635` and means the same numbers this
    reader stores. Every plausible spelling is generated rather than one: forcing two decimal
    places called `(4.7)` a mismatch and made this file fail on twelve percentages, which was
    the test being wrong about printing rather than the reader being wrong about reading.
    """
    whole = abs(value)
    forms = {f"{whole:,.0f}"} if whole == int(whole) else set()
    for places in (1, 2, 3):
        forms.add(f"{whole:,.{places}f}")
    forms |= {form.replace(",", "") for form in set(forms)}
    forms |= {form.rstrip("0").rstrip(".") for form in set(forms) if "." in form}
    return forms | {f"({form})" for form in forms} | {f"${form}" for form in forms}


# ------------------------------------------------- nothing is invented, over a whole filing


def test_every_figure_a_pdf_row_carries_is_printed_on_that_row(filing) -> None:
    """The one that matters. A row's `raw` is the words the page actually holds, and its
    value has to be among them - otherwise the figure came from somewhere else, and a
    locator pointing at a row that does not contain it is a citation to nothing.
    """
    invented = []
    for page in filing.pages:
        for table in page.tables:
            for column in table.columns:
                for row in column.rows:
                    if row.value is None:
                        continue
                    if not any(form in row.raw for form in written(row.value)):
                        invented.append(
                            f"p{page.number}: {row.value} is not on {row.raw[:70]!r}"
                        )
    assert invented == [], (
        f"{len(invented)} figure(s) are not on the row they cite:\n" + "\n".join(invented[:8])
    )


def test_a_pdf_row_keeps_its_label_out_of_its_value(filing) -> None:
    """P151's second half, over the whole document rather than the one row that proved it.

    A label may carry numbers of its own - a share count, a note reference, a percentage -
    and none of them may be the row's value unless it is also printed in a column. Checked
    by the one thing that cannot be faked: a value has to appear *after* the label ends.
    """
    wrong = []
    for page in filing.pages:
        for table in page.tables:
            for column in table.columns:
                for row in column.rows:
                    if row.value is None or not row.label:
                        continue
                    tail = row.raw[len(row.label) :] if row.raw.startswith(row.label) else row.raw
                    if not any(form in tail for form in written(row.value)):
                        wrong.append(f"p{page.number}: {row.value} for {row.label[:52]!r}")
    # Not a tolerance. It was `<= 2` while `written` forced two decimal places and called
    # `(4.7)` a mismatch; with the spellings right the answer over a hundred and eight pages
    # is none, and a count that is allowed to be two is a count nobody will notice becoming
    # three.
    assert wrong == [], (
        f"{len(wrong)} value(s) appear only inside their own label:\n" + "\n".join(wrong[:8])
    )


def test_every_figure_is_a_figure_and_not_a_year(filing) -> None:
    """A column headed by a year must not have that year as a value. The bare-number rule
    that keeps a header out of a table is what stops it, and it is easy to loosen."""
    for page in filing.pages:
        for table in page.tables:
            for column in table.columns:
                if not column.heading.isdigit():
                    continue
                years = [r for r in column.rows if r.value == float(column.heading)]
                assert len(years) <= 1, (
                    f"p{page.number}: the {column.heading} column holds {column.heading} "
                    f"as a value on {len(years)} rows"
                )


# -------------------------------------------- and the same question of a converted file


CSV = (
    b"Henderson Manufacturing\n"
    b"Trial balance, 31 December 2025\n"
    b"\n"
    b"Account,Debit,Credit\n"
    b"Cash,402000,\n"
    b"Accounts receivable,318400,\n"
    b"Revenue,,4650000\n"
    b"Total,720400,4650000\n"
)


def test_every_figure_a_converted_file_carries_is_in_the_bytes_it_came_from() -> None:
    """A CSV is the hardest case for this, because converting it is where a figure could be
    invented: every cell is text and something had to decide what the text meant."""
    conversion = as_workbook(CSV, "TB 2025.csv")
    survey = survey_workbook(conversion.workbook)
    source = CSV.decode()
    missing = []
    for table in normalize_workbook(conversion.workbook, [s.name for s in survey.sheets]):
        for locator, rows in table.blocks.items():
            for row in rows:
                if row.value is None:
                    continue
                if not any(form in source for form in written(row.value)):
                    missing.append(f"{locator}: {row.value} for {row.label!r}")
    assert missing == [], "a figure that is not in the file:\n" + "\n".join(missing)


def test_a_converted_file_cites_a_cell_the_way_a_workbook_does() -> None:
    """The locator is what a figure carries for as long as it exists, and a converted file
    has to cite the same way a native one does or a reviewer has two things to learn."""
    conversion = as_workbook(CSV, "TB 2025.csv")
    survey = survey_workbook(conversion.workbook)
    tables = normalize_workbook(conversion.workbook, [s.name for s in survey.sheets])
    locators = [locator for table in tables for locator in table.blocks]
    assert locators, "the converted file wrote no block"
    for locator in locators:
        assert re.fullmatch(r"'[^']+'![A-Z]+\d+:[A-Z]+\d+", locator), locator
        assert locator.startswith("'TB 2025'!"), locator


def test_what_had_to_be_decided_to_read_it_is_carried_with_it() -> None:
    """A native workbook decides nothing - a number in a cell is a number. A converted file
    decided an encoding, a delimiter and what a comma means, and a reader who cannot see
    those decisions cannot check them."""
    conversion = as_workbook(CSV, "TB 2025.csv")
    assert conversion.encoding and conversion.delimiter
    assert conversion.ambiguous == ()

    native = as_workbook(b"Account,Amount\nCash,402000\n", "TB.csv")
    assert native.decimal == "", "a file with nothing to decide should claim no convention"


def test_the_two_readers_agree_about_what_a_row_is(filing) -> None:
    """One `Row` shape, from a page and from a sheet, so everything downstream - provenance,
    footing, tie-out, the review queue - has one thing to read."""
    from ops.source_parse import Row

    page_row = next(
        r for p in filing.pages for t in p.tables for r in t.rows if r.value is not None
    )
    conversion = as_workbook(CSV, "TB 2025.csv")
    survey = survey_workbook(conversion.workbook)
    sheet_row = next(
        r
        for table in normalize_workbook(conversion.workbook, [s.name for s in survey.sheets])
        for rows in table.blocks.values()
        for r in rows
    )
    assert isinstance(page_row, Row) and isinstance(sheet_row, Row)
    for field in ("label", "value", "raw", "ordinal"):
        assert hasattr(page_row, field) and hasattr(sheet_row, field)
