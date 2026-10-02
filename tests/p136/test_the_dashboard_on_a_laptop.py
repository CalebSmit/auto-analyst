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

ROOT = Path(__file__).resolve().parents[2]


def theme() -> str:
    return (ROOT / "ui" / "theme.py").read_text(encoding="utf-8")


# ---------------------------------------------------------- the short-viewport fallback


def test_a_short_viewport_falls_back_the_same_way_a_narrow_one_does() -> None:
    """The same five declarations, because it is the same decision. Two fallbacks that
    drifted apart would be two layouts to reason about instead of one."""
    css = theme()
    short = re.search(r"@media \(max-height:760px\)\{(.*?)\n\}", css, re.S)
    assert short, "there is no short-viewport rule at all"
    narrow = re.search(r"@media \(max-width:1100px\)\{(.*?)\n\}", css, re.S)
    assert narrow, "the rule this one was derived from is gone"

    def declarations(block: str) -> set[str]:
        return {line.strip() for line in block.strip().splitlines() if line.strip()}

    missing = declarations(short.group(1)) - declarations(narrow.group(1))
    assert not missing, f"the short rule says something the narrow one does not: {missing}"

    # The five that make a grid into a page. Named, because a fallback that keeps any one
    # of them is a fallback that still hides something.
    for needed in (
        "html,body{overflow:auto}",
        ".wrap{overflow:visible}",
        ".board{display:block!important}",
        ".card .body{max-height:none}",
    ):
        assert needed in short.group(1), f"the short fallback does not {needed}"


def test_the_breakpoint_is_where_a_work_laptop_lands() -> None:
    """768 minus the browser's chrome is around 630, so 760 puts that machine inside the
    rule with room rather than on its edge. Asserted so that moving it is a decision."""
    css = theme()
    assert "@media (max-height:760px)" in css
    assert "1366x768" in css, "the machine the number was chosen for is not written down"


def test_the_desk_layout_is_untouched() -> None:
    """Everything above is a fallback. The board at desk size is still one screen, which
    is the design and not an accident of it."""
    css = theme()
    assert ".board{flex:1;min-height:0;display:grid" in css
    assert ".card .body{flex:1;min-height:0;overflow:auto" in css


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


def test_the_checklist_holds_four_rows_while_it_has_work_in_it() -> None:
    """It held three, and gave them up at `all-done` - so the only layout decision ever
    made about this panel was how to shrink it."""
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")
    board = r"\.board\{\{grid-template-columns:.*?grid-template-areas:(.*?)\}\}"
    default = re.search(board, page, re.S)
    assert default, "the board's areas are gone"
    assert default.group(1).count('"steps') == 4, "the checklist no longer holds four rows"

    done = re.search(r"body\.all-done \.board\{\{grid-template-areas:(.*?)\}\}", page, re.S)
    assert done, "the finished layout is gone"
    assert done.group(1).count('"steps') == 1, "a finished checklist holds the board again"


def test_every_area_the_grid_names_is_a_panel_on_the_page() -> None:
    """Changing a template is where a typo turns into a panel that renders nowhere. The
    areas and the sections are asserted against each other rather than read side by side."""
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")
    placed = set(re.findall(r'style="grid-area:([a-z]+)"', page))
    for template in re.findall(r"grid-template-areas:(.*?)\}\}", page, re.S):
        named = set(re.findall(r"[a-z]+", template))
        assert named == placed, f"areas and panels disagree: {named ^ placed}"
