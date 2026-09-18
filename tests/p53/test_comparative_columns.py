"""A statement with two columns of figures is not read as though it had one.

Every audited statement is comparative - this year beside last year - and `knowledge`
records that historicals usually arrive as PDFs. The document reader matches one figure
per row, anchored to the end of the line, so on a comparative row it took the *last*
column: the current year was swallowed into the label and every figure in the run became
the prior year's.

It went past everything. Provenance passes, because the number genuinely is at that
locator. Footing passes, because every row is consistently prior-year so the totals still
re-add. It is the failure the blueprint says nothing catches - "a confidently wrong,
internally consistent, correctly sourced classification" - and it lands on the step an
analyst is least likely to re-key by hand.

The row store holds one value per row, so nothing here guesses which column was meant. It
stops the run and asks, the way an unstated scale already does.
"""

from __future__ import annotations

from harness.procedures.timing_normalization import TimingNormalization
from intake.readers.documents import _NUMBER_AT_END
from intake.readers.periods import detect_periods

COMPARATIVE = """Consolidated Statements of Operations
(in thousands)
Year ended December 31,            2025            2024
Revenue                    12,450,000     11,200,000
Cost of revenue             7,100,000      6,480,000
Net income                  1,240,000        980,000
"""

SINGLE = """Statement of Operations
(in thousands)
Year ended December 31, 2025
Revenue                    12,450,000
Cost of revenue             7,100,000
Net income                  1,240,000
"""


def test_the_reader_really_does_take_the_last_column() -> None:
    """The defect this stops, stated as what the parser does - so that if the reader is
    ever taught to hold both columns, this test fails and says why rather than quietly
    describing something that is no longer true."""
    row = "Revenue                    12,450,000     11,200,000"
    match = _NUMBER_AT_END.match(row)
    assert match
    label = match.group("label") or match.group("label2")
    number = match.group("num") or match.group("num2")
    assert number == "11,200,000", "the prior year is what a single-value row keeps"
    assert "12,450,000" in label, "and the current year ends up inside the label"


def test_a_comparative_statement_is_flagged_rather_than_read() -> None:
    found = detect_periods(COMPARATIVE)
    flags = [a for a in found.ambiguous if a.startswith("columns")]
    assert flags, "two figures on a row is an ambiguity, not a reading"
    assert "2 figures" in flags[0]
    assert "which column belongs to which period is not stated" in flags[0]
    assert found.cues.get("columns"), "and it says what it saw"


def test_a_single_column_statement_is_not_flagged() -> None:
    """The point of the check is the run that should stop. A check that stops every run
    would be turned off inside a week."""
    found = detect_periods(SINGLE)
    assert [a for a in found.ambiguous if a.startswith("columns")] == []


def test_prose_and_page_furniture_are_not_columns_of_figures() -> None:
    """A page number, a note reference and a year are all numbers. Only money-shaped
    figures - four digits or comma-grouped - count, or every document would stop."""
    ordinary = """Notes to the Financial Statements
    See Note 12 and Note 14 for the basis of preparation.
    The company was incorporated in 1998 and reorganised in 2014.
    Page 3 of 12
    """
    found = detect_periods(ordinary)
    assert [a for a in found.ambiguous if a.startswith("columns")] == []


def test_the_flag_stops_the_run_before_the_model() -> None:
    """An ambiguity nothing acts on is a note in a record nobody reads. `columns` joins
    `scale` and `period_type` in the escalation that holds a file back for a person."""
    import inspect

    source = inspect.getsource(TimingNormalization.escalate)
    assert '("scale", "period_type", "columns")' in source


def test_the_two_halves_agree_on_what_a_comparative_row_is() -> None:
    """The reader's regex and the detector's are written separately and have to see the
    same thing, or a document is flagged that parses cleanly, or worse, not flagged and
    parsed wrongly."""
    rows = [line for line in COMPARATIVE.splitlines() if _NUMBER_AT_END.match(line)]
    # Four, not three: the column header matches too, and the reader would keep `2024` as
    # that row's value. Recorded here because it is the same confusion seen from the other
    # end - a row store with one value per row cannot tell a period header from a figure -
    # and because a test that asserted three would be asserting something untrue.
    assert len(rows) == 4
    assert rows[0].startswith("Year ended"), "the header is read as a row of figures"
    found = detect_periods("\n".join(rows))
    assert [a for a in found.ambiguous if a.startswith("columns")], (
        "the detector flags exactly the rows the reader would have mis-read"
    )
