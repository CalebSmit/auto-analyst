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
    with the content and covers the shadows at an edge with nothing behind it.

    On the stream rule since P142. Every panel used to scroll, so every panel needed to say
    whether it was cut; now a panel is as tall as what it holds and only a stream - an event
    log, a hundred and eighteen nodes - is capped. The shadow means more than it did: it
    used to appear because the grid was short, and now it appears because there is genuinely
    more to read.
    """
    body = re.search(r"\.card\.stream>\.body\{([^}]*)\}", CSS)
    assert body, "the stream rule is gone, so nothing says when a panel is cut"
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
    118 nodes - which a run touches eight of - had the largest share.

    P47 got that by giving the detail two rows of the three, and P172 found what spanning
    rows cost: a panel in two rows has its height shared out across rows nothing else is
    in, so every panel beside it is stretched to a height nothing in its band asked for,
    and with an unbounded detail that was 2,500px of white in the Runs panel.

    So the claim is kept and the mechanism is not. The detail has the widest of the three
    columns, it is on the first band beside the list it is chosen from, and *being cut
    while the map runs on* cannot happen any more: both are streams, so they are bounded to
    the same height by construction rather than by how the rows divide.
    """
    areas = re.search(r"grid-template-areas:(.*?)\}", ACTIVITY, re.S)
    assert areas, "the Activity board names no areas"
    named = areas.group(1)
    bands = [row.split() for row in re.findall(r'"([^"]*)"', named)]
    assert bands[0] == ["runs", "detail", "inbox"], "the run and its list no longer lead"
    assert "trace" not in bands[0], "the map is back on the band the detail is read from"
    assert named.count("trace") == 2, "the map should hold one band, across two columns"

    # The board's own rule, not the first `grid-template-columns` in the page: the shared
    # sheet and the map have several, and the loose version of this measured one of those.
    columns = re.search(r"\.board\{grid-template-columns:([^;]*);", ACTIVITY).group(1)
    widths = [float(w) for w in re.findall(r"minmax\(0,([\d.]+)fr\)", columns)]
    assert len(widths) == 3, columns
    assert widths[1] == max(widths), (
        f"the column the run's detail is in is {widths[1]}fr and the widest is "
        f"{max(widths)}fr - the detail is what a person reads"
    )

    # And the thing that made the detail short in the first place cannot come back without
    # the panel bound coming back with it.
    assert '<section class="card stream" style="grid-area:detail">' in ACTIVITY
    assert '<section class="card stream" style="grid-area:trace">' in ACTIVITY


def test_the_steps_table_reads_down() -> None:
    """A step and the skill that ran it on one line, so seven steps are seven lines.

    Asked as *are they one label* rather than as the one spelling of it. P173 moved the
    size and the gap off the element and onto `.step-id`, which is the same row rendered
    the same way, and the literal version of this went red on it.

    **One label means nesting, and the first rewrite of this did not ask for it.** It
    checked that a `</b>` came before the skill and that a `.sub` appeared after, and both
    of those survive the label being closed early and the skill left outside it - which is
    exactly the regression it exists to catch, and it stayed green on it. So the label's
    own tags are matched: the skill has to fall inside the element that opens
    `<span class="lbl step-id">` and ends at the `</span>` that closes *it*.
    """
    body = scripts(ACTIVITY)
    opens = body.index('<span class="lbl step-id">')

    depth, inside = 0, None
    for tag in re.finditer(r"<span\b|</span>", body[opens:]):
        depth += 1 if tag.group(0) == "<span" else -1
        if depth == 0:
            inside = body[opens + len('<span class="lbl step-id">') : opens + tag.start()]
            break
    assert inside is not None, "the step-id label is never closed"

    assert "${esc(x.step_id)}" in inside, "the step id is not in its own label"
    assert "x.skill" in inside, (
        "the skill is outside the step-id label, so the step and the skill are two things "
        "on the row rather than one label with two lines"
    )
    assert '<span class="sub">' in inside, "the skill is no longer the quiet line beneath"
    assert "step-id" in CSS, "the sheet does not put them on one line"


@pytest.mark.parametrize("page", ["analytics"])
def test_columns_of_figures_are_set_to_one_width(page: str) -> None:
    assert ".r .num{flex:none;width:4.5rem;text-align:right" in CSS
    assert '<span class="num">Runs</span>' in ANALYTICS
    assert '<span class="num">Clean run</span>' in ANALYTICS, "and the column says process"
