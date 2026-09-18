"""P48: the whole design, painted with what one run did.

The picture has to be the blueprint's own, or it is a second drawing that somebody has to
keep in step by hand. So the positions come from the blueprint's layout tables, through the
same export and the same digest as its nodes - and what is drawn on them comes from the
trace the run recorded, including the part where a run names something the design does not
have.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ops.console.app import PAGE as ACTIVITY
from ops.console.app import Console, create_app
from ops.console.map_view import MAP_HTML, MAP_JS, MAP_STYLE
from ops.events import EventBus
from ops.run_store import SqlRunStore
from tests.p23.conftest import Clock, halted_run

ROOT = Path(__file__).resolve().parents[2]
GRAPH = json.loads((ROOT / "graph" / "architecture.json").read_text(encoding="utf-8"))


@pytest.fixture
def client(store: SqlRunStore, bus: EventBus) -> TestClient:
    halted_run(store, bus)
    return TestClient(create_app(Console(store, bus, clock=Clock())))


# ------------------------------------------------------------------ the blueprint's own geometry


def test_every_node_of_the_design_has_the_position_the_blueprint_gives_it() -> None:
    """118 nodes, and the layout tables place all of them: a node the blueprint draws and
    the export cannot place would be a node missing from the map with nothing to say so."""
    assert len(GRAPH["nodes"]) == 118
    unplaced = [n["id"] for n in GRAPH["nodes"] if n.get("x") is None or n.get("y") is None]
    assert unplaced == [], f"the export places no node at {unplaced}"
    assert len({(n["x"], n["y"]) for n in GRAPH["nodes"]}) == len(GRAPH["nodes"]), (
        "two nodes share a position, so one is drawn on top of the other"
    )


def test_the_bands_and_the_columns_come_with_it() -> None:
    layout = GRAPH["layout"]
    assert layout["node_width"] == 178
    assert len(layout["bands"]) >= 10
    assert any(b["privacy"] for b in layout["bands"]), "the masking boundary is a ruled line"
    assert [c["label"] for c in layout["columns"]]


def test_the_geometry_is_under_the_same_digest_as_the_graph() -> None:
    """A blueprint moved on the canvas without a re-export is the same drift as a node added
    without one. The digest covers both, and tests/p07 recomputes it."""
    from tools.export_architecture import ARRAYS, LAYOUT_ARRAYS

    assert set(LAYOUT_ARRAYS) == {"LAYOUT", "COLUMNS", "BANDS", "COL_LABELS"}
    assert not set(ARRAYS) & set(LAYOUT_ARRAYS)


def test_the_console_serves_the_positions_and_the_edges(client: TestClient) -> None:
    served = client.get("/api/graph").json()
    assert len(served["nodes"]) == 118
    assert len(served["edges"]) == 240
    assert all(n["x"] is not None for n in served["nodes"])
    assert served["layout"]["bands"]


# ------------------------------------------------------------------ the view


def test_the_map_is_reachable_from_a_run_and_from_a_link() -> None:
    body = "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))
    assert 'data-act="map" data-run=' in ACTIVITY, "no way into it from the run"
    assert "ACTIONS.map = d => openMap(d.run);" in body
    assert "wanted.startsWith('map=')" in body, "no link straight to one run's map"


def test_the_overlay_does_not_reuse_an_id_the_page_already_has() -> None:
    """The first build did: `#map` is the trace panel's own container, so the overlay
    styled and hid the wrong element and never appeared."""
    ids = re.findall(r'id="([\w-]+)"', ACTIVITY)
    doubled = sorted({i for i in ids if ids.count(i) > 1})
    assert doubled == [], f"the page carries {doubled} twice"


def test_a_node_is_bordered_by_what_the_run_did_there() -> None:
    # P51: the border is one of three custom properties the state sets - a wash, a hairline
    # and a mark - rather than a rule of its own per state, so the five read as a family.
    for state, mark in (("passed", "--mark:var(--good)"),
                        ("failed", "--mark:var(--bad)"),
                        ("active", "--mark:var(--accent)")):
        rule = re.search(rf"#dmap \.mn\.{state}\{{([^}}]*)\}}", MAP_STYLE)
        assert rule and mark in rule.group(1), state
        assert "--edge:" in rule.group(1) and "--wash:" in rule.group(1), state
    never = re.search(r"#dmap \.mn\.notreached,[^{]*\{([^}]*)\}", MAP_STYLE)
    assert never and "border-style:dashed" in never.group(1), (
        "a node the run never reached is drawn as never reached, not as one that passed"
    )


def test_the_map_says_what_happened_in_a_node() -> None:
    assert "async function pickNode(id)" in MAP_JS
    assert "What happened here" in MAP_JS
    # P50: keyed by the node's name as a string, because an event with no node would
    # otherwise become the key "null" and take a place in the sequence.
    assert "(MAP_EVENTS[at] = MAP_EVENTS[at] || []).push(e)" in MAP_JS
    assert "const events = MAP_EVENTS[id] || [];" in MAP_JS
    assert "(MAP_TRACE || {}).diagnostics" in MAP_JS, "and the diagnostic, where there is one"


def test_it_opens_where_the_run_went_and_fits_on_request() -> None:
    assert "function mapFocus()" in MAP_JS and "function mapFit()" in MAP_JS
    assert 'data-act="mapFocus"' in MAP_HTML and 'data-act="mapFit"' in MAP_HTML
    # P52: it opens on the part the run touched, and picks the place it stopped at - which
    # is the reason this view gets opened - unless the link named somewhere else.
    assert "mapFocus();" in MAP_JS
    assert "pickNode(nodeId && $('mn-' + nodeId) ? nodeId : (stopped || null));" in MAP_JS


def test_the_keyboard_can_work_it() -> None:
    assert "function mapKeys(e)" in MAP_JS
    assert "e.key === 'Escape'" in MAP_JS
    assert "ArrowLeft" in MAP_JS and "mapZoom" in MAP_JS
    assert "<button" in MAP_HTML and "el.type = 'button'" in MAP_JS, "a node is a button"


def test_far_out_the_labels_are_still_legible() -> None:
    # P51: far out it is the *id* that goes and the name that stays, because the names are
    # the English somebody wrote for this and the ids are not; and the state stops being a
    # 1px border, which at that scale is a third of a pixel, and becomes the whole fill.
    assert "#dmap.far .mn .id{display:none}" in MAP_STYLE
    assert "#dmap.far .mn{padding:.3rem .45rem;border-width:0}" in MAP_STYLE
    assert "classList.toggle('far', MAP_K < .52)" in MAP_JS


# ------------------------------------------------------------------ what it found


def test_a_name_the_design_does_not_have_is_reported_rather_than_dropped(
    client: TestClient,
) -> None:
    """Drawing the design beside what a run records is the first thing that compares the
    two, and it found `run_driver`: a node runs emit against that the blueprint has none of.
    The map names it under a heading that says what it means."""
    on_canvas = {n["id"] for n in GRAPH["nodes"]}
    recorded = set(client.get("/api/runs/run_halted/trace").json()["nodes"])
    assert recorded - on_canvas, "the discrepancy this test is about has gone - update it"
    # P52: in the words the two readers use - "the drawing", not "this map"; "part", not
    # "node" - but saying the same thing, which is that the disagreement is real.
    assert "Recorded, but not in the drawing" in MAP_JS
    assert "a difference between the system and its blueprint" in MAP_JS
    assert "not in this drawing" in MAP_JS, "and the count beside the key says so too"
