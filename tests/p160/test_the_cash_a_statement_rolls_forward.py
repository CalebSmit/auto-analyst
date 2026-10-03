"""P160: the third tie-out a reviewer makes, and nothing produced it.

Footing proves a column adds. `two_sides` proves the balance sheet balances. The next thing
an analyst does is the cash roll-forward, and it catches what neither of the others can.

**Footing finds no totals on a cash flow statement at all.** `is_a_total` reads what the
statement calls a row, and not one line on the filing's own begins with the word total - they
are `Net cash provided by operating activities`, `Net decrease in cash, cash equivalents and
restricted cash`. So every figure on that statement is uncovered by construction, which is
the state P99 found the whole build in, and this is the only arithmetic there is over it.
Measured in C89, where the claim this file was first written on - that the subtotals foot and
merely fail to cover the ending cash - turned out to be too weak.

Measured on page 59 of the filing in `fixtures/public`, which the reader already parses into
five tables and ninety-eight rows:

| column | beginning | net change | ending stated |
|---|---|---|---|
| FY2025 | 172,881 | (75,781) | **97,100** |
| FY2024 | 333,111 | (160,230) | **172,881** |
| FY2023 | 391,975 | (58,864) | **333,111** |

All three reconcile exactly, and each year's ending is the next year's beginning - so the
inputs exist and the arithmetic holds, which is the state to write a check in.

**The same measurement says which check not to write.** The obvious fourth one is that this
ending cash equals the balance sheet's cash line, and here it does not: page 56 says
**95,635** where page 59 says **97,100**, because the cash flow line reads *cash, cash
equivalents **and restricted cash***. The difference is the restricted cash, both statements
are correct, and a check comparing them would report a discrepancy of 1,465 on a document
with nothing wrong with it. A check whose findings are mostly not findings teaches a reader
to skip the section it is in (B-086), so that comparison is not made - and the figures are
written down in `CashRollForward` so the next person to think of it finds the measurement
rather than the idea.

**It speaks about one page in a hundred and eight**, which is the calibration: a check that
spoke about every page would be noise and one that spoke about none would be nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from intake.readers.documents import read_document
from intake.readers.footing import (
    CashRollForward,
    cash_roll_forward,
    footings_in,
    rolls_on,
    two_sides,
)

ROOT = Path(__file__).resolve().parents[2]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"
CASH_FLOWS = 59
BALANCE_SHEET = 56


@dataclass(frozen=True)
class R:
    """A parsed row, as the reader reads one."""

    label: str
    value: float | None
    ordinal: int = 0


def rows(*pairs: tuple[str, float | None]) -> list[R]:
    return [R(label, value, n) for n, (label, value) in enumerate(pairs, start=1)]


@pytest.fixture(scope="module")
def filing():
    return read_document(FILING.read_bytes(), FILING.name)


def columns_of(document, page_number: int) -> list[list]:
    page = next(p for p in document.pages if p.number == page_number)
    widest = max((len(t.columns) for t in page.tables), default=0)
    return [
        [
            row
            for table in page.tables
            if n < len(table.columns)
            for row in table.columns[n].rows
        ]
        for n in range(widest)
    ]


# ------------------------------------------------------------------- the filing's own cash


def test_the_filings_three_columns_each_roll_forward(filing) -> None:
    """The exit criterion, on the document nobody here wrote."""
    found = [
        rolled
        for rows_ in columns_of(filing, CASH_FLOWS)
        if (rolled := cash_roll_forward(rows_)).stated
    ]
    assert len(found) == 3, [r.as_line() for r in found]
    assert [(r.began, r.changed, r.ended) for r in found] == [
        (172_881.0, -75_781.0, 97_100.0),
        (333_111.0, -160_230.0, 172_881.0),
        (391_975.0, -58_864.0, 333_111.0),
    ]
    for rolled in found:
        assert rolled.rolls_forward is True, rolled.as_line()
        assert rolled.out_by is None
        assert "rolls forward" in rolled.as_line()


def test_the_columns_chain_into_each_other(filing) -> None:
    """A comparative statement prints its years side by side, so each year's closing cash is
    the next year's opening. That makes the columns a chain, and a chain is checkable without
    knowing which column is which year."""
    found = [
        rolled
        for rows_ in columns_of(filing, CASH_FLOWS)
        if (rolled := cash_roll_forward(rows_)).stated
    ]
    assert rolls_on(found) == (), rolls_on(found)

    # And it is a real chain rather than three unrelated columns: the figures overlap.
    assert found[0].began == found[1].ended
    assert found[1].began == found[2].ended


def test_it_speaks_about_one_page_in_a_hundred_and_eight(filing) -> None:
    """The calibration. A check that spoke about every page would be noise, and one that
    spoke about none would be nothing - and this is a document full of pages that mention
    cash without rolling any forward."""
    spoke = {
        page.number
        for page in filing.pages
        for rows_ in columns_of(filing, page.number)
        if cash_roll_forward(rows_).stated
    }
    assert spoke == {CASH_FLOWS}, sorted(spoke)
    assert len(filing.pages) > 100, "and it is a long document, or this means little"


def test_the_balance_sheets_cash_is_not_compared_to_it(filing) -> None:
    """The check deliberately not made, with the figures that settle it.

    Both statements are correct and they state different things: the cash flow line is *cash,
    cash equivalents **and restricted cash***. A reader that compared them would open every
    engagement by reporting a discrepancy on a document with nothing wrong with it.
    """
    sheet = next(
        row.value
        for rows_ in columns_of(filing, BALANCE_SHEET)
        for row in rows_
        if (row.label or "").strip().lower().startswith("cash and cash equivalents")
        and row.value is not None
    )
    flows = next(
        rolled.ended
        for rows_ in columns_of(filing, CASH_FLOWS)
        if (rolled := cash_roll_forward(rows_)).stated
    )
    assert sheet == 95_635.0
    assert flows == 97_100.0
    assert flows - sheet == pytest.approx(1_465.0), "which is the restricted cash"

    # And nothing in the check reaches for the other statement: it takes rows, and it is
    # given one column of one page at a time.
    import inspect

    source = inspect.getsource(cash_roll_forward)
    assert "balance" not in source.lower()
    # And the reason is written down where the next person to think of it will look, with
    # the figures rather than the idea - `or True` was on the end of this line and made it
    # say nothing, which is the defect this repository is named after.
    said = inspect.getdoc(CashRollForward) or ""
    assert "restricted cash" in said
    assert "95,635" in said and "97,100" in said


def test_a_statement_can_foot_everywhere_and_still_not_roll_forward(filing) -> None:
    """Why this is a separate check rather than more footing.

    Asked of blocks the way footing is asked of them in production, and what it finds on this
    page is **nothing**: a cash flow statement calls no line a total, so footing has no
    opinion about it at all. The roll-forward is not a stronger version of footing here, it
    is the only arithmetic there is.
    """
    page = next(p for p in filing.pages if p.number == CASH_FLOWS)
    found = [
        f
        for table in page.tables
        for column in table.columns
        for f in footings_in(column.rows).footings
    ]
    assert found == [], (
        "footing now finds totals on a cash flow statement, which would be news: "
        f"{[f.label for f in found][:5]}"
    )

    # And the roll-forward does have an answer about the same page, which is the point.
    rolled = [
        r for rows_ in columns_of(filing, CASH_FLOWS) if (r := cash_roll_forward(rows_)).stated
    ]
    assert len(rolled) == 3
    assert all(r.rolls_forward for r in rolled)


# ---------------------------------------------------------- and the arithmetic, said small


def test_a_statement_that_is_out_says_by_how_much() -> None:
    """The whole value of a tie-out is that it is arithmetic. A hundred out is a fact
    somebody needs, not a tolerance to be widened to."""
    out = cash_roll_forward(
        rows(
            ("Net decrease in cash", -75_781.0),
            ("Cash at the beginning of the period", 172_881.0),
            ("Cash at the end of the period", 97_200.0),
        )
    )
    assert out.rolls_forward is False
    assert out.out_by == pytest.approx(-100.0)
    assert "out by -100.00" in out.as_line()


def test_a_statement_that_does_not_state_the_three_says_nothing() -> None:
    """An income statement is not a failed cash flow statement. `None` rather than `False`,
    exactly as `two_sides` answers about a document that states one side."""
    for given in (
        rows(("Revenue", 386_902.0), ("Cost of sales", -240_000.0)),
        rows(("Cash at the beginning of the period", 172_881.0)),
        rows(("Cash at the end of the period", 97_100.0)),
        rows(
            ("Cash at the beginning of the period", 172_881.0),
            ("Cash at the end of the period", 97_100.0),
        ),
    ):
        rolled = cash_roll_forward(given)
        assert not rolled.stated
        assert rolled.rolls_forward is None
        assert rolled.out_by is None
        assert rolled.as_line() == ""


def test_the_first_of_each_is_taken() -> None:
    """A filing states its cash line twice on some statements - once in the roll-forward and
    once in a reconciliation of restricted cash beneath it - and the second is a different
    figure for a different purpose."""
    twice = cash_roll_forward(
        rows(
            ("Net decrease in cash", -75_781.0),
            ("Cash at the beginning of the period", 172_881.0),
            ("Cash at the end of the period", 97_100.0),
            ("Restricted cash at the end of the period", 1_465.0),
            ("Cash at the end of the period, excluding restricted", 95_635.0),
        )
    )
    assert twice.ended == 97_100.0, "the first, which is the one in the roll-forward"
    assert twice.rolls_forward is True


def test_a_chain_of_fewer_than_two_columns_says_nothing() -> None:
    """Not a pass. One column is not a chain, and reporting it as one would be a check
    answering a question nobody could have asked."""
    one = cash_roll_forward(
        rows(
            ("Net decrease in cash", -1.0),
            ("Cash at the beginning of the period", 10.0),
            ("Cash at the end of the period", 9.0),
        )
    )
    assert rolls_on([one]) == ()
    assert rolls_on([]) == ()
    assert rolls_on([CashRollForward(), one]) == (), "an unstated column is not a link"


def test_a_broken_chain_is_named_with_both_figures() -> None:
    """What a person needs is which two columns disagree and by how much, not that something
    somewhere does not line up."""
    newer = cash_roll_forward(
        rows(
            ("Net decrease in cash", -75_781.0),
            ("Cash at the beginning of the period", 172_881.0),
            ("Cash at the end of the period", 97_100.0),
        )
    )
    older = cash_roll_forward(
        rows(
            ("Net decrease in cash", -160_230.0),
            ("Cash at the beginning of the period", 333_111.0),
            ("Cash at the end of the period", 172_000.0),
        )
    )
    (said,) = rolls_on([newer, older])
    assert "172,881.00" in said and "172,000.00" in said
    assert "881.00" in said, "and the difference between them"


def test_the_two_sides_check_is_untouched(filing) -> None:
    """Said here because this phase added a second cross-row check to the same module, and
    the first one is what the balance sheet rests on."""
    for rows_ in columns_of(filing, BALANCE_SHEET):
        sides = two_sides(rows_)
        if sides.stated:
            assert sides.balances is True
            assert sides.assets == 521_728.0 or sides.assets == 608_846.0
