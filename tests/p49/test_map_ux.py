"""P49: the map as something to work with.

A picture of a run answers "which nodes" and leaves out "in what order", "joined to what",
and "where is the one I am looking for" - which are the three questions somebody standing in
front of a stopped run actually has. These are those, plus the keyboard, which on a view of
118 boxes is the difference between navigable and not.
"""

from __future__ import annotations

import re

from ops.console.app import PAGE as ACTIVITY
from ops.console.map_view import MAP_HTML, MAP_JS, MAP_STYLE

# ------------------------------------------------------------------ the order it happened


def test_the_run_is_numbered_in_the_order_it_happened() -> None:
    """From the first event recorded against each node, not from the order a dictionary
    happened to hand them over."""
    assert "MAP_ORDER = Object.keys(MAP_EVENTS)" in MAP_JS
    assert "localeCompare(String(MAP_EVENTS[b][0].ts))" in MAP_JS, "ordered by when"
    assert "MAP_SEQ[id] = i + 1" in MAP_JS
    assert "el.dataset.ord = MAP_SEQ[id]" in MAP_JS, "and the number is on the node"
    assert "#dmap .mn .ord{" in MAP_STYLE


def test_a_person_can_walk_the_run_a_step_at_a_time() -> None:
    assert "function mapStep(by)" in MAP_JS
    assert 'data-act="mapStep" data-by="-1"' in MAP_HTML
    assert 'data-act="mapStep" data-by="1"' in MAP_HTML
    assert "if (e.key === 'n' || e.key === ']')" in MAP_JS, "and from the keyboard"
    assert "MAP_ORDER.indexOf(MAP_PICKED)" in MAP_JS


def test_the_side_list_is_in_that_order_with_the_time_of_each() -> None:
    assert "const ordered = MAP_ORDER.map(nodeId => [nodeId, MAP_STATES[nodeId]]);" in MAP_JS
    assert "MAP_SEQ[nodeId] ? esc(MAP_SEQ[nodeId]) + '. '" in MAP_JS
    assert "MAP_EVENTS[nodeId][0].ts).slice(11, 19)" in MAP_JS


def test_a_number_missing_from_the_map_is_accounted_for() -> None:
    """The sequence counts everything the run recorded, including a name the design has no
    node for - so a gap in the numbers on screen is explained further down the panel rather
    than left as a hole."""
    stray = MAP_JS[MAP_JS.index("stray.map(") :]
    assert "MAP_SEQ[nodeId] ? esc(MAP_SEQ[nodeId]) + '. '" in stray[:400]


# ------------------------------------------------------------------ what it is joined to


def test_picking_a_node_draws_the_edges_it_is_on() -> None:
    """240 edges at one weight is a hairball. The ones the picked node is on are drawn and
    the rest fall back, which is the only way to read what feeds what."""
    assert "path.classList.toggle('on', Boolean(id) && (path.dataset.from === id" in MAP_JS
    assert "#dmap.focused #dmap-edges path:not(.on){opacity:.12}" in MAP_STYLE
    assert "#dmap #dmap-edges path.on{stroke:var(--accent)" in MAP_STYLE


def test_what_feeds_it_and_what_it_feeds_are_links() -> None:
    assert "What it is joined to" in MAP_JS
    assert "MAP_IN[id] || []" in MAP_JS and "MAP_OUT[id] || []" in MAP_JS
    assert "nothing feeds this node" in MAP_JS, "and it says so when nothing does"
    assert "MAP_LABEL[from + '>' + id]" in MAP_JS, "the edge's own words, on hover"
    # The chips are the same action as the nodes, so the panel navigates the graph.
    assert MAP_JS.count('data-act="mapPick" data-node="${esc(from)}"') == 1


def test_the_neighbours_are_marked_on_the_canvas() -> None:
    assert "el.classList.toggle('near', near.has(el.id.slice(3)))" in MAP_JS
    assert "#dmap .mn.near{" in MAP_STYLE
    assert "#dmap.focused .mn:not(.on):not(.near){opacity:.4}" in MAP_STYLE


# ------------------------------------------------------------------ finding and filtering


def test_a_node_can_be_found_by_name_id_or_group() -> None:
    assert 'id="dmap-find"' in MAP_HTML
    assert "function mapFind()" in MAP_JS
    assert "el.dataset.search.includes(q)" in MAP_JS
    assert "`${n.label} ${n.id} ${n.group || ''}`.toLowerCase()" in MAP_JS
    assert "function mapFindEnter()" in MAP_JS, "Enter goes to the first one"
    assert "if (e.key === '/')" in MAP_JS, "and a key reaches the box"


def test_the_legend_shows_and_hides_rather_than_only_labelling() -> None:
    swatches = re.findall(r'data-act="mapFilter" data-state="(\w+)"', MAP_HTML)
    assert set(swatches) == {"passed", "failed", "active", "used", "notreached"}
    assert 'aria-pressed="true"' in MAP_HTML
    assert "ACTIONS.mapFilter" in MAP_JS
    assert "#dmap.hide-passed .mn.passed" in MAP_STYLE


# ------------------------------------------------------------------ the keyboard


def test_the_keyboard_has_one_stop_per_node_the_run_touched() -> None:
    """118 tab stops is not navigation; the rest are reached through the find box."""
    assert "el.tabIndex = went ? 0 : -1;" in MAP_JS


def test_every_node_says_what_state_it_is_in() -> None:
    assert "el.setAttribute('aria-label'," in MAP_JS
    assert "says[state] || state" in MAP_JS
    assert 'role="status" aria-live="polite"' in MAP_HTML, "and the selection is announced"
    assert "said.textContent =" in MAP_JS


def test_the_dialog_keeps_the_focus_and_gives_it_back() -> None:
    assert 'role="dialog" aria-modal="true"' in MAP_HTML
    assert "function mapTrap(e)" in MAP_JS
    assert "MAP_CAME_FROM = document.activeElement;" in MAP_JS
    assert "if (MAP_CAME_FROM && MAP_CAME_FROM.focus) MAP_CAME_FROM.focus();" in MAP_JS


# ------------------------------------------------------------------ links


def test_a_link_can_name_one_node_of_one_run() -> None:
    assert "function mapHash(runId, nodeId)" in MAP_JS
    assert "history.replaceState(null, '', mapHash(MAP_RUN, id));" in MAP_JS, (
        "picking a node updates the link, so the address bar is always the thing to send"
    )
    body = "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))
    assert "const [runId, ...rest] = wanted.slice(4).split('/');" in body
    assert "openMap(runId, rest.join('/') || null)" in body


def test_clicking_the_paper_puts_the_whole_run_back() -> None:
    assert "if (from && !moved && MAP_PICKED) pickNode(null);" in MAP_JS
