"""Fixtures for P14.

Two plans: `monthly` (a chain - everything downstream of ebitda depends on it) and `ddr`
(a fork - ddr-tagging and timing both hang off mask, and only qc joins them). The first
shows loops; the second shows that a quarantine halts dependents and nothing else.

`Repairer` is the runner: it plays a skill whose output a guard keeps rejecting. What it
hands back as feedback is the knob - the same bytes every time, or different ones.
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
from harness.loops import LoopController, RepairNeeded
from ops.blobs import ContentRef, LocalContentStore
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.errors import TIEOUT_MISMATCH, diagnose

ROOT = Path(__file__).resolve().parents[2]
ENGAGEMENT = "HEND-2026-04"
RUN_ID = "run_p14"
CONTEXT_REF = "context:" + "7c" * 8

STATED = 332324.0
RECOMPUTED = 331000.0
POSITIONS = {
    "proposed": {"value": STATED, "by": "ebitda-normalization@0.1.0"},
    "recomputed": {"value": RECOMPUTED, "by": "recompute", "rows": ["TB_FY25!B44:B47"]},
}


def _plan(name: str) -> CompiledGraph:
    scope = ScopeResolver().resolve("valuation/esop/repeat")
    return compile_recipe(
        load_recipe(name),
        PlanContext(
            engagement_id=ENGAGEMENT,
            scope=scope,
            taxonomy_version="coa-taxonomy@1.0.0",
            precedent_snapshot="precedent_snapshot_2026_09_01",
        ),
    )


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def constraints() -> ConstraintRegistry:
    return ConstraintRegistry.load()


@pytest.fixture(scope="session")
def monthly() -> CompiledGraph:
    return _plan("monthly-refresh")


@pytest.fixture(scope="session")
def ddr() -> CompiledGraph:
    return _plan("full-ddr-intake")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p14.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def blobs(tmp_path: Path) -> LocalContentStore:
    return LocalContentStore(tmp_path / "blobs")


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


@pytest.fixture
def controller(
    constraints: ConstraintRegistry, store: SqlRunStore, bus: EventBus
) -> LoopController:
    return LoopController(constraints, store, bus)


def start(store: SqlRunStore, plan: CompiledGraph, run_id: str = RUN_ID) -> str:
    store.start_run(
        run_id=run_id,
        engagement_id=ENGAGEMENT,
        plan_hash=plan.plan_hash,
        versions={
            "model_pin": "claude-opus-5 @ effort=high",
            "skills": ["ebitda-normalization@1.0.0"],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": "coa-taxonomy@1.0.0",
        },
        tieout_tolerance=1.0,
    )
    store.transition(run_id, RunState.RUNNING)
    return run_id


@pytest.fixture
def started(store: SqlRunStore, monthly: CompiledGraph) -> str:
    return start(store, monthly)


@pytest.fixture
def started_ddr(store: SqlRunStore, ddr: CompiledGraph) -> str:
    return start(store, ddr)


@pytest.fixture
def run_inputs(
    blobs: LocalContentStore, monthly: CompiledGraph, ddr: CompiledGraph
) -> dict[str, ContentRef]:
    """Whatever arrives from outside either plan, already content-addressed."""
    names = {
        ref.name
        for plan in (monthly, ddr)
        for step in plan.steps
        for ref in step.inputs
        if ref.from_run
    }
    return {name: blobs.put_json({"run_input": name}, name=name) for name in sorted(names)}


def tieout_diagnostic(step_id: str) -> Any:
    return diagnose(
        TIEOUT_MISMATCH,
        "FY25 officer comp: stated 332,324 against rows summing to 331,000",
        locator=step_id,
        expected=RECOMPUTED,
        found=STATED,
        delta=STATED - RECOMPUTED,
        step_id=step_id,
        skill="ebitda-normalization@0.1.0",
    )


class Repairer:
    """A runner whose target step keeps failing its guard.

    `feedback(n)` is what the guard hands back on the n-th rejection. Return the same
    dict every time to play a skill that will not budge; return something that names
    `n` to play one whose feedback genuinely changes. `passes_after` makes the step
    succeed on the call after that many rejections.
    """

    def __init__(
        self,
        blobs: LocalContentStore,
        target: str,
        loop: str,
        feedback: Callable[[int], dict[str, Any]],
        passes_after: int | None = None,
    ) -> None:
        self.blobs = blobs
        self.target = target
        self.loop = loop
        self.feedback = feedback
        self.passes_after = passes_after
        self.attempts: list[Attempt] = []

    def calls(self, step_id: str) -> list[Attempt]:
        return [a for a in self.attempts if a.step_id == step_id]

    def __call__(self, attempt: Attempt) -> ContentRef:
        self.attempts.append(attempt)
        n = len(self.calls(attempt.step_id))
        rejecting = self.passes_after is None or n <= self.passes_after
        if attempt.step_id == self.target and rejecting:
            raise RepairNeeded(
                self.loop,
                tieout_diagnostic(attempt.step_id),
                self.blobs.put_json(self.feedback(n), name="feedback"),
                positions=POSITIONS,
                guard_output={"mismatches": [{"stated": STATED, "recomputed": RECOMPUTED}]},
            )
        return self.blobs.put_json(
            {
                "step": attempt.step_id,
                "inputs": {name: ref.content_hash for name, ref in sorted(attempt.inputs.items())},
                "call": n,
            },
            name=attempt.step_id,
        )


@pytest.fixture
def executor_with(
    store: SqlRunStore, bus: EventBus, blobs: LocalContentStore, controller: LoopController
) -> Callable[[Any], StepExecutor]:
    def build(runner: Any) -> StepExecutor:
        return StepExecutor(store, bus, runner, blobs=blobs, loops=controller)

    return build


def loop_events(store: SqlRunStore, run_id: str) -> list[Any]:
    return [e for e in store.events(run_id) if e.level == "loop"]


def events_of(store: SqlRunStore, run_id: str, event_type: str) -> list[Any]:
    return [e for e in store.events(run_id) if e.type == event_type]
