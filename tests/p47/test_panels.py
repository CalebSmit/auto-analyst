"""P47: a panel shows what it holds, and a figure does not read as more certain than it is.

Two failures of the same kind. A panel cut by the fold looked complete, and a rate printed
without its denominator looked measured: in both cases the screen said less than the record
knew and left the reader to assume the rest.
"""

from __future__ import annotations

import re

import pytest

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.events import EventBus
from ops.run_store import SqlRunStore
from tests.p23.conftest import Clock, clean_run, reviewed_run
from ui.theme import CSS


def scripts(page: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", page, re.S))


# ------------------------------------------------------------------ denominators


def test_the_rates_carry_the_counts_they_were_computed_from(
    store: SqlRunStore, bus: EventBus
) -> None:
    """They were computed on the way to every rate and dropped at the return statement."""
    from ops.analytics import Analytics

    clean_run(store, bus)
    reviewed_run(store, bus, run_id="run_reviewed")
    trends = Analytics(store, clock=Clock()).overview(days=30).trends
    for field in ("routed_items", "decided_items", "tieout_checked_runs"):
        assert field in trends, f"{field} is not reported beside the rate it explains"
        assert isinstance(trends[field], int)
    assert trends["decided_items"] > 0, "a run where somebody decided has a denominator"


def test_no_rate_is_printed_without_what_it_is_out_of() -> None:
    body = scripts(ANALYTICS)
    assert "function rate(value, n, unit)" in body
    for line in re.findall(r"<span class=\"val\">\$\{\{?(pct|rate)\(t\.[\w.]+", body):
        assert line == "rate", "a rate on the trends card is printed without its count"


def test_a_rate_on_too_few_says_so_instead_of_being_coloured() -> None:
    """A tone on a denominator of four is a claim the number cannot support - and a green
    first-pass yield on a single run is the most flattering figure this page could print."""
    body = scripts(ANALYTICS)
    assert "const JUDGEABLE = 10;" in body
    assert "too few to judge" in body
    assert "const judgeable = h.finished >= 10;" in body
    assert "(!judgeable || h.first_pass_yield === null) ? ''" in body


def test_a_week_of_outcomes_says_it_is_a_week() -> None:
    assert "The mix is worth\n         reading once there are a few to compare" in ANALYTICS


# ------------------------------------------------------------------ what a panel hides


def test_a_panel_cut_by_the_fold_shows_it() -> None:
    """Drawn by the browser at whichever edge has something past it: the white pair scrolls
    with the content and covers the shadows at an edge with nothing behind it."""
    body = re.search(r"\.card \.body\{([^}]*)\}", CSS)
    assert body, "the panel body's rule is gone"
    rule = body.group(1)
    assert rule.count("radial-gradient") == 2, "no shadow at the cut edge"
    assert rule.count("no-repeat local") == 2, "nothing covers it when there is nothing to cut"


def test_a_panel_says_how_much_it_holds() -> None:
    for page, ids in ((ACTIVITY, ("n-runs", "n-inbox", "n-alerts")), (SETUP, ("n-roster",))):
        for name in ids:
            assert f'id="{name}"' in page, f"{name} has no count in its title"
    body = scripts(ACTIVITY)
    assert "function count(id, n)" in body
    assert "count('n-runs', runs.length);" in body


def test_an_empty_panel_is_composed_rather_than_top_aligned() -> None:
    assert ".card .body:has(>.empty:only-child){display:flex;align-items:center" in CSS


# ------------------------------------------------------------------ the board


def test_the_run_and_its_list_have_more_of_the_screen_than_the_map() -> None:
    """The detail is what a person reads. It was cut at its fifth line while the map of
    118 nodes - which a run touches eight of - had the largest share."""
    areas = re.search(r"grid-template-areas:(.*?)\}", ACTIVITY, re.S)
    assert areas, "the Activity board names no areas"
    named = areas.group(1)
    assert named.count('"runs detail inbox"') == 1
    assert '"runs detail alerts"' in named, "the detail no longer spans two rows"
    assert named.count("trace") == 2, "the map should hold one row, across two columns"


def test_the_steps_table_reads_down() -> None:
    """A step and the skill that ran it on one line, so seven steps are seven lines."""
    body = scripts(ACTIVITY)
    assert 'esc(x.step_id)}</b>\n      <span class="sub" style="margin-left:.45rem"' in body


@pytest.mark.parametrize("page", ["analytics"])
def test_columns_of_figures_are_set_to_one_width(page: str) -> None:
    assert ".r .num{flex:none;width:4.5rem;text-align:right" in CSS
    assert '<span class="num">Runs</span>' in ANALYTICS
    assert '<span class="num">Clean run</span>' in ANALYTICS, "and the column says process"
