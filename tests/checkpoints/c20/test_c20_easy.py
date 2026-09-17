"""Checkpoint C20 - easy to start and use.

Proves: on the system `start.cmd` starts, a setting written only in .env reaches the composed
server; a person sets up a watch and a destination from the page's own routes, adds a client's
file through the page and finds it where the sweep reads; the file is recorded against them;
and Help is served beside the consoles it explains.

P43 touched the composition root (serve.py), the admin console (P24) and the ops console
(P23). Each was tested alone; this is where the start path, the page and the folders meet.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

import ports
from intake.roster import RosterEntry, RosterState
from tools.serve import build

WHO = {"who": "C. Smit"}


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    # Only the database is in the shell; the folders arrive from .env, as on Caleb's machine.
    for name in ("AA_INBOX_ROOT", "AA_OUTBOX_ROOT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c20.db').as_posix()}")
    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    (tmp_path / "inbox").mkdir()
    (tmp_path / "outbox").mkdir()
    env = tmp_path / ".env"
    env.write_text(
        f"AA_INBOX_ROOT={tmp_path / 'inbox'}\nAA_OUTBOX_ROOT={tmp_path / 'outbox'}\n",
        encoding="utf-8",
    )
    applied = ports.load_env_file(env)
    assert {"AA_INBOX_ROOT", "AA_OUTBOX_ROOT"} <= set(applied)

    ports.reset()
    system = build()
    yield system, TestClient(system.app), tmp_path
    system.close()
    ports.reset()
    for name in applied:
        monkeypatch.delenv(name, raising=False)


def test_a_person_sets_up_and_adds_a_file_from_the_page(served: Any) -> None:
    system, client, home = served
    change = {**WHO, "reason": "C20"}
    assert client.post("/api/admin/initialise", json=change).status_code == 200
    watched = client.post(
        "/api/admin/watches",
        json={
            **change,
            "id": "w-clients",
            "kind": "pattern",
            "name": "Clients",
            "root": "Clients",
            "recipe": "mature-company-valuation",
        },
    )
    assert watched.status_code == 200, watched.text
    destined = client.post(
        "/api/admin/destinations",
        json={**change, "id": "d-out", "name": "Deliverables", "path": "_deliverables"},
    )
    assert destined.status_code == 200, destined.text

    system.roster.register(
        RosterEntry(
            engagement_id="PILOT-2026-01",
            client="Pilot Manufacturing Co",
            scope_path="valuation/non-esop/repeat",
            watch_id="w-clients",
            destination_id="d-out",
            state=RosterState.PAUSED,
            folder="Pilot Manufacturing/2026",
        ),
        who="C. Smit",
        reason="C20",
    )
    panel = client.get("/api/admin/engagements/PILOT-2026-01/files").json()
    expected = home / "inbox" / "Clients" / "Pilot Manufacturing" / "2026"
    assert Path(panel["absolute"]) == expected, "the folder .env named is the one the page shows"
    assert panel["can_add"] and panel["files"] == []

    added = client.post(
        "/api/admin/engagements/PILOT-2026-01/files",
        json={
            **change,
            "name": "Pilot Income Statement FY2025.xlsx",
            "content_base64": base64.b64encode(b"statements").decode(),
        },
    )
    assert added.status_code == 200, added.text
    assert (expected / "Pilot Income Statement FY2025.xlsx").read_bytes() == b"statements"
    listed = client.get("/api/admin/engagements/PILOT-2026-01/files").json()
    assert [f["path"] for f in listed["files"]] == ["Pilot Income Statement FY2025.xlsx"]
    changes = client.get("/api/admin/changes").json()
    assert any(c["field"] == "files/PILOT-2026-01" for c in changes)


def test_help_is_served_beside_the_consoles(served: Any) -> None:
    _, client, _ = served
    for path in ("/", "/admin", "/analytics", "/help"):
        page = client.get(path)
        assert page.status_code == 200, path
        assert 'href="/help"' in page.text, path
