"""The Footing Reader: which totals re-add, and which rows they cover.

`review/router.py` has routed an extracted figure to a person since P37 unless something
re-added a total it feeds. The rule is built, tested and right - *"the failure that matters
is a misread the model is confident about, and nothing in a probability catches it. What
catches it is a total that stops adding up."* Nothing has ever produced its evidence, so
every extracted figure has been uncovered by construction and the rule has only ever said
"show him all of it".

The first real client folder showed the producer was sitting in rows this build already
parses. Across the fourteen sheets of their balance sheets and income statements, **every
one of 280 subtotals re-adds exactly** from the rows above it, and 1,910 of the 2,198
parsed rows sit under one. That is the difference between an analyst reading two thousand
figures and reading the three hundred nothing covers.

**What this proves, and what it does not.** It proves addition. Eight wrong rows added
correctly still foot, and a statement whose every total re-adds can still be the wrong
statement, the wrong period or the wrong company. `guards/tieout.py` says the same thing
about its own half: *"Tie-out proves arithmetic, not selection."* Arithmetic cover is
evidence that a figure was not *misread*, which is precisely the failure that a confidence
score cannot see and a person re-keying a scanned page cannot avoid.

Deterministic, like everything on this path. No model, no OCR, no network: the rows arrive
already parsed, and what happens here is addition.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Footing", "FootingReport", "footings_in", "is_a_total"]

LINES = "the lines above it"
SUBTOTALS = "the subtotals above it"
MIXED = "the subtotals and the lines above it"

CENT = 0.005
"""Half a cent: what "it re-adds" means.

Deliberately tight. These values are read from a workbook at full stored precision, not
off a rounded display, so a total that is really the sum of its rows matches to floating
point and a total that is not misses by a real amount. A loose tolerance here would buy a
few more covered rows and sell the only thing the cover is worth - that a misread figure
shows up as a total that stopped adding up. On the real statements every one of the 280
subtotals re-adds inside half a cent.
"""

RELATIVE = 1e-9
"""Room for float64 to be itself when adding forty figures of seven digits. Not a
materiality threshold and not to be turned into one: at a million it is a hundredth of a
cent."""


def is_a_total(label: str) -> bool:
    """Does this row's label announce itself as a total?

    Only what the document says. A row is a total because the statement calls it one -
    `Total Cash`, `TOTAL ASSETS` - and not because its value happens to equal the sum of
    the rows above it, which on a short statement happens by accident.

    `Gross Profit` and `Net Income` are deliberately not totals here, though a P&L derives
    both. They are **subtractions** - revenue less cost of sales, pre-tax income less tax -
    and this reader adds. Counting them cost more than it bought when tried: on the real
    income statement `Gross Profit` was reported uncovered, which is true and useless, and
    on the balance sheet `Net Income (Loss) Y-T-D` sits inside equity as an ordinary line,
    so calling it a total consumed the rows above it and broke `Total Stockholder's Equity`
    underneath. A reader that claims less and breaks nothing is worth more than one that
    reaches for every derived figure.
    """
    first = (label or "").strip().lower()
    return first.startswith(("total", "subtotal"))


@dataclass(frozen=True)
class Footing:
    """One total, and the run of rows that re-adds to it."""

    label: str
    value: float
    ordinals: tuple[int, ...]
    """The rows it re-adds from, in document order. Empty when nothing did."""
    how: str = ""
    """`LINES`, `SUBTOTALS`, or empty when uncovered."""
    delta: float | None = None
    """For an uncovered total: the nearest miss, stated so a person can see whether it is
    a rounding difference or a missing row. None when nothing above it could be tried."""

    @property
    def covered(self) -> bool:
        return bool(self.ordinals)


@dataclass(frozen=True)
class FootingReport:
    footings: tuple[Footing, ...] = ()
    covered_ordinals: frozenset[int] = field(default_factory=frozenset)
    """Every row that sits under a total that re-adds."""
    rows: int = 0

    @property
    def totals(self) -> int:
        return len(self.footings)

    @property
    def uncovered(self) -> tuple[Footing, ...]:
        return tuple(f for f in self.footings if not f.covered)

    @property
    def foots(self) -> bool:
        """Did every total this statement declares re-add?

        The question an analyst asks of a client's statement before anything else, and one
        nothing in this build could answer until P99.
        """
        return bool(self.footings) and not self.uncovered

    def as_line(self) -> str:
        if not self.footings:
            return "no totals to check"
        if self.foots:
            return (
                f"all {self.totals} total(s) re-add; "
                f"{len(self.covered_ordinals)} of {self.rows} rows are covered by one"
            )
        worst = ", ".join(
            f"{f.label} (out by {f.delta:,.2f})" if f.delta is not None else f.label
            for f in self.uncovered[:3]
        )
        return (
            f"{self.totals - len(self.uncovered)} of {self.totals} total(s) re-add; "
            f"{len(self.uncovered)} did not: {worst}"
            + (", and others" if len(self.uncovered) > 3 else "")
        )


def _matching_tail(
    candidates: Sequence[Any], target: float, *, least: int = 1
) -> tuple[Any, ...] | tuple[float | None, None]:
    """The longest contiguous tail of `candidates` summing to `target`.

    A tail rather than any subset, because that is how a statement is laid out: a total
    sums a run of rows ending just above it. Subsets would find a combination for almost
    any target on a long enough statement, which is how an algorithm produces a number that
    is right about nothing.

    Longest first, so `Total Current Assets` takes all three subtotals above it rather than
    stopping at whichever shorter run happens to match.
    """
    nearest: float | None = None
    for start in range(len(candidates) - least + 1):
        run = tuple(candidates[start:])
        if not run:
            continue
        total = sum(r.value for r in run)
        gap = abs(total - target)
        if gap <= max(CENT, abs(target) * RELATIVE):
            return run
        if nearest is None or gap < abs(nearest):
            nearest = total - target
    return (nearest, None)


def _shape(run: Sequence[Any]) -> str:
    """Which of the three a total turned out to be. Kept because it is what a reader checks
    when a footing looks wrong: a total of subtotals that should have been a total of lines
    is a statement laid out differently from how it reads."""
    totals = sum(1 for r in run if is_a_total((getattr(r, "label", "") or "").strip()))
    if totals == 0:
        return LINES
    if totals == len(run):
        return SUBTOTALS
    return MIXED


def footings_in(rows: Sequence[Any]) -> FootingReport:
    """Walk a block of parsed rows once, in order, pairing each total with its run.

    Two shapes, tried in that order, because that is the order a statement nests them:

    * a total of **the lines above it** - `Total Cash` over eleven cash accounts;
    * a total of **the subtotals above it** - `Total Current Assets` over the three totals
      that precede it, `TOTAL ASSETS` over those.

    A total that matches neither is reported uncovered with the nearest miss. It is never
    attached to the closest thing that nearly fits: the whole value of the cover is that it
    is arithmetic, and a total that is out by nine dollars is a fact about the statement
    that somebody needs to see.
    """
    footings: list[Footing] = []
    covered: set[int] = set()

    # What stands above the next total: the rows it could be a total of. A loose row stands
    # for itself; a run that has already been totalled stands as its own total, so the next
    # total up adds the subtotal once rather than adding its parts again.
    #
    # One list rather than two. The old reader kept leaves and subtotals apart and tried
    # each in turn, which reads a statement that nests cleanly and no other: a real balance
    # sheet's grand total is `Total current assets` **and** the seven non-current rows after
    # it, and neither list alone holds that. Over the lines it double-counted the subtotal
    # and missed by exactly the subtotal; over the subtotals it had one and needed two.
    standing: list[Any] = []

    for row in rows:
        value = getattr(row, "value", None)
        if value is None:
            continue
        label = (getattr(row, "label", "") or "").strip()
        if not is_a_total(label):
            standing.append(row)
            continue

        found = _matching_tail(standing, value)
        # One subtotal equal to a later total is a figure carried down, not a sum of it.
        # The old reader refused that by requiring two subtotals; with one list the same
        # rule is said directly, and it matters because calling it a footing would cover
        # the subtotal's own rows a second time and claim evidence twice.
        if (
            isinstance(found, tuple)
            and len(found) == 1
            and is_a_total((getattr(found[0], "label", "") or "").strip())
        ):
            footings.append(Footing(label, value, (), "", 0.0))
            standing = []
            continue
        if isinstance(found, tuple) and len(found) == 2 and found[1] is None:
            footings.append(Footing(label, value, (), "", found[0]))
            standing = []
            continue

        ordinals = tuple(getattr(r, "ordinal", i) for i, r in enumerate(found))
        footings.append(Footing(label, value, ordinals, _shape(found)))
        covered.update(ordinals)
        # The run it summed is now spoken for, and this total speaks for it.
        standing = standing[: len(standing) - len(found)] + [row]

    return FootingReport(
        footings=tuple(footings),
        covered_ordinals=frozenset(covered),
        rows=sum(1 for r in rows if getattr(r, "value", None) is not None),
    )


# ------------------------------------------------------- and the check a person makes first


ASSETS = "total assets"
BOTH_SIDES = "total liabilities"
EQUITY = "equity"


@dataclass(frozen=True)
class TwoSides:
    """Whether a balance sheet balances.

    Footing proves that each side adds up. It cannot prove the two sides agree, because
    they are different runs of rows and a total only ever sums what stands above it - on a
    real filing the assets total and the line that totals the other side are not even in the
    same block, since the reader starts a new one at every heading.

    This is the check an analyst makes before any other, and the statement states both
    numbers itself, so nothing here infers anything: it reads the two labels the statement
    wrote and compares the two figures it printed under them.
    """

    assets: float | None = None
    liabilities_and_equity: float | None = None

    @property
    def stated(self) -> bool:
        """Both sides are on the statement. A balance sheet states both; an income
        statement states neither, and saying nothing about one is the right answer."""
        return self.assets is not None and self.liabilities_and_equity is not None

    @property
    def balances(self) -> bool | None:
        """`None` where the statement does not state both sides - which is not a failure
        and must not read as one."""
        if not self.stated:
            return None
        assert self.assets is not None and self.liabilities_and_equity is not None
        gap = abs(self.assets - self.liabilities_and_equity)
        return gap <= max(CENT, abs(self.assets) * RELATIVE)

    @property
    def out_by(self) -> float | None:
        if not self.stated or self.balances:
            return None
        assert self.assets is not None and self.liabilities_and_equity is not None
        return self.assets - self.liabilities_and_equity

    def as_line(self) -> str:
        if not self.stated:
            return ""
        if self.balances:
            return f"the two sides agree at {self.assets:,.2f}"
        return (
            f"the two sides do not agree: assets {self.assets:,.2f} against "
            f"{self.liabilities_and_equity:,.2f}, out by {self.out_by:,.2f}"
        )


def two_sides(rows: Sequence[Any]) -> TwoSides:
    """The assets total and the total of the other side, by the names the statement uses.

    `Total liabilities` on its own is not the other side - it is one part of it - so the
    label has to name the equity as well. On the real filing the line reads `Total
    liabilities, redeemable non-controlling interest and stockholders' equity`, and on a
    plainer one `Total liabilities and stockholders' equity`; both say liabilities and say
    equity, and a line that says only the first is a subtotal of one side.

    The assets side is matched **exactly** rather than by prefix, because a statement writes
    `Total assets held for sale` too, and that is a line inside the assets rather than the
    sum of them. Taking the first label that began with the words would compare the wrong
    figure and report a balance sheet as out by nearly all of itself.
    """
    assets: float | None = None
    other: float | None = None
    for row in rows:
        value = getattr(row, "value", None)
        if value is None:
            continue
        label = (getattr(row, "label", "") or "").strip().lower()
        if label.strip(" :.") == ASSETS and assets is None:
            assets = value
        elif label.startswith(BOTH_SIDES) and EQUITY in label and other is None:
            other = value
    return TwoSides(assets=assets, liabilities_and_equity=other)
