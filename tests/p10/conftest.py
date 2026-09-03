"""Fixtures for P10.

The tools registered here are fakes that return what they are told. The phase is about
the decision before the call and the caps around it, not about what recompute computes -
that is P13. Keeping the tools trivial is what makes every test here about the gate.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness.policy import PolicyGate, ProposedAction, RunScope
from harness.runtime import GuardedRuntime
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry

ENGAGEMENT = "HEND-2026-04"
OTHER = "NOVK-2026-11"
RUN_ID = "run_p10"
ROOT = "engagements/HEND-2026-04"
CALLER = "ebitda-normalization@0.1.0"


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def constraints() -> ConstraintRegistry:
    return ConstraintRegistry.load()


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p10.db').as_posix()}")
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
                  "constraints": "1.0.0", "taxonomy": "coa-taxonomy@1.0.0"},
    )
    store.transition(RUN_ID, RunState.RUNNING)
    return RUN_ID


@pytest.fixture
def run(started: str) -> RunScope:
    return RunScope(
        run_id=started,
        engagement_id=ENGAGEMENT,
        engagement_root=ROOT,
        scope_path="valuation/esop/repeat",
        versions={
            "chart_of_accounts_lookup": "coa-taxonomy@1.0.0",
            "template_schema_lookup": "Chartwell_ESOP_Model_v9@9.4",
        },
        budget_remaining_usd=12.0,
    )


@pytest.fixture
def gate(constraints: ConstraintRegistry, bus: EventBus) -> PolicyGate:
    return PolicyGate(constraints, bus)


def action(tool: str = "recompute", **overrides: Any) -> ProposedAction:
    """A well-formed proposal from ebitda-normalization. Tests vary one thing."""
    fields: dict[str, Any] = {
        "tool": tool,
        "args": {"engagement_id": ENGAGEMENT, "limit": 100},
        "caller": CALLER,
        "engagement": ENGAGEMENT,
        "mode": "write" if tool in ("recompute", "timing_normalizer") else "read",
        "estimated_cost_usd": 0.05,
        "step_id": "ebitda",
    }
    fields.update(overrides)
    return ProposedAction(**fields)


class Fakes:
    """Six tools that remember what they were asked and answer with rows."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.answer_rows: int = 3

    def make(self, name: str) -> Any:
        def tool(**kwargs: Any) -> dict[str, Any]:
            self.calls.append((name, kwargs))
            return {"rows": [{"n": i} for i in range(self.answer_rows)], "tool": name}

        return tool

    def all(self, constraints: ConstraintRegistry) -> dict[str, Any]:
        return {name: self.make(name) for name in constraints.tools}


@pytest.fixture
def fakes() -> Fakes:
    return Fakes()


@pytest.fixture
def runtime(
    gate: PolicyGate, constraints: ConstraintRegistry, bus: EventBus, fakes: Fakes
) -> GuardedRuntime:
    return GuardedRuntime(gate, constraints, bus, fakes.all(constraints))
