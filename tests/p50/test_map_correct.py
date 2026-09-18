"""P50: the map, made correct.

Five reviews of the full-design map - a visual design director, an information-visualization
specialist, an accessibility engineer, a frontend engineer, and one reading it as the two
people who use it - found defects before they found preferences. These are the defects.

Each test names the thing a person was doing when they hit it, because that is what makes
a regression recognisable later: not "the threshold is wrong" but "a slow pan lost the node
I was reading".
"""

from __future__ import annotations

import re

from ops.console.app import PAGE as ACTIVITY
from ops.console.map_view import MAP_HTML, MAP_JS, MAP_STYLE

# ------------------------------------------------------------------ the drawing's geometry


def test_the_box_is_the_height_the_edges_are_drawn_to() -> None:
    """Every downward edge left from a point below the box it belonged to.

    The edge maths used a hard-coded 52 while the box was whatever the fluid root made it -
    measured at 45.7px on a 14.5px root and about 38px on a 12.5px one. So the lines began
    in white space, which is the single thing that made the drawing read as generated.
    The box is now a fixed height and the geometry measures it, so the two cannot disagree:
    change the stylesheet and the edges follow.
    """
    assert "height:52px" in MAP_STYLE, "the box is a fixed height, like the grid it sits on"
    assert "const NH = MAP_NODE_H;" in MAP_JS, "and the edges are drawn to that height"
    measured = "MAP_NODE_H = (first && Math.round(first.getBoundingClientRect().height))"
    assert measured in MAP_JS
    # Measured, which means the nodes are in the document before the edges are computed.
    nodes_at = MAP_JS.index("const first = g.nodes.length ? $('mn-' + g.nodes[0].id) : null;")
    edges_at = MAP_JS.index("(g.edges || []).forEach((e, i) => {")
    assert nodes_at < edges_at, "the boxes have to exist before one of them can be measured"


def test_a_node_is_not_nudged_off_the_grid_by_being_clicked() -> None:
    """The page's own `button:active{transform:translateY(1px)}` reached in here, so
    clicking a node moved it a pixel off the position the blueprint gives it."""
    assert "#dmap .mn:active{transform:none}" in MAP_STYLE


# ------------------------------------------------------------------ the pointer


def test_a_slow_pan_keeps_the_node_you_were_reading() -> None:
    """`e.clientX - from.x - MAP_X` was the distance since the *previous* pointermove, not
    since the button went down, because MAP_X is rewritten on every move. A pan at reading
    speed produces 2-3px per event, never passes the 3px threshold, and so counted as a
    click on the paper - which clears the selection. Dragging towards a node deselected it.
    """
    assert "origin = {x: e.clientX, y: e.clientY};" in MAP_JS
    assert "Math.abs(e.clientX - origin.x) > 3 || Math.abs(e.clientY - origin.y) > 3" in MAP_JS
    assert "e.clientX - from.x - MAP_X" not in MAP_JS, "the old measurement is gone"


def test_only_the_left_button_pans() -> None:
    """A right-click started a pan and left the stage in it while the context menu was
    open; a second finger overwrote the first mid-drag."""
    assert "if (e.button !== 0 || !e.isPrimary || e.target.closest('.mn')) return;" in MAP_JS
    assert "try { stage.setPointerCapture(e.pointerId); } catch" in MAP_JS


def test_the_wheel_is_scaled_by_how_far_it_turned_and_ctrl_still_zooms_the_page() -> None:
    """A mouse notch reports about 100 and a trackpad reports single digits, and a fixed
    step per event took a light two-finger flick from 100% to the ceiling in about fifty
    milliseconds. And ctrl+wheel is the browser's own zoom - and what a trackpad pinch
    arrives as - so cancelling it leaves a low-vision reader no way to enlarge the page.
    """
    assert "if (e.ctrlKey || e.metaKey) return;" in MAP_JS
    assert "e.deltaMode === 1 ? 16 : e.deltaMode === 2" in MAP_JS
    assert "mapZoomTo(MAP_K * Math.exp(-e.deltaY * unit * 0.0022)" in MAP_JS
    assert "function mapZoom(by, at)" in MAP_JS, "the buttons still step by one notch"


# ------------------------------------------------------------------ the keyboard


def test_escape_in_the_find_box_clears_the_box_and_not_the_view() -> None:
    """Type a search, press Escape to clear it, and the whole map closed: the box's own
    handler cleared the field and then the document handler ran and shut the dialog."""
    assert "if (e.key === 'Escape') { e.stopPropagation(); box.value = ''; mapFind(); }" in MAP_JS
    assert "if (e.key === 'Escape') return typing ? undefined : closeMap();" in MAP_JS


def test_a_single_letter_shortcut_does_not_take_ctrl_p_from_the_browser() -> None:
    """`e.key` for Ctrl+P is 'p', and nothing checked for a modifier - so printing the
    console stepped the run backwards instead."""
    assert "if (e.ctrlKey || e.metaKey || e.altKey) return;" in MAP_JS
    guard = MAP_JS.index("if (e.ctrlKey || e.metaKey || e.altKey) return;")
    assert guard < MAP_JS.index("if (e.key === 'n' || e.key === ']')")


def test_tab_is_handled_before_the_guard_that_turns_the_trap_off() -> None:
    """The guard bails on anything typed into, and opening the view used to focus the find
    box - so the trap was off for the first key a reader pressed."""
    keys = MAP_JS[MAP_JS.index("function mapKeys(e) {") :]
    assert keys.index("if (e.key === 'Tab') return mapTrap(e);") < keys.index("const typing =")


def test_the_trap_holds_from_anywhere_not_only_from_the_ends() -> None:
    """It used to act only when focus was already on the first or last stop. Panning the
    canvas with the mouse leaves focus on <body>, which is neither, so the next Tab walked
    out of the dialog and into the page behind it."""
    assert "const at = stops.indexOf(document.activeElement);" in MAP_JS
    reenter = "if (at === -1) return (e.shiftKey ? stops[stops.length - 1] : stops[0])"
    assert reenter in MAP_JS


def test_what_the_overlay_covers_is_inert_while_it_covers_it() -> None:
    """`aria-modal` promises the page behind is out of reach; `inert` is what does it. The
    masthead is included because its links come first in the document, so an escaping Tab
    lands there."""
    assert "function mapBehind(off)" in MAP_JS
    assert "document.querySelectorAll('.top, .wrap').forEach(el => { el.inert = off; });" in MAP_JS
    assert "mapBehind(true);" in MAP_JS and "mapBehind(false);" in MAP_JS


def test_opening_it_does_not_put_the_focus_in_a_search_box() -> None:
    """Focusing an input turns off every shortcut the buttons advertise, including the
    arrow keys that pan - so the view opened with its own controls dead."""
    assert "if (find) { find.value = ''; mapFind(); }" in MAP_JS
    assert "$('dmap').focus();" in MAP_JS
    assert 'tabindex="-1"' in MAP_HTML, "and the dialog can hold the focus it is given"


def test_the_side_panel_keeps_its_own_arrow_keys() -> None:
    """The panel scrolls; with focus inside it, the arrow keys panned the canvas instead
    and there was no other way to scroll it."""
    assert "if (e.target && e.target.closest('#dmap-side')) return;" in MAP_JS


# ------------------------------------------------------------------ what it says is true


def test_a_run_that_could_not_be_read_is_not_a_run_that_did_nothing() -> None:
    """Both fetches swallowed their failures, so a dropped connection drew 118 dashed
    outlines, a count of `0 of 118 touched`, and the sentence "Nothing ran - this run
    touched no node of the design". That is a confident statement of fact manufactured
    from a network error, in the view whose whole purpose is not confusing those two.
    """
    assert "MAP_UNREAD = unread;" in MAP_JS
    assert "unread = true" in MAP_JS
    assert "Could not read what ${runId} did" in MAP_JS
    assert "Could not read the blueprint from this server" in MAP_JS


def test_the_map_reads_the_run_it_is_showing() -> None:
    """Borrowing the page's last trace cost two bugs: it carries no note of whose it is,
    and it is painted progressively - so a deep link opened on a four-node snapshot of a
    twenty-one-node run and drew seventeen passed nodes as never reached."""
    assert "const trace = await get(`/api/runs/${encodeURIComponent(runId)}/trace`)" in MAP_JS
    assert "LAST_TRACE" not in MAP_JS, "the page's trace is not the map's"
    assert "(MAP_TRACE || {}).diagnostics" in MAP_JS, "and neither is the page's diagnostic"


def test_a_name_the_design_has_no_box_for_does_not_blank_the_canvas() -> None:
    """Every run records against `run_driver`, which the blueprint has no node for - so
    this was step six of every run, not an edge case. Picking it set `.focused` with
    nothing marked on or near, which dropped all 118 nodes to .4 and all 240 edges to .12:
    the map went blank and nothing said why."""
    assert "const drawn = Boolean(id) && Boolean($('mn-' + id));" in MAP_JS
    assert "$('dmap').classList.toggle('focused', drawn);" in MAP_JS
    assert "is a name this run recorded work against that the design has no box for" in MAP_JS


def test_the_order_comes_from_the_server_rather_than_from_collating_strings() -> None:
    """The events arrive in `seq` order, which is a contract. Sorting their timestamps
    with localeCompare re-derived it, locale-dependently, and a clock that stepped
    backwards would have inverted two events the sequence numbers order correctly."""
    assert "localeCompare" not in MAP_JS
    assert "const seen = new Set();" in MAP_JS
    assert "if (!at || seen.has(at)) continue;" in MAP_JS


# ------------------------------------------------------------------ what the reader asked for


def test_hiding_a_state_hides_its_nodes_and_the_lines_into_them() -> None:
    """The legend faded to `opacity:.12`: the nodes stayed clickable, stayed tab stops,
    stayed search hits and were still stepped onto, and their edges never went at all - so
    turning off "never reached" left 227 lines anchored to boxes that were not there."""
    assert "opacity:.12}" not in MAP_STYLE.replace("path:not(.on){opacity:.12}", "")
    assert "#dmap.hide-notreached #dmap-edges path.f-notreached" in MAP_STYLE
    gone = r"#dmap\.hide-notreached \.mn\.pending,[\s\S]{0,700}?\n display:none\}"
    assert re.search(gone, MAP_STYLE), "hidden is display:none, not a ghost left at .12"
    assert "p.classList.add('f-' + a, 't-' + b);" in MAP_JS, "each line carries both its ends"


def test_the_rest_of_the_view_agrees_about_what_is_hidden() -> None:
    assert "el.dataset.search.includes(q) && el.offsetParent !== null" in MAP_JS
    assert "const walk = MAP_ORDER.filter(id => {" in MAP_JS
    assert "Every step of this run is hidden by the filters." in MAP_JS
    assert "note.textContent = off.length ? 'hiding ' + off.join(', ') : ''" in MAP_JS


def test_a_neighbour_keeps_the_colour_of_what_the_run_did_there() -> None:
    """`.near` set `border-color:var(--accent)` at the same specificity as the state rules
    and later in the file, so picking `context_builder` - nineteen edges - repainted
    nineteen nodes' run state with the colour that means *running*."""
    near = re.search(r"#dmap \.mn\.near\{([^}]*)\}", MAP_STYLE)
    assert near and "border-color" not in near.group(1), "adjacency is not a state"
    assert "box-shadow:0 0 0 1px var(--surface),0 0 0 3px var(--accent-line)" in near.group(1)


def test_focus_is_not_dressed_as_selection() -> None:
    """Both were a 2px accent ring, so a keyboard reader could not tell where they were
    from what was picked. And hover came after both, so pointing at the selected node
    removed the only mark saying it was selected."""
    assert "#dmap .mn:focus-visible{outline:3px solid var(--navy)" in MAP_STYLE
    assert "#dmap .mn:not(.on):not(.hit):hover{box-shadow:var(--shadow-lift)}" in MAP_STYLE


def test_the_paint_does_not_throw_away_what_the_reader_marked() -> None:
    """`el.className = 'mn ' + state` dropped `.near` and `.hit` on every paint."""
    assert "el.className = 'mn '" not in MAP_JS
    assert "for (const was of MAP_ALL_STATES) el.classList.remove(was);" in MAP_JS


# ------------------------------------------------------------------ the view survives use


def test_the_address_bar_is_rewritten_at_most_four_times_a_second() -> None:
    """Holding `n` walks the run at the key-repeat rate - about 31 a second. Chrome drops
    the excess, so the link stops matching the selection; Safari throws, and the throw came
    before the panel was built, leaving the canvas moved on and the panel behind."""
    assert "function mapLink(id)" in MAP_JS
    assert "clearTimeout(MAP_URL_TIMER);" in MAP_JS
    assert "try { history.replaceState" in MAP_JS
    assert MAP_JS.count("history.replaceState") == 3, "open, close, and the coalesced one"


def test_the_window_can_be_resized() -> None:
    """Every offset is absolute pixels against a stage measured when it was read, and
    crossing 1100px takes the side panel away and grows the stage by 23rem - so the
    drawing could end up entirely off-screen with no way back but a button."""
    assert "window.addEventListener('resize'" in MAP_JS
    assert "function mapStage()" in MAP_JS
    assert "MAP_RECT = null;" in MAP_JS
    assert "$('dmap-stage').getBoundingClientRect()" not in MAP_JS.replace(
        "return MAP_RECT || (MAP_RECT = $('dmap-stage').getBoundingClientRect());", ""
    ), "one place reads the stage, so one place has to be told it changed"


def test_the_segmented_controls_are_the_same_height() -> None:
    """`.step` is a component in the page's own stylesheet, and its padding leaked in here:
    the step control rendered 42px tall beside a 26px zoom control of the same species."""
    assert "#dmap .step" not in MAP_STYLE
    assert 'class="step"' not in MAP_HTML
    assert "#dmap .seg{" in MAP_STYLE


def test_a_second_open_does_not_lose_the_way_back() -> None:
    """Two opens in flight and the second captured the find box - inside the overlay - as
    the element to hand focus back to."""
    assert "const mine = ++MAP_OPENING;" in MAP_JS
    assert "if (!already) MAP_CAME_FROM = document.activeElement;" in MAP_JS
    assert MAP_JS.count("if (mine !== MAP_OPENING) return;") >= 3


def test_focus_comes_back_to_something_that_still_exists() -> None:
    """refresh() rewrites the run's buttons every five seconds, so within five seconds of
    opening the map the element it was opened from is detached and focusing it does
    nothing - which is the exact outcome the code was written to prevent."""
    assert "MAP_CAME_FROM.isConnected" in MAP_JS
    assert "document.querySelector('[data-act=\"map\"]')" in MAP_JS


def test_a_failed_graph_load_is_not_remembered_for_the_life_of_the_page() -> None:
    """One transient failure was cached as `{nodes: []}` forever, and the map then
    diagnosed it as a blueprint exported without positions and sent the reader to re-run
    the exporter on a file that was fine."""
    body = "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))
    assert "GRAPH_LOADING = get('/api/graph').then(g => { GRAPH = g; return g; })" in body
    assert ".finally(() => { GRAPH_LOADING = null; });" in body
    assert "GRAPH = await get('/api/graph').catch" not in body


def test_every_binding_the_collision_test_reads_is_on_its_own_line() -> None:
    """A duplicate `let` across the page's two scripts is an early SyntaxError: the second
    script never runs, and the entire map disappears with only a console message. The
    checkpoint guards that - but its regex reads the first name on a declaration, so
    `let MAP_RUN = null, MAP_STATES = {}, ...` hid five bindings from it.
    """
    body = "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))
    doubled = []
    for line in body.splitlines():
        if not re.match(r"^(?:const|let|var)\s+\w+\s*=", line):
            continue
        # A default in an arrow function's parameter list is a comma and an `=` too, so
        # the bracketed parts come out before the line is read for a second name.
        bare = re.sub(r"\([^()]*\)|\{[^{}]*\}|\[[^\[\]]*\]", "", line)
        if re.search(r",\s*\w+\s*=", bare):
            doubled.append(line.strip())
    assert doubled == [], f"these declare more than one name on a line: {doubled[:4]}"
