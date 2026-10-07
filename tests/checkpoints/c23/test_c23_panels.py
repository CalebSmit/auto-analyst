"""Checkpoint C23 - panels that earn their space, as served.

Proves on the assembled system: the Analytics route carries the denominator beside every
rate it reports, and every served page carries the counts in its titles, the shadow at a cut
edge, and a board that puts the run's own detail beside the list it is chosen from.

P47 touched the analytics computation and three pages. This is the join.

The last of those used to read *two rows of the three*, which is a shape rather than a
property, and P172 found what that shape cost every panel beside it. The test below says
why, and asks for what P47 was after instead of for how it got it.
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


def test_the_run_detail_is_served_the_room_it_needs_in_one_band(served: TestClient) -> None:
    """P47 gave the run's own detail two rows of the three, and this checkpoint asserted
    that shape. P172 found what the shape cost.

    On a grid, every panel in a row is stretched to that row's height. A panel spanning two
    rows has its height shared out across rows nothing else is in, so the panels beside it
    are stretched to heights nothing in their own band asked for - and the run detail is
    unbounded, because it draws one row per decision a person made and the median run has
    34 of them. Measured with three real runs loaded: the detail panel 3,018px, the Runs
    panel stretched to 3,108px around 259px of content, Waiting on a person to 1,557px
    around 92, and the page 3,750px tall.

    So what P47 was actually after is kept and the shape it used is not: the detail is
    served on the first band, beside the list it is chosen from, and nothing on the board
    spans a row. The property is `tests/p172`'s; what this checkpoint adds is that it is
    true of the page the server assembles rather than of the string a module holds.
    """
    areas = re.search(r"grid-template-areas:(.*?)\}", served.get("/").text, re.S)
    assert areas, "the board no longer names its areas"
    bands = [row.split() for row in re.findall(r'"([^"]*)"', areas.group(1))]
    assert bands, "the board names no bands"
    assert "detail" in bands[0], "the run's own detail is not on the band it is chosen from"
    assert "runs" in bands[0], "the list and the thing the list is for are in different bands"

    rows_of: dict[str, set[int]] = {}
    for n, row in enumerate(bands):
        for area in row:
            rows_of.setdefault(area, set()).add(n)
    spanning = sorted(area for area, rows in rows_of.items() if len(rows) > 1)
    assert spanning == [], f"served with a panel in more than one band: {spanning}"
