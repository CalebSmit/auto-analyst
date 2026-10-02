"""P142: the board handed every panel the same share of the screen, whatever was in it.

Measured on all three board pages at a desk viewport, with a store of three real runs and
three engagements. Each panel's body against the content inside it:

    Activity   Live activity 6.07   Run trace 3.58   |  Alerts 0.44  Waiting 0.41  Runs 0.54
    Setup      What is wired 4.39   Engagements 3.16 |  Methodology 0.56  Report 0.69
    Analytics  -                                     |  What to fix first 0.13  By skill 0.36

**Seven of twenty panels hid content behind an inner scrollbar while eight sat under
seventy per cent full - on the same screens.** The fixed six-row grid was wrong in both
directions at once, and a reader scrolled inside twelve boxes rather than scrolling one
page. A box only tells you it scrolls once you have found it.

What the old rule was keeping is kept: the chrome is sticky, so the counts that say what
needs a person are in view wherever the page is. What could not be kept was the claim -
the board was not showing everything at a glance, it was hiding most of it.

Three panels still scroll, and they are marked `stream` because their content has no end:
the event log, the map of a hundred and eighteen nodes, and the list of every seam. The
scroll shadow means something now: it used to appear because the grid was short.

And one panel was titled with the name of the box rather than the thing in it. "Run detail"
was set three sizes larger than the client the panel was about, which sat in the smallest
type on the page.
"""

from __future__ import annotations

import re
from pathlib import Path

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ui.theme import CSS

ROOT = Path(__file__).resolve().parents[2]

BOARDS = ((SETUP, "Setup"), (ACTIVITY, "Activity"), (ANALYTICS, "Analytics"))


# ------------------------------------------------- a panel is as tall as what it holds


def test_no_row_is_a_share_of_the_screen() -> None:
    """`1fr` is what made a panel's height a fact about the viewport rather than about its
    content. Asserted per page, because each names its own rows."""
    for page, where in BOARDS:
        rows = re.search(r"grid-template-rows:([^;]*);", page)
        assert rows, f"{where} names no rows"
        assert "fr" not in rows.group(1), (
            f"{where} sizes a row as a share of the screen: {rows.group(1).strip()}"
        )
        assert "min-content" in rows.group(1), f"{where} does not size its rows to content"


def test_the_board_stacks_from_the_top_rather_than_filling() -> None:
    assert ".board{display:grid;gap:var(--s3);align-content:start}" in CSS
    assert "flex:1;min-height:0;display:grid" not in CSS, "the board fills the screen again"


def test_the_page_can_scroll() -> None:
    """It could not: html and body were both `overflow:hidden` with `height:100%`, which is
    what forced every panel to hide its own content instead."""
    assert "overflow:hidden}" not in re.search(r"^html\{[^}]*\}", CSS, re.M).group(0)
    body = re.search(r"^body\{[^}]*\}", CSS, re.M)
    assert body and "overflow:hidden" not in body.group(0)
    assert "min-height:100%" in CSS


def test_the_counts_stay_in_view_while_the_page_moves() -> None:
    """The one thing the old layout did well. A count you have to scroll back up to read is
    a count nobody reads, and these two are the reason somebody opens the page."""
    top = re.search(r"^\.top\{[^}]*\}", CSS, re.M)
    assert top, "the chrome's rule is gone"
    assert "position:sticky" in top.group(0)
    assert "top:0" in top.group(0)
    assert "z-index" in top.group(0), "sticky with nothing above the board is sticky underneath it"


# ------------------------------------------------------- except a stream, which says so


def test_only_a_stream_is_capped() -> None:
    body = re.search(r"\.card \.body\{([^}]*)\}", CSS)
    assert body, "the panel body rule is gone"
    assert "overflow" not in body.group(1), "every panel scrolls again"
    assert "max-height" not in body.group(1)
    assert ".card.stream>.body{max-height:26rem;overflow:auto" in CSS


def test_every_stream_is_one_whose_content_has_no_end() -> None:
    """Named in the markup rather than inferred from height, because being a stream is a
    fact about what a panel holds. Each one carries a comment saying which."""
    streams = {
        where: re.findall(r'<!--([^>]*?)-->\s*<section class="card stream"', page, re.S)
        for page, where in BOARDS
    }
    assert streams["Activity"], "the Activity console marks no stream"
    assert streams["Setup"], "Setup marks no stream"
    for where, said in streams.items():
        for comment in said:
            assert "stream" in comment.lower(), f"{where}: a stream with no reason beside it"

    # And nothing else is marked. A panel that is merely long is not a stream; capping it
    # would be the old defect under a new name.
    for page, where in BOARDS:
        assert page.count('class="card stream"') == len(streams[where]), where


def test_a_cut_panel_still_shows_that_it_is_cut() -> None:
    """The scroll shadows moved to the stream rule with the scrolling. They say more than
    they did: a shadow used to mean the grid was short."""
    rule = re.search(r"\.card\.stream>\.body\{([^}]*)\}", CSS)
    assert rule
    assert rule.group(1).count("radial-gradient") == 2
    assert rule.group(1).count("no-repeat local") == 2


# --------------------------------------------- a panel is titled with the thing in it


def test_the_run_panel_is_titled_with_the_run() -> None:
    """"Run detail" named the box. The client it was about was in the smallest type on the
    page, three sizes below a heading that said nothing a reader did not already know."""
    assert '<h2 id="detail-title">Run detail</h2>' in ACTIVITY, "the title cannot be set"
    body = "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))
    assert "$('detail-title').textContent = row.client" in body
    assert "|| 'Run detail'" in body, "a run with no client leaves the panel untitled"


def test_the_run_id_moved_out_of_the_title_line() -> None:
    """It is the least readable thing about a run and it was in the subtitle beside the
    client. The subtitle is now the engagement and the id, and the client is the title."""
    body = "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))
    assert "$('detail-why').textContent = (run.engagement_id" in body
    assert "row.client ? row.client + ' \\u2014 '" not in body, "the old subtitle is back"


# ------------------------------------------------------------- and one layout, not two


def test_the_height_breakpoint_is_gone_because_nothing_is_left_for_it() -> None:
    """P136 added it and this supersedes it. Measured with the block applied and removed,
    the same two panels scrolled either way - and it let height decide the column count,
    which is a question about width."""
    assert "@media (max-height" not in CSS
    assert "@media (max-width:1100px)" in CSS, "the rule that is about columns went too"


def test_the_measurement_that_justified_this_is_written_down() -> None:
    """A layout decision with no number attached is one the next person undoes on taste."""
    assert "seventy per cent" in CSS
    assert "six-row grid" in CSS or "equal share" in CSS
