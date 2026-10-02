"""P149: the cap went to what was long that day, not to what grows.

P142 introduced `stream` and wrote the reason beside it - *a panel whose content has no
end*. The criterion it actually applied was different: whichever panels looked long on a
screen with three runs on it. So the event log was capped and **the list of every run the
firm has ever done was not**.

Measured by putting a realistic firm through the real page - 54 runs over 18 engagements,
against the same server, with nothing changed but the number of rows:

| | before | after |
|---|---|---|
| the page | 4787px | **1134px** |
| the Runs panel | 4148px, four screens | **494px** |
| scrolling to the last run | 3686px down | **24px** |
| where the detail panel then is | **3570px above the window** | 91px, on screen |
| tallest panel / shortest | 8x | **2.1x** |

The fourth row is the one with consequence. A reader scrolls to a run near the bottom,
clicks it, and the panel it opens is three and a half screens behind them - the list and the
thing the list is for cannot be on screen together once the list is long.

**And it costs nothing until it is needed.** The cap is a `max-height`, so at the three runs
this machine actually has, every measurement is identical with it and without it: the Runs
panel is 422px either way.

**The rule, written so it can be asked rather than seen.** The question is *whose length it
is*. One row per step of setup, per practice group, per recipe, per seam: that is as long as
this build made it, and it is as tall as what it holds. One row per run, per engagement, per
open question, per week of history: that is as long as the firm's own work, and nothing here
can know how long that is.

`WHOSE` below is that judgement, written down for all twenty panels on the three boards -
and it is the only hand-written thing here. Which panels carry the cap is read off the
markup, and the two are required to agree.
"""

from __future__ import annotations

import re

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ui.theme import CSS

BOARDS = ((ACTIVITY, "Activity"), (SETUP, "Setup"), (ANALYTICS, "Analytics"))

# Whose length each panel's content is, and what follows.
#
#   `firm`      one row per thing the firm has done or holds. Nothing here can bound it, so
#               it *must* be capped - that is the finding this phase is about.
#   `ours-long` a list this build decides, which this build has made long enough to need a
#               cap anyway. The reason has to say how long, because that is the whole claim.
#   `ours`      a list this build decides and keeps short. It must *not* be capped: a panel
#               that hides rows it could have shown is the opposite mistake.
#
# The first draft of this file had two values and asserted capped-if-and-only-if-firm, and
# went red on `trace` and `seams` - which are ours, are capped, and are right to be. There
# are two reasons to cap and only one of them is about the firm.
WHOSE = {
    # Activity
    "runs": ("firm", "one row per run, for as long as the firm keeps running them"),
    "detail": ("ours", "one run at a time, and its shape is fixed"),
    "inbox": ("firm", "one per question a run has stopped on"),
    "trace": ("ours-long", "one per node of the design - 118 of them, so it is long "
              "by this build's own decision rather than by the firm's work"),
    "alerts": ("firm", "one per run gone quiet or review past its SLA"),
    "feed": ("firm", "the event log, which has no end at all"),
    # Setup
    "steps": ("ours", "the setup checklist; this build decides how many steps there are"),
    "eng": ("firm", "one per piece of client work on the roster"),
    "pre": ("firm", "one finding per thing wrong, and the things grow with the engagements"),
    "meth": ("ours", "one per methodology file the firm keeps, which is a short fixed set"),
    "scopes": ("ours", "one per practice group in scopes.yaml"),
    "recipes": ("ours", "one per recipe the repo ships"),
    "report": ("ours", "one report at a time"),
    "seams": ("ours-long", "one per seam in the design - eleven, with a paragraph "
              "each, which is longer than the panel it sits in"),
    # Analytics
    "funnel": ("ours", "one per stage of a run, which the design fixes"),
    "failures": ("firm", "one per thing going wrong, ranked - as many as there are"),
    "stuck": ("ours", "a fixed set of questions about what is stuck"),
    "outcomes": ("firm", "one row per week, forever"),
    "skills": ("ours", "one per skill in the library"),
    "trends": ("ours", "a fixed set of measures"),
}


def panels() -> dict[str, tuple[str, bool]]:
    """Every panel on the three boards: its area, which board, and whether it is capped."""
    found = {}
    for page, board in BOARDS:
        for match in re.finditer(r'<section class="card( stream)?" style="grid-area:(\w+)">', page):
            found[match.group(2)] = (board, bool(match.group(1)))
    return found


# ----------------------------------------------- the classification, and the markup, agree


def test_every_panel_on_every_board_has_been_asked_whose_length_it_is() -> None:
    """A panel nobody has decided about is a panel that will be whatever it happens to be,
    which is the state all twenty were in."""
    missing = sorted(set(panels()) - set(WHOSE))
    assert missing == [], f"these panels have no answer recorded: {missing}"
    gone = sorted(set(WHOSE) - set(panels()))
    assert gone == [], f"these are answered for and no longer on a board: {gone}"


def test_the_panels_that_are_capped_are_exactly_the_ones_that_are_the_firms() -> None:
    """Derived both ways, which is the whole guard: a panel that grows and does not scroll
    takes the page with it, and a panel that does not grow and scrolls hides what it has for
    no reason."""
    wrong = []
    for area, (board, capped) in sorted(panels().items()):
        whose, why = WHOSE[area]
        if whose == "firm" and not capped:
            wrong.append(f"{board}/{area} grows with the firm and is not capped - {why}")
        if whose == "ours" and capped:
            wrong.append(f"{board}/{area} is ours to size and scrolls anyway - {why}")
        if whose == "ours-long" and not capped:
            wrong.append(f"{board}/{area} is capped on purpose and is not - {why}")
    assert wrong == [], "\n".join(wrong)


def test_the_seven_that_were_missed_are_capped_by_name() -> None:
    """Named one by one, because a sweep that passes because a panel was deleted is a sweep
    that has stopped watching what it was written for."""
    for area in ("runs", "inbox", "alerts", "eng", "pre", "failures", "outcomes"):
        board, capped = panels()[area]
        assert capped, f"{board}/{area} is back to growing without a bound"


def test_the_two_that_were_already_right_stayed_right() -> None:
    """`feed` is the firm's and was capped; `trace` and `seams` are ours and are capped
    because they are long, which is a different reason the sheet now has to carry."""
    assert panels()["feed"][1] and WHOSE["feed"][0] == "firm", (
        "the event log is the one panel P142 capped for the reason it gave"
    )
    for area in ("trace", "seams"):
        assert panels()[area][1], f"{area} has lost a cap it has had since P142"
        assert WHOSE[area][0] == "ours-long", (
            f"{area} is capped because this build made it long, not because the firm did, "
            "and the two reasons are worth keeping apart"
        )


# ------------------------------------------------- what the sheet says, and what it costs


def test_the_sheet_states_the_rule_as_a_question_about_the_panel() -> None:
    """P142's reason - *content that has no end* - was true of the ones it capped and said
    nothing about the ones it did not. The rule has to be answerable about a panel nobody
    has looked at on a screen."""
    rule = CSS[CSS.index("/* A stream:") : CSS.index(".card.stream>.body{")]
    assert "whose length it is" in rule, "the sheet does not say what the test is"
    assert "per run" in rule and "per seam" in rule, (
        "the rule names no example of either side, which is what made the first one unusable"
    )


def test_a_cap_is_a_maximum_so_it_costs_nothing_until_it_is_reached() -> None:
    """The measurement that made this safe to do to seven panels at once: at the three runs
    this machine has, the Runs panel is 422px with the cap and 422px without."""
    body = re.search(r"\.card\.stream>\.body\{([^;]*);", CSS)
    assert body and body.group(1).startswith("max-height:"), (
        "a stream sets a height rather than a maximum, and now it costs something always"
    )
    plain = re.search(r"\n\.card \.body\{([^}]*)\}", CSS)
    assert plain and "max-height" not in plain.group(1), (
        "every panel is capped now, which is the opposite mistake"
    )


def test_only_a_stream_scrolls_so_a_shadow_still_means_something() -> None:
    """P142's property, which this phase triples the number of panels relying on: a scroll
    shadow has to mean there is genuinely more, not that the grid was short."""
    assert ".card.stream>.body{max-height:26rem;overflow:auto" in CSS
    for page, board in BOARDS:
        own = page.split("</style>")[0]
        if CSS in own:
            own = own.replace(CSS, "")
        for rule in re.findall(r"^\s*([^{\n@]+)\{([^}]*)\}", own, re.M):
            selector, declarations = rule[0].strip(), rule[1]
            if ".card" in selector or ".board" in selector:
                assert "overflow" not in declarations, (
                    f"{board} decides for itself whether {selector!r} scrolls"
                )
