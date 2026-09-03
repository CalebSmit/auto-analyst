"""Fixtures for P08.

`runner` is the seam. In a real run it is the Context Builder and the Dispatcher; here it
is whatever the test needs it to be - something that records what it was asked to do,
times out twice then succeeds, or blocks on a person. Keeping the executor's guarantees
testable without a model anywhere near them is the whole reason that seam is a Protocol.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from graph.compile import CompiledGraph, PlanContext, compile_recipe
from graph.execute import Attempt, StepExecutor
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver
from ops.blobs import ContentRef, LocalContentStore
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from registries.contracts import ContractRegistry

ENGAGEMENT = "HEND-2026-04"
RUN_ID = "run_p08"
CONTEXT_REF = "context:" + "7c" * 8


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def plan() -> CompiledGraph:
    scope = ScopeResolver().resolve("valuation/esop/repeat")
    return compile_recipe(
        load_recipe("monthly-refresh"),
        PlanContext(
            engagement_id=ENGAGEMENT,
            scope=scope,
            taxonomy_version="coa-taxonomy@1.0.0",
            precedent_snapshot="precedent_snapshot_2026_09_01",
        ),
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p08.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def blobs(tmp_path: Path) -> LocalContentStore:
    return LocalContentStore(tmp_path / "blobs")


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


@pytest.fixture
def started(store: SqlRunStore, plan: CompiledGraph) -> str:
    """A run in progress, with nothing executed yet."""
    store.start_run(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
        plan_hash=plan.plan_hash,
        versions={
            "model_pin": "claude-opus-5 @ effort=high",
            "skills": ["ebitda-normalization@1.0.0"],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": "coa-taxonomy@1.0.0",
        },
    )
    store.transition(RUN_ID, RunState.RUNNING)
    return RUN_ID


@pytest.fixture
def run_inputs(blobs: LocalContentStore) -> dict[str, ContentRef]:
    """What arrives from outside the plan, already content-addressed."""
    return {
        "source_documents": blobs.put_json({"files": ["FY25 TB.xlsx"]}, name="source_documents"),
        "engagement_profile": blobs.put_json(
            {"industry": "manufacturing", "scale_convention": 1}, name="engagement_profile"
        ),
    }


class Recorder:
    """A runner that succeeds and remembers what it was asked.

    `seen` is what the executor handed each step - refs, by the name the step calls them -
    which is what the "refs, never values" tests read.
    """

    def __init__(self, blobs: LocalContentStore) -> None:
        self.blobs = blobs
        self.calls: list[str] = []
        self.attempts: list[Attempt] = []
        self.seen: dict[str, dict[str, ContentRef]] = {}

    def __call__(self, attempt: Attempt) -> ContentRef:
        self.calls.append(attempt.step_id)
        self.attempts.append(attempt)
        self.seen[attempt.step_id] = dict(attempt.inputs)
        # The output depends on the input *hashes*, as a real step's would. A double
        # that ignored its inputs would make every downstream key stable no matter what
        # changed upstream, and the cascade tests would prove nothing.
        return self.blobs.put_json(
            {
                "step": attempt.step_id,
                "inputs": {name: ref.content_hash for name, ref in sorted(attempt.inputs.items())},
            },
            name=attempt.step_id,
        )


@pytest.fixture
def recorder(blobs: LocalContentStore) -> Recorder:
    return Recorder(blobs)


@pytest.fixture
def executor(
    store: SqlRunStore, bus: EventBus, recorder: Recorder, blobs: LocalContentStore
) -> StepExecutor:
    return StepExecutor(store, bus, recorder, blobs=blobs)


@pytest.fixture
def executor_with(
    store: SqlRunStore, bus: EventBus, blobs: LocalContentStore
) -> Callable[[Any], StepExecutor]:
    """An executor over some other runner - one that fails, times out or blocks."""

    def build(runner: Any) -> StepExecutor:
        return StepExecutor(store, bus, runner, blobs=blobs)

    return build
