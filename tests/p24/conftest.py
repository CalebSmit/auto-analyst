"""Fixtures for P24: a whole environment set up through the Admin Console.

A watched inbox and an outbox on disk behind the real ports, a `.env` behind the
Secrets Port, the two synthetic templates registered, a configuration document written
through the store, and a roster built through the console - so preflight is exercised
against the same adapters a run uses. Nothing is mocked; a check that fails here fails
for the reason it would fail on a real machine.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import ports
from admin import AdminConsole, Preflight
from deliver.registry import TemplateRegistry
from graph.resolve import ScopeResolver
from intake.config import ConfigStore
from intake.roster import ProjectRoster, RosterEntry, RosterState
from intake.store import IntakeStore
from ops.events import EventBus
from ops.run_store import SqlRunStore, open_store
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from tests.p15.conftest import profile as p15_profile

ROOT = Path(__file__).resolve().parents[2]
WHO = "C. Smit"
HEND = "HEND-2026-04"
NOVK = "NOVK-2026-11"
PMBR = "PMBR-2026-01"
ESOP_PIN = "Chartwell_ESOP_Model_v9@9.4"
MASTER_PIN = "Chartwell_Master_Model_v14@14.2"
T0 = datetime(2026, 9, 4, 8, 0, tzinfo=UTC)


class Clock:
    def __init__(self, at: datetime = T0) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at

    def advance(self, **delta: float) -> None:
        self.at = self.at + timedelta(**delta)


def config_document(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "config_document@1.1.0",
        "environment": "local",
        "watches": [
            {
                "id": "w-val",
                "kind": "pattern",
                "name": "Valuation - client tree",
                "root": "Clients",
                "recipe": "monthly-refresh",
                "depth": 2,
            }
        ],
        "intake": {"quiet_period_minutes": 30, "max_wait_hours": 24, "lock_timeout_hours": 6},
        "document_type_conventions": {
            "trial_balance": ["tb_", "trial balance"],
            "financial_statements": ["income statement", "balance sheet", "financials"],
        },
        "destinations": [
            {
                "id": "d-local",
                "name": "Pilot / scratch",
                "path": "_pilot",
                "adapter": "local_folder",
            }
        ],
        "credentials": [
            {"name": "ANTHROPIC_API_KEY", "purpose": "model access", "expires_on": "2027-03-01"},
            {"name": "AA_VAULT_KEY", "purpose": "mask vault", "expires_on": "2027-03-01"},
        ],
        "model_bindings": [
            {
                "layer": "_firm",
                "file": "Chartwell_Master_Model_v14.xlsx",
                "template_version": "14.2",
                "why": "The template most of the firm builds into.",
            },
            {
                "layer": "valuation/esop/_segment",
                "file": "Chartwell_ESOP_Model_v9.xlsx",
                "template_version": "9.4",
                "why": "ESOP work carries schedules the master has no rows for.",
            },
            {
                "layer": "consulting/_group",
                "file": None,
                "template_version": None,
                "why": "Declared and bound to nothing; falls through to the firm default.",
            },
        ],
        "engagements": {},
    }
    body.update(overrides)
    return body


def profile_for(engagement_id: str, scope_path: str = "valuation/esop/repeat") -> dict[str, Any]:
    practice, segment, disposition = scope_path.split("/")
    return p15_profile(
        engagement_id=engagement_id, practice=practice, segment=segment, disposition=disposition
    )


def entry(
    engagement_id: str = HEND,
    *,
    client: str = "Henderson Manufacturing",
    scope_path: str = "valuation/esop/repeat",
    folder: str = "Henderson Manufacturing/2026 ESOP",
    destination_id: str = "d-local",
    template_pin: str = "",
    budget_usd: float | None = 12.0,
    state: RosterState = RosterState.PAUSED,
) -> RosterEntry:
    return RosterEntry(
        engagement_id=engagement_id,
        client=client,
        scope_path=scope_path,
        watch_id="w-val",
        destination_id=destination_id,
        state=state,
        folder=folder,
        template_pin=template_pin,
        budget_usd=budget_usd,
    )


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def constraints() -> ConstraintRegistry:
    return ConstraintRegistry.load()


@pytest.fixture
def environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """The ports' roots on disk, and the credentials preflight expects."""
    inbox = tmp_path / "inbox"
    (inbox / "Clients" / "Henderson Manufacturing" / "2026 ESOP").mkdir(parents=True)
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    # The dotenv adapter reads the process environment ahead of the file, and presence
    # is all preflight ever asks it. Nothing here is a real key.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setenv("AA_VAULT_KEY", "not-a-real-key")
    monkeypatch.delenv("BOX_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("AA_INBOX_ROOT", str(inbox))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(outbox))
    ports.reset()
    return {"inbox": inbox, "outbox": outbox}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p24.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def config(store: SqlRunStore, contracts: ContractRegistry) -> ConfigStore:
    cfg = ConfigStore(store, contracts, environment="local")
    cfg.write(config_document(), who=WHO, reason="P24 test setup")
    return cfg


@pytest.fixture
def roster(store: SqlRunStore, config: ConfigStore) -> ProjectRoster:
    return ProjectRoster(store, config)


@pytest.fixture
def templates() -> TemplateRegistry:
    """The two synthetic masters. The checked-in bindings also name a Corporate
    Finance model that has no input schema yet - that is P24's own finding, and
    preflight reports it rather than this fixture hiding it."""
    registry = TemplateRegistry()
    registry.register("Chartwell_ESOP_Model_v9.xlsx", "9.4")
    registry.register("Chartwell_Master_Model_v14.xlsx", "14.2")
    return registry


@pytest.fixture
def preflight(
    environment: dict[str, Path],
    config: ConfigStore,
    roster: ProjectRoster,
    templates: TemplateRegistry,
    store: SqlRunStore,
    constraints: ConstraintRegistry,
    clock: Clock,
) -> Preflight:
    return Preflight(
        config,
        roster,
        storage=ports.get_storage(),
        delivery=ports.get_delivery(),
        secrets=ports.get_secrets(),
        templates=templates,
        resolver=ScopeResolver(bindings=config.model_bindings()),
        intake_store=IntakeStore(store),
        constraints=constraints,
        clock=clock,
    )


@pytest.fixture
def console(
    config: ConfigStore,
    roster: ProjectRoster,
    preflight: Preflight,
    constraints: ConstraintRegistry,
) -> AdminConsole:
    return AdminConsole(config, roster, preflight, constraints=constraints)


@pytest.fixture
def henderson(console: AdminConsole) -> RosterEntry:
    """Registered with a complete profile, paused, ready to activate."""
    return console.register_engagement(
        entry(), profile=profile_for(HEND), who=WHO, reason="engagement letter signed"
    )
