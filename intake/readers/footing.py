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

__all__ = [
    "CashRollForward",
    "Footing",
    "FootingReport",
    "cash_roll_forward",
    "footings_in",
    "is_a_total",
    "rolls_on",
]

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

# ------------------------------------------------------ the direction a label states
#
# Every tie-out in this module passes a statement whose every sign is inverted. Rows of
# -12,000 and -3,000 under a total of -15,000 re-add, and so do the same three flipped
# positive; two sides that agree at 521,728 agree at -521,728; cash rolls forward to a
# negative balance as readily as to a positive one. A cash flow investing or financing
# section is all-negative, so a column read with every sign flipped foots exactly - and
# arithmetic cover is the evidence that decides whether a person looks at a figure at all.
#
# What catches it is not arithmetic but a statement about the table: `Total assets` is not
# negative, and `Net cash used in financing activities` is not positive. The whole of the
# rule is the line between a label that cannot honestly go either way and one that can,
# and the second kind says nothing here. Calibrated over every row of the three public
# filings - 2,373 of them, audited and read right - where the phrases kept read 69 rows and
# contradict none, and where every phrase rejected was rejected on a row that fired:
#
# * an expense or income line (`Interest expense`, `Depreciation`, `Cost of sales`) - 3D's
#   income statement prints operating expenses positive and non-operating ones negative on
#   the same page, so sign is a presentation convention and the label carries no direction;
# * `Proceeds from`, `Repayments of`, `Payments for`, `Purchases of`, `Dividends paid` -
#   a proceed inside an investments roll-forward is a deduction and prints negative, and
#   EDGAR's detail sheets store every payment as an unsigned magnitude;
# * `Total equity`, which a deficit makes negative, and `Cash at end of period`, which an
#   overdraft does - facts about the business, which this must never state;
# * `Net cash provided by`, `Net increase in`, `Net income`, `Net loss` - accounting
#   software writes these as fixed labels whatever the sign (`Net Income -96,083`), so a
#   positive reading has to be right for them and a negative one cannot be called wrong;
# * `Gross profit`, which can be negative, and any share count, which feeds no footing.
#
# `used in` and `net decrease in` survive because no package writes them as a fixed label:
# a fixed label has to be right for the positive case, and those are only ever written
# when the figure went that way.

NOT_NEGATIVE = (
    "total assets",
    "total current assets",
    "total liabilities",
    "total current liabilities",
)
"""Grand and section totals of a balance sheet, matched whole. `Total liabilities and
stockholders' equity` is taken by prefix below, because it equals total assets."""

_CHANGE_COLUMN = ("change", "increase", "decrease", "variance", "difference", "%", "percent", "vs")
"""Words in a column heading that make every figure under it a movement, where a sign
says which way something moved and contradicts nothing. The known limit is a change column
with no heading at all - 55 of the 3D filing's 179 columns are unnamed - which this cannot
see and on which an MD&A table will one day fire."""

_TREASURY_ACTIVITY = ("purchas", "repurchas", "issu", "retire", "acqui", "sold", "sale")
"""`Treasury stock, at cost` is a balance and is not positive. `Treasury stock purchases` is
an activity line on a statement of equity, and in a shares column it is a count."""


def states_a_direction(label: str) -> str | None:
    """The direction a label states, or `None` for every label that could go either way.

    Returns `"not negative"` or `"not positive"`. A label carrying both directions -
    `Net cash provided by (used in) investing activities`, `Net increase (decrease) in
    cash` - states nothing, and that is most of the section lines on an audited cash flow
    statement; this rule is honest about reading few rows rather than wrong about many.
    """
    said = " ".join((label or "").split()).lower().strip(" :.")
    if said in NOT_NEGATIVE or (said.startswith("total liabilities") and "equity" in said):
        return "not negative"
    if said.startswith(("net cash used in", "net cash used for")) and "provided" not in said:
        return "not positive"
    if said.startswith("net decrease in") and "increase" not in said:
        return "not positive"
    if "accumulated deficit" in said and "retained earnings" not in said:
        return "not positive"
    if said.startswith(("treasury stock", "treasury shares")) and not any(
        word in said for word in _TREASURY_ACTIVITY
    ):
        return "not positive"
    if "accumulated other comprehensive loss" in said and "income" not in said:
        return "not positive"
    return None


def is_a_change_column(heading: str) -> bool:
    """Whether a column's heading makes its figures movements rather than balances."""
    words = (heading or "").lower().replace("%", " % ").split()
    return any(word.strip("().,") in _CHANGE_COLUMN for word in words)


@dataclass(frozen=True)
class Contradiction:
    """A row whose sign contradicts the direction its own label states."""

    ordinal: int
    label: str
    value: float
    states: str
    """What the label says: `"not negative"` or `"not positive"`."""

    def as_line(self) -> str:
        return f"{self.label} is {self.value:,.2f}, and the label says it is {self.states}"


def sign_contradictions(rows: Sequence[Any], heading: str = "") -> tuple[Contradiction, ...]:
    """Every row whose sign contradicts its own label. A statement about the table, never
    about the business, and silent on a column headed as a change."""
    if is_a_change_column(heading):
        return ()
    out: list[Contradiction] = []
    for index, row in enumerate(rows):
        value = getattr(row, "value", None)
        if value is None:
            continue
        # Zero needs no case of its own: it is neither negative nor positive, so the two
        # comparisons below pass it. A branch for it was here and the revert harness showed
        # it could not be made to matter.
        states = states_a_direction(getattr(row, "label", "") or "")
        if states == "not negative" and value < 0 or states == "not positive" and value > 0:
            out.append(
                Contradiction(
                    ordinal=getattr(row, "ordinal", index),
                    label=(getattr(row, "label", "") or "").strip(),
                    value=float(value),
                    states=states,
                )
            )
    return tuple(out)


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
    """Every row that sits under a total that re-adds - and **none at all** where a row in
    the block contradicts the direction its label states. A proof that passes a wholly
    negated column proves nothing about any row of it, so one contradiction withdraws the
    block's cover rather than one row's: on a flipped column the rows carrying no direction
    word look right, and the one row that does is the only thing that saw it."""
    rows: int = 0
    contradictions: tuple[Contradiction, ...] = ()
    """Rows whose sign contradicts their own label. The footings above are still facts -
    the arithmetic did re-add - and are kept; what they no longer are is cover."""

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
        if self.contradictions:
            said = "; ".join(c.as_line() for c in self.contradictions[:3])
            return (
                f"{len(self.contradictions)} row(s) contradict the direction the label "
                f"states: {said}"
                + (", and others" if len(self.contradictions) > 3 else "")
                + "; no row is covered by a total, whatever re-adds"
            )
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


def footings_in(rows: Sequence[Any], heading: str = "") -> FootingReport:
    """Walk a block of parsed rows once, in order, pairing each total with its run.

    `heading` is what the document wrote above this column, if anything, and is only used
    to keep the sign check quiet on a column of changes.

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

    contradicted = sign_contradictions(rows, heading)
    return FootingReport(
        footings=tuple(footings),
        covered_ordinals=frozenset() if contradicted else frozenset(covered),
        rows=sum(1 for r in rows if getattr(r, "value", None) is not None),
        contradictions=contradicted,
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

# ------------------------------------------- and the third tie-out, which is about cash


BEGINS = ("at the beginning", "beginning of")
ENDS = ("at the end", "end of period", "end of year", "end of the")
CHANGES = ("net increase", "net decrease", "net change")
"""The three lines a cash flow statement states, by the words it states them in.

Matched on a phrase rather than a prefix, because every one of these sits at the end of a
long label: `Cash, cash equivalents and restricted cash at the beginning of the period`. The
label is also the reason the balance-sheet comparison is not made - see `CashRollForward`.
"""


@dataclass(frozen=True)
class CashRollForward:
    """Whether a statement's cash rolls forward: beginning plus the change is the ending.

    The third tie-out a reviewer makes, after footing and after the two sides of the balance
    sheet, and the one that catches a transposed figure in the middle of a cash flow
    statement - where every subtotal can foot perfectly and the statement still not work,
    because the ending cash is stated rather than derived.

    Pure arithmetic over three figures the statement prints itself. Nothing is inferred and
    nothing is compared across statements.

    **Why it does not reach for the balance sheet.** The obvious fourth check is that this
    ending cash equals the balance sheet's cash line, and on the filing this build measures
    against it would be **wrong**: the balance sheet says 95,635 and the cash flow statement
    says 97,100, because the cash flow line reads *cash, cash equivalents **and restricted
    cash***. The difference is the restricted cash, the statement is correct, and a check
    comparing the two would report a discrepancy of 1,465 on a document with nothing wrong
    with it. A check whose findings are mostly not findings teaches a reader to skip the
    section it is in, so that one is not made - and this comment is here so that the next
    person to think of it finds the figures rather than the idea.
    """

    began: float | None = None
    changed: float | None = None
    ended: float | None = None

    @property
    def stated(self) -> bool:
        """All three are on the statement. Two of them is a statement this says nothing
        about, which is most statements - an income statement states none."""
        return None not in (self.began, self.changed, self.ended)

    @property
    def rolls_forward(self) -> bool | None:
        """`None` where the statement does not state all three, which is not a failure and
        must not read as one."""
        if not self.stated:
            return None
        assert self.began is not None and self.changed is not None and self.ended is not None
        gap = abs(self.began + self.changed - self.ended)
        return gap <= max(CENT, abs(self.ended) * RELATIVE)

    @property
    def out_by(self) -> float | None:
        if not self.stated or self.rolls_forward:
            return None
        assert self.began is not None and self.changed is not None and self.ended is not None
        return self.began + self.changed - self.ended

    def as_line(self) -> str:
        if not self.stated:
            return ""
        if self.rolls_forward:
            return f"the cash rolls forward to {self.ended:,.2f}"
        assert self.began is not None and self.changed is not None
        return (
            f"the cash does not roll forward: {self.began:,.2f} and {self.changed:,.2f} "
            f"make {self.began + self.changed:,.2f} against {self.ended:,.2f} stated, "
            f"out by {self.out_by:,.2f}"
        )


def cash_roll_forward(rows: Sequence[Any]) -> CashRollForward:
    """The beginning, the change and the ending, by the words the statement uses.

    The **first** of each is taken. A cash flow statement states its cash line twice on some
    filings - once in the roll-forward and once in a reconciliation of restricted cash
    beneath it - and the second is a different figure for a different purpose.
    """
    began: float | None = None
    changed: float | None = None
    ended: float | None = None
    for row in rows:
        value = getattr(row, "value", None)
        if value is None:
            continue
        label = (getattr(row, "label", "") or "").strip().lower()
        # Anywhere in the label rather than at the front of it. Every one of these sits at
        # the *end* of a long one - `Cash, cash equivalents and restricted cash at the
        # beginning of the period` - so a prefix match finds none of them.
        if began is None and any(phrase in label for phrase in BEGINS):
            began = value
        elif ended is None and any(phrase in label for phrase in ENDS):
            ended = value
        elif changed is None and any(phrase in label for phrase in CHANGES):
            changed = value
    return CashRollForward(began=began, changed=changed, ended=ended)


def rolls_on(columns: Sequence[CashRollForward]) -> tuple[str, ...]:
    """Where one column's beginning is not the column before's ending.

    A comparative statement prints three years side by side and each year's closing cash is
    the next year's opening - so the columns are a chain, and a chain is checkable without
    knowing which column is which year. Said as sentences rather than as a verdict, because
    a statement whose columns are not years (a segment note, a currency split) would report
    a difference that means nothing, and the order of the columns is the page's rather than
    this reader's.

    Empty where fewer than two columns state a roll-forward, which is the honest answer and
    not a pass. That falls out of the pairing rather than being guarded for: with one column
    there is no pair, so the loop below runs no times. An `if len(stated) < 2: return ()`
    was here and a revert harness showed it changing no answer in any case - the state this
    build removes a check in rather than keeping it as reassurance, because a line that
    never runs is a line nobody can be sure about.
    """
    stated = [c for c in columns if c.stated]
    out: list[str] = []
    for older, newer in zip(stated[1:], stated[:-1], strict=False):
        assert older.ended is not None and newer.began is not None
        gap = abs(older.ended - newer.began)
        if gap > max(CENT, abs(newer.began) * RELATIVE):
            out.append(
                f"one column opens at {newer.began:,.2f} where the one beside it closes "
                f"at {older.ended:,.2f}, a difference of {older.ended - newer.began:,.2f}"
            )
    return tuple(out)
