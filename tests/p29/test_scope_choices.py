"""An engagement is labelled by choosing its practice group, and a group with nothing
behind it says so.

Three exit criteria. The third is the one that is easy to lose: a way to *choose* a scope
must not become a second way to *store* one, or the roster and the dashboard start
disagreeing about what an engagement is.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from admin import AdminConsole
from admin.app import create_admin_app
from admin.preflight import CHECKS
from intake.roster import RosterState
from registries.scopes import ScopeRegistry
from tests.p24.conftest import HEND, NOVK, WHO, entry, profile_for

CONSULTING = "consulting/tbd/repeat"


@pytest.fixture
def client(console: AdminConsole) -> TestClient:
    return TestClient(create_admin_app(console))


def test_the_surface_offers_every_declared_scope_and_marks_the_undefined_ones(
    console: AdminConsole,
) -> None:
    """The first exit criterion. The registry is the source, so adding a practice group
    is an entry there and it appears here without anything else changing."""
    registry = ScopeRegistry.load()
    choices = console.scope_choices()

    assert [p["id"] for p in choices["practices"]] == [p.id for p in registry.practices]
    assert [d["id"] for d in choices["dispositions"]] == [d.id for d in registry.dispositions]
    assert choices["layer_order"] == list(registry.layer_order)

    valuation = next(p for p in choices["practices"] if p["id"] == "valuation")
    assert valuation["defined"] is True
    assert {s["id"] for s in valuation["segments"]} == {"esop", "non-esop"}
    assert all(s["defined"] for s in valuation["segments"])

    consulting = next(p for p in choices["practices"] if p["id"] == "consulting")
    assert consulting["defined"] is False
    assert [s["id"] for s in consulting["segments"]] == ["tbd"]
    assert consulting["segments"][0]["defined"] is False
    assert "segments" in consulting["note"], "it says why, rather than just being empty"

    # Every path the taxonomy admits, with what each one would actually get.
    paths = {p["scope_path"]: p for p in choices["paths"]}
    assert paths["valuation/esop/repeat"]["defined"] is True
    assert paths["valuation/esop/repeat"]["skills"] >= 10
    assert paths["valuation/esop/repeat"]["firm_layer_only"] is False
    assert paths[CONSULTING]["defined"] is False
    assert paths[CONSULTING]["firm_layer_only"] is True
    assert paths[CONSULTING]["skills"] > 0, "the firm's skills are still there"


def test_what_a_group_would_get_is_measured_rather_than_inferred(
    console: AdminConsole,
) -> None:
    """`defined` is what somebody declared; `firm_layer_only` is what a run would get.
    They can disagree - a group declared defined with nothing written for it yet - and
    when they do, the resolver is the one telling the truth."""
    choices = console.scope_choices()
    for path in choices["paths"]:
        assert isinstance(path["firm_layer_only"], bool)
        assert path["skills"] > 0, "every path gets the firm layer at least"
        if path["defined"]:
            assert not path["firm_layer_only"], path["scope_path"]


def test_the_choices_are_served_over_http(client: TestClient) -> None:
    response = client.get("/api/admin/scopes")
    assert response.status_code == 200
    body = response.json()
    assert {"layer_order", "practices", "dispositions", "paths"} <= set(body)
    assert any(p["id"] == "valuation" for p in body["practices"])
    assert json.dumps(body), "it is serialisable, which a dashboard needs"


def test_an_engagement_scoped_to_an_undefined_group_is_visible_in_preflight(
    console: AdminConsole, henderson: Any
) -> None:
    """The second exit criterion. Allowed, and never silent."""
    console.register_engagement(
        entry(NOVK, client="Novak Advisory", scope_path=CONSULTING, folder="Novak Advisory/2026"),
        profile=profile_for(NOVK, CONSULTING),
        who=WHO,
        reason="consulting pilot, before the segments are named",
    )
    # Named, because preflight considers the engagement being activated whatever its
    # roster state - which is the moment somebody needs to be told.
    report = console.check(NOVK)
    check = next(c for c in report.checks if c.id == "scope_defined")

    assert check.status == "warn", "correct, and not useful, is a warning"
    assert len(check.failures) == 1
    failure = check.failures[0]
    assert failure.diagnostic.code == "SCOPE.GROUP_UNDEFINED"
    assert failure.diagnostic.owner == "config"
    assert NOVK in failure.diagnostic.detail
    assert "firm layer only" in failure.diagnostic.detail
    assert "named its segments" in failure.diagnostic.detail
    assert "practice leads" in failure.diagnostic.what_now


def test_an_undefined_group_does_not_block_activation(
    console: AdminConsole, henderson: Any
) -> None:
    """A warning blocks nothing. The firm may onboard an engagement before its practice
    group has been described, and the alternative - refusing - would make the tool the
    reason the work waits.

    What does block is a workflow the group cannot run. `monthly-refresh` needs the EBITDA
    skill, which lives at the valuation group layer, so a consulting engagement on it
    cannot compile - and P32 found that at a sweep, not at setup. Preflight compiles now.
    The undefined group still does not block: on a workflow made of firm-layer skills,
    which `full-ddr-intake` is, the same engagement activates.
    """
    console.register_engagement(
        entry(NOVK, client="Novak Advisory", scope_path=CONSULTING, folder="Novak Advisory/2026"),
        profile=profile_for(NOVK, CONSULTING),
        who=WHO,
        reason="consulting pilot",
    )
    refused = console.check(NOVK).blocking(NOVK)
    assert [f.diagnostic.code for f in refused] == ["SCOPE.RECIPE_INVALID"], refused
    assert NOVK in refused[0].diagnostic.detail, "named, so the person who chose it hears"

    console.set_recipe(NOVK, "full-ddr-intake", who=WHO, reason="a workflow of firm skills")
    report = console.check(NOVK)
    assert report.blocking(NOVK) == ()
    assert console.activate(NOVK, who=WHO, reason="go").state is RosterState.ACTIVE

    # And it is still reported afterwards: activation does not clear it.
    after = next(c for c in console.check().checks if c.id == "scope_defined")
    assert after.status == "warn" and after.failures


def test_a_fully_defined_setup_passes_the_check(console: AdminConsole, henderson: Any) -> None:
    check = next(c for c in console.check(HEND).checks if c.id == "scope_defined")
    assert check.status == "pass"
    assert check.detail.startswith("1 of 1")
    assert check.failures == ()


def test_the_check_sits_beside_the_one_that_resolves_scopes(
    console: AdminConsole, henderson: Any
) -> None:
    """Position, not count. This check reports on what `scope_resolves` just resolved, so
    it reads immediately after it; the number of checks is the blueprint's, and tests/p30
    is where the two are compared."""
    ids = [c[0] for c in CHECKS]
    assert ids.index("scope_defined") == ids.index("scope_resolves") + 1

    blueprint = (Path(__file__).resolve().parents[2] / "docs" / "architecture.html").read_text(
        encoding="utf-8"
    )
    assert "checks over a proposed or live configuration" in blueprint
    assert "practice group and segment that are actually defined" in blueprint

    report = console.check(HEND)
    assert [c.id for c in report.checks] == ids


def test_choosing_a_scope_adds_no_second_place_to_store_one(
    console: AdminConsole, henderson: Any
) -> None:
    """The third exit criterion, and the one worth guarding. The roster entry holds a
    scope path and nothing else; the choices are derived from the registry every time.
    A stored copy of the practice or segment would be a second source of truth the first
    time somebody edited one of them."""
    setup = console.setup()
    row = next(r for r in setup["roster"] if r["engagement_id"] == HEND)
    assert row["scope_path"] == "valuation/esop/repeat"
    assert not {k for k in row if k in ("practice", "segment", "disposition", "group")}

    document = console.config.document()
    engagements = document.get("engagements", {})
    for record in engagements.values():
        assert not {k for k in record if k in ("practice", "segment", "disposition")}

    # And the choices carry no engagement: they are a property of the registry alone.
    choices = console.scope_choices()
    assert HEND not in json.dumps(choices)


def test_the_registry_stays_the_source_when_it_changes(console: AdminConsole) -> None:
    """Adding a practice group is an entry in scopes.yaml. Nothing in admin/ names one,
    so a group added there appears in the dashboard with no code change."""
    import inspect

    import admin.console

    source = inspect.getsource(admin.console)
    for hardcoded in ('"valuation"', '"consulting"', '"corporate-finance"', '"esop"'):
        assert hardcoded not in source, hardcoded
