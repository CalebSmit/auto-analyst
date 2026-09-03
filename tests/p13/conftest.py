"""Fixtures for P13.

`parsed` is a Source Parse Store with one document in it - four officer-compensation
rows under one locator - which is enough for provenance to resolve against and tie-out
to recompute from. The guards are built over the real registries and the real store; only
the rows are synthetic.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from guards.numeric_lock import NumericLock
from guards.provenance import ProvenanceGate
from guards.reconcile import Reconcile
from guards.schema import SchemaGate
from guards.tieout import TieoutGate
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from ops.source_parse import Row, SourceParseStore
from registries.contracts import ContractRegistry
from tools.recompute import recompute

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "guards"

ENGAGEMENT = "HEND-2026-04"
RUN_ID = "run_p13"
SOURCE = "sha256:" + "ab" * 32
ROWS_LOCATOR = "TB_FY25!B44:B47"
TOTAL_LOCATOR = "TB_FY25!B48"
TOLERANCE = 1.0

ROWS = (
    Row("Officer salary", 240000.0, "240,000.00"),
    Row("Officer bonus", 60000.0, "60,000.00"),
    Row("Auto allowance", 18400.0, "18,400.00"),
    Row("Health premium", 12600.0, "12,600.00"),
)
TRUE_TOTAL = 331000.0


def figure(
    value: float,
    locator: str = TOTAL_LOCATOR,
    derivation: dict[str, Any] | None = None,
    source_id: str = SOURCE,
    **overrides: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "value": value,
        "unit": "currency",
        "currency": "USD",
        "scale": 1,
        "period": {"type": "FY", "end": "2025-12-31"},
        "source_id": source_id,
        "locator": locator,
        "source_version": 1,
        "derivation": derivation,
        "masked": True,
        "confidence": 0.9,
        "produced_by": "ebitda-normalization@0.1.0",
        "model_pin": "claude-sonnet-5 @ effort=high",
    }
    body.update(overrides)
    return body


def addback(
    amount: dict[str, Any], ref: str = "li_officer_comp", category: str = "owner_related"
) -> dict[str, Any]:
    return {
        "candidate_id": "c1",
        "line_item_ref": ref,
        "category": category,
        "amount": amount,
        "rationale": "Owner compensation above market",
        "evidence": [{"source_id": SOURCE, "locator": ROWS_LOCATOR, "excerpt": "Officer comp"}],
        "recomputed": False,
        "above_materiality": True,
        "review_required": True,
    }


def ebitda_output(*items: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "skills/ebitda-normalization@1.0.0",
        "produced_by": "ebitda-normalization@0.1.0",
        "addback_schedule": list(items),
    }


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def fixture_table() -> dict[str, Any]:
    return yaml.safe_load((FIXTURES / "fixtures.yaml").read_text(encoding="utf-8"))


def case(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p13.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


@pytest.fixture
def started(store: SqlRunStore) -> str:
    store.start_run(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
        plan_hash="sha256:" + "7c" * 32,
        versions={
            "model_pin": "x",
            "skills": ["a@1.0.0"],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": "coa@1.0.0",
        },
        tieout_tolerance=TOLERANCE,
    )
    store.transition(RUN_ID, RunState.RUNNING)
    store.record_source(
        RUN_ID,
        {
            "source_id": SOURCE,
            "filename": "FY25 TB.xlsx",
            "document_type": "trial_balance",
            "source_version": 1,
            "received_at": "2026-04-02T09:15:00Z",
        },
    )
    return RUN_ID


@pytest.fixture
def parsed(store: SqlRunStore, started: str) -> SourceParseStore:
    parse_store = SourceParseStore(store)
    parse_store.write(started, SOURCE, ROWS_LOCATOR, ROWS)
    parse_store.write(
        started, SOURCE, TOTAL_LOCATOR, [Row("Total officer comp", TRUE_TOTAL, "331,000.00")]
    )
    return parse_store


@pytest.fixture
def sources() -> dict[str, int]:
    return {SOURCE: 1}


@pytest.fixture
def schema_gate(contracts: ContractRegistry, bus: EventBus) -> SchemaGate:
    return SchemaGate(contracts, bus)


@pytest.fixture
def provenance_gate(
    contracts: ContractRegistry, parsed: SourceParseStore, bus: EventBus
) -> ProvenanceGate:
    return ProvenanceGate(contracts, parsed, bus)


@pytest.fixture
def tieout_gate(parsed: SourceParseStore, bus: EventBus) -> TieoutGate:
    return TieoutGate(parsed, recompute, TOLERANCE, bus)


@pytest.fixture
def reconcile(bus: EventBus) -> Reconcile:
    return Reconcile(bus)


@pytest.fixture
def numeric_lock(bus: EventBus) -> NumericLock:
    return NumericLock(bus)
