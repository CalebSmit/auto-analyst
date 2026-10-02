"""C78 - the screen is the shape of what is on it.

Two phases from one design review, both found by opening the product and measuring rather
than by reading its source.

* **P142.** The board handed every panel the same share of the viewport whatever was in it.
  Seven of twenty panels hid content behind an inner scrollbar - one showing a sixth of what
  it held - while eight sat under seventy per cent full, on the same screens. Rows are as
  tall as their content now, the page scrolls, the chrome is sticky so the counts stay in
  view, and the three panels that still scroll are marked as streams because their content
  has no end.
* **P143.** The Setup page handed out `#settings=` and ignored it on arrival, and answered
  to `#files=` which nothing linked to. One table now, read in both directions.

What a checkpoint can ask that a phase cannot: whether the three consoles still agree after
a change made in the one stylesheet they share, and whether the two mechanisms this block
introduced - `stream` and `DEEP_LINKS` - are each one thing rather than three copies.
"""

from __future__ import annotations

import re
from pathlib import Path

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from tests.reading import inline_handlers
from ui.theme import CSS

ROOT = Path(__file__).resolve().parents[3]

BOARDS = ((SETUP, "Setup"), (ACTIVITY, "Activity"), (ANALYTICS, "Analytics"))


# --------------------------------------------- one layout, across the three consoles


def test_every_board_sizes_its_rows_the_same_way() -> None:
    """The change was made once in the theme and three times in the pages, which is where
    three consoles start behaving differently at the same size."""
    for page, where in BOARDS:
        rows = re.search(r"grid-template-rows:([^;]*);", page)
        assert rows, f"{where} names no rows"
        assert "fr" not in rows.group(1), f"{where} is back to a share of the screen"


def test_the_decision_lives_in_the_theme_and_the_pages_only_name_areas() -> None:
    """A page may say which panel goes where. Whether a panel scrolls is one decision for
    the product, and it is in the sheet all three inline."""
    assert ".board{display:grid;gap:var(--s3);align-content:start}" in CSS
    assert ".card.stream>.body{max-height:26rem;overflow:auto" in CSS
    # A page may scroll and cap a component of its own - the map view's side panel is
    # `#dmap .side-in`, and how that behaves is the map's business. What it may not do is
    # say how a *panel on the board* behaves, because then two consoles differ at the same
    # size and only one of them is in the sheet they share.
    for page, where in BOARDS:
        own = page.split("</style>")[0].split(CSS)[-1]
        for rule in re.findall(r"^\s*([^{\n@]+)\{([^}]*)\}", own, re.M):
            selector, body = rule[0].strip(), rule[1]
            if ".card" not in selector and ".board" not in selector:
                continue
            for decides in ("overflow", "max-height"):
                assert decides not in body, (
                    f"{where} decides {decides} for {selector!r}, which belongs to the sheet"
                )


def test_a_stream_is_declared_in_markup_and_nowhere_else() -> None:
    """Being a stream is a fact about what a panel holds. If a page could make something a
    stream from script, the reason would stop travelling with it."""
    for page, where in BOARDS:
        for found in re.findall(r'class="card stream"', page):
            assert found
        assert "classList.add('stream')" not in page, f"{where} makes a stream at runtime"
    streams = sum(page.count('class="card stream"') for page, _ in BOARDS)
    assert streams == 3, f"{streams} streams; the three are the log, the map and the seams"


# ------------------------------------------------ a link is a link on every surface


def test_only_one_console_deep_links_and_it_does_it_once() -> None:
    """Setup is the one with things to link into. The property worth holding is that the
    mechanism is one table, so a fourth destination cannot be half-added."""
    assert "const DEEP_LINKS" in SETUP
    assert SETUP.count("const DEEP_LINKS") == 1
    for page, where in ((ACTIVITY, "Activity"), (ANALYTICS, "Analytics")):
        assert "DEEP_LINKS" not in page, f"{where} grew a second copy of the table"


def test_the_two_halves_of_every_deep_link_agree() -> None:
    """Said again here because this is what drifted, and a checkpoint that took the phase's
    word for it would be the apparatus not working."""
    script = "\n".join(re.findall(r"<script>(.*?)</script>", SETUP, re.S))
    table = re.search(r"const DEEP_LINKS = \{(.*?)\};", script, re.S)
    assert table
    routed = set(re.findall(r"'([a-z]+=)'", table.group(1)))
    linked = set(re.findall(r'href="#([a-z]+=)', SETUP))
    assert routed == linked, f"routed {routed} and linked {linked}"


def test_every_console_still_builds_its_handlers_from_the_actions_table() -> None:
    """`ui/who.py`'s rule, which the anchors had to keep: a control that is also a link
    still reaches its handler by name rather than by anything in the URL."""
    for page, where in BOARDS:
        assert inline_handlers(page) == [], f"{where} wires a handler inline"
        assert "javascript:" not in page, f"{where} has a javascript: URL"
    for anchor in re.findall(r"<a [^>]*href=\"#[a-z]+=[^\"]*\"[^>]*>", SETUP):
        assert "data-act=" in anchor, f"a deep link with no action: {anchor[:70]}"


# --------------------------------------------------- and the product still looks like one


def test_a_control_looks_the_same_whether_it_is_a_button_or_a_link() -> None:
    """Half the theme's modifiers named only `button`, so the two anchors rendered solid
    beside the quiet buttons they sit with."""
    alone = [
        m.group(1)
        for m in re.finditer(r"(?:^|[,}])\s*button\.(\w[\w.]*)\s*(?=[,{])", CSS, re.M)
        if f".btn.{m.group(1)}" not in CSS
    ]
    assert alone == [], f"these style a button and not an anchor: {alone}"


def test_the_chrome_is_the_same_on_every_page_and_stays_put() -> None:
    top = re.search(r"^\.top\{[^}]*\}", CSS, re.M)
    assert top and "position:sticky" in top.group(0)
    for page, where in BOARDS:
        assert 'class="top"' in page, f"{where} does not use the shared chrome"
