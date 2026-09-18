"""Checkpoint C26 - the map, whole, on the system that serves it.

P50, P51 and P52 are one piece of work on one view. Each passed alone against the strings
the view is built from. What a checkpoint is for is the part that can only be wrong when
they meet: that the drawing's geometry is the one the console serves, that the state a run
left on each part is derivable from the record rather than decided by the browser, and that
the view's headline cannot contradict the run's own page.

The browser-side detail stays in tests/p50, p51 and p52. What is here needs a server.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from ops.console.map_view import MAP_JS, MAP_STYLE
from tools.serve import build


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c26.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("AA_NO_ENV_FILE", "1")
    (tmp_path / "inbox").mkdir()
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    system = build()
    client = TestClient(system.app)
    system.store.start_run("run_c26", "PILOT-2026-01", "sha256:c26", {})
    for node, kind in (("intake_window", "run.launched"), ("source_parse", "intake.read")):
        system.ops.bus.emit(
            run_id="run_c26",
            engagement_id="PILOT-2026-01",
            node_id=node,
            type=kind,
            message=f"{node}: {kind}",
        )
    system.ops.bus.emit_guard(
        run_id="run_c26",
        engagement_id="PILOT-2026-01",
        node_id="untrusted_boundary",
        guard="untrusted_boundary",
        passed=False,
        checked=1,
        failed=1,
    )
    yield system, client
    system.close()
    ports.reset()


def test_the_box_the_edges_are_drawn_to_is_the_box_the_blueprint_places(served: Any) -> None:
    """The geometry is shared between two files that cannot see each other: the stylesheet
    fixes the box's height and the JavaScript draws every edge to it. P50 measured the box
    at build time so they cannot drift - but the width is the blueprint's own, exported,
    and if the two ever disagree the edges leave from beside their boxes rather than from
    them. That is what made the drawing look generated, and it is invisible in code review.
    """
    _, client = served
    layout = client.get("/api/graph").json()["layout"]
    assert layout["node_width"] == 178
    assert f"width:{layout['node_width']}px" in MAP_STYLE, "the box is the served width"
    # And the height the edges are drawn to is measured off a built box, not written twice.
    assert "height:52px" in MAP_STYLE
    assert "const NH = MAP_NODE_H;" in MAP_JS


def test_what_the_run_never_got_to_is_derivable_from_what_is_served(served: Any) -> None:
    """P52 tells a part this run was stopped before reaching from a part no run ever uses.
    It derives the first from the blueprint's own edges, walking downstream of the failure -
    so the console has to serve directed edges, and the failure has to be in the trace.
    """
    _, client = served
    trace = client.get("/api/runs/run_c26/trace").json()
    failed = [node for node, state in (trace["nodes"] or {}).items() if state == "failed"]
    assert failed, "the guard this run failed at is on the trace as failed"

    edges = client.get("/api/graph").json()["edges"]
    forward: dict[str, list[str]] = {}
    for edge in edges:
        forward.setdefault(edge["from"], []).append(edge["to"])

    # The walk the view does, done here against the served graph.
    blocked, queue = set(), list(failed)
    while queue:
        for nxt in forward.get(queue.pop(), []):
            state = (trace["nodes"] or {}).get(nxt, "notreached")
            if nxt in blocked or state not in ("notreached", "pending"):
                continue
            blocked.add(nxt)
            queue.append(nxt)
    assert blocked, "a failure with nothing downstream would make the distinction moot"
    assert not (blocked & set(failed)), "what it reached is not what it never got to"


def test_the_headline_cannot_contradict_the_runs_own_page(served: Any) -> None:
    """The map's count is "N of M steps done". The run's own page counts the same steps
    from the same record. Two panels about one run that disagree on how far it got is the
    thing this checkpoint exists to refuse - and the reason the map reads the run's record
    rather than the page's copy of it.
    """
    _, client = served
    detail = client.get("/api/runs/run_c26").json()
    assert "steps" in detail, "the map's denominator comes from here"
    assert "spend" in detail and "state" in detail
    # Read from the run being shown, never borrowed from whatever the page last painted.
    assert "const trace = await get(`/api/runs/${encodeURIComponent(runId)}/trace`)" in MAP_JS
    assert "MAP_RUN_DETAIL = await get(`/api/runs/${encodeURIComponent(runId)}`)" in MAP_JS
    assert "LAST_TRACE" not in MAP_JS


def test_the_order_and_the_trail_come_from_the_events_as_served(served: Any) -> None:
    """The numbering is first appearance in the order the server sent them, and the trail
    is drawn between consecutive ones - so the events have to arrive in a settled order
    with a node on each."""
    _, client = served
    events = client.get("/api/runs/run_c26/events").json()
    assert events and all(e["node_id"] for e in events)
    seen: list[str] = []
    for event in events:
        if event["node_id"] not in seen:
            seen.append(event["node_id"])
    assert seen[:3] == ["intake_window", "source_parse", "untrusted_boundary"]
    assert "localeCompare" not in MAP_JS, "the server's order is the order"


def test_the_page_serves_the_whole_view_and_one_script_namespace(served: Any) -> None:
    _, client = served
    page = client.get("/").text
    for part in ('id="dmap-rail"', 'id="dmap-path"', 'data-act="mapStop"', 'class="plate"'):
        assert part in page, part
    ids = re.findall(r'id="([\w-]+)"', page)
    doubled = sorted({i for i in ids if ids.count(i) > 1})
    assert doubled == [], f"the page carries {doubled} twice"


def test_the_geometry_the_view_draws_is_under_the_blueprints_digest() -> None:
    """A blueprint moved on the canvas without a re-export is the same drift as a node
    added without one, and this view is now drawn entirely from that export."""
    root = Path(__file__).resolve().parents[3]
    graph = json.loads((root / "graph" / "architecture.json").read_text(encoding="utf-8"))
    assert len(graph["nodes"]) == 118
    assert all(n.get("x") is not None for n in graph["nodes"])
    assert graph["layout"]["row_height"] and graph["layout"]["node_width"]
    # The sheet is ruled at the blueprint's own module rather than at a chosen number.
    rule = "transparent 1px {}px)"
    assert rule.format(graph["layout"]["row_height"]) in MAP_STYLE
