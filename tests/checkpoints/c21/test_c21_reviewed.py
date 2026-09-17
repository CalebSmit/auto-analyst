"""Checkpoint C21 - the dashboards, after five reviews of them.

Proves, on the system a person starts: a request that arrives under another name is refused
before a route sees it; the console reads alerts rather than raising them; a run's decisions
are readable over the real routes with the reveal beside each; an item on a run a newer file
replaced is not asked of anybody; and every served page says when it cannot reach the server
and builds no handler out of data.

P44 and P45 touched the composition root (serve.py), the run store, both consoles and the
shared theme. Each was tested alone; this is where they meet.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from ops.models import DecisionKind
from tools.serve import build


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c21.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("AA_NO_ENV_FILE", "1")
    (tmp_path / "inbox" / "Clients").mkdir(parents=True)
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    system = build()
    client = TestClient(system.app)
    system.store.start_run(
        "run_c21", "PILOT-2026-01", "sha256:c21", {"model_pin": "claude-sonnet-5"}
    )
    system.store.open_review_item(
        "run_c21", "tagging:line-4", kind="line-item-tagging", subject="Which category?"
    )
    yield system, client
    system.close()
    ports.reset()


def test_a_page_at_another_name_is_refused_before_a_route_runs(served: Any) -> None:
    _, client = served
    assert client.get("/api/runs", headers={"host": "rebound.example.com"}).status_code == 403
    assert client.get("/api/runs").status_code == 200


def test_reading_the_console_writes_nothing_to_the_record(served: Any) -> None:
    """The page says it drives nothing, and it was the only thing raising alerts - so a run
    that stalled on a Friday raised nothing until somebody opened a browser."""
    system, client = served
    before = len(system.store.events("run_c21"))
    client.get("/api/alerts")
    client.get("/api/alerts")
    assert len(system.store.events("run_c21")) == before


def test_a_decision_is_readable_afterwards_with_its_reveal(served: Any) -> None:
    system, client = served
    shown = client.get("/api/runs/run_c21/review/tagging:line-4").json()
    client.post("/api/runs/run_c21/review/tagging:line-4/reveal", json={})
    decided = client.post(
        "/api/runs/run_c21/review/tagging:line-4/decide",
        json={
            "decision": "accepted",
            "expected_version": shown["version"],
            "rationale": "",
        },
    )
    assert decided.status_code == 200, decided.text

    (row,) = client.get("/api/runs/run_c21/decisions").json()
    assert row["decision"] == str(DecisionKind.ACCEPTED)
    assert row["decided_by"] and row["revealed_at"], "who decided, and that they looked first"
    assert row["seconds_looking"] is not None


def test_an_item_on_a_replaced_run_is_not_asked_of_anybody(served: Any) -> None:
    system, client = served
    system.store.start_run("run_c21b", "PILOT-2026-01", "sha256:c21b", {})
    system.store.mark_superseded_by("run_c21", "run_c21b")
    assert client.get("/api/review").json() == []
    assert system.store.review_items("run_c21"), "it stays on the record, on its own run"


def test_every_served_page_says_when_it_is_blind_and_writes_no_handler(served: Any) -> None:
    _, client = served
    for path in ("/", "/admin", "/analytics"):
        page = client.get(path).text
        assert '<div id="offline"></div>' in page, path
        assert re.findall(r'on\w+="[^"]*\$\{[^"]*"', page) == [], path
