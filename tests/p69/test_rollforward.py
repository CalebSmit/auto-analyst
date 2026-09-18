"""P69: last year's model, rolled forward.

Three quarters of engagements are repeat clients. For those the analyst copies the previous
year's tabs into the new workbook, shifts the years across, and fills in the new period -
the same move for the model, the WS grouping, the Input tab and the request list.

The rules were given precisely and this pins each one:

* the historical block is **ten columns wide and does not grow** - 2016 falls off as 2026
  arrives;
* only the most recent five are usually filled, so a short history must not lose a year it
  never had to;
* on the Input tab **only two fields change**, the valuation date and the latest fiscal
  year end, "usually just one year later";
* the WS **line items are carried forward, not re-decided**.

`test_a_short_history_grows_before_it_starts_dropping` is the one that stops the fix being
"always drop the first element", and
`test_a_mismatch_is_reported_from_both_sides_and_resolved_from_neither` is the one that
stops this module quietly deciding something that belongs to a person.
"""

from __future__ import annotations

from datetime import date

import pytest

from tools.rollforward import (
    WINDOW,
    YearWindow,
    carry_line_items,
    roll_dates,
    roll_window,
)

FULL = YearWindow(tuple(range(2016, 2026)))


# ------------------------------------------------------------------ the year window


def test_a_full_window_drops_its_oldest_year() -> None:
    rolled = roll_window(FULL, 2026)
    assert rolled.dropped == 2016
    assert rolled.added == 2026
    assert rolled.window.years[0] == 2017
    assert rolled.window.years[-1] == 2026


def test_the_window_does_not_grow() -> None:
    """Asked directly: does it grow by one column? It does not."""
    assert len(roll_window(FULL, 2026).window.years) == WINDOW


def test_a_short_history_grows_before_it_starts_dropping() -> None:
    """Five years filled is the normal state, because the request list asks for five fiscal
    years. Such a client must not lose 2021 to make room for 2026."""
    five = YearWindow((2021, 2022, 2023, 2024, 2025))
    rolled = roll_window(five, 2026)
    assert rolled.dropped is None
    assert rolled.window.years == (2021, 2022, 2023, 2024, 2025, 2026)


def test_a_window_fills_to_ten_and_only_then_drops() -> None:
    window = YearWindow((2021,))
    dropped: list[int | None] = []
    for year in range(2022, 2033):
        rolled = roll_window(window, year)
        window, _ = rolled.window, dropped.append(rolled.dropped)
    assert dropped[:9] == [None] * 9, dropped
    assert dropped[9] == 2021
    assert len(window.years) == WINDOW


def test_rolling_backwards_is_refused() -> None:
    """Re-stating a year already in the window is a correction, and a correction that
    arrived as a roll would silently duplicate a column."""
    with pytest.raises(ValueError, match="does not follow"):
        roll_window(FULL, 2025)


def test_a_window_is_ordered_and_unique() -> None:
    with pytest.raises(ValueError, match="oldest first"):
        YearWindow((2025, 2024))
    with pytest.raises(ValueError, match="twice"):
        YearWindow((2024, 2024))
    with pytest.raises(ValueError, match="at most"):
        YearWindow(tuple(range(2010, 2026)))


def test_an_empty_window_takes_its_first_year() -> None:
    assert roll_window(YearWindow(()), 2026).window.years == (2026,)


# ------------------------------------------------------------------ the two dates


def test_the_two_input_dates_roll_a_year() -> None:
    valuation, fye = roll_dates(date(2025, 12, 31), date(2025, 12, 31))
    assert valuation == date(2026, 12, 31)
    assert fye == date(2026, 12, 31)


def test_a_leap_day_lands_on_a_real_date() -> None:
    """A fiscal year ending on the last day of February still ends on the last day of
    February. Raising here would stop a roll-forward on an arbitrary client."""
    assert roll_dates(date(2024, 2, 29)) == (date(2025, 2, 28),)


def test_a_non_leap_february_end_is_unchanged_in_shape() -> None:
    assert roll_dates(date(2025, 2, 28)) == (date(2026, 2, 28),)


def test_a_leap_day_rolled_four_years_is_a_leap_day_again() -> None:
    assert roll_dates(date(2024, 2, 29), years=4) == (date(2028, 2, 29),)


def test_a_mid_year_end_rolls_cleanly() -> None:
    assert roll_dates(date(2025, 6, 30)) == (date(2026, 6, 30),)


# ------------------------------------------------------------------ the line items


def test_last_years_line_items_are_this_years_schema() -> None:
    carried = carry_line_items(
        ["Rent", "Insurance", "Repairs"],
        {"Rent": 120.0, "Insurance": 44.0, "Repairs": 9.0},
    )
    assert carried.matched == (("Rent", 120.0), ("Insurance", 44.0), ("Repairs", 9.0))
    assert not carried.needs_a_person


def test_matching_ignores_case_and_whitespace_and_nothing_else() -> None:
    carried = carry_line_items(["Office  Rent"], {"office rent": 1.0})
    assert carried.matched == (("Office  Rent", 1.0),)

    near = carry_line_items(["Rent"], {"Rent expense": 1.0})
    assert near.matched == ()
    assert near.missing == ("Rent",)
    assert near.unclaimed == ("Rent expense",)


def test_a_mismatch_is_reported_from_both_sides_and_resolved_from_neither() -> None:
    """The analyst: work out whether the client actually changed it, or whether we just
    grouped it differently last year. This module must hand over both sides and answer
    neither - a wrong guess here puts last year's rent against this year's insurance and
    a footed total hides it."""
    carried = carry_line_items(["Rent", "Repairs"], {"Rent": 1.0, "Maintenance": 2.0})
    assert carried.matched == (("Rent", 1.0),)
    assert carried.missing == ("Repairs",)
    assert carried.unclaimed == ("Maintenance",)
    assert carried.needs_a_person


def test_the_question_asks_rather_than_answers() -> None:
    carried = carry_line_items(["Repairs"], {"Maintenance": 2.0})
    asked = carried.question
    assert "Did the client change their accounts" in asked
    assert "did we group them differently last year" in asked
    for decided in ("renamed", "is the same as", "matched to"):
        assert decided not in asked


def test_nothing_matching_means_everything_is_reported() -> None:
    carried = carry_line_items(["A", "B"], {"C": 1.0})
    assert carried.matched == ()
    assert set(carried.missing) == {"A", "B"}
    assert carried.unclaimed == ("C",)


def test_no_prior_items_leaves_every_row_unclaimed() -> None:
    """A new client, where there is no last year to carry. Everything is unclaimed, which
    is the honest description of a first engagement rather than an error."""
    carried = carry_line_items([], {"Rent": 1.0})
    assert carried.unclaimed == ("Rent",)
    assert carried.missing == ()
