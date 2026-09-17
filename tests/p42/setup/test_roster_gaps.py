"""P42: the engagement list says what a profile still lacks, where the engagement is set up."""

from __future__ import annotations

from typing import Any

from admin import AdminConsole
from tests.p24.conftest import NOVK, WHO, entry


def test_a_complete_profile_has_no_gaps(console: AdminConsole, henderson: Any) -> None:
    (row,) = [r for r in console.setup()["roster"] if r["engagement_id"] == henderson.engagement_id]
    assert row["profile_gaps"] == []


def test_a_gap_is_named_beside_the_engagement(console: AdminConsole, henderson: Any) -> None:
    """Registered with no profile yet: the list says so, before any run could stop on it."""
    console.register_engagement(
        entry(NOVK, client="Novak Advisory", folder="Novak Advisory/2026"),
        profile=None,
        who=WHO,
        reason="registered before the engagement letter came back",
    )
    (row,) = [r for r in console.setup()["roster"] if r["engagement_id"] == NOVK]
    assert row["profile_gaps"] == ["no engagement profile recorded"]
