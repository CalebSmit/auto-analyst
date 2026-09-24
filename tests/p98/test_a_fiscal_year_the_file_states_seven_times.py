"""P98 - a fiscal year the file states seven times, and columns it names but does not date.

Two gaps, both found on the first real client folder's workbooks, both on version 1's path.

**The fiscal year end.** The balance-sheet workbook's sheets are named `2019-12-31` through
`2023-12-31` plus `2023-02-28` and `2024-02-29`. The detector read all seven ends correctly
and then reported `fiscal_year_end: not stated`, because its derivation wanted every end in
one month and two of these were February interims. Interim stubs beside the year ends are
the ordinary shape of a valuation's financial statements, not an exception - so the file
said December five times and the tool sent a person to type it in.

**Bare year columns.** The projections tab is headed `2021 | 2022 | 2023 | 2024 Feb YTD |
2024 (P)` and carries no date anywhere, so the detector reported "no period cue". That is
not what the page says: it says which years, and leaves only the calendar open. A forecast
whose periods are unknown cannot be placed in a model, which is version 1's entire job.

The line this phase must not cross is the one `headings_in` already draws: **a derivation
from evidence in hand is not an assumption; a bare year turned into a year end is.** So the
years are reported and `period_ends` stays empty, and the fiscal year end arrives with the
dates it was read off.
"""

from __future__ import annotations

import inspect

import pytest

from intake.readers.periods import (
    YEARS_BEFORE_IT_IS_A_PATTERN,
    PeriodDetection,
    _recurring_year_end,
    detect_periods,
)

#: The sheet names of the real client's consolidated balance sheets, in the order the
#: workbook carries them. Nothing about the client is in them; they are seven dates.
THE_REAL_WORKBOOK = [
    "2023-02-28",
    "2024-02-29",
    "2019-12-31",
    "2020-12-31",
    "2021-12-31",
    "2022-12-31",
    "2023-12-31",
]

#: The real projections tab's header row and one figure row under it.
THE_REAL_FORECAST = (
    "            2021    2022    2023    2024 Feb YTD    2024 (P)\n"
    "Net Sales Revenue 37,559,559 49,636,182 58,207,473 12,762,523 62,864,071"
)


def about(*period_ends: str) -> PeriodDetection:
    return detect_periods("\n".join(period_ends))


# ============================================================ the fiscal year end


def test_the_real_workbook_states_december_and_is_now_read_that_way() -> None:
    found = about(*THE_REAL_WORKBOOK)
    assert found.fiscal_year_end_month == 12
    assert not any(a.startswith("fiscal_year_end") for a in found.ambiguous)


def test_the_derivation_says_what_it_was_read_off() -> None:
    """A derived value that cannot say where it came from is indistinguishable from a
    default, and this module's whole discipline is that difference."""
    why = " ".join(about(*THE_REAL_WORKBOOK).cues["fiscal_year_end"])
    assert "5 period ends" in why
    assert "2019" in why and "2023" in why
    assert "no other month end recurs as often" in why


def test_the_interim_stubs_do_not_get_a_vote() -> None:
    """February appears twice and is not the fiscal year end. If the two interims could
    outvote the five year ends, every comparative statement would set a fiscal calendar
    from whichever stub happened to be attached."""
    assert about(*THE_REAL_WORKBOOK).fiscal_year_end_month == 12


@pytest.mark.parametrize(
    ("why_not", "ends"),
    [
        # Two years is what every comparative statement carries. Calling it a pattern
        # would read a fiscal calendar off the commonest document in the folder.
        ("too few years recur", ["2023-02-28", "2023-12-31", "2024-12-31"]),
        # A tie is refused rather than broken: the cost of a wrong fiscal year end is
        # every period in the engagement mislabelled.
        (
            "two months are equally dominant",
            [
                "2022-06-30", "2023-06-30", "2024-06-30",
                "2022-12-31", "2023-12-31", "2024-12-31",
            ],
        ),
        # A run of mid-month dates beside an interim is something other than a year end,
        # and this path will not guess at what.
        ("the candidates are not month ends", ["2022-12-15", "2023-12-15", "2024-12-15",
                                               "2023-02-28"]),
    ],
)
def test_it_refuses_where_the_answer_would_be_a_guess(why_not: str, ends: list[str]) -> None:
    found = about(*ends)
    assert found.fiscal_year_end_month is None, why_not
    assert "fiscal_year_end: not stated" in found.ambiguous


def test_the_threshold_is_named_and_reasoned_rather_than_a_literal() -> None:
    """Three is a judgement about how many closings make a calendar, and a bare `3` in a
    comparison is how a judgement becomes a magic number nobody can argue with."""
    assert YEARS_BEFORE_IT_IS_A_PATTERN == 3
    said = inspect.getdoc(_recurring_year_end) or ""
    assert "tie is refused" in said


def test_a_clean_annual_set_is_still_read_the_way_it_always_was() -> None:
    """The rule that predates P98 handles the uniform case and keeps it - including the
    52/53-week calendar, which ends *near* a month end rather than on one. The new
    derivation is stricter because it runs on the harder shape, not because month ends
    became a requirement everywhere."""
    assert about("2023-12-31", "2024-12-31").fiscal_year_end_month == 12
    assert about("2022-12-15", "2023-12-15", "2024-12-15").fiscal_year_end_month == 12


def test_a_year_end_the_text_states_outright_still_wins() -> None:
    """Reading beats deriving. A document that says its year end is not a document to
    infer one for."""
    found = detect_periods("Fiscal year end: June 30\n2022-12-31\n2023-12-31\n2024-12-31")
    assert found.fiscal_year_end_month == 6


# ============================================================ periods named, not dated


#: The same header row as `THE_REAL_FORECAST`, in the shape the *workbook* reader hands
#: over: `survey_workbook` collects header cells into a flat list, so one row of six
#: headings arrives as six lines of one heading each. Taken from the real file rather than
#: written out - see `test_the_shape_the_workbook_reader_actually_produces`.
AS_THE_WORKBOOK_READER_EMITS_IT = chr(10).join(
    ["[redacted] Projected Financial Statements",
     "2021", "2022", "2023", "2024 Feb YTD", "2024 (P)", "2025 (P)", "2026 (P)"]
)


def test_the_shape_the_workbook_reader_actually_produces() -> None:
    """The test that was missing, and the reason the first fix did nothing.

    P98's label detection was written against a hand-made single-line header - `2021  2022
    2023` - which is what a *document* reader produces. It passed, and then found nothing at
    all in the real projections tab, because a *workbook* reader emits one cell per line and
    no single line had more than one heading. The fix was tested against a shape that was
    imagined rather than the one in the folder the phase was for.
    """
    found = detect_periods(AS_THE_WORKBOOK_READER_EMITS_IT)
    assert found.period_labels[:3] == ("2021", "2022", "2023")
    assert "2024" in found.period_labels
    assert found.period_ends == (), "still never dated"


def test_prose_that_mentions_years_is_not_a_set_of_columns() -> None:
    """The cost of reading down the lines instead of across one. An annual report discusses
    its own history in sentences, and a rule that could not tell a paragraph from a column
    header would report periods for every narrative document in the folder."""
    prose = (
        "Revenue grew steadily through 2021 and the market recovered." + chr(10)
        + "By 2023 the company had expanded into three further states." + chr(10)
    )
    assert detect_periods(prose).period_labels == ()


def test_the_forecast_tab_reports_the_years_it_covers() -> None:
    found = detect_periods(THE_REAL_FORECAST)
    assert found.period_labels == ("2021", "2022", "2023", "2024", "2024")


def test_a_bare_year_is_never_turned_into_a_year_end() -> None:
    """The line the phase must not cross. `headings_in` refuses this for the same reason
    and P98 does not quietly make an exception for itself."""
    found = detect_periods(THE_REAL_FORECAST)
    assert found.period_ends == ()
    assert not any(label.count("-") for label in found.period_labels)


def test_it_says_what_dating_them_would_need() -> None:
    """Better than "no period cue", which was the old answer and understated the page. The
    engagement profile knows the year end; the document does not."""
    found = detect_periods(THE_REAL_FORECAST)
    named = [a for a in found.ambiguous if a.startswith("period_ends:")]
    assert named, found.ambiguous
    assert "fiscal year end" in named[0]
    assert "2021" in named[0]


def test_two_columns_headed_the_same_year_are_reported_rather_than_merged() -> None:
    """P38's hazard wearing a header. `2024 Feb YTD` and `2024 (P)` are an interim actual
    and a projection; merging them puts projected figures in a historical column, which is
    the error P38 exists to prevent. Reported rather than resolved - which of the two is
    the forecast is a question for somebody who can see the page."""
    found = detect_periods(THE_REAL_FORECAST)
    flagged = [a for a in found.ambiguous if a.startswith("columns:")]
    assert flagged, found.ambiguous
    assert "2024" in flagged[0]
    assert "interim and a projection" in flagged[0]


def test_one_year_on_a_page_is_not_a_set_of_columns() -> None:
    """A single year in a sentence is a date in prose, not a comparative statement. Two is
    the smallest thing that can be a column header."""
    found = detect_periods("Revenue for 2023 was strong.")
    assert found.period_labels == ()
    assert not any(a.startswith("period_ends:") for a in found.ambiguous)


def test_a_dated_document_does_not_get_labels_it_does_not_need() -> None:
    """One fact, one source. `period_labels` exists for pages that name periods without
    dating them; a page carrying both would give the timing skill two answers to the same
    question and no rule for which wins.

    The input matters here. Seven ISO sheet names would pass this whatever the guard did -
    an ISO date is not a bare year, so the filter alone keeps the labels empty and the
    guard is never asked. This page has a real date *and* bare year columns, so the guard
    is the only thing deciding.
    """
    both = (
        "Consolidated Balance Sheet as of December 31, 2023\n"
        "                 2021      2022      2023\n"
        "Total assets  1,000     2,000     3,000"
    )
    found = detect_periods(both)
    assert found.period_ends, "the page states a date and it is still read"
    assert found.period_labels == (), "dated wins; the years are not a second source"
