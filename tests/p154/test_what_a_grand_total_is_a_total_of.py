"""P154: a statement's grand total is a total of a mix, and the reader knew two pure shapes.

The footing check is the evidence the acceptance rule turns on: `review/router.py` routes an
extracted figure to a person unless a total that re-adds covers it. It knew two shapes - a
total of the lines above it, and a total of the subtotals above it - and a real balance
sheet's grand total is neither:

    Total current assets          346,707     <- subtotal, over the five rows above
    Property and equipment, net    49,249
    ... six more
    Total assets                  521,728     <- the subtotal AND the seven loose rows

Over the lines it double-counted the subtotal and missed by exactly 346,707. Over the
subtotals it needed two and had one. So the three totals a person checks first - `Total
assets`, `Total liabilities`, and the line that totals the other side - were all uncovered,
and every row above them stayed uncovered too, which means every figure on the statement
went to a person as though nothing had been checked.

**The two shapes are one shape seen twice.** A total sums the run of rows standing above it,
where a run that has already been totalled stands as its own total rather than as its parts.
One list, and the mix falls out of it. Measured over the whole filing: the 65 totals that
footed over lines still foot over lines, four more foot over a mix, and nothing else moved -
`Total assets` takes eight rows and `Total liabilities` takes five, which is exactly what
they are.

**And footing cannot prove the two sides agree.** They are different runs, and on a real
filing they are not even in the same block, because the reader starts a new one at every
heading. That check is made separately, by reading the two labels the statement wrote and
comparing the two figures it printed - nothing is inferred, and on a document that states no
balance sheet it says nothing at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from intake.readers.documents import read_document
from intake.readers.footing import LINES, MIXED, SUBTOTALS, footings_in, two_sides

ROOT = Path(__file__).resolve().parents[2]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"


@dataclass(frozen=True)
class R:
    """A parsed row, as the footing reader reads one."""

    label: str
    value: float | None
    ordinal: int = 0


def rows(*pairs: tuple[str, float | None]) -> list[R]:
    return [R(label, value, n) for n, (label, value) in enumerate(pairs, start=1)]


@pytest.fixture(scope="module")
def filing():
    return read_document(FILING.read_bytes(), FILING.name)


def column_rows(document, page_number: int, index: int) -> list:
    """One statement: a page read down one column, across whatever blocks it is split into.

    Tables on a page need not be the same width - page 59 carries one narrower than its
    neighbour - so a table without this column contributes nothing rather than raising.
    """
    page = next(p for p in document.pages if p.number == page_number)
    return [
        row
        for table in page.tables
        if index < len(table.columns)
        for row in table.columns[index].rows
    ]


# ------------------------------------------------------------------- the shape that was missing


def test_a_total_over_a_subtotal_and_the_rows_after_it_re_adds() -> None:
    """The shape of every balance sheet. Written out small so the arithmetic is visible:
    346,707 is the subtotal and the three rows after it are 49,249, 16,614 and 15,575."""
    statement = rows(
        ("Cash", 95_635),
        ("Inventories", 127_496),
        ("Prepaid", 123_576),
        ("Total current assets", 346_707),
        ("Property and equipment, net", 49_249),
        ("Intangible assets, net", 16_614),
        ("Goodwill", 15_575),
        ("Total assets", 428_145),
    )
    report = footings_in(statement)
    grand = report.footings[-1]
    assert grand.covered, f"out by {grand.delta}"
    assert grand.how == MIXED
    assert len(grand.ordinals) == 4, "the subtotal and the three rows after it"


def test_the_filings_own_grand_totals_re_add(filing) -> None:
    """The same thing on the document nobody here wrote."""
    for index, assets, liabilities in ((0, 521_728, 279_177), (1, 608_846, 430_695)):
        report = footings_in(column_rows(filing, 56, index))
        by_label = {f.label: f for f in report.footings}
        assert by_label["Total assets"].covered
        assert by_label["Total assets"].value == assets
        assert by_label["Total liabilities"].covered
        assert by_label["Total liabilities"].value == liabilities


def test_the_pure_shapes_still_work_and_still_say_which_they_were() -> None:
    """A total of plain lines is the common case and must not have moved."""
    plain = footings_in(rows(("Cash", 10), ("Bank", 20), ("Total cash", 30)))
    assert plain.footings[-1].how == LINES

    nested = footings_in(
        rows(
            ("Cash", 10),
            ("Bank", 20),
            ("Total cash", 30),
            ("Trade", 40),
            ("Other", 60),
            ("Total receivables", 100),
            ("Total current assets", 130),
        )
    )
    assert nested.footings[-1].covered
    assert nested.footings[-1].how == SUBTOTALS


def test_nothing_that_did_not_foot_is_made_to_foot(filing) -> None:
    """The measurement that makes the change safe: nothing is made to foot that did not.

    Sixty-five of these footed over plain lines when this phase was written, and the mixed
    shape it added accounts for four more. **P155 took the plain count to sixty-nine**, and
    it is worth saying why rather than moving a number: a statement prints `$` in front of
    the first figure of a column, the reader kept that mark on the label when other words
    followed it in the band, and `is_a_total` asks whether a label *begins* with the word
    total. So `$ Total property and equipment, net` was not a total, and four real ones were
    invisible - the property and equipment schedule on page 75 in both years, and page 104's
    two. All four re-add exactly, and `test_the_four_p155_uncovered` adds them up here.
    """
    shapes: dict[str, int] = {}
    for page in filing.pages:
        for table in page.tables:
            for column in table.columns:
                for found in footings_in(column.rows).footings:
                    if found.covered:
                        shapes[found.how] = shapes.get(found.how, 0) + 1
    assert shapes.get(LINES) == 69, f"the plain footings moved: {shapes}"
    assert shapes.get(MIXED) == 4, f"the mixed footings are {shapes.get(MIXED)}"
    assert sum(shapes.values()) == 73


def test_the_four_p155_uncovered(filing) -> None:
    """The four a stray currency mark was hiding, each with its own arithmetic.

    Counted in the test above and added up here, because a count that goes up is the one
    direction that matters - a total that re-adds is what lets a figure past a person
    unseen, so four new ones are four claims, not a number.
    """
    want = {
        (75, "Total property and equipment, net", 49_249.0): (210_959.0, -161_710.0),
        (75, "Total property and equipment, net", 51_044.0): (208_078.0, -157_034.0),
        (104, "Total", 8_242.0): (1_401.0, 5_598.0, 1_243.0),
        (104, "Total", 8_450.0): (1_034.0, 5_855.0, 1_561.0),
    }
    found: dict[tuple[int, str, float], tuple[float, ...]] = {}
    for page in filing.pages:
        if page.number not in (75, 104):
            continue
        for table in page.tables:
            for column in table.columns:
                by_ordinal = {row.ordinal: row for row in column.rows}
                for footing in footings_in(column.rows).footings:
                    key = (page.number, footing.label.strip(), footing.value)
                    if footing.covered and key in want:
                        found[key] = tuple(
                            by_ordinal[o].value or 0.0 for o in footing.ordinals
                        )
    assert found == want, f"missing {sorted(set(want) - set(found))}"
    for (_, label, value), parts in want.items():
        assert sum(parts) == pytest.approx(value), label


def test_a_figure_carried_down_is_not_a_sum_of_itself() -> None:
    """A subtotal repeated as a later total adds nothing and covers nothing. Calling it a
    footing would claim the same evidence twice for the same rows."""
    carried = footings_in(
        rows(("Cash", 10), ("Bank", 20), ("Total cash", 30), ("Total current assets", 30))
    )
    assert carried.footings[0].covered, "the real subtotal should still foot"
    assert not carried.footings[1].covered, "the carried figure must not"


def test_a_total_that_is_out_still_says_what_it_is_out_by() -> None:
    """The whole value of the cover is that it is arithmetic. A total that is out by nine
    dollars is a fact somebody needs, not a footing to be stretched to."""
    wrong = footings_in(rows(("Cash", 10), ("Bank", 20), ("Total cash", 39)))
    found = wrong.footings[0]
    assert not found.covered
    assert found.delta == pytest.approx(-9.0)
    assert "out by" in wrong.as_line()


# ---------------------------------------------------------- and whether the two sides agree


def test_the_balance_sheet_balances(filing) -> None:
    """The check an analyst makes before any other, and one footing cannot make: the two
    sides are different runs of rows, in different blocks."""
    for index, expected in ((0, 521_728), (1, 608_846)):
        sides = two_sides(column_rows(filing, 56, index))
        assert sides.stated
        assert sides.balances is True
        assert sides.assets == expected == sides.liabilities_and_equity
        assert sides.out_by is None


def test_a_statement_that_does_not_balance_says_so_and_by_how_much() -> None:
    out = two_sides(
        rows(("Total assets", 521_728), ("Total liabilities and equity", 520_728))
    )
    assert out.balances is False
    assert out.out_by == pytest.approx(1_000.0)
    assert "out by 1,000.00" in out.as_line()


def test_a_total_of_one_side_only_is_not_the_other_side() -> None:
    """`Total liabilities` is a part of the other side, not the other side. Taking it as
    one would report every balance sheet in the world as out by its equity."""
    half = two_sides(rows(("Total assets", 521_728), ("Total liabilities", 279_177)))
    assert not half.stated
    assert half.balances is None
    assert half.as_line() == ""


def test_a_statement_that_states_neither_side_says_nothing(filing) -> None:
    """An income statement is not a failed balance sheet. Of a hundred and eight pages this
    speaks about one, which is the one that states both sides."""
    speaks = [
        page.number
        for page in filing.pages
        for index in range(len(page.tables[0].columns) if page.tables else 0)
        if two_sides(column_rows(filing, page.number, index)).stated
    ]
    assert set(speaks) == {56}, f"it spoke about pages {sorted(set(speaks))}"


def test_a_line_inside_the_assets_is_not_the_assets_total() -> None:
    """A statement writes `Total assets held for sale` as an ordinary line in the current
    assets. It begins with the same two words as the sum of the whole side, and it comes
    first - so a prefix match takes it and reports the balance sheet as out by nearly all
    of itself. The filing this build measures against carries that very label.
    """
    sheet = rows(
        ("Total assets held for sale", 3_176),
        ("Total assets", 521_728),
        ("Total liabilities and stockholders' equity", 521_728),
    )
    sides = two_sides(sheet)
    assert sides.assets == 521_728, f"it took {sides.assets}"
    assert sides.balances is True


def test_a_statement_with_only_one_side_is_not_a_balance_sheet() -> None:
    """`stated` needs both. With either, every income statement that happens to total its
    assets - or any schedule that totals liabilities and equity - would be reported as a
    balance sheet that does not balance."""
    assets_only = two_sides(rows(("Cash", 10), ("Total assets", 10)))
    assert not assets_only.stated and assets_only.balances is None

    other_only = two_sides(rows(("Total liabilities and equity", 10)))
    assert not other_only.stated and other_only.balances is None
