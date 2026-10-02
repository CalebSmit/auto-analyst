"""C82 - how tall a page gets is this build's answer, not the firm's.

**P149.** P142 capped three panels and wrote the reason beside them - *content that has no
end*. The criterion it applied was different: whichever panels were long on a screen with
three runs on it. So the event log was capped and the list of every run the firm has ever
done was not. Measured at 54 runs over 18 engagements, against the same server: the Runs
panel grew to 4148px, the page to 4787, and a reader who scrolled to the last run found that
clicking it opened a panel **3570px above the window**.

What a checkpoint can ask that the phase could not.

The phase proved its seven panels. The property underneath them is about the whole page, and
it is the one worth holding: **every panel is bounded by something this build decides.** A
panel is either capped - so at most one cap tall, whatever is in it - or its rows come from a
list this build fixes. One uncapped panel fed by the firm's own work breaks that, and the
page stops having a maximum height at all.

That is checkable without a browser, which matters: the measurement that found this needed a
simulated firm and a running server, and a property that can only be seen that way is a
property nobody will check again. This one is a question about the source.
"""

from __future__ import annotations

import re

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.map_view import MAP_STYLE
from tests.p149.test_the_panels_whose_length_is_not_ours import WHOSE
from ui.theme import CSS

BOARDS = ((ACTIVITY, "Activity"), (SETUP, "Setup"), (ANALYTICS, "Analytics"))


def panels_of(page: str) -> dict[str, bool]:
    """Each board panel's grid area, and whether it is capped."""
    return {
        m.group(2): bool(m.group(1))
        for m in re.finditer(r'<section class="card( stream)?" style="grid-area:(\w+)">', page)
    }


# ----------------------------------------------- the bound, stated over the whole page


def test_every_panel_on_every_board_is_bounded_by_something_this_build_decides() -> None:
    """The claim. A panel is bounded if it is capped, or if its rows come from a list this
    build fixes - and one that is neither makes the page as tall as the firm's history.
    """
    unbounded = []
    for page, board in BOARDS:
        for area, capped in panels_of(page).items():
            whose = WHOSE[area][0]
            if not capped and whose == "firm":
                unbounded.append(f"{board}/{area}: fed by the firm and nothing caps it")
    assert unbounded == [], (
        "the page has no maximum height any more:\n" + "\n".join(unbounded)
    )


# The things in this sheet allowed a maximum height of their own, with what each one is.
# A panel is not among them: ten of those share one number, and a second would be a page
# height kept in step in two places.
MAY_CAP_ITSELF = {
    ".card.stream>.body": "the panel cap itself - the one number this checkpoint is about",
    ".excerpt": "a quoted passage from a client's document inside a review dialog, which is "
    "as long as the client wrote it and is not a panel on a board",
}


def test_the_panel_bound_is_one_number_in_one_place() -> None:
    """Ten panels rely on it now, against three before. A second panel cap would make the
    page's height two numbers that have to be kept in step."""
    stray = []
    for match in re.finditer(r"max-height:\s*[\d.]+rem", CSS):
        start = CSS.rfind("}", 0, match.start()) + 1
        selector = CSS[start : CSS.find("{", start)].strip().replace("\n", " ")
        if not any(allowed in selector for allowed in MAY_CAP_ITSELF):
            stray.append(selector[:70])
    assert stray == [], "something other than the panel cap sets a maximum:\n" + "\n".join(stray)
    assert CSS.count(".card.stream>.body{max-height:26rem") == 1
    for page, board in BOARDS:
        # The Activity console is served the map's sheet as well as the theme's, so
        # subtracting only the theme leaves the map's rules looking like the board's.
        own = page.split("</style>")[0]
        for shared in (CSS, MAP_STYLE):
            own = own.replace(shared, "")
        assert "max-height" not in own, f"{board} sets a height of its own"


def test_a_board_still_sizes_its_rows_to_what_is_in_them() -> None:
    """P142's half of this, which the caps rest on: if a row were a share of the screen
    again, a capped panel would be stretched to fill it and the cap would mean nothing."""
    for page, board in BOARDS:
        rows = re.search(r"grid-template-rows:([^;]*);", page)
        assert rows, f"{board} names no rows"
        assert "fr" not in rows.group(1), f"{board} is back to a share of the screen"


# ------------------------------------------ and the reason still travels with the panel


def test_every_capped_panel_says_why_where_it_is_declared() -> None:
    """Ten panels, three files. The reason has to be beside the markup rather than in a test,
    or the next person to add a panel has nothing to copy."""
    for page, board in BOARDS:
        declared = page.count('class="card stream"')
        explained = len(re.findall(r"<!--[^>]*?-->\s*<section class=\"card stream\"", page, re.S))
        assert declared == explained, (
            f"{board}: {declared} capped panels and {explained} reasons beside them"
        )


def test_the_classification_covers_every_panel_the_three_boards_have() -> None:
    """Said at this level because the three boards are three files, and a panel added to one
    of them is exactly the case that goes unnoticed."""
    on_screen = {area for page, _ in BOARDS for area in panels_of(page)}
    assert on_screen == set(WHOSE), (
        f"on the boards but unclassified: {sorted(on_screen - set(WHOSE))}; "
        f"classified and gone: {sorted(set(WHOSE) - on_screen)}"
    )


def test_the_firms_panels_are_the_ones_a_firm_would_recognise() -> None:
    """A spot check with a person's eye rather than a derivation, because the classification
    is the one judgement here and a checkpoint that only re-derived it would be checking the
    table against itself."""
    firm = {area for area, (whose, _) in WHOSE.items() if whose == "firm"}
    assert {"runs", "eng", "feed", "outcomes"} <= firm, (
        "runs, engagements, the event log and the weekly history are the firm's by definition"
    )
    ours = {area for area, (whose, _) in WHOSE.items() if whose.startswith("ours")}
    assert {"steps", "scopes", "recipes", "seams", "trace"} <= ours, (
        "the setup checklist, the practice groups, the recipes, the seams and the design's "
        "own nodes are all this build's to count"
    )
    assert firm & ours == set()
