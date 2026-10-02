"""P46: the design language, held to what it claims.

A stylesheet is the one part of a codebase where "it looks fine" is usually the whole of the
review, and it is where a promise like "legible" quietly stops being true. These tests are the
parts of the design that are facts: the contrast of every ink against the paper it is read on,
the scales every value comes from, and the states a person who is not using a mouse depends on.
"""

from __future__ import annotations

import re

import pytest

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.help_page import PAGE as HELP
from ui.theme import CSS

PAGES = {"setup": SETUP, "activity": ACTIVITY, "analytics": ANALYTICS, "help": HELP}


def _tokens() -> dict[str, str]:
    """Every token that resolves to a colour, read out of the stylesheet rather than repeated
    here - following one token that names another, which is how the palette is built."""
    declared = dict(re.findall(r"--([\w-]+):\s*([^;}]+)[;}]", CSS))
    resolved: dict[str, str] = {}
    for name, raw in declared.items():
        seen, value = 0, raw.strip()
        while value.startswith("var(--") and seen < 5:
            value = declared.get(value[6:].split(")")[0], "").strip()
            seen += 1
        if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            resolved[name] = value
    return resolved


TOKENS = _tokens()


def body_of(page: str) -> str:
    """The page without the stylesheet it carries: every page inlines the whole sheet, so the
    sheet's own values are not the page inventing one."""
    return re.sub(r"<style>.*?</style>", "", page, flags=re.S)


def luminance(value: str) -> float:
    raw = value.lstrip("#")
    channels = [int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# ------------------------------------------------------------------ ink on paper


@pytest.mark.parametrize(
    ("token", "floor", "what"),
    [
        ("ink", 10.0, "body text"),
        ("ink-2", 6.0, "secondary text"),
        ("ink-3", 4.5, "the quiet grey every explanatory line is set in"),
    ],
)
def test_ink_is_legible_on_the_paper_behind_it(token: str, floor: float, what: str) -> None:
    """Before this the quiet grey was the brand's own neutral at 3.42:1 - under the 4.5:1
    floor for normal text, and it carried the one-line explanation under every panel title,
    every caption under every figure and every hint under every field."""
    assert token in TOKENS, f"--{token} is not a literal value, so it cannot be measured"
    ratio = contrast(TOKENS[token], TOKENS["bg"])
    assert ratio >= floor, f"--{token} ({what}) is {ratio:.2f}:1 on the paper, under {floor}:1"


def test_the_quiet_grey_is_not_used_for_anything_that_must_be_read() -> None:
    """`--ink-4` is below the floor by design - it is for a placeholder, a disabled control
    and a node a run never reached. Anything a person has to read uses a darker one."""
    assert contrast(TOKENS["ink-4"], TOKENS["bg"]) < 4.5, "then it should be --ink-3"
    for rule in re.findall(r"\.(?:card \.why|metric \.c|r \.d|note)\{[^}]*\}", CSS):
        assert "--ink-4" not in rule, f"explanatory text set in the decorative grey: {rule[:60]}"


def test_meaning_carrying_colours_are_legible_where_they_are_used() -> None:
    """A pill's text sits on its own soft wash, not on the card."""
    for ink, wash in (("good", "good-soft"), ("bad", "bad-soft"), ("accent-ink", "accent-soft")):
        ratio = contrast(TOKENS[ink], TOKENS[wash])
        assert ratio >= 4.5, f"--{ink} on --{wash} is {ratio:.2f}:1"


def test_the_brand_colours_are_still_the_brand_colours() -> None:
    """The palette is the firm's. Everything else in the sheet is a mix of these or a
    measured value derived from them; these are not ours to drift."""
    assert TOKENS["brand-p1"] == "#0c2e3f"
    assert TOKENS["brand-p2"] == "#4f758b"
    assert TOKENS["brand-s2"] == "#512a44"
    assert TOKENS["brand-s3"] == "#c19b2b"


# ------------------------------------------------------------------ the scales


def test_there_is_one_spacing_scale_and_one_type_scale() -> None:
    for name in ("s1", "s2", "s3", "s4", "s5", "s6", "s7"):
        assert f"--{name}:" in CSS, f"the spacing scale is missing --{name}"
    for name in ("t-display", "t-title", "t-body", "t-sm", "t-xs", "t-label"):
        assert f"--{name}:" in CSS, f"the type scale is missing --{name}"


@pytest.mark.parametrize("name", PAGES)
def test_no_page_invents_a_colour_or_a_type_size(name: str) -> None:
    """A page that reaches for its own hex or its own pixel size is a page that will not
    follow the next change to the palette - and a pixel size does not follow the root size
    the whole tool is scaled from."""
    body = body_of(PAGES[name])
    assert re.findall(r"#[0-9a-fA-F]{6}\b", body) == [], f"{name} defines its own colour"
    sizes = re.findall(r"font-size:\s*[\d.]+px", body)
    assert sizes == [], f"{name} sets type in pixels: {sizes[:3]}"


def test_the_stylesheet_takes_its_own_values_from_the_scales() -> None:
    """Spot-check the components that carry the page: if these stop using the tokens, the
    scales are decoration."""
    for rule in ("--s4) var(--s5)", "var(--t-display)", "var(--t-label)"):
        assert rule in CSS, f"the stylesheet no longer uses {rule}"


# ------------------------------------------------------------------ states


def test_the_keyboard_can_see_where_it_is() -> None:
    """One ring for the whole tool, and only for the keyboard - a mouse click should not
    leave an outline behind it.

    It names a token rather than a colour: P145 found the ring at 2.40:1 on the navy chrome,
    which is where a keyboard arrives first, so the ground decides the colour and the rule
    stays one rule. What this test is for is that there is still exactly one of them - what
    colour it comes out is measured in `tests/p145`, against each ground it lands on.
    """
    assert ":focus-visible{outline:2px solid var(--ring)" in CSS
    assert ":focus{outline" not in CSS, "a focus ring on every click is noise"


def test_motion_is_a_preference() -> None:
    assert "@media (prefers-reduced-motion:reduce)" in CSS
    assert "animation-duration:.001ms!important" in CSS


def test_emphasis_is_spent_where_the_meaning_is() -> None:
    """The map draws 118 nodes and a run touches eight. The ones it did not touch are
    named, not drawn: no chip, no border - or they are the loudest thing on the screen."""
    untouched = re.search(r"\n\.node\{([^}]*)\}", CSS)
    assert untouched, "the map's own rule is gone"
    assert "box-shadow:none" in untouched.group(1)
    assert "background:transparent" in untouched.group(1)


def test_a_dialog_and_a_panel_are_not_the_same_surface() -> None:
    """Elevation says which one is on top of the other, which is the whole of what a modal
    has to communicate before it is read."""
    assert "--shadow:" in CSS and "--shadow-modal:" in CSS
    assert (
        ".modal>.card{width:min(56rem,100%);max-height:100%;box-shadow:var(--shadow-modal)" in CSS
    )


def test_an_engagement_row_survives_a_long_client_name() -> None:
    """Five controls and a name were on one line, so "Brightwater Fabrication LLC" wrapped
    to three and the buttons crowded the edge."""
    assert ".r.engagement{flex-wrap:wrap" in CSS
    assert ".r.engagement .acts{flex:1 0 100%" in CSS
    assert 'class="r engagement"' in SETUP
