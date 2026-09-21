"""P85: a comparative statement, read as two columns.

Every audited statement is comparative and none of them reached a model. The reader
anchored on the last figure of a line, so `Revenue $ 386,902 $ 440,121 $ (53,219)` gave a
label of `Revenue $ 386,902 $ 440,121 $` and a value of **-53,219** - the *Change* column,
not a year at all. On the same page `Loss from operations` stored **+181,317** in a year
the company lost 96,083. Both guards passed: provenance because the number really was at
that locator, footing because every row was consistently the same wrong column so the
totals still re-added.

The detector caught the shape and stopped the run rather than guess, which is why nothing
comparative ever got through - and the check it used is computed from a *sample*, page-one
headers plus one table's first rows, so on the real filing in `fixtures/public` it said
nothing at all while fifty-eight comparative tables were read wrong.

The column goes in the locator rather than more values in the row: `p12/t1/c2`. `Row`
keeps its shape, so provenance, tie-out and the numeric lock are untouched, and footing
gets *more* exact - a stated total is re-added against its own column instead of a mixture
of years that happens to sum.

Three rules earned by the real document rather than reasoned out:

* the columns are the **trailing** figures and a label may contain numbers of its own
* the width is what **most** rows in a run agree on, not what any one row has
* a heading is used only when every token could be one and at least one names a period -
  a header split across lines whose last line reads `2024 $ %` would otherwise have
  labelled the 2025 column 2024, and a wrong heading does not stop a run the way a missing
  one does
"""

from __future__ import annotations

import pytest

from intake.readers.documents import read_document
from intake.readers.periods import detect_periods, headings_in
from ops.source_parse import DocLocator, parse_locator


def doc(*lines: str, name: str = "statement.txt"):
    return read_document("\n".join(lines).encode("utf-8"), name)


COMPARATIVE = (
    "CONSOLIDATED STATEMENTS OF OPERATIONS",
    "(in thousands of US dollars)",
    "                          2025          2024",
    "Revenue                1,482,113     1,391,204",
    "Cost of sales            912,004       880,117",
    "Gross profit             570,109       511,087",
)


# ------------------------------------------------------------ the locator carries it


def test_a_locator_can_name_a_column() -> None:
    found = parse_locator("p12/t1/c2")
    assert isinstance(found, DocLocator)
    assert (found.page, found.table, found.column) == (12, 1, 2)
    assert found.block == "p12/t1/c2"


def test_a_locator_can_name_a_column_and_a_row() -> None:
    found = parse_locator("p12/t1/c2/r7")
    assert (found.page, found.table, found.column, found.row) == (12, 1, 2, 7)


def test_a_locator_written_before_this_means_what_it_always_meant() -> None:
    """A locator is what a figure cites, and citations outlive the code that made them. A
    single-column table keeps the locator it always had, so nothing already written points
    somewhere new."""
    found = parse_locator("p12/t1")
    assert found.column is None
    assert found.block == "p12/t1"
    assert parse_locator("p3/text/r4").column is None


@pytest.mark.parametrize("bad", ["p12/t1/c", "p12/c2", "p12/t1/c2/c3", "p12/t1/r2/c3"])
def test_a_locator_the_grammar_does_not_name_is_still_refused(bad: str) -> None:
    """The grammar is two shapes and nothing else, which is what makes a locator
    resolvable rather than a string somebody hopes means something."""
    with pytest.raises(ValueError):
        parse_locator(bad)


# ------------------------------------------------------------ both columns are read


def test_both_columns_are_read() -> None:
    table = doc(*COMPARATIVE).pages[0].tables[0]
    assert len(table.columns) == 2
    assert [c.rows[0].value for c in table.columns] == [1482113.0, 1391204.0]


def test_the_label_comes_from_before_the_first_figure() -> None:
    """The whole defect in one assertion. Before, the label was everything up to the last
    figure, so it carried the current year inside it."""
    table = doc(*COMPARATIVE).pages[0].tables[0]
    assert [r.label for r in table.columns[0].rows] == ["Revenue", "Cost of sales", "Gross profit"]
    assert all("1,482,113" not in r.label for r in table.columns[0].rows)


def test_one_row_has_one_label_across_its_columns() -> None:
    """The columns are one table read down, not two tables side by side. A column that
    dropped a row - because that row's figure was missing, say - would put `Gross profit`
    beside `Cost of sales` and every comparison after it would be a year out.

    So the row that could go missing is the one this checks: `-` is a real statement's way
    of writing nothing, and the second column has one where the first has a figure."""
    table = doc(
        "                          2025          2024",
        "Revenue                1,482,113     1,391,204",
        "Assets held for sale       3,176             -",
        "Gross profit             570,109       511,087",
    ).pages[0].tables[0]
    first, second = table.columns
    assert [r.label for r in first.rows] == [r.label for r in second.rows]
    assert "Assets held for sale" in [r.label for r in second.rows]


def test_each_column_is_written_to_its_own_block() -> None:
    blocks = doc(*COMPARATIVE).blocks()
    assert "p1/t1/c1" in blocks and "p1/t1/c2" in blocks
    assert blocks["p1/t1/c1"][0].value == 1482113.0
    assert blocks["p1/t1/c2"][0].value == 1391204.0


def test_a_single_column_table_still_writes_where_it_always_did() -> None:
    """The compatibility that matters: a document with one column of figures produces the
    locators it produced before this phase, so nothing that reads them has to change."""
    blocks = doc("Officer salary   240,000", "Officer bonus     60,000").blocks()
    assert "p1/t1" in blocks
    assert not any("/c" in locator for locator in blocks)


def test_table_rows_still_means_the_first_column() -> None:
    """Everything that read `table.rows` before this goes on reading the same rows."""
    table = doc(*COMPARATIVE).pages[0].tables[0]
    assert table.rows == table.columns[0].rows


# ------------------------------------------------ the rules the real document taught


def test_a_figure_inside_a_label_is_not_a_column() -> None:
    """`net of reserves - $3,608 and $2,433` is disclosure, not a column. Counting every
    figure made this row four wide, which broke the run and dropped the row above it."""
    table = doc(
        "                                        2025        2024",
        "Cash and cash equivalents             95,635     171,324",
        "Accounts receivable, net of reserves - $3,608 and $2,433  83,806  101,471",
        "Inventories                          127,496     118,530",
    ).pages[0].tables[0]

    assert len(table.columns) == 2
    labels = [r.label for r in table.columns[0].rows]
    assert "Cash and cash equivalents" in labels, "the row above the odd one was dropped"
    receivable = next(r for r in table.columns[0].rows if r.label.startswith("Accounts"))
    assert receivable.value == 83806.0
    assert "3,608" in receivable.label


def test_a_row_that_cannot_fill_the_columns_is_left_out_rather_than_guessed() -> None:
    """A row with fewer figures than the table is wide cannot say which column it is in,
    and putting it in the first would be the same kind of guess this phase removed."""
    table = doc(
        "                          2025          2024",
        "Revenue                1,482,113     1,391,204",
        "Cost of sales            912,004       880,117",
        "Restructuring            145,000",
        "Gross profit             570,109       511,087",
    ).pages[0].tables[0]
    assert len(table.columns) == 2
    assert "Restructuring" not in [r.label for r in table.columns[0].rows]


def test_the_width_is_what_most_rows_agree_on() -> None:
    table = doc(
        "                          2025          2024",
        "Revenue                1,482,113     1,391,204",
        "Cost of sales            912,004       880,117",
        "Gross profit             570,109       511,087",
        "Tax note 4 - see 1,234 and 5,678 above   12,004      11,117",
    ).pages[0].tables[0]
    assert len(table.columns) == 2


# ------------------------------------------------------------ the columns are named


def test_the_header_row_names_the_columns() -> None:
    """A header of real dates, which only the date reader can name: splitting it into
    words gives six for two columns. The bare-year header in COMPARATIVE is named by
    either route, so it could not tell the two apart and proved neither."""
    table = doc(
        "        December 31, 2025    December 31, 2024",
        "Revenue                1,482,113     1,391,204",
        "Cost of sales            912,004       880,117",
    ).pages[0].tables[0]
    assert table.headings == ("December 31, 2025", "December 31, 2024")
    assert doc(*COMPARATIVE).pages[0].tables[0].headings == ("2025", "2024")


def test_a_header_that_is_not_all_dates_still_names_them() -> None:
    """`2025 2024 Change` is the commonest real header and reading only the dates finds
    two headings for three columns."""
    table = doc(
        "                       2025        2024      Change",
        "Revenue             386,902     440,121     (53,219)",
        "Cost of sales       255,857     275,943     (20,086)",
    ).pages[0].tables[0]
    assert table.headings == ("2025", "2024", "Change")
    assert [c.rows[0].value for c in table.columns] == [386902.0, 440121.0, -53219.0]


def test_a_header_of_punctuation_names_nothing() -> None:
    """The case the real filing produced: a header split over several lines whose last
    line is `2024 $ %`. Three tokens over three columns - and taking them would label the
    column holding 2025 as 2024. A wrong heading is worse than none, because none stops
    the run and a wrong one does not."""
    table = doc(
        "December 31,",
        "2025",
        "December 31,",
        "2024 $ %",
        "Cash and cash equivalents  95,635  171,324  (75,689)",
        "Accounts receivable, net   83,806  101,471  (17,665)",
    ).pages[0].tables[0]
    assert table.headings == ("", "", "")
    assert [c.rows[0].value for c in table.columns] == [95635.0, 171324.0, -75689.0]


def test_a_heading_needs_something_that_names_a_period() -> None:
    """Three ordinary words above a table are prose, not headings - and the count matching
    is exactly why the date check is needed. Written first with a five-word line, which
    was rejected for its length and told this nothing."""
    table = doc(
        "as shown below",
        "Revenue             386,902     440,121     (53,219)",
        "Cost of sales       255,857     275,943     (20,086)",
    ).pages[0].tables[0]
    assert len(["as", "shown", "below"]) == len(table.columns), "the count must match"
    assert table.headings == ("", "", "")


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("     2025        2024", ("2025", "2024")),
        ("  December 31, 2025    December 31, 2024", ("December 31, 2025", "December 31, 2024")),
        ("  12/31/2025   12/31/2024   12/31/2023", ("12/31/2025", "12/31/2024", "12/31/2023")),
        ("     FY2025      FY2024", ("FY2025", "FY2024")),
        ("Revenue   1,482,113   1,391,204", ()),
    ],
)
def test_headings_are_read_in_the_order_they_are_written(line: str, expected: tuple) -> None:
    """Order is the whole point - a set would lose which one is in the third column."""
    assert headings_in(line) == expected


def test_the_longest_heading_at_a_position_wins() -> None:
    """`December 31, 2025` is matched by two patterns that start at the same character,
    and the shorter one winning is how a column headed 2025 gets labelled `December 31`."""
    assert headings_in("  December 31, 2025  ") == ("December 31, 2025",)


# ------------------------------------------------------ and the escalation is narrowed


def test_a_named_comparative_statement_is_not_stopped() -> None:
    """What the phase is for. Before this, every audited statement was stopped here."""
    parsed = doc(*COMPARATIVE)
    tables = [t for page in parsed.pages for t in page.tables]
    found = detect_periods(parsed.as_text(), tables=tables)
    assert not [a for a in found.ambiguous if a.startswith("columns:")]


def test_an_unnamed_comparative_statement_is_still_stopped() -> None:
    parsed = doc(*[line for line in COMPARATIVE if "2025" not in line])
    tables = [t for page in parsed.pages for t in page.tables]
    found = detect_periods(parsed.as_text(), tables=tables)
    (columns,) = [a for a in found.ambiguous if a.startswith("columns:")]
    assert "no header row names them" in columns


def test_the_escalation_says_which_table() -> None:
    """A document of fifty-eight tables and one problem is a document nobody can act on
    until they are told which one."""
    parsed = doc(
        "                          2025          2024",
        "Revenue                1,482,113     1,391,204",
        "Cost of sales            912,004       880,117",
        "and separately",
        "Segment A                120,000       118,000",
        "Segment B                 90,000        88,000",
    )
    tables = [t for page in parsed.pages for t in page.tables]
    found = detect_periods(parsed.as_text(), tables=tables)
    (columns,) = [a for a in found.ambiguous if a.startswith("columns:")]
    assert "p1/t2" in columns and "p1/t1" not in columns


def test_a_single_column_document_is_not_stopped() -> None:
    parsed = doc("Officer salary   240,000", "Officer bonus     60,000")
    tables = [t for page in parsed.pages for t in page.tables]
    found = detect_periods(parsed.as_text(), tables=tables)
    assert not [a for a in found.ambiguous if a.startswith("columns:")]


def test_the_text_form_is_kept_for_a_caller_with_no_tables() -> None:
    """The detector is called on text elsewhere. Asked without tables it still answers,
    coarsely - and the coarseness is exactly why the caller was changed to pass them."""
    found = detect_periods("Revenue   1,482,113   1,391,204\nCost   912,004   880,117")
    assert [a for a in found.ambiguous if a.startswith("columns:")]
