"""P136: the board is a monitor layout, and the machine this is moving to is a laptop.

Measured rather than guessed. With the Setup page open and its wrapper forced to a 600px
height - a 1366x768 laptop, less the browser's own chrome - the "Getting set up" panel
reported:

    clientHeight 259, scrollHeight 750

35% of its own content. Three steps of eleven, in the panel somebody's first day is spent
in, with the other eleven panels no better. The page looked fine on this desk's monitor,
which is exactly why it had never been noticed.

The stylesheet already contains the argument, written for the other dimension:

    One screen, no scrolling, is the rule at desk width. Below it the same rule hides
    whatever does not fit, with no way to reach it.

That is true of height too and nobody had said so. Three changes, smallest first:

* **A finished step takes one line.** Its title and its single line of detail share a line,
  because a done step is a receipt rather than an instruction. `.step.done .d` was already
  truncated to one line; it was the line break above it that cost the space.
* **The checklist gets a fourth of the board's six rows** while there is work in it. The
  `all-done` layout already takes rows away when the list has nothing to say; nothing gave
  it any while it did.
* **And below 760px of viewport the board stops being a grid**, exactly as it does below
  1100px of width: the cards take their own height and the page scrolls like a page.

Together, eleven steps of eleven, visible at once.
"""

from __future__ import annotations

import re
from pathlib import Path

from admin.page import PAGE as SETUP
from ops.console.app import PAGE as ACTIVITY

ROOT = Path(__file__).resolve().parents[2]


def theme() -> str:
    return (ROOT / "ui" / "theme.py").read_text(encoding="utf-8")


# ------------------------------------------------- the laptop, and what superseded the fix


def test_a_short_viewport_is_handled_by_the_board_rather_than_by_a_rule_of_its_own() -> None:
    """This phase measured the problem and fixed it at one size; P142 fixed the cause.

    What P136 found is still true and is what matters: at a laptop's height every panel in a
    fixed six-row grid was a peephole - "Getting set up" showing 35% of its own content. The
    fix then was a `max-height:760px` block that turned the board into one column.

    P142 made the board's rows as tall as what is in them at *every* size, so a short screen
    shows fewer rows and scrolls exactly as a tall one does with more content. Measured with
    the old block applied and removed, the answer was identical - the same two panels
    scrolled either way, and both are streams. The block also made a claim it should not
    have: it let height decide the *column count*, and how many columns fit is a question
    about width. A 1366x600 laptop is a wide screen and keeps its three columns.

    So the assertion is the opposite of the original: there is no height breakpoint, because
    there is nothing left for one to do.
    """
    css = theme()
    assert "@media (max-height" not in css, "a height breakpoint is back; the board should fit"
    assert "@media (max-width:1100px)" in css, "the rule that is about columns is gone"


def test_the_board_gives_a_panel_the_height_of_what_is_in_it() -> None:
    """The cause, where it now lives. No row is a fraction of the viewport, so no panel is
    sized by anything except its content."""
    css = theme()
    assert ".board{display:grid;gap:var(--s3);align-content:start}" in css
    assert ".board{flex:1;min-height:0;display:grid" not in css, "the rows fill the screen again"
    for page, where in ((SETUP, "Setup"), (ACTIVITY, "Activity")):
        rows = re.search(r"grid-template-rows:([^;]*);", page)
        assert rows, f"{where} names no rows"
        assert "fr" not in rows.group(1), f"{where} sizes a row as a share of the screen"


def test_only_a_stream_scrolls_inside_itself() -> None:
    """The one thing a panel may still hide behind, and it has to say so. A stream is a
    panel whose content has no end - an event log, a map of a hundred and eighteen nodes -
    and capping those is why the page does not become a mile long."""
    css = theme()
    assert ".card .body{flex:1;min-height:0;padding:" in css, "the default body rule changed"
    body = re.search(r"\.card \.body\{([^}]*)\}", css)
    assert body and "overflow" not in body.group(1), "every panel scrolls again"
    assert ".card.stream>.body{max-height:26rem;overflow:auto" in css

    for page, where in ((ACTIVITY, "Activity"), (SETUP, "Setup")):
        assert 'class="card stream"' in page, f"{where} marks no panel as a stream"


def test_what_the_phase_measured_is_written_down() -> None:
    """The number is the argument. Without it the next person reads a layout decision with
    no reason attached and is free to undo it on taste."""
    css = theme()
    assert "35%" in css or "seventy per cent" in css, "the measurement is gone from the CSS"


# ------------------------------------------------------------- a finished step is a line


def test_a_finished_step_puts_its_detail_on_the_same_line_as_its_title() -> None:
    css = theme()
    assert ".step.done .t{display:inline}" in css
    assert ".step.done .d{display:inline" in css
    # And the row, not the detail alone, is what truncates - or the title would be clipped
    # by a rule meant for the sentence after it.
    assert ".step.done>span:not(.mark):not(.go){white-space:nowrap" in css


def test_an_unfinished_step_still_reads_as_two_lines() -> None:
    """The compaction is for steps that are done. A step somebody still has to do is the
    whole reason the panel exists, and it keeps its title and its instruction apart."""
    css = theme()
    assert ".step .t{display:block" in css
    assert ".step .d{display:block" in css
    assert ".step.now .t{font-size:var(--t-subtitle)" in css, "the next step stops standing out"


def test_the_step_list_is_capped_to_a_readable_measure() -> None:
    """In the single-column fallback the rows would otherwise run the full width of a
    1366px screen, putting a step's button a long way from the step."""
    assert "max-width:84ch" in theme()


# ----------------------------------------------------------------- and the board's rows


def test_the_checklist_leads_the_board_while_it_has_work_in_it() -> None:
    """It held three rows, and P136 gave it a fourth after measuring the panel at a laptop's
    viewport - so the only layout decision ever made about it was how to shrink it.

    P172 took the rows away from every panel on this board, because a panel spanning rows
    stretches everything beside it to a height nothing in that band asked for. What that
    phase had to keep is this one's point: while there is work in it, the checklist is the
    screen. On a board of bands that is a position rather than a row count - first band,
    first column, which is where a reader starts - and it is still given up when the last
    box is ticked.
    """
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")
    board = r"\.board\{\{grid-template-columns:.*?grid-template-areas:(.*?)\}\}"
    default = re.search(board, page, re.S)
    assert default, "the board's areas are gone"
    bands = [row.split() for row in re.findall(r'"([^"]*)"', default.group(1))]
    assert bands and bands[0][0] == "steps", (
        f"the checklist no longer starts the board: the first band is {bands[0]}"
    )

    done = re.search(r"body\.all-done \.board\{\{grid-template-areas:(.*?)\}\}", page, re.S)
    assert done, "the finished layout is gone"
    finished = [row.split() for row in re.findall(r'"([^"]*)"', done.group(1))]
    assert finished[0][0] == "eng", (
        "a finished checklist still starts the board, and nothing took the place it gave up"
    )
    assert "steps" in {area for band in finished for area in band}, (
        "the checklist is removed rather than moved - how this got set up is a real question"
    )


def test_every_area_the_grid_names_is_a_panel_on_the_page() -> None:
    """Changing a template is where a typo turns into a panel that renders nowhere. The
    areas and the sections are asserted against each other rather than read side by side."""
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")
    placed = set(re.findall(r'style="grid-area:([a-z]+)"', page))
    for template in re.findall(r"grid-template-areas:(.*?)\}\}", page, re.S):
        named = set(re.findall(r"[a-z]+", template))
        assert named == placed, f"areas and panels disagree: {named ^ placed}"
