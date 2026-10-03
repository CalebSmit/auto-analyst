"""C89 - the three tie-outs, together.

Three arithmetic checks over a statement now live in one module, each added by a different
phase and each measured on the same document:

* **`footings_in`** (P99, widened P154) re-adds a column: a total against the run of rows
  standing above it.
* **`two_sides`** (P154) compares the two halves of a balance sheet, from the two labels the
  statement wrote.
* **`cash_roll_forward`** (P160) re-adds a beginning and a net change against a stated
  ending, and chains the columns of a comparative statement into each other.

What no phase can ask is whether the three say one consistent thing, and asking it here
corrected the argument for the newest of them. **Footing finds no totals at all on a cash
flow statement** - not one line on the filing's own begins with the word total, because they
are called `Net cash provided by operating activities` - so without the roll-forward there
is no arithmetic over that statement whatsoever, and every figure on it is uncovered by
construction. They also
share a tolerance, a notion of what a row is, and a habit of answering `None` rather than
`False` where the statement says nothing, and each of those is a thing two of them could
start disagreeing about.

The whole filing is read once here and all three asked of every page, because the thing worth
holding is the **shape of their answers across a document**: which pages each speaks about,
and that no two of them speak about the same page for the same reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intake.readers.documents import read_document
from intake.readers.footing import (
    CENT,
    cash_roll_forward,
    footings_in,
    rolls_on,
    two_sides,
)

ROOT = Path(__file__).resolve().parents[3]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"
BALANCE_SHEET = 56
CASH_FLOWS = 59


@pytest.fixture(scope="module")
def filing():
    return read_document(FILING.read_bytes(), FILING.name)


def blocks(document) -> dict[str, list]:
    """What **footing** is given: one column of one table.

    Per table, not per page, and that is not a detail. A footing is a run of rows and its
    ordinals are a block's, so pooling two tables into one list collides them - the first
    draft of this file did exactly that, and `Total current assets` came back with a part
    whose value was `None` because the ordinal belonged to a row in the other table.
    """
    return {
        f"p{page.number}/t{n}/c{c.index}": list(c.rows)
        for page in document.pages
        for n, table in enumerate(page.tables, start=1)
        for c in table.columns
    }


def statements(document) -> dict[str, list]:
    """What the **two cross-row checks** are given: one page read down one column, across
    whatever blocks the reader split it into.

    A wider grouping than footing's, deliberately and for a reason the filing proves: the
    reader starts a new block at every heading, so on page 56 the assets total and the line
    that totals the other side are in *different* blocks. A check given a block at a time
    would never see both.

    So the three do not share one grouping, and the two groupings are the two shapes of
    question: *does this run add up* is a block's question, *do these two figures agree* is
    a statement's.
    """
    out: dict[str, list] = {}
    for page in document.pages:
        widest = max((len(t.columns) for t in page.tables), default=0)
        for n in range(widest):
            out[f"p{page.number}/c{n}"] = [
                row
                for table in page.tables
                if n < len(table.columns)
                for row in table.columns[n].rows
            ]
    return out


# --------------------------------------------------- which pages each of the three speaks about


def test_each_check_speaks_only_where_its_own_figures_are_stated(filing) -> None:
    """The shape of the three answers across a hundred and eight pages.

    Written as one test because the interesting thing is the comparison: footing has an
    opinion about most statements, the other two about one page each, and if that ever
    stopped being true it would mean one of them had started guessing.
    """
    found = statements(filing)
    foots = {
        where.split("/")[0]
        for where, rows in blocks(filing).items()
        if footings_in(rows).footings
    }
    balances = {
        where.split("/")[0] for where, rows in found.items() if two_sides(rows).stated
    }
    cash = {
        where.split("/")[0]
        for where, rows in found.items()
        if cash_roll_forward(rows).stated
    }

    assert len(foots) > 15, f"footing speaks about {len(foots)} pages, which is too few"
    assert balances == {f"p{BALANCE_SHEET}"}, sorted(balances)
    assert cash == {f"p{CASH_FLOWS}"}, sorted(cash)
    assert balances != cash, "the two cross-row checks are about different statements"


def test_footing_has_nothing_to_say_about_a_cash_flow_statement(filing) -> None:
    """Why there are three of these rather than one, and it is stronger than I first wrote.

    The draft of this test asserted that the cash flow statement's totals all foot and that
    none of them covers the ending cash. It failed, and the reason is better than the claim:
    **footing finds no totals on that page at all.** `is_a_total` reads what the statement
    calls a row, and a cash flow statement calls them `Net cash provided by operating
    activities` and `Net decrease in cash, cash equivalents and restricted cash` - not one
    line on it begins with the word total.

    So without the roll-forward there is **no arithmetic over a cash flow statement
    whatsoever**: every figure on it is uncovered by construction, which is the state P99
    found the whole build in. The page is not a page where footing is insufficient; it is a
    page where footing is silent.
    """
    rolls = {
        where: rows
        for where, rows in statements(filing).items()
        if cash_roll_forward(rows).stated
    }
    assert rolls, "the filing has a cash flow statement in it"

    for where, rows in rolls.items():
        page = where.split("/")[0]
        assert cash_roll_forward(rows).rolls_forward is True

        # Footing asked of the blocks that make up this statement, which is the grouping it
        # is given - see `blocks` above.
        on_the_page = [
            found
            for block, block_rows in blocks(filing).items()
            if block.startswith(f"{page}/")
            for found in footings_in(block_rows).footings
        ]
        assert on_the_page == [], (
            f"{page}: footing now finds totals here, which would be news - the claim above "
            f"is that it finds none: {[f.label for f in on_the_page][:5]}"
        )

    # And the contrast, on the statement footing does have a great deal to say about.
    sheet = [
        found
        for block, rows in blocks(filing).items()
        if block.startswith(f"p{BALANCE_SHEET}/")
        for found in footings_in(rows).footings
    ]
    assert len([f for f in sheet if f.covered]) == 10, [f.label for f in sheet if f.covered]


def test_all_three_agree_about_the_document_they_were_measured_on(filing) -> None:
    """Every answer each check gives about this filing, in one place.

    The numbers are here so that a change to any of the three has to come past a reader
    rather than past a count. Each was measured by its own phase; this is the only place
    they are measured together.
    """
    found = statements(filing)

    covered = sum(
        1 for rows in blocks(filing).values() for f in footings_in(rows).footings if f.covered
    )
    uncovered = sum(
        1
        for rows in blocks(filing).values()
        for f in footings_in(rows).footings
        if not f.covered
    )
    sided = [two_sides(rows) for rows in found.values() if two_sides(rows).stated]
    rolled = [
        cash_roll_forward(rows)
        for rows in found.values()
        if cash_roll_forward(rows).stated
    ]

    assert covered == 73, f"totals that re-add moved to {covered}"
    assert uncovered > 0, "and some do not, or the check is accepting everything"
    assert [s.balances for s in sided] == [True, True]
    assert [r.rolls_forward for r in rolled] == [True, True, True]
    assert rolls_on(rolled) == ()


# --------------------------------------------- and each one's arithmetic, done again here


def test_every_claim_of_cover_re_adds_independently(filing) -> None:
    """Given its rows, not asked whether it believes itself. A total that re-adds is what
    lets a figure past a person unseen."""
    wrong = []
    for where, rows in blocks(filing).items():
        by_ordinal = {r.ordinal: r for r in rows}
        for found in footings_in(rows).footings:
            if not found.covered:
                continue
            parts = [by_ordinal[o].value for o in found.ordinals]
            assert all(v is not None for v in parts), f"{where}: {found.label}"
            added = sum(v for v in parts if v is not None)
            if abs(added - found.value) > CENT:
                wrong.append(
                    f"{where}: {found.label} says {found.value:,.2f} and its "
                    f"{len(parts)} rows add to {added:,.2f}"
                )
    assert wrong == [], "a footing that does not foot:\n" + "\n".join(wrong[:8])


def test_the_two_sides_and_the_cash_re_add_independently(filing) -> None:
    """The same, for the two checks whose arithmetic is three figures rather than a run."""
    for rows in statements(filing).values():
        sides = two_sides(rows)
        if sides.stated:
            assert sides.assets is not None and sides.liabilities_and_equity is not None
            assert abs(sides.assets - sides.liabilities_and_equity) <= CENT

        rolled = cash_roll_forward(rows)
        if rolled.stated:
            assert rolled.began is not None and rolled.changed is not None
            assert rolled.ended is not None
            assert abs(rolled.began + rolled.changed - rolled.ended) <= CENT


def test_the_three_share_one_tolerance(filing) -> None:
    """All three decide "it adds up" and they have to decide it the same way.

    `CENT` is half a cent, and it is deliberately tight: these values come from a workbook at
    full stored precision or off a statement at its printed precision, so a total that really
    is the sum of its rows matches to floating point. Two of these drifting apart would mean
    a figure accepted by one check and shown by another, which is the kind of disagreement
    nobody would see.
    """
    import inspect

    from intake.readers import footing

    assert CENT == 0.005, "half a cent, which is what all three mean by it adds up"

    # The classes rather than the properties, because `inspect.getsource` will not take a
    # property object - and the class is the honest unit anyway: what is being asked is
    # whether this check's arithmetic is written against the shared tolerance at all.
    using = {
        "footing": inspect.getsource(footing._matching_tail),  # noqa: SLF001
        "the two sides": inspect.getsource(footing.TwoSides),
        "the cash": inspect.getsource(footing.CashRollForward),
    }
    for which, source in using.items():
        assert "CENT" in source, f"{which} does not use the shared tolerance"
        assert "RELATIVE" in source, f"{which} does not allow for float64 the same way"


def test_each_says_nothing_rather_than_false_where_the_statement_is_silent(filing) -> None:
    """The habit all three share, and the one most easily lost.

    An income statement is not a failed balance sheet and not a failed cash flow statement.
    `None` is "this does not apply", `False` is "this is wrong", and a surface that got the
    second where it should have had the first would route every statement in the filing to a
    person.
    """
    silent = 0
    for rows in statements(filing).values():
        sides, rolled = two_sides(rows), cash_roll_forward(rows)
        if not sides.stated:
            assert sides.balances is None and sides.out_by is None and sides.as_line() == ""
            silent += 1
        if not rolled.stated:
            assert rolled.rolls_forward is None and rolled.out_by is None
            assert rolled.as_line() == ""
    assert silent > 50, f"only {silent} statements were silent; this document has hundreds"


def test_footing_says_nothing_about_a_statement_with_no_totals() -> None:
    """The same habit in the third check, which says it differently because it reports a
    list rather than a verdict - and `no totals to check` is not `nothing re-added`."""
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class R:
        label: str
        value: float | None
        ordinal: int = 0

    empty = footings_in([R("Revenue", 100.0), R("Cost of sales", -60.0)])
    assert empty.footings == ()
    assert empty.foots is False, "no totals is not all totals re-adding"
    assert empty.as_line() == "no totals to check"
