"""P163: which column is which year.

Two findings that are one mechanism.

**The years printed above a statement's columns were being thrown away.** `_tables` kept
`last_plain_band` - the most recent band with no figure in it - and handed that to
`_headings` when a run of figure rows began. On a real statement the date header is never
the last plain band: `ASSETS`, `Current assets:`, `Non-current liabilities:` and `Cash
flows from investing activities:` always sit between the header and the first figure row,
and overwrote it. `_headings` was already positional and already places the dates
correctly when handed the right band - its own docstring predicted that the
`(in thousands)` prefix would be three to four hundred points away and lose. Over 232
pages of two filings the cost was **70 of 119** tables.

**And the consumer was already wired.** `periods.py` collects the tables that carry more
than one column and name none of them, and reports `columns: N table(s) carry more than one
column of figures and no header row names them`. That cue is why `settled` was False on
*every* real statement - `0 of 3 tables name their columns` on 3D's balance sheet, `0 of 5`
on ResMed's - so a comparative statement escalated to a person on every filing, forever,
for want of a band two bands further up. The detector was right about everything else:
scale, currency, ResMed's June year end, and both period ends. It reports those ends
**sorted ascending**, while a statement prints the current year first, so anything that
mapped them positionally would date every column a year wrong.

**The second finding is why the first one is dangerous alone.** `_columns` establishes a
column only from money-shaped figures, so a column of small or nil amounts falls one short
of `COLUMN_NEEDS` and is never built - and every figure to its right then sits at a column
index belonging to another year. Naming the columns is what lets the rest settle, so a
table that dropped a column would now settle, **on a wrong date**. The same read that names
the columns is therefore the read that notices one is missing: non-consecutive years mean a
column between them was never built.

Reported, not repaired. Rebuilding the missing column is a guess; saying its indices cannot
be trusted is a fact.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intake.readers.documents import read_document
from intake.readers.layout import _dated, _table, _years
from intake.readers.periods import _skips_a_year, detect_periods

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "fixtures" / "public"
THREE_D = "sec-ars-3d-systems-2025.pdf"
RESMED = "sec-ars-resmed-2026.pdf"


@pytest.fixture(scope="module")
def three_d():
    return read_document((PUBLIC / THREE_D).read_bytes(), THREE_D)


@pytest.fixture(scope="module")
def resmed():
    return read_document((PUBLIC / RESMED).read_bytes(), RESMED)


def word(text: str, x1: float, top: float = 100.0) -> dict[str, object]:
    """A word where `_years` looks for one: right edge and nothing else matters."""
    return {"text": text, "x0": x1 - 20.0, "x1": x1, "top": top, "bottom": top + 9.0}


# ------------------------------------------- a comparative statement names its columns


def test_a_comparative_balance_sheet_says_which_column_is_which_year(three_d, resmed) -> None:
    """The three blocks of 3D's balance sheet and the five of ResMed's, every one of them.

    A balance sheet is split into blocks at every heading, and each block is its own table
    with its own columns - so the header has to reach all of them, which is exactly what
    `last_plain_band` could never do: by the second block the header is five bands up.
    """
    page = next(p for p in three_d.pages if p.number == 56)
    assert [t.headings for t in page.tables] == [("2025", "2024")] * 3

    page = next(p for p in resmed.pages if p.number == 79)
    assert [t.headings for t in page.tables] == [("2026", "2025")] * 5

    # Current year first, as the statement prints it - and not the ascending order the
    # detector's own `period_ends` comes back in, which is the trap a positional read of
    # that tuple would fall into.
    assert page.tables[0].headings == ("2026", "2025")


def test_the_detector_settles_on_statements_it_used_to_escalate(three_d, resmed) -> None:
    """The payoff, in the detector's own words.

    Before this phase every one of these reported `0 of N tables name their columns` and
    `settled` was False, so which figure belonged to which year was a question for a person
    on every filing.
    """
    for doc, number in ((three_d, 56), (resmed, 79), (resmed, 80), (resmed, 83)):
        page = next(p for p in doc.pages if p.number == number)
        found = detect_periods(page.text, tables=list(page.tables))
        assert found.cues.get("columns") == ["every column is named by a header row"], (
            f"p{number}: {found.cues.get('columns')}"
        )
        assert not [said for said in found.ambiguous if said.startswith("columns:")], (
            f"p{number} still escalates its columns: {found.ambiguous}"
        )
        assert found.settled is True, f"p{number}: {found.ambiguous}"


def test_a_year_is_not_a_year_end_and_the_detector_still_says_so(three_d) -> None:
    """3D's statements of operations and cash flows name their columns now and **still do
    not settle**, which is correct and is the honest half of this.

    Those pages head the years with `Year Ended December 31,` on a line of its own, so the
    columns are headed `2025 2024 2023` and nothing on the page says what date a year ends
    on. Naming a column is not dating it - the fiscal calendar is on the engagement
    profile, which is the same reason `Column.heading` is documented as the text as written
    rather than a parsed date.
    """
    for number in (57, 58):
        page = next(p for p in three_d.pages if p.number == number)
        found = detect_periods(page.text, tables=list(page.tables))
        assert all(t.headings == ("2025", "2024", "2023") for t in page.tables)
        assert found.cues.get("columns") == ["every column is named by a header row"]
        assert found.settled is False
        assert any("none is dated" in said for said in found.ambiguous), found.ambiguous


# --------------------------------------------- the column the page has and the table has not


def test_the_table_that_dropped_a_column_is_dated_with_a_gap(three_d) -> None:
    """3D's cash flow statement, the investing block.

    Its four siblings on the page are dated 2025, 2024, 2023. This one is dated 2025 and
    **2023**, because the 2024 column was never built - and the gap is the only thing on
    the page that says so. Everything else about the table looks right: two columns, rows
    with labels, figures at locators that resolve.
    """
    page = next(p for p in three_d.pages if p.number == 59)
    assert [t.headings for t in page.tables] == [
        ("2025", "2024", "2023"),
        ("2025", "2024", "2023"),
        ("2025", "2024", "2023"),
        ("2025", "2023"),
        ("2025", "2024", "2023"),
    ]
    lost = page.tables[3]
    assert len(lost.columns) == 2
    assert all(len(t.columns) == 3 for n, t in enumerate(page.tables) if n != 3)


def test_a_dropped_column_keeps_the_page_from_settling(three_d) -> None:
    """**The half that makes the other half safe.** Naming the columns is what settles a
    statement, so a table that lost one would settle on a wrong date. It does not."""
    page = next(p for p in three_d.pages if p.number == 59)
    found = detect_periods(page.text, tables=list(page.tables))
    said = [s for s in found.ambiguous if s.startswith("columns:")]
    assert len(said) == 1, found.ambiguous
    assert "p59/t4" in said[0]
    assert "gap" in said[0]
    assert "cannot be trusted to be the ones they are indexed as" in said[0]
    assert found.cues.get("columns") == [
        "every column is named by a header row",
        "1 table(s) are dated with a year missing",
    ]
    assert found.settled is False


def test_the_filer_says_the_figures_in_that_column_are_the_year_befores(three_d) -> None:
    """Not an opinion about the geometry - the filer's own XBRL, from the same accession.

    `ProceedsFromDivestitureOfBusinesses` is **96** over 2024 and **194** over 2023. The
    page prints `Proceeds from sale of assets and businesses, net of cash sold 122,681 96
    194`. The reader dropped the 96 and put the 194 at column index 2, where the
    statement's second column is 2024 - so the same concept, in the same table, is read
    off by a year, and both years are in the feed to prove it. That is B-030, this
    repository's worst extraction defect, in a cash flow statement.
    """
    facts = json.loads(
        (PUBLIC / "filer-facts" / "sec-ars-3d-systems-2025.json").read_text(encoding="utf-8")
    )
    over = facts["over_period"]
    concept = "us-gaap:ProceedsFromDivestitureOfBusinesses|USD"
    assert concept in over["2024-12-31"]["96000.0"]
    assert concept in over["2023-12-31"]["194000.0"]

    page = next(p for p in three_d.pages if p.number == 59)
    lost = page.tables[3]
    second = [row.value for row in lost.columns[1].rows]
    assert 194.0 in second, second
    assert 96.0 not in second, "the 2024 figure is not in the table at all"

    # And the three other figures that landed a year early, each one the filer's own.
    for value, year, tag in (
        (27_183_000.0, "2023-12-31", "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment|USD"),
        (
            180_925_000.0,
            "2023-12-31",
            "us-gaap:ProceedsFromSaleAndMaturityOfAvailableForSaleSecurities|USD",
        ),
    ):
        assert tag in over[year][str(value)], (value, year)


def test_a_maturity_schedule_counts_up_and_is_not_a_gap() -> None:
    """A statement prints the current year first and a maturity schedule counts up, so
    consecutive in either direction is consecutive. ResMed's debt maturities are headed
    2028 to 2031 and nothing is missing from them."""
    assert _skips_a_year(("2028", "2029", "2030", "2031")) is False
    assert _skips_a_year(("2025", "2024", "2023")) is False
    assert _skips_a_year(("2026", "2025")) is False
    assert _skips_a_year(("2024", "2023")) is False
    assert _skips_a_year(("2025", "2023")) is True
    assert _skips_a_year(("2025", "2022")) is True


def test_a_table_that_is_not_dated_is_not_asked_about_a_gap() -> None:
    """The question only means something where every column carries a year. A partly dated
    table is the naming cue's business and a table headed `Products Services Total` is not
    dated at all - answering `True` for either would report a missing column on a page that
    has not got one."""
    assert _skips_a_year(("2025", "", "2023")) is False
    assert _skips_a_year(("Products", "Services", "Total")) is False
    assert _skips_a_year(("2025",)) is False
    assert _skips_a_year(()) is False


# ----------------------------------------------- what the rule refuses, and why it refuses it


def test_a_sentence_that_crosses_the_columns_dates_nothing(three_d) -> None:
    """Why the rule asks for years and not for whatever a band says up there.

    Page 34 reads `The following table sets forth the Company's operating working capital
    at December 31, 2025, and 2024.` - one sentence, crossing all three columns, offering
    `December`, `2025,` and `2024.` to them. Page 67's is `As of December 31, 2025 and
    December 31, 2024, no single customer represented...`, which offers `and`, `customer`
    and `represented`. The wider rule - the nearest band above whose words *could* name the
    columns - takes both.
    """
    for number in (34, 67):
        page = next(p for p in three_d.pages if p.number == number)
        for table in page.tables:
            assert not any(table.headings), f"p{number}: {table.headings}"


def test_a_year_out_of_a_sentence_is_not_a_year() -> None:
    """The mechanism, said directly rather than through a page: the punctuation is the
    tell. `2025,` and `2024.` are words out of a sentence.

    This is the whole of the distinction, and it is the whole of it because nothing else
    separated them. Measured over all 118 candidate bands, the share of a band's words
    sitting at a column is **0.38** for that sentence and **0.50** for the legitimate
    header `(in thousands) 2025 2024` - so no cut on that share keeps the one and refuses
    the other, and shipping one would be a threshold nobody could check.
    """
    columns = (480.0, 550.0)
    assert _years([word("2025", 478.0), word("2024", 548.0)], columns) == ("2025", "2024")
    assert _years([word("2025,", 478.0), word("2024.", 548.0)], columns) == ()
    assert _years([word("December", 478.0), word("2024", 548.0)], columns) == ()


def test_a_row_of_data_cannot_date_a_table() -> None:
    """`Short-term lease cost 157 347 494` reads as a plain band, because none of those
    figures is money-shaped enough to establish a column - so it is a candidate heading
    band. Four-digit numbers in such a row would date the columns if they were years.

    Distinctness is what refuses it where it matters: a repeated figure cannot name two
    columns. Two columns headed the same year is a hazard `detect_periods` already reports
    and this path will not manufacture one.
    """
    columns = (480.0, 550.0)
    assert _years([word("1,234", 478.0), word("1,234", 548.0)], columns) == ()
    assert _years([word("2020", 478.0), word("2020", 548.0)], columns) == ()


def test_half_a_header_is_no_header() -> None:
    """All-or-nothing, the way `_headings` is and for the reason `_headings_for` gives: a
    header offering two years over three columns cannot say which column is unlabelled, and
    naming two and leaving one blank is a worse answer than saying nothing."""
    columns = (410.0, 480.0, 550.0)
    assert _years([word("2026", 408.0), word("2025", 478.0)], columns) == ()
    assert _years(
        [word("2026", 408.0), word("2025", 478.0), word("2024", 548.0)], columns
    ) == ("2026", "2025", "2024")

    # And one column is not a comparative statement, so there is nothing to tell apart.
    assert _years([word("2025", 478.0)], (480.0,)) == ()


def test_the_nearest_band_above_wins(three_d) -> None:
    """A search that reaches up the page has to prefer what is nearest, so a second table
    under its own header cannot take the first table's.

    Said as a unit, because the corpus has no page that distinguishes them: `_dated` walks
    the bands in reverse and stops at the first that dates every column.
    """
    columns = (480.0, 550.0)
    far = [word("2019", 478.0), word("2018", 548.0)]
    near = [word("2025", 478.0), word("2024", 548.0)]
    assert _dated([far, near], columns) == ("2025", "2024")
    assert _dated([near, far], columns) == ("2019", "2018")
    # A band that dates nothing is stepped over rather than ending the search, which is
    # the entire defect: `Current assets:` ended it.
    assert _dated([near, [word("Current", 240.0), word("assets:", 280.0)]], columns) == (
        "2025",
        "2024",
    )
    assert _dated([], columns) == ()


def test_a_heading_the_page_already_gave_is_never_overwritten() -> None:
    """The new read fills in where there was nothing, and never replaces something.

    **Written as a unit because no page in the corpus can prove it**, which the revert
    harness is what established: swapping the two in `_table` left the page-30 assertion
    below green. Page 30 is headed `(in thousands) 2025 2024 Change`, and `Change` is not a
    year, so the year read declines that table either way and the order never comes up. A
    guard that cannot fail is the defect this repository names first, so the ordering is
    asserted directly against the thing that decides it.

    Here the band immediately above names the columns `2025` and `Change`, and a band
    further up dates them `2025` and `2024`. The near one has to win - it is the header a
    person reads - and `Change` has to survive, because a column the document named
    something other than a year is still named.
    """
    columns_at = (480.0, 550.0)
    # Three rows, because `COLUMN_NEEDS` is three: a column has to run down the table, and
    # two figures sharing a right edge are a coincidence.
    run = [
        [word(label, 260.0, top), word("1,000", 480.0, top), word("2,000", 550.0, top)]
        for label, top in (("Revenue", 200.0), ("Cost of sales", 215.0), ("Gross", 230.0))
    ]
    named = [word("2025", 478.0, 180.0), word("Change", 548.0, 180.0)]
    dated = [word("2025", 478.0, 160.0), word("2024", 548.0, 160.0)]

    # The band that would date them really would, so this test can tell the two apart.
    assert _years(dated, columns_at) == ("2025", "2024")

    built = _table(1, run, named, [dated])
    assert built is not None
    assert built.columns == columns_at
    assert built.headings == ("2025", "Change")

    # And with nothing above it, the near band is still what it was.
    assert _table(1, run, named, []).headings == ("2025", "Change")
    # With no near heading at all, the dated band is reached - which is the whole phase.
    assert _table(1, run, [], [dated]).headings == ("2025", "2024")


def test_the_page_whose_third_column_is_not_a_year(three_d) -> None:
    """Page 30, where the document named a column `Change`. The year read declines a table
    it cannot date every column of, so this heading is the one `_headings` gave and is
    unchanged by this phase - which is what `tests/p151` asserts and this re-asserts
    against the whole corpus having moved."""
    page = next(p for p in three_d.pages if p.number == 30)
    assert page.tables[0].headings == ("2025", "2024", "Change")


# -------------------------------------------------------- measured over the whole corpus


def test_what_changed_and_what_did_not(three_d, resmed) -> None:
    """The counts, asserted because they are the argument.

    Tables and rows must not move at all - this writes column headings and touches neither
    the columns nor the rows. 72 tables and 815 rows on the 3D filing are the numbers
    `tests/checkpoints/c86` has asserted since P155, and they are unchanged; what moved is
    **27 named to 45**, and c86's assertion moves with it in this commit.
    """
    for doc, tables, rows, multi, named in (
        (three_d, 72, 815, 59, 45),
        (resmed, 70, 960, 66, 59),
    ):
        assert sum(len(p.tables) for p in doc.pages) == tables
        assert (
            sum(
                1
                for p in doc.pages
                for t in p.tables
                for c in t.columns
                for r in c.rows
                if r.value is not None
            )
            == rows
        )
        assert len([t for p in doc.pages for t in p.tables if len(t.columns) > 1]) == multi
        assert (
            len(
                [
                    t
                    for p in doc.pages
                    for t in p.tables
                    if len(t.columns) > 1 and t.headings and all(t.headings)
                ]
            )
            == named
        )


def test_every_page_reporting_a_gap_is_one_of_the_two(three_d, resmed) -> None:
    """Two tables over 232 pages, which is the honest frequency: a lost column needs a
    statement column whose figures are nearly all small or nil, and that is rare. Rare and
    silent is the combination that matters - this one had been read correctly 194 times and
    wrongly four times, and nothing could tell which."""
    found: list[str] = []
    for doc in (three_d, resmed):
        for page in doc.pages:
            said = detect_periods(page.text, tables=list(page.tables))
            found += [
                f"p{page.number}" for s in said.ambiguous if s.startswith("columns:") and "gap" in s
            ]
    assert sorted(found) == ["p104", "p59"], found
