"""Checkpoint C23 - panels that earn their space, as served.

Proves on the assembled system: the Analytics route carries the denominator beside every
rate it reports, and every served page carries the counts in its titles, the shadow at a cut
edge, and a board that gives the run's own detail two rows of the three.

P47 touched the analytics computation and three pages. This is the join.
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
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c23.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("AA_NO_ENV_FILE", "1")
    (tmp_path / "inbox").mkdir()
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    system = build()
    yield TestClient(system.app)
    system.close()
    ports.reset()


def test_the_analytics_route_reports_the_counts_behind_its_rates(served: TestClient) -> None:
    trends = served.get("/api/analytics?days=30").json()["trends"]
    for field in ("routed_items", "decided_items", "tieout_checked_runs"):
        assert field in trends, f"{field} is not served beside the rate it explains"


def test_every_served_page_says_what_it_holds_and_what_it_hides(served: TestClient) -> None:
    for path, ids in (("/", ("n-runs", "n-inbox", "n-alerts")), ("/admin", ("n-roster",))):
        page = served.get(path).text
        for name in ids:
            assert f'id="{name}"' in page, f"{path} is missing the count {name}"
    for path in ("/", "/admin", "/analytics", "/help"):
        page = served.get(path).text
        assert page.count("radial-gradient(farthest-side at 50% 0") == 1, path


def test_the_run_detail_is_served_two_rows_of_the_three(served: TestClient) -> None:
    areas = re.search(r"grid-template-areas:(.*?)\}", served.get("/").text, re.S)
    assert areas and '"runs detail alerts"' in areas.group(1)
