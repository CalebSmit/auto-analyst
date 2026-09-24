"""The roster and the sweep planner: inactive is unreachable, not merely unchecked."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy import text

from graph.architecture_assertions import assert_the_roster_gates_every_source, load_graph
from intake import Intake
from intake.config import ConfigStore
from intake.roster import ProjectRoster, RosterState
from intake.store import IntakeStore
from intake.sweep import SweepPlanner
from ops.models import AppendOnlyViolation
from ops.run_store import SqlRunStore
from registries.errors import RegistryError
from tests.importing import imported_modules
from tests.p16.conftest import (
    BRDG,
    BRDG_FOLDER,
    HEND,
    HEND_FOLDER,
    LAUNCH,
    ROOT,
    THRP,
    WHO,
    WSTF,
    WSTF_FOLDER,
    Clock,
    Spy,
    config_document,
    drop,
    entry,
)

# ------------------------------------------------------------------ roster


def test_three_states_and_every_change_is_logged(
    roster: ProjectRoster, config: ConfigStore
) -> None:
    states = {e.engagement_id: e.state for e in roster.entries()}
    assert states == {
        HEND: RosterState.ACTIVE,
        WSTF: RosterState.PAUSED,
        BRDG: RosterState.ARCHIVED,
        THRP: RosterState.PAUSED,
    }
    roster.set_state(WSTF, RosterState.ACTIVE, who="J. Reyes", reason="FY25 TB received", note="")
    assert roster.get(WSTF).state is RosterState.ACTIVE  # type: ignore[union-attr]
    change = config.changes()[-1]
    assert change.who == "J. Reyes" and change.reason == "FY25 TB received"
    assert change.field == f"roster/{WSTF}/state"
    assert change.old == {"state": "paused"} and change.new == {"state": "active"}


def test_the_roster_has_no_delete_and_touches_no_run(roster: ProjectRoster) -> None:
    for forbidden in ("delete", "remove", "cancel", "halt", "run"):
        assert not any(forbidden in name for name in dir(ProjectRoster)), forbidden
    roster.set_state(HEND, RosterState.ARCHIVED, who=WHO, reason="done")
    assert roster.get(HEND) is not None, "archiving keeps the binding for the record"


def test_a_change_needs_a_person_and_a_reason(roster: ProjectRoster) -> None:
    with pytest.raises(ValueError, match="person"):
        roster.set_state(HEND, RosterState.PAUSED, who=" ", reason="x")
    with pytest.raises(ValueError, match="reason"):
        roster.set_state(HEND, RosterState.PAUSED, who=WHO, reason="")


# ------------------------------------------------------------------- sweep


def test_the_planner_sweeps_active_skips_paused_and_never_sees_archived(
    inbox: Path, port: Spy, roster: ProjectRoster, config: ConfigStore, intake_store: IntakeStore
) -> None:
    drop(inbox, f"Clients/{HEND_FOLDER}/TB_FY25.xlsx", "hend")
    drop(inbox, f"Clients/{WSTF_FOLDER}/TB_FY25.xlsx", "wstf")
    drop(inbox, f"Clients/{BRDG_FOLDER}/TB_FY24.xlsx", "brdg")
    drop(inbox, "Clients/Pinecrest Holdings/2026 ESOP/TB_FY25.xlsx", "pine")
    drop(inbox, "Consulting/Thorpe/DDR response.pdf", "thrp")

    plan = SweepPlanner(roster, config, port, intake_store).plan()

    assert [(t.location, t.engagement_id) for t in plan.targets] == [
        (f"Clients/{HEND_FOLDER}", HEND),
    ]
    assert {(s.engagement_id, s.state) for s in plan.skipped} == {
        (WSTF, RosterState.PAUSED),
        (THRP, RosterState.PAUSED),
    }
    assert [(u.location, u.files) for u in plan.unclaimed] == [
        ("Clients/Pinecrest Holdings/2026 ESOP", 1)
    ]
    assert BRDG not in {t.engagement_id for t in plan.targets}
    assert BRDG not in {s.engagement_id for s in plan.skipped}
    assert port.touched == [], "planning lists; it reads nothing"


def test_an_unclaimed_folder_is_reported_and_never_guessed(
    inbox: Path,
    port: Spy,
    roster: ProjectRoster,
    config: ConfigStore,
    intake_store: IntakeStore,
    clock: Clock,
) -> None:
    drop(inbox, "Clients/Delaney Bros/2026 Sale/financials.xlsx", "x")
    drop(inbox, "Clients/Delaney Bros/2026 Sale/TB_FY25.xlsx", "y")
    planner = SweepPlanner(roster, config, port, intake_store, clock=clock)
    planner.plan()
    clock.advance(hours=1)
    planner.plan()

    (row,) = intake_store.unclaimed()
    assert row.location == "Clients/Delaney Bros/2026 Sale" and row.files == 2
    assert row.first_seen < row.last_seen
    assert not any("Delaney" in p for p in port.touched)


def test_no_two_watches_claim_the_same_path(config: ConfigStore) -> None:
    doc = config_document()
    doc["watches"].append(
        {
            "id": "w-dup",
            "kind": "bound",
            "name": "dup",
            "root": "Clients/Henderson Manufacturing",
            "recipe": "monthly-refresh",
            "engagement_id": HEND,
        }
    )
    with pytest.raises(RegistryError) as refused:
        config.write(doc, who=WHO, reason="oops")
    assert refused.value.diagnostic.code == "INTAKE.WATCH_OVERLAP"
    assert config.version() == 1, "nothing was written"


def test_no_two_roster_entries_claim_one_folder(
    port: Spy, roster: ProjectRoster, config: ConfigStore, intake_store: IntakeStore
) -> None:
    roster.register(
        entry("HEND-2027-01", HEND_FOLDER, RosterState.ACTIVE, "Henderson again"),
        who=WHO,
        reason="next year",
    )
    with pytest.raises(RegistryError) as refused:
        SweepPlanner(roster, config, port, intake_store).plan()
    assert refused.value.diagnostic.code == "INTAKE.WATCH_OVERLAP"


def test_a_bound_watch_for_an_engagement_not_on_the_roster_is_not_swept(
    inbox: Path, port: Spy, roster: ProjectRoster, config: ConfigStore, intake_store: IntakeStore
) -> None:
    doc = config_document()
    doc["watches"].append(
        {
            "id": "w-ghost",
            "kind": "bound",
            "name": "ghost",
            "root": "Consulting/Ghost",
            "recipe": "full-ddr-intake",
            "engagement_id": "GHST-2026-01",
        }
    )
    config.write(doc, who=WHO, reason="a watch nobody listed")
    drop(inbox, "Consulting/Ghost/TB_FY25.xlsx", "ghost")
    plan = SweepPlanner(roster, config, port, intake_store).plan()
    assert "Consulting/Ghost" not in plan.locations()
    assert "Consulting/Ghost" not in port.listed


# ----------------------------------------------------------- invariant 24


def test_invariant_24_by_graph_walk() -> None:
    """The exit criterion, on the blueprint graph: every intake source is dominated by
    the sweep planner, and the sweep planner reads the roster."""
    assert_the_roster_gates_every_source(load_graph())


def test_invariant_24_by_running_it(
    inbox: Path, intake: Intake, port: Spy, store: SqlRunStore
) -> None:
    """The exit criterion, on the code: an off-roster folder's files are never listed,
    never stat'd, never read, and start no run - while the active engagement beside
    them is processed."""
    drop(inbox, f"Clients/{HEND_FOLDER}/TB_FY25.xlsx", "hend tb")
    drop(inbox, f"Clients/{WSTF_FOLDER}/TB_FY25.xlsx", "paused")
    drop(inbox, f"Clients/{BRDG_FOLDER}/TB_FY24.xlsx", "archived")
    drop(inbox, "Clients/Pinecrest Holdings/2026 ESOP/TB_FY25.xlsx", "unclaimed")

    result = intake.sweep(LAUNCH)

    assert [r.engagement_id for r in result.arrived] == [HEND]
    for foreign in ("Westfield", "Bridgewater", "Pinecrest"):
        assert not any(foreign in p for p in port.touched), foreign
        assert not any(foreign in p for p in port.listed), foreign
    assert {r.engagement_id for r in store.runs()} <= {HEND}


def test_the_planner_reads_the_roster_and_the_config_and_nothing_else() -> None:
    tree = ast.parse((ROOT / "intake" / "sweep.py").read_text(encoding="utf-8"))
    imported = {(n.module or "") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any(
        m.startswith(("harness", "graph", "guards", "tools", "privacy")) for m in imported
    )
    assert "intake.roster" in imported and "intake.config" in imported


# ------------------------------------------------------------ config store


def test_the_config_document_is_validated_on_write(config: ConfigStore) -> None:
    from registries.errors import ContractViolation

    bad = config_document()
    bad["watches"][0]["root"] = "/absolute/path"
    with pytest.raises(ContractViolation):
        config.write(bad, who=WHO, reason="bad root")
    bad = config_document(document_type_conventions={"invoice": ["inv"]})
    with pytest.raises(RegistryError) as refused:
        config.write(bad, who=WHO, reason="unknown type")
    assert refused.value.diagnostic.code == "INTAKE.UNKNOWN_TYPE"
    assert config.version() == 1


def test_every_write_bumps_the_version_and_logs_the_fields_that_changed(
    config: ConfigStore,
) -> None:
    doc = config_document()
    doc["intake"]["quiet_period_minutes"] = 10
    assert config.write(doc, who="J. Reyes", reason="faster pilot cycle") == 2
    change = config.changes()[-1]
    assert change.field == "intake" and change.who == "J. Reyes"
    assert change.old["value"]["quiet_period_minutes"] == 30
    assert change.new["value"]["quiet_period_minutes"] == 10
    assert config.timing().quiet_period_minutes == 10


def test_an_engagement_override_tightens_timing(config: ConfigStore) -> None:
    doc = config_document(engagements={HEND: {"quiet_period_minutes": 5, "max_wait_hours": 4}})
    config.write(doc, who=WHO, reason="pilot")
    assert config.timing(HEND).quiet_period_minutes == 5
    assert config.timing(HEND).max_wait_hours == 4
    assert config.timing(WSTF).quiet_period_minutes == 30


def test_the_change_log_is_append_only(config: ConfigStore, store: SqlRunStore) -> None:
    from sqlalchemy import select

    from ops.models import ConfigChange

    with pytest.raises(AppendOnlyViolation), store._session() as session:  # noqa: SLF001
        row = session.scalars(select(ConfigChange)).first()
        assert row is not None
        row.reason = "rewritten"
    with pytest.raises(Exception, match="append-only"), store._engine.begin() as conn:  # noqa: SLF001
        conn.execute(text("DELETE FROM config_change"))
    assert config.changes()[0].reason == "P16 test setup"


def test_configuration_reaches_no_guard() -> None:
    """Configuration writes the engagement record; guards read the run. No module under
    guards/ or harness/ imports the config store."""
    # By import tree. This asserted `"intake.config" not in source`, which
    # `from intake import config` defeats entirely - and that spelling is the natural one
    # to reach for. tests/importing.py has the rule and the reason.
    for folder in ("guards", "harness", "graph", "privacy"):
        for path in (ROOT / folder).rglob("*.py"):
            names = imported_modules(path.read_text(encoding="utf-8"))
            assert "intake.config" not in names, path
            assert not any(n == "intake" for n in names), (path, "imports the package")
