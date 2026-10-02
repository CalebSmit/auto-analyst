"""P143: the Setup page handed out a link it did not answer to.

Read off the source, both halves side by side:

    routed   #profile=   #files=
    linked   #profile=   #settings=

So `#settings=` was a link the page ignored on arrival. It worked when clicked, because the
same element carries `data-act="settings"` and the ACTIONS table handles that - and did
nothing at all when pasted into a message or reloaded, which is the only reason a control is
a link rather than a button. And `#files=` was a destination the router knew and nothing
reached: built, and wired to nothing.

The comment over the router says what it is for - *"so the person who owns the missing
judgements can be sent straight to them"* - and that is the half that worked.

One table now, read in both directions by a test, because this drifted by one side being
edited without the other.

(Separately: `.btn` exists so an anchor can look like a button, and half the theme's rules
named only `button`. A control that is also a link has to be an anchor, so `files` and
`settings` rendered as solid buttons beside the quiet ones they sit with until the pairing
was made everywhere.)
"""

from __future__ import annotations

import re
from pathlib import Path

from admin.page import PAGE as SETUP
from ui.theme import CSS

ROOT = Path(__file__).resolve().parents[2]


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", SETUP, re.S))


def routed() -> set[str]:
    """The prefixes the router answers to, read from the table it is built on."""
    table = re.search(r"const DEEP_LINKS = \{(.*?)\};", script(), re.S)
    assert table, "the deep-link table is gone"
    return set(re.findall(r"'([a-z]+=)'", table.group(1)))


def linked() -> set[str]:
    return set(re.findall(r'href="#([a-z]+=)', SETUP))


# ----------------------------------------------------------- the two halves are one set


def test_every_link_the_page_hands_out_is_one_it_answers_to() -> None:
    """`#settings=` was handed out and ignored. Pasted into a message it opened the Setup
    page and nothing else, which is worse than no link: it looks like it worked."""
    unanswered = linked() - routed()
    assert unanswered == set(), f"the page links to {unanswered} and the router ignores them"


def test_every_link_the_router_answers_to_is_one_something_reaches() -> None:
    """`#files=` was a destination nothing linked to - reachable only by typing the URL."""
    orphaned = routed() - linked()
    assert orphaned == set(), f"the router handles {orphaned} and nothing on the page links there"


def test_there_are_three_and_they_are_the_three_an_engagement_has() -> None:
    """Named, so that adding a fourth control without a link, or a fourth link without a
    route, is a failure rather than a silence."""
    assert routed() == {"profile=", "settings=", "files="}


def test_the_table_is_the_only_place_the_prefixes_are_written() -> None:
    """The drift was two lists. One table, and the router reads it rather than repeating
    it, so there is nowhere for a fourth to be added to only one of them."""
    body = script()
    assert "for (const [prefix, open] of Object.entries(DEEP_LINKS))" in body
    assert body.count("startsWith(prefix)") == 1
    assert "startsWith('profile=')" not in body, "a prefix is tested outside the table again"


# --------------------------------------------- a link opens what its control opens


def test_each_link_names_the_handler_its_control_names() -> None:
    """The anchor carries both: `href` for arriving, `data-act` for clicking. If the two
    disagreed, a link would open one thing when pasted and another when pressed."""
    body = script()
    table = re.search(r"const DEEP_LINKS = \{(.*?)\};", body, re.S)
    assert table
    for prefix, handler in re.findall(r"'([a-z]+)=':\s*(\w+)", table.group(1)):
        # The rendered page, so the f-string's doubled braces are single by now.
        anchor = re.search(rf'href="#{prefix}=[^"]*"[^>]*', SETUP)
        assert anchor, f"nothing links to #{prefix}="
        act = re.search(r'data-act="(\w+)"', anchor.group(0))
        assert act, f"the #{prefix}= link carries no action, so clicking it reloads the page"
        assert act.group(1) == handler, (
            f"#{prefix}= opens {handler} on arrival and {act.group(1)} on click"
        )


def test_a_control_that_is_also_a_link_is_an_anchor() -> None:
    """A button cannot be pasted. The three that deep-link are anchors styled as buttons."""
    for prefix in ("files=", "settings=", "profile="):
        assert f'href="#{prefix}' in SETUP, f"#{prefix} is not reachable from the page"
    assert '<a class="btn quiet" href="#files=' in SETUP
    assert '<a class="btn quiet" href="#settings=' in SETUP


# ------------------------------------------- and it looks like the controls beside it


def test_the_theme_styles_an_anchor_that_is_a_button_like_a_button() -> None:
    """`.btn` is paired with `button` in the base rule and was not in the modifiers, so an
    anchor got the shape and none of the variants - a quiet link rendering solid beside the
    quiet buttons it sits with."""
    for variant in ("primary", "quiet", "ghost", "small"):
        assert f"button.{variant},.btn.{variant}{{" in CSS, (
            f".btn.{variant} is unstyled, so an anchor with that class looks wrong"
        )


def test_no_modifier_is_written_for_a_button_alone() -> None:
    """Swept rather than listed: any `button.x{` with no `.btn.x` beside it is the next one
    of these."""
    alone = [
        m.group(1)
        for m in re.finditer(r"(?:^|[,}])\s*button\.(\w[\w.]*)\s*(?=[,{])", CSS, re.M)
        if f".btn.{m.group(1)}" not in CSS
    ]
    assert alone == [], f"these modifiers style a button and not an anchor: {alone}"
