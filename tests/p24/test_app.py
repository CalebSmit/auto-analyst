"""The admin surface over HTTP: setup without touching code, refusals as diagnostics."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from admin import AdminConsole
from admin.app import create_admin_app
from tests.p24.conftest import HEND, WHO, profile_for


@pytest.fixture
def client(console: AdminConsole) -> TestClient:
    return TestClient(create_admin_app(console))


def change(**extra: Any) -> dict[str, Any]:
    return {"who": WHO, "reason": "over http", **extra}


def test_an_engagement_is_set_up_over_http_and_activated_only_when_preflight_passes(
    client: TestClient,
) -> None:
    registered = client.post(
        "/api/admin/engagements",
        json=change(
            engagement_id=HEND,
            client="Henderson Manufacturing",
            scope_path="valuation/esop/repeat",
            watch_id="w-val",
            destination_id="d-local",
            folder="Henderson Manufacturing/2026 ESOP",
            budget_usd=12.0,
        ),
    )
    assert registered.status_code == 200 and registered.json()["state"] == "paused"

    refused = client.post(f"/api/admin/engagements/{HEND}/activate", json=change())
    assert refused.status_code == 409
    (d,) = refused.json()["detail"]["refused"]
    assert d["code"] == "CONFIG.PROFILE_INCOMPLETE" and d["owner"] == "config" and d["what_now"]

    assert (
        client.post(
            f"/api/admin/engagements/{HEND}/profile", json=change(profile=profile_for(HEND))
        ).status_code
        == 200
    )
    report = client.get("/api/admin/preflight", params={"engagement_id": HEND}).json()
    assert report["passed"] and len(report["checks"]) == 11
    activated = client.post(f"/api/admin/engagements/{HEND}/activate", json=change())
    assert activated.status_code == 200 and activated.json()["state"] == "active"

    setup = client.get("/api/admin/setup").json()
    row = next(r for r in setup["roster"] if r["engagement_id"] == HEND)
    assert row["state"] == "active" and row["template_pin"].startswith("Chartwell_ESOP")
    assert row["profile_recorded"] is True
    assert setup["credentials"][0]["present"] is True and "value" not in setup["credentials"][0]
    assert len(setup["cannot"]) == 7

    log = client.get("/api/admin/changes").json()
    assert [c["field"] for c in log][-2:] == ["engagements", f"roster/{HEND}/state"]
    assert all(c["who"] == WHO and c["reason"] for c in log)


def test_what_an_admin_cannot_do_comes_back_as_a_diagnostic(
    client: TestClient, henderson: Any
) -> None:
    over = client.post(f"/api/admin/engagements/{HEND}/budget", json=change(usd=1000.0))
    assert over.status_code == 409
    assert over.json()["detail"]["refused"][0]["code"] == "CONFIG.ADMIN_FORBIDDEN"
    assert (
        client.post(
            f"/api/admin/engagements/{HEND}/review-level", json=change(level="elevated")
        ).status_code
        == 200
    )
    lower = client.post(
        f"/api/admin/engagements/{HEND}/review-level", json=change(level="standard")
    )
    assert lower.status_code == 409
    assert client.get("/api/admin/credentials/AA_VAULT_KEY").json() == {
        "name": "AA_VAULT_KEY",
        "present": True,
    }
    model = client.get("/api/admin/model", params={"scope_path": "valuation/esop/repeat"}).json()
    assert model["bound_at"] == "valuation/esop/_segment"
    assert client.post("/api/admin/engagements/NOPE/activate", json=change()).status_code == 400
