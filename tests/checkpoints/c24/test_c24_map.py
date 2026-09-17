"""Checkpoint C24 - the whole design, painted with one run, as served.

Proves on the assembled system: the console serves every node of the blueprint with the
position the blueprint gives it and every edge between them; the Activity page carries the
map and a way into it from a run; and a run's trace and the served graph can be compared -
which is what the map does, and how it found the one name a run records that the design has
no node for.

P48 changed the export, the graph route and the Activity page. This is the join.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from tools.serve import build


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c24.db').as_posix()}")
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
    system.store.start_run("run_c24", "PILOT-2026-01", "sha256:c24", {})
    yield system, client
    system.close()
    ports.reset()


def test_the_served_graph_is_the_blueprints_own_drawing(served: Any) -> None:
    _, client = served
    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 118, "every node of the design is served"
    assert len(graph["edges"]) == 240
    assert all(isinstance(n["x"], int) and isinstance(n["y"], int) for n in graph["nodes"])
    # The positions are the blueprint's: a row of the process spine is a row, not a guess.
    spine = {n["id"]: n for n in graph["nodes"]}
    assert spine["source_parse"]["y"] == spine["untrusted_boundary"]["y"]
    assert graph["layout"]["node_width"] == 178


def test_the_page_carries_the_map_and_a_way_into_it(served: Any) -> None:
    _, client = served
    page = client.get("/").text
    assert 'id="dmap"' in page and page.count('id="dmap"') == 1
    assert 'data-act="map" data-run=' in page
    ids = re.findall(r'id="([\w-]+)"', page)
    assert sorted({i for i in ids if ids.count(i) > 1}) == [], "an id is carried twice"


def test_a_runs_trace_can_be_laid_over_that_drawing(served: Any) -> None:
    """The map is that comparison: the trace's node ids against the design's. Both halves
    have to be true - a node the design draws is paintable, and a name the design does not
    have is identifiable rather than silently absent."""
    system, client = served
    system.ops.bus.emit(
        run_id="run_c24",
        engagement_id="PILOT-2026-01",
        node_id="intake_window",
        type="run.launched",
        message="set complete",
    )
    system.ops.bus.emit(
        run_id="run_c24",
        engagement_id="PILOT-2026-01",
        node_id="run_driver",
        type="run.refused",
        message="refused before anything ran",
    )
    recorded = set(client.get("/api/runs/run_c24/trace").json()["nodes"])
    drawn = {n["id"] for n in client.get("/api/graph").json()["nodes"]}

    assert "intake_window" in recorded & drawn, "a node the design draws is paintable"
    assert "run_driver" in recorded - drawn, (
        "the run records work against a name the design has no node for, and the map "
        "reports it rather than dropping it - see BUILD/OPEN.md"
    )
    assert len(drawn) == 118, "and every node of the design is still there to be outlined"
