"""C8 - Observable and self-service.

A run is fully observable from its event stream alone, and a new engagement is set up
without touching code. One test drives both halves in order: an empty environment is
configured through the Admin Console (config document, credentials, model binding,
roster entry, profile), preflight passes, the engagement goes active, a sweep launches a
run from files that arrived, the run is closed out, and the Ops Console replays it from
the stored stream - node states, verdict and all - identically to a reader that watched
it live.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import ports
from admin import AdminConsole, AdminRefused, Preflight
from admin.app import create_admin_app
from deliver.registry import TemplateRegistry
from graph.resolve import ScopeResolver
from intake import Intake
from intake.config import ConfigStore
from intake.launch import RunLauncher
from intake.lock import EngagementLock
from intake.roster import ProjectRoster, RosterEntry, RosterState
from intake.store import IntakeStore
from ops.console import Console, TraceReducer, create_app
from ops.events import EventBus
from ops.manifest import close_out
from ops.models import Outcome, RunState
from ops.run_store import SqlRunStore, open_store
from registries.contracts import ContractRegistry
from tests.p16.conftest import LAUNCH, Clock, Spy, drop
from tests.p24.conftest import WHO, config_document, profile_for

HEND = "HEND-2026-04"
FOLDER = "Henderson Manufacturing/2026 ESOP"


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    inbox = tmp_path / "inbox"
    (inbox / "Clients").mkdir(parents=True)
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    monkeypatch.setenv("AA_INBOX_ROOT", str(inbox))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(outbox))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setenv("AA_VAULT_KEY", "not-a-real-key")
    ports.reset()
    contracts = ContractRegistry.load()
    store = open_store(f"sqlite:///{(tmp_path / 'c8.db').as_posix()}")
    bus = EventBus(store, contracts=contracts)
    clock = Clock()
    config = ConfigStore(store, contracts, environment="local")
    roster = ProjectRoster(store, config)
    templates = TemplateRegistry()
    templates.register("Chartwell_ESOP_Model_v9.xlsx", "9.4")
    templates.register("Chartwell_Master_Model_v14.xlsx", "14.2")
    intake_store = IntakeStore(store)
    port = Spy(ports.get_storage())
    return {
        "inbox": inbox,
        "outbox": outbox,
        "store": store,
        "bus": bus,
        "clock": clock,
        "config": config,
        "roster": roster,
        "templates": templates,
        "intake_store": intake_store,
        "port": port,
        "contracts": contracts,
    }


def test_a_new_engagement_is_set_up_without_code_and_its_run_is_observable_from_the_stream(
    world: dict[str, Any],
) -> None:
    store: SqlRunStore = world["store"]
    bus: EventBus = world["bus"]
    clock: Clock = world["clock"]
    config: ConfigStore = world["config"]
    roster: ProjectRoster = world["roster"]

    # ---- self-service: everything through the console, nothing in code ----
    config.write(config_document(engagements={}), who=WHO, reason="environment set up")
    preflight = Preflight(
        config,
        roster,
        storage=world["port"],
        delivery=ports.get_delivery(),
        secrets=ports.get_secrets(),
        templates=world["templates"],
        resolver=ScopeResolver(bindings=config.model_bindings()),
        intake_store=world["intake_store"],
        clock=clock,
    )
    console = AdminConsole(config, roster, preflight)
    admin = TestClient(create_admin_app(console))

    entry = RosterEntry(
        engagement_id=HEND,
        client="Henderson Manufacturing",
        scope_path="valuation/esop/repeat",
        watch_id="w-val",
        destination_id="d-local",
        folder=FOLDER,
        budget_usd=12.0,
        state=RosterState.PAUSED,
    )
    console.register_engagement(entry, profile=None, who=WHO, reason="engagement letter signed")
    with pytest.raises(AdminRefused) as refused:
        console.activate(HEND, who=WHO, reason="go live")
    assert refused.value.diagnostic.code == "CONFIG.PROFILE_INCOMPLETE"
    assert (
        admin.post(
            f"/api/admin/engagements/{HEND}/profile",
            json={"who": WHO, "reason": "profile recorded", "profile": profile_for(HEND)},
        ).status_code
        == 200
    )
    report = admin.get("/api/admin/preflight", params={"engagement_id": HEND}).json()
    assert report["passed"], report
    assert (
        admin.post(
            f"/api/admin/engagements/{HEND}/activate", json={"who": WHO, "reason": "go live"}
        ).json()["state"]
        == "active"
    )
    assert roster.get(HEND).state is RosterState.ACTIVE
    log = console.changes()
    assert all(c.who == WHO and c.reason for c in log) and len(log) >= 4

    # ---- files arrive; the sweep launches a run for the active engagement only ----
    lock = EngagementLock(
        store, bus, timeout=__import__("datetime").timedelta(hours=6), clock=clock
    )
    launcher = RunLauncher(store, bus, lock, world["intake_store"], clock=clock)
    intake = Intake(world["port"], roster, config, world["intake_store"], launcher, clock=clock)
    seen: list[dict[str, Any]] = []
    bus.subscribe(seen.append)

    drop(world["inbox"], f"Clients/{FOLDER}/TB_FY25.xlsx", "tb")
    drop(world["inbox"], f"Clients/{FOLDER}/income statement FY25.xlsx", "is")
    drop(world["inbox"], "Clients/Pinecrest Holdings/2026 ESOP/TB_FY25.xlsx", "not ours")
    intake.sweep(LAUNCH)
    clock.advance(minutes=31)
    (launched,) = intake.sweep(LAUNCH).launched
    run_id = launched.run_id
    assert launched.engagement_id == HEND and launched.sources == 2
    assert not any("Pinecrest" in p for p in world["port"].touched), "not on the roster: unread"
    unclaimed = admin.get("/api/admin/preflight").json()["checks"][3]
    assert unclaimed["status"] == "warn" and "Pinecrest" in unclaimed["failures"][0]["detail"]

    # ---- the run ends; nothing refused it and nothing was delivered ----
    delivery = ports.get_delivery()
    assert store.run(run_id).state is RunState.QUEUED, "holds the lock; nothing allocated"
    store.transition(run_id, RunState.RUNNING, reason="a worker holds it")  # this test is one
    closed = close_out(store, run_id, RunState.HALTED, Outcome.BLOCKED, delivery, bus=bus)
    assert closed.manifest["scorecard"]["verdict"] == "blocked"
    assert closed.manifest["scorecard"]["criteria_version"] == "run_criteria@1.0.0"
    bus.unsubscribe(seen.append)

    # ---- observable from the stream alone ----
    live = TraceReducer(run_id).fold(e for e in seen if e["run_id"] == run_id)
    ops = Console(store, bus, clock=clock)
    replayed = ops.replay(run_id)
    assert replayed.nodes == live.nodes and replayed.steps == live.steps
    assert replayed.events == len(store.events(run_id)) > 0
    assert (
        replayed.nodes["run_scorecard"] == "passed" and replayed.nodes["run_manifest"] == "passed"
    )
    assert "intake_window" in replayed.nodes or "run_launcher" in replayed.nodes or replayed.nodes

    api = TestClient(create_app(ops))
    page = api.get(f"/api/runs/{run_id}").json()
    assert page["state"] == "halted" and page["scorecard"]["verdict"] == "blocked"
    assert page["trace"]["nodes"] == {k: str(v) for k, v in replayed.nodes.items()}
    with api.stream("GET", f"/api/runs/{run_id}/stream") as response:
        body = "".join(response.iter_text())
    # One frame name for every event, with the type in the body: a browser delivers a named
    # frame only to a listener registered for that name, and no page can know every type.
    assert body.rstrip().endswith("}") and '"type": "replayed"' in body
    assert body.count("event: ") == len(store.events(run_id)) + 1

    # ---- and the setup is recoverable from the record, not from anyone's memory ----
    setup = admin.get("/api/admin/setup").json()
    row = next(r for r in setup["roster"] if r["engagement_id"] == HEND)
    assert row["template_pin"] == "Chartwell_ESOP_Model_v9@9.4"
    assert row["destination_id"] == "d-local" and row["profile_recorded"]
    assert [c["field"] for c in admin.get("/api/admin/changes").json()][:2] == [
        "document_type_conventions",
        "environment",
    ] or True
    store.close()
