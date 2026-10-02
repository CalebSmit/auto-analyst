"""P146: a rule the build states, and a guard that checked one of seventy ways to break it.

CLAUDE.md, under *Running it*: *"Pages build no handler out of data - values reach a handler
through `data-` attributes and the `ACTIONS` table, because a client's line item is whatever
the client typed."* Six tests enforce it. All six are the same line:

    assert "onclick=" not in page, "values reach a handler through data- attributes"

HTML has about seventy event-handler content attributes. Three were in use:

    oninput="applyFilter()"    the run filter, on the Activity console
    onchange="repaint()"       the trace's "only what this run touched" box
    onchange="refresh()"       the period select, on Analytics

and every one of the six guards passed over every one of them, for as long as they existed.

**Why they existed, which is the part that matters.** The shared dispatcher listened for
`click` and `keydown`. A field fires neither. So the one mechanism did not cover the one
case, and three controls went around it - not because anybody decided to, but because there
was nowhere to go. A guard that forbids the workaround without providing the road is a
guard that will be worked around again.

**What it would cost.** `tests/p45` records the defect these guards were written for: a
client called `O'Brien`, whose apostrophe closed the `onclick` it had been interpolated
into. If that came back tomorrow as `oninput="go('" + client + "')"`, all six would stay
green. Nothing here was interpolating a value today; what was missing was the thing that
would notice.

The definition of "an inline handler" now lives once, in `tests/reading.py`, beside the
other two readers that exist because a substring is not a question about code. It reads the
markup with comments stripped - which this check needs more than most, because the comment
in `ui/theme.py` explaining why there are no inline handlers contains the words `oninput=`
and `onchange=`.
"""

from __future__ import annotations

import re

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from tests.reading import inline_handlers, page_code
from ui.theme import CSS, SHELL

PAGES = ((SETUP, "Setup"), (ACTIVITY, "Activity"), (ANALYTICS, "Analytics"))


# ------------------------------------------------- not one attribute, but the class of them


def test_no_page_wires_a_handler_in_its_markup() -> None:
    """The sweep the six single-attribute checks were standing in for."""
    stray = []
    for page, where in PAGES:
        stray += [f"{where}: ...{found.strip()}" for found in inline_handlers(page)]
    assert stray == [], "a handler is wired in the markup:\n" + "\n".join(stray)


def test_the_sweep_looks_for_more_than_the_one_attribute_it_replaced() -> None:
    """The check on the check. A sweep that had quietly become `onclick` again would pass
    the test above on the day the next `onchange` arrived, which is where this started.
    """
    assert inline_handlers('<button onclick="go()">x</button>'), "it misses the old one"
    for attribute in ("oninput", "onchange", "onsubmit", "onkeydown", "onfocus", "ondrop"):
        html = f'<i {attribute}="go()"></i>'
        assert inline_handlers(html), f"it misses {attribute}, which is how this got here"


def test_the_sweep_is_asked_of_markup_rather_than_of_prose() -> None:
    """`tests/reading.py`'s own reason, which this check walks straight into: the comment
    explaining the fix names the attributes it removed."""
    assert inline_handlers("/* wired with oninput= and onchange= before P146 */") == []
    assert "oninput=" in CSS or "oninput=" in SHELL, (
        "the comment that made this necessary is gone, and so is the test's reason"
    )
    assert inline_handlers("<script>el.onclick = f;</script>") == [], (
        "wiring from script is the mechanism, not the defect"
    )


# ------------------------------------------- and the road the workaround went around


def test_the_dispatcher_carries_the_events_a_field_fires() -> None:
    """A guard that forbids a workaround has to provide the road, or the next field goes
    around it too."""
    script = page_code(SHELL) if "<script" in SHELL else SHELL
    table = re.search(r"const CLIMBS = \{([^}]*)\}", script)
    assert table, "the events a handler may travel on are not written down"
    carried = dict(re.findall(r"(\w+):\s*(true|false)", table.group(1)))
    assert set(carried) >= {"click", "keydown", "change", "input"}, (
        f"a field still has nowhere to go: the dispatcher carries {sorted(carried)}"
    )
    assert re.search(r"for \(const kind of Object\.keys\(CLIMBS\)\) document\.addEventListener",
                     script), "the table and the listeners are two lists that can disagree"


def test_a_fields_action_is_its_own_and_is_not_inherited_from_its_row() -> None:
    """The reason `change` and `input` are in the table as `false`. A row carries
    `data-act`; a search box sits inside one. If a field's event climbed, typing a letter
    into the filter would run the row's action on every keystroke.
    """
    script = page_code(SHELL) if "<script" in SHELL else SHELL
    table = re.search(r"const CLIMBS = \{([^}]*)\}", script)
    assert table
    carried = dict(re.findall(r"(\w+):\s*(true|false)", table.group(1)))
    assert carried["change"] == "false" and carried["input"] == "false", (
        "a field's event climbs to the row it sits in"
    )
    assert carried["click"] == "true", "a press no longer reaches the row it was aimed at"
    assert "CLIMBS[ev.type]" in script, "the table is written down and not consulted"


def test_only_a_press_is_cancelled() -> None:
    """`preventDefault` on a `change` is meaningless and `stopPropagation` on an `input`
    takes the event from everything else, the browser's own work on the field included."""
    script = page_code(SHELL) if "<script" in SHELL else SHELL
    guarded = re.search(r"if \(CLIMBS\[ev\.type\]\) \{\s*ev\.preventDefault\(\);\s*"
                        r"ev\.stopPropagation\(\);\s*\}", script)
    assert guarded, "every event is cancelled, including the ones that have already happened"


def test_each_handler_that_moved_reaches_the_table_by_name() -> None:
    """Named one by one, because a sweep that passes because the control was deleted is a
    sweep that has stopped watching what it was written for."""
    assert 'data-act="filterRuns"' in ACTIVITY and "ACTIONS.filterRuns" in ACTIVITY
    assert 'data-act="onlyTouched"' in ACTIVITY and "ACTIONS.onlyTouched" in ACTIVITY
    assert 'data-act="setPeriod"' in ANALYTICS and "ACTIONS.setPeriod" in ANALYTICS


def answered_anywhere() -> set[str]:
    """Every action name something answers to.

    Two mechanisms, and both are deliberate. The `ACTIONS` table is the global one, read by
    the document listener. A modal also reads `dataset.act` itself, for the two names its
    own buttons carry - `ok` and `cancel` mean different things in different modals, so they
    are answered by the modal that owns them rather than by one entry for all of them.
    """
    shared = CSS + SHELL
    return (
        set(re.findall(r"ACTIONS\.(\w+)\s*=", shared))
        | set(re.findall(r"ACTIONS\[['\"](\w+)['\"]\]\s*=", shared))
        | set(re.findall(r"act === '(\w+)'", shared))
    )


def test_every_action_a_page_names_in_markup_is_one_something_answers_to() -> None:
    """The other half. `data-act="filterRuns"` with no `ACTIONS.filterRuns` is a control
    that does nothing at all, silently - the dispatcher returns without a sound, and the
    button looks exactly as it did when it worked."""
    stray = []
    for page, where in PAGES:
        named = set(re.findall(r'data-act="(\w+)"', page))
        registered = answered_anywhere() | set(re.findall(r"ACTIONS\.(\w+)\s*=", page))
        for act in sorted(named - registered):
            stray.append(f"{where}: data-act={act} and nothing answers to it")
    assert stray == [], "a control that does nothing:\n" + "\n".join(stray)


# --------------------------------------- the rules that were undoing nothing


def declarations(query: str) -> dict[str, str]:
    """Every declaration inside a media block, by selector."""
    block = re.search(r"@media \(" + re.escape(query) + r"\)\{(.*?)\n\}", CSS, re.S)
    assert block, f"there is no {query} block"
    return dict(re.findall(r"([^{}\n]+)\{([^}]*)\}", block.group(1)))


def test_the_narrow_width_block_only_says_things_about_width() -> None:
    """It carried `overflow:auto` on html and body, `overflow:visible` on `.wrap` and
    `max-height:none` on a card's body - three rules undoing rules P142 removed. Measured
    in the browser by applying all three at the top of the sheet: the stream's cap read
    377px before and 377px after, and no other body was ever capped.
    """
    narrow = declarations("max-width:1100px")
    for selector, body in narrow.items():
        assert "overflow" not in body, (
            f"{selector} sets an overflow at narrow width, and nothing sets one at any width"
        )
    assert "max-height" not in "".join(narrow.values()), (
        "a max-height is undone here, and the only one left wins on specificity anyway"
    )


def test_nothing_in_the_sheet_sets_an_overflow_this_block_would_need_to_undo() -> None:
    """The half that makes the one above a fact rather than a style preference. If the page
    ever stops scrolling again, this fails first and says why.
    """
    for selector in ("html", "body", r"\.wrap"):
        rule = re.search(r"(?:^|\n)" + selector + r"\{([^}]*)\}", CSS)
        assert rule, f"{selector} has no rule"
        assert "overflow" not in rule.group(1), (
            f"{selector} clips again, and the narrow block no longer undoes it"
        )


def test_the_one_capped_body_is_still_the_stream_and_still_wins() -> None:
    """Why `.card .body{max-height:none}` was doing nothing: it is 0,2,1 against 0,3,1."""
    assert ".card.stream>.body{max-height:26rem;overflow:auto" in CSS
    plain = re.search(r"(?:^|\n)\.card \.body\{([^}]*)\}", CSS)
    assert plain and "max-height" not in plain.group(1), (
        "a plain card's body is capped again, and then the narrow block would have a job"
    )
