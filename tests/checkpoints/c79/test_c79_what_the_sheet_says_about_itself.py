"""C79 - the sheet states its own floors, and the statement is true.

Two phases from one review, both found by opening the product and measuring rather than by
reading its source.

* **P144.** Six pieces of text a person has to read sat below the 4.5:1 this theme sets for
  a word - a locator, a formula, the list of checks that did not run, the count of runs that
  need somebody. The hand-written check over four selectors had missed every one.
* **P145.** Three cues that are a shape rather than a word sat below the 3:1 a non-text
  indicator gets - a control's own boundary at 1.54:1, the focus ring at 2.40:1 on the navy
  chrome, and two states of the map that were the same colour.

What a checkpoint can ask that neither phase can. Both phases wrote measurements into the
sheet's own prose: *"body text at 12:1, secondary at 7:1, quiet at 4.6:1"*, and *"3.13 on
white, 3.06, 3.02 and 3.03 on the others"*. A comment is the one part of a stylesheet nothing
checks, so a number in one is a claim that stops being true silently - and these particular
numbers are the whole argument for the colours underneath them. Here they are read back out
of the prose and recomputed from the tokens.

And the two sweeps have to agree on the thing they share: every colour in this product comes
from a token, so that *any* sweep over the tokens is a sweep over the product. A page that
writes a literal is outside both phases' reach at once, and that is exactly the shape of what
P144 found - six colours written inline, where neither the theme's own checks nor anybody
reading the sheet would ever meet them.
"""

from __future__ import annotations

import re

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.map_view import MAP_STYLE as MAP_CSS
from ui.theme import CSS

PAGES = ((SETUP, "Setup"), (ACTIVITY, "Activity"), (ANALYTICS, "Analytics"))

WORD = 4.5  # WCAG 1.4.3, for normal text
SHAPE = 3.0  # WCAG 1.4.11, for anything that is not text


# --------------------------------------------------------------- the measuring, once


def rgba(colour: str) -> tuple[float, float, float, float]:
    if colour.startswith(("rgba(", "rgb(")):
        parts = [float(p) for p in re.findall(r"[\d.]+", colour)]
        return (*parts[:3], parts[3] if len(parts) > 3 else 1.0)  # type: ignore[return-value]
    h = colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)


def over(top: str, bottom: str) -> str:
    f, b = rgba(top), rgba(bottom)
    a = f[3]
    return "#" + "".join(f"{round(f[i] * a + b[i] * (1 - a)):02x}" for i in range(3))


def luminance(colour: str) -> float:
    chan = [v / 255 for v in rgba(colour)[:3]]
    lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in chan]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def tokens() -> dict[str, str]:
    block = CSS[CSS.index(":root{") : CSS.index("}", CSS.index(":root{"))]
    raw = dict(re.findall(r"--([\w-]+):\s*([^;]+);", block))
    out: dict[str, str] = {}
    for _ in range(4):
        for name, value in raw.items():
            value = value.strip()
            hop = re.fullmatch(r"var\(--([\w-]+)\)", value)
            if hop and hop.group(1) in out:
                out[name] = out[hop.group(1)]
            elif value.startswith(("#", "rgba(")):
                out[name] = value
    return out


# ------------------------------------------------ the prose, held to the measurement


def test_the_four_inks_measure_what_the_sheet_says_they_measure() -> None:
    """The comment over them names a ratio per weight. Each one is recomputed against the
    paper, to one decimal place, because a number in a comment is a claim nothing else in a
    build ever checks."""
    t = tokens()
    said = re.search(
        r"body text at\s*\n?\s*([\d.]+):1, secondary at ([\d.]+):1, quiet at ([\d.]+):1", CSS
    )
    assert said, "the sheet has stopped saying what its inks measure"
    for weight, claimed in zip(("ink", "ink-2", "ink-3"), said.groups(), strict=True):
        actual = contrast(t[weight], t["bg"])
        assert abs(actual - float(claimed)) < 0.5, (
            f"--{weight} is {actual:.1f}:1 and the sheet says {claimed}:1"
        )


def test_the_control_edge_measures_what_the_sheet_says_it_measures() -> None:
    """P145 wrote four numbers into the prose, one per surface. They are in the order the
    surfaces are declared, and that is the order they are checked in."""
    said = re.search(r"([\d.]+) on white, ([\d.]+), ([\d.]+) and ([\d.]+) on the others", CSS)
    assert said, "the sheet has stopped saying what a control's edge measures"
    t = tokens()
    papers = [t["surface"]] + [
        v for n, v in t.items() if n in ("surface-2", "surface-sunken", "bg")
    ]
    for paper, claimed in zip(papers, said.groups(), strict=True):
        actual = contrast(over(t["line-strong"], paper), paper)
        assert abs(actual - float(claimed)) < 0.1, (
            f"the edge is {actual:.2f}:1 on {paper} and the sheet says {claimed}"
        )


def test_both_floors_are_stated_and_both_are_the_real_ones() -> None:
    """One sheet, two bars, and the sheet says which is which. P144 put the first in prose
    and P145 the second; a checkpoint is where they have to still be one theme."""
    assert "4.6:1 - the floor" in CSS or f"{WORD}" in CSS, "the floor for a word is not stated"
    assert "3:1" in CSS, "the floor for a shape is not stated"
    t = tokens()
    assert contrast(t["ink-3"], t["bg"]) >= WORD, "the quiet ink no longer clears its own floor"
    assert contrast(over(t["line-strong"], t["surface"]), t["surface"]) >= SHAPE


# ------------------------------------- and every colour is a token, so a sweep is a sweep

def own_rules(page: str) -> str:
    """What a page adds to the two stylesheets it is served with.

    The Activity console embeds the map's sheet as well as the theme's, so subtracting only
    the theme leaves the map's rules looking like the console's own - which would make this
    file report a focus ring the map has had since P112.
    """
    head = page.split("</style>")[0]
    for shared in (CSS, MAP_CSS):
        if shared in head:
            head = head.replace(shared, "")
    return head




LITERAL = re.compile(r"(?:color|background|border(?:-\w+)?|outline|fill|stroke)\s*:[^;{}\"']*"
                     r"(#[0-9a-fA-F]{3,8}\b|\brgba?\()")


def test_no_page_writes_a_colour_of_its_own() -> None:
    """What makes both phases' sweeps complete rather than approximately complete.

    Each phase measures tokens and then looks for them in the sheet and the three pages. A
    page that wrote `#949a9b` instead of `var(--ink-4)` would be invisible to both, and that
    is the exact shape of what P144 found - six colours set on the element, where no rule
    named them and nobody reading the stylesheet would ever meet them. They were at least
    tokens, which is why a sweep could be written at all. This is the property that made
    that possible, said out loud so it cannot quietly stop being true.
    """
    stray = []
    for page, where in PAGES:
        own = own_rules(page)
        for match in LITERAL.finditer(own):
            line = own[max(0, match.start() - 60) : match.end() + 10].replace("\n", " ")
            stray.append(f"{where}, in its own rules: ...{line.strip()}")
        for match in re.finditer(r'style="[^"]*(?:color|background)\s*:[^"]*"', page):
            if LITERAL.search(match.group(0)):
                stray.append(f"{where}, on an element: {match.group(0)[:80]}")
    assert stray == [], "a page writes a colour nothing can sweep:\n" + "\n".join(stray)


def declared() -> set[str]:
    """Every custom property this product declares anywhere - colours, spacing, type, and the
    three the map sets on a node. Wider than `tokens()`, which resolves colours only."""
    return set(re.findall(r"--([\w-]+)\s*:", CSS + MAP_CSS))


def test_every_token_a_page_names_is_one_the_theme_defines() -> None:
    """The other half of the same guarantee. `var(--ink-5)` renders as nothing at all - no
    error, no warning, just text the colour of whatever it inherited - so a typo here is
    invisible in the browser and invisible to a sweep that only walks the tokens that exist.
    """
    known = declared()
    stray = []
    for text, where in ((CSS, "the theme"), (MAP_CSS, "the map")) + PAGES:
        for name in set(re.findall(r"var\(--([\w-]+)\)", text)):
            if name not in known:
                stray.append(f"{where}: --{name}")
    assert stray == [], "a token is used and never defined:\n" + "\n".join(sorted(stray))


# -------------------------------------------------------- the three consoles still agree


# Where each focus ring is actually drawn. The ground is the only hand-written part: it is
# where the element sits on the screen, which no amount of reading the rule can tell you.
# The colour is read out of the rule, because a table of colours here would be a table this
# file measures against itself - the first draft did exactly that, and stayed green while the
# chip's ring was changed to one that fails on navy.
GROUNDS = {
    ":focus-visible": ("bg", "anything on paper, which is most of the tool"),
    ".chip:focus-visible": ("navy", "the chip lives in the navy chrome"),
    "#dmap .mn:focus-visible": ("surface-sunken", "a node, on the map's stage"),
}


def rings() -> dict[str, str]:
    """Each focus ring in the product, and the token it paints with, read off the rules."""
    found = re.findall(
        r"([#.\w \-\[\]=\"]*:focus-visible)\{outline:[\d.]+px solid var\(--([\w-]+)\)",
        CSS + MAP_CSS,
    )
    return {selector.strip(): colour for selector, colour in found}


def test_every_focus_ring_in_the_product_clears_the_bar_where_it_lands() -> None:
    """A checkpoint's question rather than a phase's. P145 fixed the global ring and left two
    more standing - one in the theme and one in the map's own sheet - and neither phase's
    scope reached both files."""
    t = tokens() | {"ring": tokens()["accent"]}
    painted = rings()
    assert set(painted) == set(GROUNDS), (
        f"the rings in the product are {sorted(painted)}, "
        f"and the ones measured here are {sorted(GROUNDS)}"
    )
    for selector, (ground, why) in GROUNDS.items():
        # Composited, because half this palette is navy at an opacity and a ring painted in
        # one of those is a ring you can see through. Reading the token as written makes
        # `--line` at .14 measure as solid navy, which is 11:1 and a lie.
        on = t[ground]
        ratio = contrast(over(t[painted[selector]], on), on)
        assert ratio >= SHAPE, (
            f"{selector} paints --{painted[selector]} at {ratio:.2f}:1 on --{ground} - {why}"
        )


def test_no_console_keeps_a_copy_of_a_decision_the_sheet_makes() -> None:
    """Both phases moved a decision into the shared sheet. A console that kept a copy would
    be the defect this build is named for, in the one place three surfaces have to match."""
    for page, where in PAGES:
        own = own_rules(page)
        assert "focus-visible" not in own, f"{where} grew a focus ring of its own"
        assert "--line-strong:" not in own, f"{where} redefines the control edge"
        assert "--ring:" not in own, f"{where} redefines the ring outside the sheet"


def test_the_map_takes_its_colours_from_the_same_palette() -> None:
    """It is the one view with a stylesheet of its own, so it is the one that can drift
    without any page changing."""
    named = set(re.findall(r"var\(--([\w-]+)\)", MAP_CSS))
    known = set(tokens()) | {"edge", "wash", "mark", "ring"}
    unknown = {n for n in named if n not in known and not n.startswith(("s", "t-", "radius"))}
    assert unknown <= {"shadow", "shadow-lift", "shadow-modal", "sans", "mono", "ease"}, (
        f"the map names tokens the theme does not define: {unknown}"
    )
