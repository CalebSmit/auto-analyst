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
    leaves: list[Any] = []
    subtotals: list[Any] = []

    for row in rows:
        value = getattr(row, "value", None)
        if value is None:
            continue
        label = (getattr(row, "label", "") or "").strip()
        if not is_a_total(label):
            leaves.append(row)
            continue

        found = _matching_tail(leaves, value)
        how = LINES
        if isinstance(found, tuple) and len(found) == 2 and found[1] is None:
            near_lines = found[0]
            # Two or more, because one subtotal equalling a later total is a carried figure
            # rather than a sum, and calling that a footing would cover its rows twice.
            found = _matching_tail(subtotals, value, least=2)
            how = SUBTOTALS
            if isinstance(found, tuple) and len(found) == 2 and found[1] is None:
                nearest = found[0] if found[0] is not None else near_lines
                footings.append(Footing(label, value, (), "", nearest))
                leaves = []
                continue
            subtotals = subtotals[: len(subtotals) - len(found)]

        ordinals = tuple(getattr(r, "ordinal", i) for i, r in enumerate(found))
        footings.append(Footing(label, value, ordinals, how))
        covered.update(ordinals)
        subtotals.append(row)
        leaves = []

    return FootingReport(
        footings=tuple(footings),
        covered_ordinals=frozenset(covered),
        rows=sum(1 for r in rows if getattr(r, "value", None) is not None),
    )
