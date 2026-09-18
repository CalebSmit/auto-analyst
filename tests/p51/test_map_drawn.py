"""P51: the map, drawn like a drawing.

The visual review's charge was that this file is intelligently specified and barely drawn.
Its sharpest finding was structural rather than aesthetic: `MAP_STYLE` is injected inside
the page's `<style>`, and `body_of()` in tests/p46 strips `<style>...</style>` before
asserting that no page invents a colour or a type size - so this is the one surface in the
tool exempt from the rule the design system is built on, which is most of why it drifted.
The last test here closes that exemption.
"""

from __future__ import annotations

import re

from ops.console.map_view import MAP_HTML, MAP_JS, MAP_STYLE
from ui.theme import CSS

# ------------------------------------------------------------------ one state, five times


def test_the_five_states_are_one_object_wearing_five_sets_of_clothes() -> None:
    """They were five unrelated recipes. Two carried a coloured shadow - a green shadow
    under a mint box, in a tool whose stylesheet says elevation is tinted navy because a
    grey shadow on warm paper is what makes a panel look printed on the page - and three
    carried none. Two used --good and --bad at full strength as a 1px border where the
    rest of the tool uses --good-line for exactly that hairline.
    """
    assert "--edge:var(--line);--wash:var(--surface);--mark:transparent;" in MAP_STYLE
    for state, edge in (
        ("passed", "--edge:var(--good-line);--wash:var(--good-soft);--mark:var(--good)"),
        ("failed", "--edge:var(--bad);--wash:var(--bad-soft);--mark:var(--bad)"),
        ("active", "--edge:var(--accent-line);--wash:var(--accent-soft);--mark:var(--accent)"),
    ):
        assert edge in MAP_STYLE, state
    assert "rgba(47,107,98" not in MAP_STYLE, "no green shadow"
    assert "rgba(81,42,68" not in MAP_STYLE, "no plum shadow"


def test_the_mark_is_a_rule_on_the_leading_edge_like_the_rest_of_the_console() -> None:
    """`.excerpt`, `.diag .d-row` and the current link all say what a block is with an
    inset rule. A coloured outline invented here was a sixth idiom for the same job."""
    mark = '#dmap .mn::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px'
    assert mark in MAP_STYLE
    assert "background:var(--mark)" in MAP_STYLE
    # Drawn as a pseudo-element, which leaves box-shadow free for the rings - selection,
    # neighbour and search were all fighting each other over that one property.
    assert "box-shadow:inset 3px 0 0" not in MAP_STYLE


def test_running_is_the_one_state_that_is_still_happening() -> None:
    """It was the quietest coloured state - no shadow, no ring, nothing moving - while the
    blueprint gives it a spinning ring. And a still picture cannot say "now" with a colour
    that selection and adjacency also use."""
    assert "#dmap .mn.active::before{animation:mnpulse" in MAP_STYLE
    assert "@keyframes mnpulse" in MAP_STYLE


def test_hover_and_selection_are_the_same_for_every_state() -> None:
    """`#dmap .mn.passed` scored higher than `#dmap .mn:hover`, so passed and failed nodes
    did not lift and the other three did - hover behaved differently by accident."""
    node_rules = [r for r in re.findall(r"#dmap [^{]*\{[^}]*\}", MAP_STYLE) if ".mn" in r]
    lifts = [r for r in node_rules if "var(--shadow-lift)" in r]
    assert len(lifts) == 2, f"one hover and one selection, not {len(lifts)}: {lifts}"
    assert "#dmap .mn.on{box-shadow:0 0 0 1px var(--surface),0 0 0 3px var(--accent)" in MAP_STYLE


# ------------------------------------------------------------------ the lines


def test_every_line_says_which_way_it_goes() -> None:
    """240 edges and not one arrowhead, in a drawing whose entire subject is flow - and 54
    of them run upward, so "down means later" was not a fallback either. Direction was
    recoverable only by clicking a node and reading the chips: 118 clicks to read a graph.
    """
    assert '<marker id="dmap-head"' in MAP_JS
    assert 'fill="context-stroke"' in MAP_JS, "one marker takes each line's own colour"
    assert 'markerUnits="userSpaceOnUse"' in MAP_JS, "a constant size, not one that grows"
    assert "path.setAttribute('marker-end', 'url(#dmap-head)');" in MAP_JS
    assert "#dmap.far #dmap-edges path{marker-end:none" in MAP_STYLE, "a blob, far out"


def test_the_kinds_that_are_actually_in_the_data_are_drawn_apart() -> None:
    """`e.kind === 'port' || e.kind === 'gov'` - `gov` is a node group and never an edge
    kind, so the branch was dead and the only thing it ever styled was the ten port edges.
    The nine declared loops, the 35 guards and the 13 masked crossings were one hairline.
    """
    assert "'gov'" not in MAP_JS
    for kind in ("guard", "loop", "masked", "data", "record", "pref", "port"):
        assert f'path[data-kind="{kind}"]' in MAP_STYLE, kind
    # The weight belongs to the kind; the paint only says whether this run used the line.
    assert "p.setAttribute('stroke-width'" not in MAP_JS
    assert "p.classList.toggle('live', Boolean(live));" in MAP_JS


# ------------------------------------------------------------------ the sheet


def test_there_is_a_ground_a_sheet_and_a_frame() -> None:
    """The stage painted flat --bg over the gradient #dmap carried, so the gradient
    appeared nowhere at all - and the canvas was the same paper as the page behind it,
    meeting the chrome at a hairline and the window at nothing."""
    assert "linear-gradient(180deg,#f6f5f0" not in MAP_STYLE, "the dead gradient is gone"
    assert "#dmap .stage{" in MAP_STYLE and "background:var(--surface-sunken)" in MAP_STYLE
    sheet = "#dmap .pan{position:absolute;top:0;left:0;transform-origin:0 0;"
    assert sheet + "\n background:var(--bg)" in MAP_STYLE
    # The vignette is on the frame, not on the drawing, so it does not travel with the pan.
    stage = re.search(r"#dmap \.stage\{([^}]*)\}", MAP_STYLE)
    assert stage and "inset 0 30px 46px -34px" in stage.group(1)


def test_the_sheet_is_ruled_at_the_blueprints_own_module() -> None:
    rule = "repeating-linear-gradient({}deg,var(--line-soft) 0 1px,transparent 1px {}px)"
    assert rule.format(0, 152) in MAP_STYLE, "the blueprint's own row height"
    assert rule.format(90, 198) in MAP_STYLE, "and its own column pitch"


def test_a_rule_that_fades_reads_as_drawn_and_the_boundary_is_ruled_twice() -> None:
    """The band rules stopped dead at both ends, and the privacy boundary - the guarantee
    that past this line an account is a token and not a name - was plum at 22% alpha at
    2px, barely stronger than the neutral hairlines either side of it."""
    fade = "linear-gradient(90deg,transparent,var(--line) 4% 96%,transparent)"
    assert fade in MAP_STYLE
    assert "#dmap .band.priv::after{" in MAP_STYLE, "a boundary is ruled twice"
    assert "color-mix(in srgb,var(--bad) 55%,transparent)" in MAP_STYLE


def test_the_band_names_stay_at_the_margin() -> None:
    """They lived inside the panned canvas: they scaled with it - about 3px at the old
    opening zoom - and panned off the left edge, which is where they spent most of the
    time. A draftsman keeps the marginalia at the margin."""
    assert '<div class="rail" id="dmap-rail"' in MAP_HTML
    assert "$('dmap-rail').appendChild(label);" in MAP_JS
    assert "el.style.top = (Number(el.dataset.y) * MAP_K + MAP_Y) + 'px';" in MAP_JS
    assert "#dmap .rail{" in MAP_STYLE


def test_a_column_is_not_drawn_as_a_band() -> None:
    """Column labels reused `.band-t` verbatim, so a vertical region and a horizontal band
    were the same size, tracking and colour."""
    assert "#dmap .col-t{" in MAP_STYLE
    assert "label.className = 'col-t';" in MAP_JS


# ------------------------------------------------------------------ the chrome


def test_the_legend_is_a_plate_on_the_drawing() -> None:
    """Five of the fifteen controls in the bar were the key to the drawing, which belongs
    with the drawing."""
    assert '<div class="plate">' in MAP_HTML
    assert "#dmap .plate{position:absolute;left:var(--s5);bottom:var(--s5)" in MAP_STYLE
    assert "n and p walk the run" in MAP_HTML, "and the keys are visible, not only in a title"


def test_the_key_cannot_drift_from_the_drawing() -> None:
    """The swatches were five inline `style=` attributes hard-coding a second copy of each
    state - and the copy had already drifted: the node is dashed, the swatch was solid, on
    the one distinction this view exists to make. They are nodes now."""
    pattern = r'data-state="(\w+)"[^>]*><i class="mn (\w+)"'
    swatches = re.findall(pattern, MAP_HTML)
    assert [(a, b) for a, b in swatches if a != b] == [], "each swatch wears its own state"
    assert len(swatches) == 6, "five states, plus what the run never got to"
    assert "style=" not in MAP_HTML, "nothing in this view carries its own inline styling"
    # And every query for "the nodes" says the canvas, because the swatches are nodes too.
    assert "querySelectorAll('#dmap .mn')" not in MAP_JS
    assert MAP_JS.count("querySelectorAll('#dmap-pan .mn')") >= 3


def test_the_way_out_is_not_the_loudest_thing_on_the_screen() -> None:
    """On a full-screen overlay, a filled navy button was the heaviest object on it."""
    assert 'class="primary" data-act="mapClose"' not in MAP_HTML
    assert 'class="ghost" data-act="mapClose"' in MAP_HTML


def test_the_bar_has_two_ranks_and_does_not_wrap() -> None:
    """Fifteen controls at one rank measured about 1330px against a 1280px viewport, so it
    wrapped at the stated minimum width - and because the bar wrapped too, the title could
    split from the tools."""
    top = re.search(r"#dmap \.map-top\{([^}]*)\}", MAP_STYLE)
    assert top and "flex-wrap:wrap" not in top.group(1)
    assert "align-items:baseline" in top.group(1), "buttons against a two-line title block"
    assert '<span class="sep" aria-hidden="true"></span>' in MAP_HTML


def test_the_chevrons_are_big_enough_to_hit() -> None:
    """About 20px square at the fluid root's floor, a tenth of a rem apart."""
    assert "#dmap .seg button,#dmap .zoom button{min-width:1.75rem;min-height:1.75rem}" in MAP_STYLE


# ------------------------------------------------------------------ opening it


def test_it_opens_at_a_size_its_own_marks_survive() -> None:
    """Measured: the box a run touches is about 1861x2354, which fitted into a 1072px stage
    gives 0.307 - below the 0.52 where this view drops its labels. So every entry landed in
    far-zoom mode, where the 1px border that carries state renders at a third of a pixel
    and the five washes sit inside a single deltaE-7 band. "Where it ran" was also 1.13x
    "Fit all" on every screen size measured: the two buttons showed the same picture.
    """
    assert "const MAP_FLOOR = .62;" in MAP_JS
    assert "Math.max(MAP_FLOOR, whole)" in MAP_JS
    threshold = float(re.search(r"classList\.toggle\('far', MAP_K < (\.\d+)\)", MAP_JS).group(1))
    assert threshold < 0.62, "the opening view must be above the threshold, not on it"


def test_far_out_the_state_stops_being_a_one_pixel_border() -> None:
    """A 1px border at 40% is a third of a pixel, and what was left - the five soft fills -
    is a single band of near-identical greens. A filled box survives any scale."""
    assert "#dmap.far .mn{padding:.3rem .45rem;border-width:0}" in MAP_STYLE
    for state, token in (("passed", "good"), ("active", "accent"), ("failed", "bad")):
        assert f"#dmap.far .mn.{state}{{--wash:var(--{token})}}" in MAP_STYLE, state
    # And the 99 boxes no run reached stop shouting their names over the ~19 that matter.
    hidden = "#dmap.far .mn.notreached .nm,#dmap.far .mn.pending .nm{visibility:hidden}"
    assert hidden in MAP_STYLE


def test_stepping_moves_rather_than_cuts() -> None:
    """A median jump of 396px and a maximum of 2336, instantly, eight times - on a view
    whose whole thesis is that a run is a sequence. Done as a CSS transition so the global
    reduced-motion rule turns it off without this file knowing about it."""
    assert "#dmap .pan.gliding{transition:transform .34s var(--ease)}" in MAP_STYLE
    assert "#dmap .stage.dragging .pan{transition:none" in MAP_STYLE, "a drag is one to one"
    assert "function mapGlide()" in MAP_JS and "mapGlide();" in MAP_JS
    assert "requestAnimationFrame" not in MAP_JS, "a JS tween would escape the motion rule"


# ------------------------------------------------------------------ the exemption, closed


def test_the_maps_stylesheet_obeys_the_rules_the_rest_of_the_tool_does() -> None:
    """tests/p46 asserts that no page invents a colour or a type size, and strips
    `<style>...</style>` first because every page inlines the whole sheet. MAP_STYLE is
    injected inside that tag, so it was the one surface the rule could not see - and it
    had ten type sizes, none of them on the scale, and a raw hex.
    """
    assert re.findall(r"#[0-9a-fA-F]{6}\b", MAP_STYLE) == [], "no colour of its own"
    assert re.findall(r"#[0-9a-fA-F]{3}\b", MAP_STYLE) == [], "not in shorthand either"
    off_scale = re.findall(r"font-size:\s*(?!var\()([^;}]+)", MAP_STYLE)
    assert off_scale == [], f"these sizes are not on the type scale: {off_scale}"
    assert re.findall(r"font-size:\s*[\d.]+px", MAP_STYLE) == []
    # Spot-check that it is using the scale rather than merely avoiding numbers.
    for token in ("var(--t-label)", "var(--t-sm)", "var(--t-title)", "var(--t-display)"):
        assert token in MAP_STYLE, token
    for token in ("--t-label:", "--t-sm:", "--t-title:", "--t-display:"):
        assert token in CSS, f"the scale no longer defines {token}"


def test_nothing_a_person_reads_is_set_in_the_quiet_grey() -> None:
    """theme.py is explicit that --ink-4 is below the floor and is for a placeholder or a
    disabled control. A node's name and its id are read, and the id gets pasted."""
    for rule in re.findall(r"#dmap [^{]*\{[^}]*\}", MAP_STYLE):
        if "var(--ink-4)" not in rule:
            continue
        # theme.py allows it for a placeholder, a disabled control, or a node no run
        # reached. What is not allowed is a name or an id somebody has to read.
        allowed = ("focused" in rule, ".keys" in rule, 'aria-pressed="false"' in rule)
        assert any(allowed), f"--ink-4 on something read: {rule[:90]}"
