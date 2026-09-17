"""P40: what the second interview (2026-09-17-1) changed in the build.

Three corrections, each to something built on an assumption the analyst's answers overturned:
the one-time test for an add-back, the pilot recipe's dependencies, and the draft methodology.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graph.compile import PlanContext, compile_recipe
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver
from harness.procedures.ebitda_normalization import (
    CONFIRM_WITH_MANAGEMENT,
    one_time_doubts,
)

ROOT = Path(__file__).resolve().parents[2]
FIVE = ("FY21", "FY22", "FY23", "FY24", "FY25")

# ------------------------------------------------------------ the one-time test


@pytest.mark.parametrize(
    ("present", "doubt"),
    [
        (("FY25",), None),
        (("FY24", "FY25"), None),
        (("FY22", "FY24"), None),
        (("FY21",), "earliest period"),
        (("FY21", "FY23"), "earliest period"),
        (("FY23", "FY24", "FY25"), "3 of 5 periods"),
        (FIVE, "every period"),
    ],
)
def test_one_time_means_one_or_two_periods_and_not_the_years_before(
    present: tuple[str, ...], doubt: str | None
) -> None:
    doubts = one_time_doubts(FIVE, present)
    assert doubts[-1] == CONFIRM_WITH_MANAGEMENT, "management confirms every one-time item"
    if doubt is None:
        assert doubts == [CONFIRM_WITH_MANAGEMENT], "passes the test: only the confirmation"
    else:
        assert len(doubts) == 2 and doubt in doubts[0], "fails the test: goes to a person"


def test_a_single_period_table_cannot_show_an_earlier_year_but_is_not_doubted_for_it() -> None:
    """With one period there is no 'before' to be absent from; the item is still confirmed."""
    assert one_time_doubts(("FY25",), ("FY25",)) == [
        "present in every period; probably not non-recurring",
        CONFIRM_WITH_MANAGEMENT,
    ]


# ------------------------------------------------------------ the pilot's order


def test_the_wacc_waits_for_the_comps_and_the_dcf_waits_for_both() -> None:
    """Version 2 put gpc and wacc side by side (2026-09-17-1); version 3 corrects it
    (2026-09-17-2): beta is the comps' median unlevered beta, so the rate waits for the set."""
    recipe = load_recipe("mature-company-valuation")
    assert recipe.version == 3, "a changed workflow is a new version"
    for scope in ("valuation/non-esop/repeat", "valuation/non-esop/non-repeat"):
        plan = compile_recipe(
            recipe,
            PlanContext(
                engagement_id="PILOT-2",
                scope=ScopeResolver().resolve(scope),
                taxonomy_version="coa-taxonomy@1.0.0",
                precedent_snapshot="snap-pilot",
            ),
        )
        level = {step: n for n, steps in enumerate(plan.levels) for step in steps}
        assert level["wacc"] > level["gpc"], "beta comes from the comp set"
        assert level["dcf"] > max(level["gpc"], level["wacc"], level["ebitda"])


# --------------------------------------------------------- the draft methodology


def test_the_methodology_says_what_the_analyst_said() -> None:
    body = (ROOT / "foundations/valuation/non-esop/_segment/how-we-work.md").read_text("utf-8")
    assert "adjusted for what the client says" not in body, "the corrected claim is gone"
    assert "used unchanged" in body and "interest expense" in body
    assert "not weighted" in body
    assert "one or two periods" in body
