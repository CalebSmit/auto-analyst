"""The repeat client's roll-forward, as deterministic code.

Three quarters of this practice's engagements are repeat clients, and for those the work
starts from last year's model rather than from the documents: copy the tabs across, shift
the years, and fill in the new period. The analyst described the same move four times over
- for the model, the WS grouping, the Input tab and the request list - which makes it one
mechanism, not four features.

This module is its arithmetic half. The Excel half needs the firm's real template and its
named ranges, which are not in hand; none of what is here depends on them.

Nothing in this module decides anything. It rolls a window, rolls two dates, and reports
what did and did not line up. Where a line item does not match, the cause is either that
the client changed their accounts or that the firm grouped them differently last year -
and telling those apart is a person's call, so both sides are handed over rather than
reconciled. `tools/statement_checks.py` takes the same line about what it will not guess.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

__all__ = [
    "WINDOW",
    "Carried",
    "YearWindow",
    "carry_line_items",
    "roll_dates",
    "roll_window",
]

WINDOW = 10
"""How many historical year columns the model holds.

Ten, and it does not grow: the oldest year falls off as a new one arrives. Usually only the
most recent five are filled, because the request list asks the client for five fiscal years
- so an empty column is the normal state of half of them and is never a gap to go hunting
for.
"""


@dataclass(frozen=True)
class YearWindow:
    """The historical year columns, oldest first."""

    years: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.years) > WINDOW:
            raise ValueError(f"a window holds at most {WINDOW} years; got {len(self.years)}")
        if list(self.years) != sorted(self.years):
            raise ValueError("years run oldest first")
        if len(set(self.years)) != len(self.years):
            raise ValueError("a year appears twice in the window")

    @property
    def newest(self) -> int | None:
        return self.years[-1] if self.years else None

    @property
    def is_full(self) -> bool:
        return len(self.years) == WINDOW


@dataclass(frozen=True)
class Rolled:
    """A window after a new year arrives, and what it cost."""

    window: YearWindow
    added: int
    dropped: int | None
    """The year that fell off the front, or None while the window was still filling."""


def roll_window(window: YearWindow, new_year: int) -> Rolled:
    """Put `new_year` on the end, dropping the oldest once the window is full.

    The width is fixed. A window that is not yet ten wide grows to ten first and only then
    starts dropping - which is what happens to a client whose history is shorter than the
    model's capacity, and it must not lose a year it did not have to.
    """
    if window.newest is not None and new_year <= window.newest:
        raise ValueError(
            f"{new_year} does not follow {window.newest}: a roll-forward moves forward, and "
            "re-stating a year already in the window is a correction, not a roll"
        )
    years = (*window.years, new_year)
    dropped: int | None = None
    if len(years) > WINDOW:
        dropped = years[0]
        years = years[1:]
    return Rolled(YearWindow(years), new_year, dropped)


def roll_dates(*dates: date, years: int = 1) -> tuple[date, ...]:
    """The Input tab's dates, a year on.

    On a repeat engagement exactly two fields change - the valuation date and the latest
    fiscal year end - and both are "usually just one year later". Usually, not always: an
    interim valuation moves differently and the template has a whole stub-year block for
    it, so this is offered to a person to confirm rather than applied silently.

    29 February has no counterpart in a common year. It lands on the 28th rather than
    raising, because a fiscal year ending on the last day of February still ends on the
    last day of February.
    """
    rolled = []
    for when in dates:
        year = when.year + years
        last = calendar.monthrange(year, when.month)[1]
        rolled.append(date(year, when.month, min(when.day, last)))
    return tuple(rolled)


@dataclass(frozen=True)
class Carried:
    """Last year's line items, set against this year's rows.

    `matched` is the work that needs no thought. The other two are the whole reason a
    person is asked: a prior label with nothing against it this year, and a row this year
    that answers to no prior label, are the *same event* seen from two sides when the
    client has renamed something - and two different events when they have not.
    """

    matched: tuple[tuple[str, float], ...]
    missing: tuple[str, ...]
    """Prior line items with no row this year."""
    unclaimed: tuple[str, ...]
    """Rows this year that no prior line item accounts for."""

    @property
    def needs_a_person(self) -> bool:
        return bool(self.missing or self.unclaimed)

    @property
    def question(self) -> str:
        """What to put in front of a reviewer. Deliberately does not answer itself."""
        if not self.needs_a_person:
            return ""
        parts = []
        if self.missing:
            parts.append(f"{len(self.missing)} line item(s) from last year have no row this year")
        if self.unclaimed:
            parts.append(
                f"{len(self.unclaimed)} row(s) this year match no line item from last year"
            )
        return (
            f"{' and '.join(parts)}. Did the client change their accounts, or did we group "
            "them differently last year?"
        )


def _key(label: str) -> str:
    return " ".join(label.split()).casefold()


def carry_line_items(
    prior: Sequence[str],
    this_year: Mapping[str, float] | Iterable[tuple[str, float]],
) -> Carried:
    """Last year's line items are this year's schema.

    The analyst copies the previous year's WS tab across, shifts the years, and fills in
    the values for line items that are already set - the labels are carried forward, not
    re-decided. So for a repeat client the prior workbook is the chart of accounts, and the
    firm-wide taxonomy is not the mapping that applies.

    Matching is on the label, insensitive to case and to runs of whitespace, and nothing
    cleverer: a near-match dressed up as a match is the failure mode that would put last
    year's rent against this year's insurance and leave a footed total to hide it.
    """
    rows = dict(this_year)
    seen = {_key(label): label for label in rows}
    matched: list[tuple[str, float]] = []
    missing: list[str] = []
    claimed: set[str] = set()

    for label in prior:
        key = _key(label)
        if key in seen:
            matched.append((label, rows[seen[key]]))
            claimed.add(key)
        else:
            missing.append(label)

    unclaimed = tuple(label for label in rows if _key(label) not in claimed)
    return Carried(tuple(matched), tuple(missing), unclaimed)
