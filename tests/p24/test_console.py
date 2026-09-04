"""The Admin Console: every write logged with who, what, when and why; what an admin
may and may not change; model binding through the same resolver as the skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from admin import AdminConsole, AdminRefused
from graph.resolve import ScopeResolver, _read_bindings
from intake.config import Destination, Watch
from intake.roster import RosterState
from registries.errors import RegistryError
from tests.p24.conftest import HEND, PMBR, ROOT, WHO, entry, profile_for


def test_every_change_lands_in_the_log_with_who_what_when_and_why(
    console: AdminConsole, henderson: Any
) -> None:
    before = len(console.changes())
    console.set_budget(HEND, 10.0, who="J. Reyes", reason="pilot budget")
    console.set_review_level(HEND, "elevated", who="J. Reyes", reason="prior-year override rate")
    console.bind_model(
        "corporate-finance/_group",
        "CF_LBO_Model_v3.xlsx",
        "3.1",
        why="CF runs a returns-driven model",
        who=WHO,
        reason="Pembroke kickoff",
    )
    console.pause(HEND, who=WHO, reason="client holding on the FY25 trial balance", note="holding")
    changes = console.changes()[before:]
    fields = [c.field for c in changes]
    assert fields == [
        f"roster/{HEND}/budget_usd",
        f"roster/{HEND}/review_level",
        "model_bindings",
        f"roster/{HEND}/state",
    ]
    budget = changes[0]
    assert budget.who == "J. Reyes" and budget.reason == "pilot budget"
    assert budget.old == {"value": 12.0} and budget.new == {"value": 10.0} and budget.at
    assert changes[3].old == {"state": "paused"} and changes[3].new["note"] == "holding"
    with pytest.raises(ValueError, match="names a person"):
        console.set_budget(HEND, 9.0, who="", reason="anon")


def test_an_admin_may_raise_a_review_level_and_never_lower_it(
    console: AdminConsole, henderson: Any
) -> None:
    assert (
        console.set_review_level(HEND, "elevated", who=WHO, reason="x").review_level == "elevated"
    )
    with pytest.raises(AdminRefused) as refused:
        console.set_review_level(HEND, "standard", who=WHO, reason="relax")
    d = refused.value.diagnostic
    assert d.code == "CONFIG.ADMIN_FORBIDDEN" and "not lowered" in d.detail
    assert console.roster.get(HEND).review_level == "elevated"
    with pytest.raises(ValueError):
        console.set_review_level(HEND, "off", who=WHO, reason="x")


def test_an_admin_may_set_a_budget_at_or_below_the_ceiling_and_never_above(
    console: AdminConsole, henderson: Any
) -> None:
    ceiling = console.firm_ceiling
    assert console.set_budget(HEND, ceiling, who=WHO, reason="max").budget_usd == ceiling
    with pytest.raises(AdminRefused) as refused:
        console.set_budget(HEND, ceiling + 0.01, who=WHO, reason="a bit more")
    assert refused.value.diagnostic.code == "CONFIG.ADMIN_FORBIDDEN"
    assert refused.value.diagnostic.expected == f"<= {ceiling:.2f}"
    assert console.roster.get(HEND).budget_usd == ceiling


def test_a_model_binds_through_the_same_five_layer_walk_as_the_skills(
    console: AdminConsole, henderson: Any
) -> None:
    esop = console.resolve_model("valuation/esop/repeat")
    assert esop["bound_at"] == "valuation/esop/_segment"
    assert esop["binding"]["file"] == "Chartwell_ESOP_Model_v9.xlsx"
    assert esop["layers"] == [
        "_firm",
        "valuation/_group",
        "valuation/_repeat",
        "valuation/esop/_segment",
        "valuation/esop/repeat",
    ]
    consulting = console.resolve_model("consulting/tbd/repeat")
    assert consulting["bound_at"] == "_firm", "declared with nothing bound falls through"
    assert consulting["binding"]["file"] == "Chartwell_Master_Model_v14.xlsx"

    # The Scope Resolver over the store's bindings agrees with the console's walk.
    resolver = ScopeResolver(bindings=console.config.model_bindings())
    assert resolver.resolve("valuation/esop/repeat").template.layer == "valuation/esop/_segment"
    assert resolver.resolve("consulting/tbd/repeat").template.layer == "_firm"

    console.bind_model(
        "valuation/esop/repeat",
        "Chartwell_Master_Model_v14.xlsx",
        "14.2",
        why="this client is on the master",
        who=WHO,
        reason="client request",
    )
    assert console.resolve_model("valuation/esop/repeat")["bound_at"] == "valuation/esop/repeat"
    assert console.roster.get(HEND).template_pin == ""
    row = next(r for r in console.setup()["roster"] if r["engagement_id"] == HEND)
    assert row["template_pin"] == "Chartwell_Master_Model_v14@14.2"


def test_the_checked_in_bindings_seed_the_store_once(console: AdminConsole) -> None:
    seed = _read_bindings(ROOT / "templates" / "bindings.yaml")
    version = console.seed_model_bindings(seed, who=WHO, reason="seed from the repo")
    assert version == console.config.version()
    assert set(console.config.model_bindings()) == set(seed)
    assert console.config.model_bindings()["consulting/_group"].file == ""


def test_watches_destinations_and_profiles_are_validated_on_the_way_in(
    console: AdminConsole, henderson: Any
) -> None:
    with pytest.raises(RegistryError) as refused:
        console.add_watch(
            Watch("w-dup", "pattern", "Overlapping", "Clients", "monthly-refresh"),
            who=WHO,
            reason="oops",
        )
    assert refused.value.diagnostic.code == "INTAKE.WATCH_OVERLAP"
    assert [w.id for w in console.config.watches()] == ["w-val"], "nothing was written"

    console.add_destination(
        Destination(
            "d-box-val",
            "Valuation deliverables",
            "Deliverables/Valuation",
            adapter="box_client_credentials",
            credential="BOX_CLIENT_SECRET",
        ),
        who=WHO,
        reason="first Box destination",
    )
    assert console.config.destination("d-box-val").credential == "BOX_CLIENT_SECRET"

    bad = profile_for(HEND)
    del bad["owner_compensation_baseline"]
    with pytest.raises(RegistryError):
        console.set_profile(HEND, bad, who=WHO, reason="incomplete")
    assert console.config.profile(HEND)["owner_compensation_baseline"]["amount"] == 285000
    with pytest.raises(ValueError, match="names"):
        console.set_profile(HEND, profile_for(PMBR), who=WHO, reason="wrong id")


def test_registration_goes_active_only_past_preflight(console: AdminConsole) -> None:
    with pytest.raises(AdminRefused):
        console.register_engagement(
            entry(state=RosterState.ACTIVE), profile=None, who=WHO, reason="go"
        )
    assert console.roster.get(HEND).state is RosterState.PAUSED, "registered, not active"
    active = console.register_engagement(
        entry(
            PMBR,
            client="Pembroke Logistics",
            scope_path="valuation/esop/repeat",
            folder="Pembroke Logistics/2026 ESOP",
            state=RosterState.ACTIVE,
        ),
        profile=profile_for(PMBR),
        who=WHO,
        reason="go",
    )
    assert active.state is RosterState.ACTIVE
    archived = console.archive(PMBR, who=WHO, reason="delivered")
    assert archived.state is RosterState.ARCHIVED


def test_the_console_cannot_reach_a_guard_the_vault_a_skill_or_the_release_gate(
    tmp_path: Path,
) -> None:
    """Invariant 23 as a property of the package and of the graph."""
    import inspect

    import admin.app
    import admin.console
    import admin.preflight
    from graph.architecture_assertions import (
        assert_config_cannot_reach_a_failclosed_node,
        assert_one_destination_and_one_template,
        load_graph,
    )

    for module in (admin.console, admin.preflight, admin.app):
        imports = [
            line
            for line in inspect.getsource(module).splitlines()
            if line.startswith(("import ", "from "))
        ]
        for forbidden in ("guards", "privacy", "skills", "deliver.release", "harness", "precedent"):
            assert not any(f"{forbidden}" in line for line in imports), (module, forbidden)
    names = {n for n in dir(AdminConsole) if not n.startswith("_")}
    assert not {n for n in names if any(w in n for w in ("guard", "mask", "release", "skill"))}
    graph = load_graph()
    assert_config_cannot_reach_a_failclosed_node(graph)
    assert_one_destination_and_one_template(graph)
