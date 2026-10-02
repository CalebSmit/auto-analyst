"""C80 - the two phases in this block are both about a thing written down twice.

* **P146.** The rule is *a page builds no handler out of data; it reaches one through the
  `ACTIONS` table.* Six tests spelled that rule `"onclick=" not in page`, which is one of
  about seventy ways to break it, and three handlers written `oninput=` and `onchange=` sat
  under all six. They existed because the dispatcher listened for `click` and `keydown`
  only, so a field had nowhere to go: a guard that forbids a workaround without providing
  the road gets worked around.
* **P147.** The Run trace's key was five swatches painted by hand, and measured against the
  nodes they stood for, all five disagreed - including the two the panel's own sentence
  calls *"the two answers it matters most not to confuse"*, which it drew as two near-white
  bordered squares when one of them has no box at all.

What a checkpoint can ask that neither phase could.

**There are two keys in this product**, in two files, and P147 only touched one. The map's
was repaired for this same drift in an earlier phase. Both have to still be the drawing's own
rules, and neither phase's scope could see both.

**And the guards have to agree about what the rule is.** P146 put one definition of "an
inline handler" in `tests/reading.py` and pointed six tests at it. A seventh written
tomorrow would spell it the old way, because the old way is the obvious way - so the sweep
here is over the test suite itself.
"""

from __future__ import annotations

import re
from pathlib import Path

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.map_view import MAP_HTML, MAP_STYLE
from tests.reading import inline_handlers
from ui.theme import CSS, SHELL

ROOT = Path(__file__).resolve().parents[3]
PAGES = ((SETUP, "Setup"), (ACTIVITY, "Activity"), (ANALYTICS, "Analytics"))


# --------------------------------------------------- two keys, and both are their drawing


KEYS = {
    "the run trace": (ACTIVITY, r'<div class="legend">(.*?)</div>', "node", CSS),
    "the map": (MAP_HTML, r'<span class="map-legend"[^>]*>(.*?)</span>\s*<', "mn", MAP_STYLE),
}


def key_of(which: str) -> tuple[str, str, str]:
    page, pattern, node_class, sheet = KEYS[which]
    found = re.search(pattern, page, re.S)
    assert found, f"{which} has no key"
    return found.group(1), node_class, sheet


def test_every_key_in_the_product_is_drawn_by_its_drawings_own_rules() -> None:
    """The property the map's key was repaired for and the trace's key did not have. Said
    here over both, because one of them having it is how the other one lost it."""
    for which in KEYS:
        markup, node_class, _ = key_of(which)
        swatches = re.findall(rf'class="{node_class} (\w+)"', markup)
        assert swatches, f"{which}'s key draws nothing with the drawing's own class"
        assert "style=" not in markup or "background" not in markup, (
            f"{which}'s key paints a swatch itself"
        )


def test_every_state_a_key_shows_is_a_state_its_sheet_defines() -> None:
    """A swatch naming a class no rule defines renders as nothing at all - which is how a
    key loses an entry without anybody deleting one."""
    for which in KEYS:
        markup, node_class, sheet = key_of(which)
        for state in set(re.findall(rf'class="{node_class} (\w+)"', markup)):
            assert re.search(rf"\.{node_class}\.{state}\b", sheet), (
                f"{which}'s key draws {state!r} and its sheet has no rule for it"
            )


def test_neither_key_has_a_rule_of_its_own_that_decides_a_colour() -> None:
    """The one place a state's appearance is decided is the node's rule. A key that sizes
    its swatch is fine - a key that colours one has become a second copy again."""
    for name, pattern in (
        ("the run trace", r"\.legend[^{}]*\{([^}]*)\}"),
        ("the map", r"#dmap \.map-legend[^{}]*\{([^}]*)\}"),
    ):
        sheet = CSS if name == "the run trace" else MAP_STYLE
        states = ("background:var(--good", "background:var(--bad", "background:var(--accent")
        for body in re.findall(pattern, sheet):
            for decides in states:
                assert decides not in body, f"{name}'s key rule picks a state's colour"


# ---------------------------------------------- and the guards agree about what the rule is


def test_no_guard_still_spells_the_rule_as_one_attribute() -> None:
    """The sweep over the suite itself. Six tests said `"onclick=" not in page` and meant
    *no handler is wired in the markup*; a seventh would say it the same way, because that
    is the obvious way to say it and it is wrong in the same direction every time.
    """
    import ast

    stray = []
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        # Asked of the assertions, not of the file's text. Every one of these modules
        # explains the defect in its docstring, and the explanation contains the string it
        # is explaining - which is the failure `tests/reading.py` was written for, met here
        # by walking the tree instead of widening a regex until the prose stops matching.
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Assert):
                continue
            written = ast.get_source_segment(source, node.test) or ""
            if re.search(r'["\']on\w+=?["\']\s+not in', written):
                stray.append(f"{path.relative_to(ROOT)}:{node.lineno}  {written[:72]}")
    assert stray == [], (
        "a guard spells the rule as one attribute instead of asking tests.reading:\n"
        + "\n".join(stray)
    )


def test_the_one_definition_is_the_one_every_surface_is_asked_about() -> None:
    """And it still answers. A sweep that quietly stopped matching would leave every one of
    those six tests green and checking nothing, which is the state they were just in."""
    for page, where in PAGES:
        assert inline_handlers(page) == [], f"{where} wires a handler in its markup"
    assert inline_handlers('<i onchange="x()"></i>'), "the definition has stopped matching"


def test_a_control_reaches_its_handler_one_way_on_every_surface() -> None:
    """Three consoles, one dispatcher, one table of the events it carries. A page that bound
    its own listener would be a second mechanism, and the next field would use whichever one
    the person writing it happened to meet first."""
    assert SHELL.count("const CLIMBS = {") == 1, "there is more than one table of events"
    for page, where in PAGES:
        own = page.split("</style>")[0]
        for shared in (CSS, MAP_STYLE):
            own = own.replace(shared, "")
        assert "addEventListener" not in own, f"{where} binds a listener in its own styles"
    # Only the dispatch binding. The shell legitimately listens for other things on its own
    # account - `visibilitychange` to stop polling in a background tab, `keydown` to close a
    # modal on Escape - and those are not a second way for a control to reach a handler.
    by_hand = re.findall(r"document\.addEventListener\('(\w+)',\s*_fire\)", SHELL)
    assert by_hand == [], (
        f"the dispatcher is bound by hand as well as from the table: {by_hand}"
    )
    assert "for (const kind of Object.keys(CLIMBS)) document.addEventListener" in SHELL, (
        "nothing binds the table, so the events it lists are a list and not a behaviour"
    )
