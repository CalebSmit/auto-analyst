"""Checkpoint C19 - the consoles, easier to use.

Proves: on the system a person starts, the Activity page's runs and review items name the
client the roster knows, every page serves a script that declares nothing twice and asks
nothing through a pop-up, and a review item can be read, its proposal revealed on the record,
and answered - the whole panel's round trip through the real routes.

P42 joined the console (P23) to the roster (P16) at the composition root and rebuilt the pages
of three phases (P23, P24, P29). The pages were tested as strings; this is where they meet the
data they render and the routes they call.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from intake.roster import RosterEntry, RosterState
from tools.serve import build


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c19.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    (tmp_path / "inbox" / "Clients").mkdir(parents=True)
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    system = build()
    client = TestClient(system.app)
    client.post("/api/admin/initialise", json={"who": "C. Smit", "reason": "C19"})
    system.roster.register(
        RosterEntry(
            engagement_id="PILOT-2026-01",
            client="Pilot Manufacturing Co",
            scope_path="valuation/non-esop/repeat",
            watch_id="w-none",
            destination_id="d-none",
            state=RosterState.PAUSED,
            folder="Pilot Manufacturing/2026",
        ),
        who="C. Smit",
        reason="C19",
    )
    system.store.start_run("run_c19", "PILOT-2026-01", "sha256:c19", {})
    system.store.open_review_item(
        "run_c19",
        "tagging:line-4",
        kind="line-item-tagging",
        subject="Which category is 'Shop supplies'?",
        detail={
            "skill": "line-item-tagging",
            "source_excerpt": "6420 Shop supplies 18,215.40",
            "locator": "TB!B4",
            "proposal": {"category": "other_operating_expense"},
            "confidence": 0.61,
        },
    )
    yield system, client
    system.close()
    ports.reset()


def test_the_activity_page_names_the_client_from_the_roster(served: Any) -> None:
    _, client = served
    (run,) = client.get("/api/runs").json()
    assert run["client"] == "Pilot Manufacturing Co"
    assert run["scope_path"] == "valuation/non-esop/repeat"
    (item,) = client.get("/api/review").json()
    assert item["client"] == "Pilot Manufacturing Co" and item["engagement_id"] == "PILOT-2026-01"


def test_every_served_page_is_one_namespace_and_asks_in_the_page(served: Any) -> None:
    _, client = served
    for path in ("/", "/admin", "/analytics"):
        page = client.get(path).text
        body = "\n".join(re.findall(r"<script>(.*?)</script>", page, re.S))
        declared = re.findall(r"^(?:const|let|var|function|async function)\s+(\w+)", body, re.M)
        assert len(declared) == len(set(declared)), path
        assert not re.search(r"(?<![\w.])(?:prompt|confirm|alert)\(", body), path


def test_the_review_panel_round_trip_through_the_real_routes(served: Any) -> None:
    system, client = served
    shown = client.get("/api/runs/run_c19/review/tagging:line-4").json()
    assert shown["source_excerpt"] and "proposal" not in shown, "the source first, no proposal"

    revealed = client.post("/api/runs/run_c19/review/tagging:line-4/reveal", json={}).json()
    assert revealed["proposal"] == {"category": "other_operating_expense"}
    assert any(e.type == "hitl.proposal.revealed" for e in system.store.events("run_c19"))

    refused = client.post(
        "/api/runs/run_c19/review/tagging:line-4/decide",
        json={"decision": "rejected", "expected_version": shown["version"], "rationale": ""},
    )
    assert refused.status_code == 422, (
        "a rejection with no reason is refused - and the page says so"
    )

    decided = client.post(
        "/api/runs/run_c19/review/tagging:line-4/decide",
        json={
            "decision": "corrected",
            "expected_version": shown["version"],
            "rationale": "shop supplies are cost of sales for this client",
            "answer": {"category": "cost_of_sales"},
        },
    )
    assert decided.status_code == 200, decided.text
    assert client.get("/api/review").json() == []
