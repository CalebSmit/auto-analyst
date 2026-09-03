"""Fixtures for P11.

`Answers` is a port under the test's control: it returns what it is told, with whatever
usage it is told, and never touches a network. The phase is about what happens on the way
to the port and on the way back - the turn check, the scan, the governor, the pin, the
meter - and none of that needs a real model to test.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness.budget import BudgetGovernor
from harness.door import ModelDoor
from ops.cost import CostMeter
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from ports.llm import LLMRequest, LLMResponse, Message, ModelPin, Usage
from privacy.payload_scan import IdentifierList, PayloadScan
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry

ENGAGEMENT = "HEND-2026-04"
RUN_ID = "run_p11"

# What the vault would hold for Henderson, and what the masker says it substituted.
NAMES = ("Henderson Manufacturing", "Bob Henderson", "Bob's LLC Checking")
TOKENS = ("[[CLIENT_1]]", "[[PERSON_1]]", "[[ACCOUNT_17]]")


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def constraints() -> ConstraintRegistry:
    return ConstraintRegistry.load()


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p11.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


@pytest.fixture
def started(store: SqlRunStore) -> str:
    store.start_run(
        run_id=RUN_ID, engagement_id=ENGAGEMENT, plan_hash="sha256:" + "7c" * 32,
        versions={"model_pin": "claude-sonnet-5 @ effort=high", "skills": ["a@1.0.0"],
                  "contracts": "1.0.0", "constraints": "1.0.0", "taxonomy": "coa@1.0.0"},
    )
    store.transition(RUN_ID, RunState.RUNNING)
    store.start_clock(RUN_ID)
    return RUN_ID


@pytest.fixture
def identifiers() -> IdentifierList:
    return IdentifierList.of(ENGAGEMENT, NAMES, TOKENS)


class Answers:
    """A port that says what it is told to say."""

    name = "answers"

    def __init__(self, text: str = "ok", model: str = "claude-sonnet-5",
                 usage: Usage | None = None) -> None:
        self.text = text
        self.model = model
        self.usage = usage or Usage(input_tokens=1200, output_tokens=300)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            text=self.text, model=self.model, stop_reason="end_turn",
            usage=self.usage, request_id="test",
        )


@pytest.fixture
def port() -> Answers:
    return Answers()


@pytest.fixture
def meter(store: SqlRunStore) -> CostMeter:
    return CostMeter(store)


@pytest.fixture
def governor(
    constraints: ConstraintRegistry, meter: CostMeter, bus: EventBus, store: SqlRunStore
) -> BudgetGovernor:
    return BudgetGovernor(constraints, meter, bus, store)


@pytest.fixture
def door(
    port: Answers, bus: EventBus, governor: BudgetGovernor, meter: CostMeter
) -> ModelDoor:
    return ModelDoor(port, PayloadScan(bus), governor, meter, bus)


def masked_request(**overrides: Any) -> LLMRequest:
    """A well-formed, single-turn request whose content is already masked."""
    fields: dict[str, Any] = {
        "pin": ModelPin.for_tier("mid"),
        "system": "You are tagging line items for [[CLIENT_1]].",
        "messages": (
            Message("user", "[[ACCOUNT_17]] 48,231.00 — categorise. [[PERSON_1]] draws."),
        ),
    }
    fields.update(overrides)
    return LLMRequest(**fields)
