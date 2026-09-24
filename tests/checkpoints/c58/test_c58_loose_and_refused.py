"""C58 - what is read loosely, and what is still refused.

P97 widened what counts as finding a name: whitespace inside a declared identifier now
matches whatever the page put there, including nothing, because OCR reads a scan at 0.97
confidence and still returns `BOARDMEETINGMINUTES`. P98 widened what counts as knowing a
period: a fiscal year end is now derived from ends that recur on a month end across years,
and a page's bare year columns are reported instead of being called "no period cue".

Two loosenings in one block is the shape that lets a wrong answer through while every phase
test passes, because each phase tests the thing it widened and neither tests the other's
edges. So this asks the questions that sit between them.

1. **Masking got looser; the numbers did not move.** The masker and the period detector
   read the same text on the same path - mask, then send - and a masker that started eating
   period labels or figures would break timing normalisation somewhere else entirely, with
   nothing here to say why.
2. **A derivation still carries its evidence.** P98's whole defence is that deriving from
   dates in hand is not assuming; that only holds while the derived value can say what it
   was read off.
3. **P38's rule survived both.** A projected year must not become a historical one, and
   both phases touched code that could let it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intake.readers.classify import Evidence, classify
from intake.readers.periods import detect_periods, headings_in
from privacy.mask import Identifier, Masker
from privacy.payload_scan import IdentifierList, PayloadScan, loosely

ROOT = Path(__file__).resolve().parents[3]

#: A page as a scanner returns it: right figures, lost spaces. The names are invented - the
#: real document's were redacted before it reached this machine - and the shape is not.
A_SCANNED_PAGE = (
    "2023 BOARDMEETINGMINUTES January17,2023\n"
    "In attendancewere thetwoOfficersof theCompany:JohnSmith(ChairmanoftheBoard)\n"
    "Consolidated Balance Sheet as of December 31, 2023\n"
    "Total assets 11,000,000 Cash 1,250,000\n"
)

THE_YEAR_ENDS = ["2023-02-28", "2024-02-29", "2019-12-31", "2020-12-31",
                 "2021-12-31", "2022-12-31", "2023-12-31"]

A_FORECAST_HEADER = (
    "            2021    2022    2023    2024 Feb YTD    2024 (P)\n"
    "Net Sales Revenue 37,559,559 49,636,182 58,207,473 12,762,523 62,864,071"
)


# ============================================ 1. looser on names, unchanged on numbers


def test_masking_a_scanned_page_leaves_every_period_and_figure_where_it_was(
    masker: Masker,
) -> None:
    """The join between the two phases, on one page. P97 made the masker match across
    missing spaces; if that reached the numbers, the timing detector downstream would start
    reading a masked page and nothing here would connect the two."""
    before = detect_periods(A_SCANNED_PAGE)
    masked = masker.mask(A_SCANNED_PAGE, "ENG-1", [Identifier("PERSON", "John Smith")])
    after = detect_periods(masked.text)

    assert "JohnSmith" not in masked.text, "P97's point: the joined name is masked"
    assert before.period_ends == after.period_ends
    assert before.fiscal_year_end_month == after.fiscal_year_end_month
    for figure in ("11,000,000", "1,250,000"):
        assert figure in masked.text, figure


def test_masking_replaces_the_name_and_not_the_gap_between_two_of_them(
    masker: Masker,
) -> None:
    r"""The failure a regex-join invites, and the reason the join is `\s*` and not `.*`.

    A client name usually appears on a statement more than once - a header and a footer is
    the ordinary case. Join the pieces of an identifier with anything that crosses
    whitespace and the pattern spans from the first occurrence to the last, swallowing
    every figure in between. The first version of this test declared a name that was not in
    the text at all, so it passed under every possible implementation and proved nothing.
    """
    text = (
        "Total Assets Holdings Inc\n"
        "Total assets 11,000,000\n"
        "Cash 1,250,000\n"
        "Prepared for Total Assets Holdings\n"
    )
    masked = masker.mask(text, "ENG-1", [Identifier("CLIENT", "Total Assets Holdings")])
    assert "Total Assets Holdings" not in masked.text, "both occurrences are masked"
    for figure in ("11,000,000", "1,250,000"):
        assert figure in masked.text, f"{figure} was inside the span and got eaten"
    assert "Total assets" in masked.text, "the statement line survived"


def test_the_scan_and_the_masker_still_agree_after_both_phases() -> None:
    """They are two nodes so the check can be tested apart from the thing it checks. What
    they may never do is disagree about what finding a name means - and P97 gave them one
    function so they cannot."""
    identifiers = IdentifierList.of("ENG-1", ["John Smith"])
    assert PayloadScan().check(A_SCANNED_PAGE, identifiers).hits == ("John Smith",)
    assert loosely("John Smith").search(A_SCANNED_PAGE)


# ============================================ 2. a derivation carries its evidence


def test_the_fiscal_year_end_can_say_what_it_was_read_off() -> None:
    """P98's defence in one assertion. A derived value that cannot name its source is a
    default wearing a derivation's clothes, and the blueprint's rule - proved by arithmetic
    or seen - is the same rule one level up."""
    found = detect_periods("\n".join(THE_YEAR_ENDS))
    assert found.fiscal_year_end_month == 12
    why = " ".join(found.cues.get("fiscal_year_end", []))
    assert why, "derived and silent about it"
    for year in ("2019", "2020", "2021", "2022", "2023"):
        assert year in why, year


def test_nothing_derived_is_reported_as_settled_while_something_else_is_open() -> None:
    """`settled` is the single word the rest of the build reads off this. Deriving one more
    field must not turn a page with an unknown scale into one that looks resolved."""
    found = detect_periods("\n".join(THE_YEAR_ENDS))
    assert found.fiscal_year_end_month is not None
    assert not found.settled, "scale and currency are still unstated on that page"
    assert any(a.startswith("scale:") for a in found.ambiguous)


# ============================================ 3. P38 survived both


def test_a_projected_column_is_still_not_a_historical_one() -> None:
    """The rule both phases could have broken from different directions: P98 by dating a
    bare year, P97 by nothing, but the block is where it would go unnoticed."""
    found = detect_periods(A_FORECAST_HEADER)
    assert found.period_ends == (), "a bare year is not a year end, whoever asks"
    flagged = [a for a in found.ambiguous if a.startswith("columns:")]
    assert flagged and "2024" in flagged[0]


def test_a_forecast_file_is_still_classified_as_one() -> None:
    """P96's rule, re-asked because P98 changed what the detector says about the same page.
    Projected years entering the historical table is the error; classification is the first
    of the two gates that stops it and periods are the second."""
    found = classify(
        Evidence("Projections_Redacted.xlsx", first_rows=[A_FORECAST_HEADER])
    )
    assert found.document_type == "forecast"


def test_the_headings_helper_and_the_detector_still_give_the_same_years() -> None:
    """Two readers of one line. `headings_in` names the columns for the reader that binds
    figures to periods; P98's labels are the detector's account of the same thing, and if
    they ever disagreed a figure would land under the wrong year."""
    line = A_FORECAST_HEADER.splitlines()[0]
    assert detect_periods(A_FORECAST_HEADER).period_labels == headings_in(line)


# ============================================ neither module drifted off its path


@pytest.mark.parametrize(
    "module", ["privacy/mask.py", "privacy/payload_scan.py", "intake/readers/periods.py"]
)
def test_none_of_the_changed_modules_reaches_a_model(module: str) -> None:
    """All three are deterministic by design - masking because re-identification may not be
    a model's job, periods because "thousands versus units" is the most expensive silent
    error available here. Both phases edited them; this is the standing check that neither
    reached for help."""
    import ast

    tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
    named: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            named.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            named.add(node.module)
    for forbidden in ("ports.llm", "anthropic", "openai", "harness", "skills", "ports.ocr"):
        assert not any(n == forbidden or n.startswith(forbidden + ".") for n in named), module
