"""Fixtures for P12.

The vault key comes through the Secrets Port from the environment, the way it does in a
run - not passed in as a parameter, which would be a second door. Each test gets a fresh
key and a fresh database; the stability tests reopen the same database on purpose.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

import ports
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from privacy.mask import Identifier, Masker
from privacy.unmask import Unmasker
from privacy.vault import KEY_NAME, MaskVault, open_vault
from privacy.verify import UnmaskVerify
from registries.contracts import ContractRegistry

ENGAGEMENT = "HEND-2026-04"
OTHER = "NOVK-2026-11"
RUN_ID = "run_p12"

HENDERSON = (
    Identifier("CLIENT", "Henderson Manufacturing"),
    Identifier("PERSON", "Bob Henderson"),
    Identifier("ACCOUNT", "Bob's LLC Checking"),
    Identifier("ACCOUNT", "Operating Account"),
)

TRIAL_BALANCE = (
    "Henderson Manufacturing - trial balance FY2025\n"
    "Bob's LLC Checking            48,231.00   acct 1234-5678-9012\n"
    "Operating Account            112,904.55\n"
    "Owner draw - Bob Henderson    36,000.00\n"
)


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch) -> str:
    fresh = Fernet.generate_key().decode()
    monkeypatch.setenv(KEY_NAME, fresh)
    ports.reset()
    return fresh


@pytest.fixture
def vault_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'vault.db').as_posix()}"


@pytest.fixture
def vault(key: str, vault_url: str) -> Iterator[MaskVault]:
    opened = open_vault(ports.get_secrets(), vault_url)
    yield opened
    opened.close()


@pytest.fixture
def masker(vault: MaskVault) -> Masker:
    return Masker(vault)


@pytest.fixture
def unmasker(vault: MaskVault) -> Unmasker:
    return Unmasker(vault)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p12.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


@pytest.fixture
def started(store: SqlRunStore) -> str:
    store.start_run(
        run_id=RUN_ID, engagement_id=ENGAGEMENT, plan_hash="sha256:" + "7c" * 32,
        versions={"model_pin": "x", "skills": ["a@1.0.0"], "contracts": "1.0.0",
                  "constraints": "1.0.0", "taxonomy": "coa@1.0.0"},
    )
    store.transition(RUN_ID, RunState.RUNNING)
    return RUN_ID


@pytest.fixture
def verifier(bus: EventBus) -> UnmaskVerify:
    return UnmaskVerify(bus)
