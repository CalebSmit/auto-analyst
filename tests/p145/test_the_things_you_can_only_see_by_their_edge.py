"""P145: three cues that are a shape rather than a word, all three under the 3:1 bar.

P144 measured every piece of *text* against the 4.5:1 floor. This measures the things that
carry meaning without being text at all, which WCAG 1.4.11 holds to 3:1 instead - a
control's own boundary, the ring that says where the keyboard is, and a fill that stands
for a state. Measured in the browser against the surface actually behind each one:

    1.54:1   a button's and a field's border          --line-strong on every surface
    2.40:1   the focus ring, on the navy chrome       --accent on #123b50
    1.01:1   "never got to" against "not used here"   --warn-soft against --surface-2

The first is the one with consequence. On a white panel a white button is told from the
panel by that line and by nothing else, and in an engagement's row the control it marks -
Pause, the one that changes state - sits beside five that only open a panel and are plain
text. The line carrying that distinction was the faintest thing in the row.

The third is worse than faint, it is absent: the far view of the map drops the labels and
says everything with fill, every state that means *something happened* fills solid - and
`blocked` was the one left out of that rule, so it kept the pale wash it wears up close and
landed on the same colour as `notreached`. Those two mean opposite things. One is "the run
never got here because it stopped"; the other is "this recipe does not include this part".

**The measure, and why it is two different ones.** Against the plate a state is read, so
that is a contrast ratio and the bar is 3:1. Against *each other* two states are told
apart, and a contrast ratio cannot say that: passed and running measure 1.25:1 and are
green and blue. That one is a perceptual distance - CIE76, bar of 10, about four
just-noticeable differences. The first draft of this file used the ratio for both and went
red on blue against gold, which is the sheet's own mistake reappearing in the test for it.

Both are derived rather than listed. The six states are read off the legend, each one's
fill is resolved through the same cascade the browser walks, and the only thing written
down by hand is which states *mean* something happened - because that is the fact the
defect turned on and the one thing no amount of reading the CSS can tell you.
"""

from __future__ import annotations

import re

from ops.console.map_view import MAP_HTML as MAP_MARKUP
from ops.console.map_view import MAP_STYLE as MAP_CSS
from ui.theme import CSS

# ------------------------------------------------------------------ measuring

BAR = 3.0  # WCAG 1.4.11, for anything that is not a word


def tokens() -> dict[str, str]:
    """Every `:root` token resolved to a literal, following `var()` one hop at a time.

    The same reader P144 used, and for the same reason: `--warn` is `var(--gold-ink)`, so
    reading only the hex declarations would quietly leave it out of the measurement.
    """
    block = CSS[CSS.index(":root{") : CSS.index("}", CSS.index(":root{"))]
    raw = dict(re.findall(r"--([\w-]+):\s*([^;]+);", block))
    out: dict[str, str] = {}
    for _ in range(4):
        for name, value in raw.items():
            value = value.strip()
            hop = re.fullmatch(r"var\(--([\w-]+)\)", value)
            if hop and hop.group(1) in out:
                out[name] = out[hop.group(1)]
            elif value.startswith("#") or value.startswith("rgba("):
                out[name] = value
    return out


def rgba(colour: str) -> tuple[float, float, float, float]:
    if colour.startswith("rgba(") or colour.startswith("rgb("):
        parts = [float(p) for p in re.findall(r"[\d.]+", colour)]
        return (*parts[:3], parts[3] if len(parts) > 3 else 1.0)  # type: ignore[return-value]
    h = colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)


def over(top: str, bottom: str) -> str:
    """Composite a possibly-transparent colour onto an opaque one.

    Every hairline in this sheet is navy at low opacity, so what a line actually looks like
    is a function of the surface under it - which is why the same token measures four
    different ratios and all four have to clear the bar.
    """
    f, b = rgba(top), rgba(bottom)
    a = f[3]
    return "#" + "".join(f"{round(f[i] * a + b[i] * (1 - a)):02x}" for i in range(3))


def luminance(colour: str) -> float:
    r, g, b, _ = rgba(colour)
    chan = [v / 255 for v in (r, g, b)]
    lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in chan]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def surfaces() -> dict[str, str]:
    """The opaque grounds this theme puts things on, read from the sheet rather than
    listed, so adding a fifth paper puts it into every measurement below."""
    t = tokens()
    return {n: v for n, v in t.items() if n == "bg" or n.startswith("surface")}


# ------------------------------------------------- a control's edge is not decoration


def test_a_control_boundary_clears_the_bar_on_every_surface_the_theme_has() -> None:
    """At .22 this measured 1.54:1 and it is the whole of what says a button is a button:
    the fill is white and so is the panel under it."""
    t = tokens()
    under = {
        name: round(contrast(over(t["line-strong"], paper), paper), 2)
        for name, paper in surfaces().items()
        if contrast(over(t["line-strong"], paper), paper) < BAR
    }
    assert under == {}, f"a control's edge is under {BAR}:1 on {under}"


def test_the_hairlines_that_are_only_decoration_stay_decoration() -> None:
    """The other two are separating content, which 1.4.11 exempts and which is most of why
    this product looks the way it does. Darkening a control must not drag them along."""
    t = tokens()
    for name in ("line", "line-soft"):
        on_white = contrast(over(t[name], t["surface"]), t["surface"])
        assert on_white < 2.0, f"--{name} is now {on_white:.2f}:1 and has stopped being a hairline"
    assert luminance(over(t["line-strong"], t["surface"])) < luminance(
        over(t["line"], t["surface"])
    ), "the control edge is no longer the darker of the two"


# The rules allowed to paint with the control edge. Each is a boundary you can press, or a
# fill standing for a state - never a rule drawn under a label. An entry here is a claim
# about what the thing is, which is the part that cannot be derived.
MAY_USE_LINE_STRONG = {
    "button,.btn": "the boundary of a button, which on a white panel is its only one",
    "button:disabled:hover": "the same button, holding its edge while it refuses",
    "input,textarea,select": "the boundary of a field",
    "#dmap .zoom": "the map's zoom control",
    "#dmap .seg": "the map's segmented control",
    "#dmap .mn.used": "a node this run touched - a state, and the fill that stands for it",
    "#dmap.far .mn.used": "the same state where the labels are gone and fill is all there is",
}


def test_every_use_of_the_control_edge_is_a_control_or_a_state() -> None:
    """Swept rather than listed, because the list of four selectors is the shape that goes
    stale - which is exactly how P144's predecessor missed six things."""
    stray = []
    for sheet, where in ((CSS, "the theme"), (MAP_CSS, "the map")):
        for match in re.finditer(r"var\(--line-strong\)", sheet):
            start = sheet.rfind("}", 0, match.start()) + 1
            selector = sheet[start : sheet.find("{", start)].strip().replace("\n", " ")
            if not any(allowed in selector for allowed in MAY_USE_LINE_STRONG):
                stray.append(f"{where}: {selector[:70]}")
    assert stray == [], "the control edge on something that is not a control:\n" + "\n".join(stray)


# ----------------------------------------------- the ring, on whatever ground it lands on


def test_the_ring_is_named_once_and_the_rule_uses_the_name() -> None:
    """It has to be a token rather than a colour, because the thing it must contrast with
    is not one colour - and a second `:focus-visible` rule for the dark case would be two
    rings to keep in step."""
    assert "--ring:var(--accent)" in CSS, "the ring has no default"
    ring_rule = re.search(r":focus-visible\{([^}]*)\}", CSS)
    assert ring_rule, "there is no focus ring"
    assert "var(--ring)" in ring_rule.group(1), "the ring rule names a colour instead of the token"
    assert CSS.count("outline:2px solid var(--accent)") == 0, "a ring still hard-codes the accent"


def test_the_default_ring_clears_the_bar_on_every_paper() -> None:
    t = tokens()
    bad = {
        name: round(contrast(t["accent"], paper), 2)
        for name, paper in surfaces().items()
        if contrast(t["accent"], paper) < BAR
    }
    assert bad == {}, f"the ring is under {BAR}:1 on {bad}"


def grounds_of(rule_body: str) -> list[str]:
    """Every literal colour a rule paints its own background with - the hex stops in a
    gradient included, because a ring on a gradient has to clear the light end too."""
    background = re.search(r"background:([^;}]*)", rule_body)
    if not background:
        return []
    text = background.group(1)
    t = tokens()
    found = re.findall(r"#[0-9a-fA-F]{6}", text)
    found += [t[n] for n in re.findall(r"var\(--([\w-]+)\)", text) if n in t]
    return found


def test_every_surface_that_redeclares_the_ring_had_to_and_the_new_one_clears_it() -> None:
    """Derived both ways. A rule that redeclares `--ring` has to be a dark one, and the
    colour it picks is measured against that rule's own background - so moving the chrome's
    gradient re-measures the ring rather than leaving a number behind that used to be true.
    """
    t = tokens()
    redeclared = [
        (sel.strip(), body)
        for sel, body in re.findall(r"(?:^|\})\s*([^{}@]+)\{([^}]*--ring:[^}]*)\}", CSS, re.M)
        if ":root" not in sel
    ]
    assert redeclared, "nothing redeclares the ring, so the dark chrome is back to 2.40:1"
    for selector, body in redeclared:
        ring = re.search(r"--ring:\s*var\(--([\w-]+)\)", body)
        assert ring, f"{selector} sets a ring that is not a token"
        colour = t[ring.group(1)]
        grounds = grounds_of(body)
        assert grounds, f"{selector} redeclares the ring but paints no background of its own"
        for ground in grounds:
            assert contrast(t["accent"], ground) < BAR, (
                f"{selector} redeclares the ring over {ground}, where the default already works"
            )
            assert contrast(colour, ground) >= BAR, (
                f"{selector}: the ring is {contrast(colour, ground):.2f}:1 on {ground}"
            )


# ------------------------------------------- the states the map says with fill alone


def legend() -> list[tuple[str, str]]:
    """The six states, read off the legend - which is the only place they are written down
    for a person, and so the only honest place to read them for a test."""
    found = re.findall(
        r'data-state="(\w+)"[^>]*>\s*<i class="mn (\w+)"></i>([^<]*)</button>', MAP_MARKUP
    )
    assert found, "the legend has no states"
    for state, swatch, _ in found:
        assert state == swatch, f"the {state!r} filter shows the {swatch!r} swatch"
    return [(state, label.strip()) for state, _, label in found]


def far_wash(state: str, ground: str) -> str:
    """What a node of this state actually looks like at the zoom where the labels are gone.

    Resolved the way the browser resolves it - the far rule wins, then the state's own
    rule, then the base `.mn`. A state with no rule of its own is the base, which is the
    case the design means by "nothing happened here".

    It takes the ground because one of these fills is not a colour but a colour at .51, and
    an alpha ignored is a measurement that did not happen: the first draft returned the
    token and `touched` read as solid navy at 17:1 wherever it appeared. That made two
    tests below pass without ever looking at the thing they name, which is this repo's own
    oldest defect wearing a new hat. Composited here so no caller can forget.
    """
    t = tokens()
    for pattern in (
        rf"#dmap\.far [^{{}}]*\.mn\.{state}\b[^{{}}]*\{{([^}}]*)\}}",
        rf"#dmap [^{{}}]*\.mn\.{state}\b[^{{}}]*\{{([^}}]*)\}}",
        r"#dmap \.mn\{([^}]*)",
    ):
        for body in re.findall(pattern, MAP_CSS):
            wash = re.search(r"--wash:\s*(?:var\(--([\w-]+)\)|(\w+))", body)
            if wash:
                literal = t["surface"] if wash.group(2) == "transparent" else t[wash.group(1)]
                return over(literal, ground)
    raise AssertionError(f"{state} has no fill at any zoom")


def plate() -> str:
    """The legend sits on its own panel, so that is the ground its swatches are read
    against - white at 92% over the sunken stage."""
    return over("rgba(255,255,255,.92)", tokens()["surface-sunken"])


def stage() -> str:
    """A node itself is drawn on the stage, not on the legend's panel. The two are a
    percent apart, but which one a thing sits on is the sort of detail that makes a
    measurement real rather than approximately real."""
    return tokens()["surface-sunken"]


# Which side of the line each state is on. This is the one thing a test cannot derive: it
# is what the state *means*, and the whole defect was a state filed on the wrong side.
SOMETHING_HAPPENED = {"passed", "failed", "active", "used", "blocked"}
NOTHING_HAPPENED = {"notreached", "pending"}


def test_the_legend_and_the_meanings_cover_each_other() -> None:
    """So a seventh state cannot be added to the drawing without someone deciding whether
    it is a thing that happened."""
    named = {state for state, _ in legend()}
    unplaced = named - SOMETHING_HAPPENED - NOTHING_HAPPENED
    assert unplaced == set(), f"the legend names states with no meaning recorded: {unplaced}"
    assert named & SOMETHING_HAPPENED, "the legend shows nothing that happened"
    assert named & NOTHING_HAPPENED, "the legend shows nothing that did not"


def test_a_state_that_happened_is_visible_and_one_that_did_not_recedes() -> None:
    """The rule the far view actually has, said out loud. `blocked` broke it by keeping the
    pale wash it wears up close, which put it on the quiet side of a line it does not
    belong on - and it is the state that says where the run stopped.
    """
    ground = plate()
    for state, label in legend():
        ratio = contrast(far_wash(state, ground), ground)
        if state in SOMETHING_HAPPENED:
            assert ratio >= BAR, f"{label!r} happened and reads at {ratio:.2f}:1"
        else:
            assert ratio < 2.0, f"{label!r} did not happen and is competing at {ratio:.2f}:1"


def lab(colour: str) -> tuple[float, float, float]:
    """sRGB to CIE L*a*b*, D65. Needed because the question here is not "can you read this
    against that" but "are these two the same colour", and a contrast ratio cannot answer
    it: running (#4f758b) and never-got-to (#806713) measure 1.08:1 against each other and
    are blue and gold. The first draft of this test used the ratio and failed on that pair,
    which is the same mistake in a test that the design had in the sheet.
    """
    r, g, b = (v / 255 for v in rgba(colour)[:3])
    to_linear = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4  # noqa: E731
    r, g, b = to_linear(r), to_linear(g), to_linear(b)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    bend = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116  # noqa: E731
    fx, fy, fz = bend(x), bend(y), bend(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def difference(a: str, b: str) -> float:
    """CIE76. A just-noticeable difference is about 2.3; the bar below is four times that,
    because these are small shapes seen in passing rather than two swatches held side by
    side."""
    first, second = lab(a), lab(b)
    return sum((first[i] - second[i]) ** 2 for i in range(3)) ** 0.5


APART = 10.0


def test_no_two_states_are_the_same_colour() -> None:
    """4.82 apart was not faint, it was two creams. Said separately from the bar above
    because a pair can both clear the bar against the plate and still be each other."""
    on = stage()
    fills = {state: far_wash(state, on) for state, _ in legend()}
    labels = dict(legend())
    same = [
        f"{labels[a]!r} {fills[a]} and {labels[b]!r} {fills[b]} are"
        f" {difference(fills[a], fills[b]):.1f} apart"
        for i, a in enumerate(fills)
        for b in list(fills)[i + 1 :]
        if difference(fills[a], fills[b]) < APART
    ]
    assert same == [], "two states of the map are the same colour:\n" + "\n".join(same)


def test_the_label_on_a_solid_fill_can_be_read_on_it() -> None:
    """The far view writes the node's name across the fill in white at display size, which
    is large text and so a 3:1 bar. On the touched node's old wash that was 1.56:1 - a
    white word on a near-white box.
    """
    white = tokens()["surface"]
    far = MAP_CSS[MAP_CSS.index("#dmap.far") :]
    written = re.search(r"([^{}]*)\{color:var\(--surface\)\}", far)
    assert written, "nothing writes a white label at this zoom any more"
    for state in re.findall(r"\.mn\.(\w+) \.nm", written.group(1)):
        ratio = contrast(far_wash(state, stage()), white)
        assert ratio >= BAR, f"the white label on {state} reads at {ratio:.2f}:1"
