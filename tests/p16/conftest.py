"""Fixtures for P16.

A watched folder on disk behind the Storage Port, a roster with one engagement in each
state, a configuration document with one pattern watch and one bound watch, and a clock
the tests move. Files are dropped into the folder; sweeps are run against the clock.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import ports
from intake import Intake
from intake.config import ConfigStore
from intake.launch import RunLauncher
from intake.lock import EngagementLock
from intake.roster import ProjectRoster, RosterEntry, RosterState
from intake.store import IntakeStore
from ops.events import EventBus
from ops.run_store import SqlRunStore, open_store
from ports.storage import FileRef, StoragePort
from registries.contracts import ContractRegistry

ROOT = Path(__file__).resolve().parents[2]
T0 = datetime(2026, 9, 3, 4, 0, tzinfo=UTC)
WHO = "C. Smit"

HEND = "HEND-2026-04"
WSTF = "WSTF-2025-19"
BRDG = "BRDG-2025-22"
THRP = "THRP-2026-03"
HEND_FOLDER = "Henderson Manufacturing/2026 ESOP"
WSTF_FOLDER = "Westfield Group/2025 ESOP"
BRDG_FOLDER = "Bridgewater Tool/2025 ESOP"
PLAN_HASH = "sha256:" + "7c" * 32
VERSIONS = {
    "model_pin": "claude-opus-5 @ effort=high",
    "skills": ["line-item-tagging@1.0.0"],
    "contracts": "1.0.0",
    "constraints": "1.0.0",
    "taxonomy": "coa-taxonomy@1.0.0",
}


def config_document(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "config_document@1.0.0",
        "environment": "local",
        "watches": [
            {
                "id": "w-val",
                "kind": "pattern",
                "name": "Valuation - client tree",
                "root": "Clients",
                "recipe": "monthly-refresh",
                "depth": 2,
            },
            {
                "id": "w-con",
                "kind": "bound",
                "name": "Consulting - pilot",
                "root": "Consulting/Thorpe",
                "recipe": "full-ddr-intake",
                "engagement_id": THRP,
            },
        ],
        "intake": {"quiet_period_minutes": 30, "max_wait_hours": 24, "lock_timeout_hours": 6},
        "document_type_conventions": {
            "trial_balance": ["tb_", "trial balance"],
            "financial_statements": ["income statement", "balance sheet", "financials"],
            "ddr_response": ["ddr"],
            "request_schedule": ["request"],
            "participant_census": ["census"],
            "tax_return": ["tax return", "1120"],
            "plan_document": ["plan document"],
        },
        "destinations": [{"id": "d-local", "name": "Pilot / scratch", "path": "_pilot"}],
        "engagements": {},
    }
    body.update(overrides)
    return body


class Clock:
    def __init__(self, at: datetime = T0) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at

    def advance(self, minutes: float = 0, hours: float = 0, seconds: float = 0) -> None:
        self.at = self.at + timedelta(minutes=minutes, hours=hours, seconds=seconds)


class Spy:
    """A storage port that remembers which files were stat'd or read. What it did not
    touch is the proof that binding happens before reading."""

    name = "spy"

    def __init__(self, inner: StoragePort) -> None:
        self.inner = inner
        self.listed: list[str] = []
        self.touched: list[str] = []

    def list(self, prefix: str = "") -> tuple[FileRef, ...]:
        self.listed.append(prefix)
        return self.inner.list(prefix)

    def read(self, ref: FileRef) -> bytes:
        self.touched.append(ref.path)
        return self.inner.read(ref)

    def stat(self, ref: FileRef):  # noqa: ANN201
        self.touched.append(ref.path)
        return self.inner.stat(ref)


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture
def inbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "inbox"
    root.mkdir()
    monkeypatch.setenv("AA_INBOX_ROOT", str(root))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    ports.reset()
    return root


@pytest.fixture
def port(inbox: Path) -> Spy:
    return Spy(ports.get_storage())


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p16.db').as_posix()}")
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
    cfg.write(config_document(), who=WHO, reason="P16 test setup")
    return cfg


def entry(engagement_id: str, folder: str, state: RosterState, client: str) -> RosterEntry:
    return RosterEntry(
        engagement_id=engagement_id,
        client=client,
        scope_path="valuation/esop/repeat",
        watch_id="w-val",
        destination_id="d-local",
        state=state,
        folder=folder,
        template_pin="Chartwell_ESOP_Model_v9.xlsx@9.4",
        budget_usd=12.0,
    )


@pytest.fixture
def roster(store: SqlRunStore, config: ConfigStore) -> ProjectRoster:
    r = ProjectRoster(store, config)
    r.register(
        entry(HEND, HEND_FOLDER, RosterState.ACTIVE, "Henderson Manufacturing"),
        who=WHO,
        reason="engagement letter signed",
    )
    r.register(
        entry(WSTF, WSTF_FOLDER, RosterState.PAUSED, "Westfield Group"),
        who=WHO,
        reason="client holding on the FY25 trial balance",
    )
    r.register(
        entry(BRDG, BRDG_FOLDER, RosterState.ARCHIVED, "Bridgewater Tool"),
        who=WHO,
        reason="delivered FY25; archived",
    )
    r.register(
        RosterEntry(
            engagement_id=THRP,
            client="Thorpe & Sons",
            scope_path="consulting/tbd/repeat",
            watch_id="w-con",
            destination_id="d-local",
            state=RosterState.PAUSED,
        ),
        who=WHO,
        reason="awaiting engagement letter",
    )
    return r


@pytest.fixture
def intake_store(store: SqlRunStore) -> IntakeStore:
    return IntakeStore(store)


@pytest.fixture
def lock(store: SqlRunStore, bus: EventBus, clock: Clock) -> EngagementLock:
    return EngagementLock(store, bus, timeout=timedelta(hours=6), clock=clock)


@pytest.fixture
def launcher(
    store: SqlRunStore, bus: EventBus, lock: EngagementLock, intake_store: IntakeStore, clock: Clock
) -> RunLauncher:
    return RunLauncher(store, bus, lock, intake_store, clock=clock)


@pytest.fixture
def intake(
    port: Spy,
    roster: ProjectRoster,
    config: ConfigStore,
    intake_store: IntakeStore,
    launcher: RunLauncher,
    clock: Clock,
) -> Intake:
    return Intake(port, roster, config, intake_store, launcher, clock=clock)


LAUNCH = {"plan_hash": PLAN_HASH, "versions": VERSIONS}


def drop(inbox: Path, relative: str, content: str | bytes) -> str:
    """Put a file in the watched folder. Returns the sha256 source_id it will get."""
    path = inbox / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8") if isinstance(content, str) else content
    path.write_bytes(data)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def hend(name: str) -> str:
    return f"Clients/{HEND_FOLDER}/{name}"


def events_of(store: SqlRunStore, run_id: str, event_type: str) -> list[Any]:
    return [e for e in store.events(run_id) if e.type == event_type]
