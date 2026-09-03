"""Fixtures for P15.

A policy for one engagement, a router reading it, a queue with a clock the tests can
move, and a surface over an in-process job queue - so "a recorded decision re-enqueues the
waiting run" is a job that actually runs, not a flag that gets set.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from graph.compile import CompiledGraph, PlanContext, compile_recipe
from graph.execute import Attempt, Blocked, StepExecutor
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver
from ops.blobs import ContentRef, LocalContentStore
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from ports.queue.in_process import InProcessQueue
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.scopes import ScopeRegistry
from review import CheckpointPolicy, ConfidenceRouter, Item, Money, ReviewQueue, ReviewSurface

ROOT = Path(__file__).resolve().parents[2]
ENGAGEMENT = "HEND-2026-04"
RUN_ID = "run_p15"
CONTEXT_REF = "context:" + "7c" * 8
OWNER = "Dana Whitfield"
SLA_HOURS = 48.0
T0 = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)

# The skills' own declarations, from their SKILL.md frontmatter.
TAGGING = "line-item-tagging"
EBITDA = "ebitda-normalization"
QC = "qc-tieout"
DECLARED = {
    TAGGING: "confidence_below_threshold_requires_review",  # rank 10
    EBITDA: "material_addbacks_require_review",  # rank 20
    QC: "always_surfaces_to_reviewer",  # rank 40
}


def profile(**overrides: Any) -> dict[str, Any]:
    """A valid engagement_profile@1.0.0 with a checkpoint policy on it."""
    body: dict[str, Any] = {
        "schema_version": "engagement_profile@1.0.0",
        "engagement_id": ENGAGEMENT,
        "practice": "valuation",
        "segment": "esop",
        "disposition": "repeat",
        "industry_classification": {
            "system": "NAICS",
            "code": "332710",
            "description": "Machine shops",
        },
        "size_band": {"metric": "revenue", "band": "10-50M", "as_of": "2025-12-31"},
        "fiscal_calendar": {"basis": "calendar", "year_end_month": 12, "year_end_day": 31},
        "scale_convention": 1,
        "owner_compensation_baseline": {
            "amount": 285000,
            "currency": "USD",
            "basis": "survey_median",
            "source": "ERI 2025",
            "as_of": "2025-06-30",
        },
        "materiality_threshold": {"amount": 20000, "currency": "USD"},
        "checkpoint_policy": {
            "owner": OWNER,
            "sla_hours": SLA_HOURS,
            "auto_accept_confidence": 0.85,
            "always_review_categories": ["owner_related"],
        },
        "recorded_by": "setup@chartwell.invalid",
        "recorded_at": "2026-09-01T08:00:00Z",
    }
    body.update(overrides)
    return body


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def constraints() -> ConstraintRegistry:
    return ConstraintRegistry.load()


@pytest.fixture(scope="session")
def scopes() -> ScopeRegistry:
    return ScopeRegistry.load()


@pytest.fixture(scope="session")
def plan() -> CompiledGraph:
    return compile_recipe(
        load_recipe("monthly-refresh"),
        PlanContext(
            engagement_id=ENGAGEMENT,
            scope=ScopeResolver().resolve("valuation/esop/repeat"),
            taxonomy_version="coa-taxonomy@1.0.0",
            precedent_snapshot="precedent_snapshot_2026_09_01",
        ),
    )


@pytest.fixture
def policy(constraints: ConstraintRegistry) -> CheckpointPolicy:
    return CheckpointPolicy.from_profile(profile(), constraints)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p15.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def blobs(tmp_path: Path) -> LocalContentStore:
    return LocalContentStore(tmp_path / "blobs")


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


def start(store: SqlRunStore, plan: CompiledGraph, run_id: str = RUN_ID) -> str:
    store.start_run(
        run_id=run_id,
        engagement_id=ENGAGEMENT,
        plan_hash=plan.plan_hash,
        versions={
            "model_pin": "claude-opus-5 @ effort=high",
            "skills": ["line-item-tagging@1.0.0"],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": "coa-taxonomy@1.0.0",
        },
    )
    store.transition(run_id, RunState.RUNNING)
    return run_id


@pytest.fixture
def started(store: SqlRunStore, plan: CompiledGraph) -> str:
    return start(store, plan)


@pytest.fixture
def router(policy: CheckpointPolicy, scopes: ScopeRegistry, bus: EventBus) -> ConfidenceRouter:
    return ConfidenceRouter(policy, scopes, bus)


class Clock:
    def __init__(self, at: datetime = T0) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at

    def advance(self, hours: float) -> None:
        self.at = self.at + timedelta(hours=hours)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def queue(store: SqlRunStore, bus: EventBus, policy: CheckpointPolicy, clock: Clock) -> ReviewQueue:
    return ReviewQueue(store, bus, policy_for=lambda engagement: policy, clock=clock)


@pytest.fixture
def jobs() -> InProcessQueue:
    return InProcessQueue()


@pytest.fixture
def surface(store: SqlRunStore, bus: EventBus, jobs: InProcessQueue) -> ReviewSurface:
    return ReviewSurface(store, bus, jobs)


def item(
    item_id: str = "li_118",
    skill: str = TAGGING,
    confidence: float | None = 0.61,
    amount: Money | None = None,
    **overrides: Any,
) -> Item:
    body: dict[str, Any] = {
        "item_id": item_id,
        "skill": skill,
        "question": "Prof fees - Q3 special: category?",
        "source_excerpt": "Professional fees - Q3 special project  14,200.00",
        "proposal": {"category": "non_recurring", "line_item_ref": item_id},
        "confidence": confidence,
        "amount": amount,
        "locator": "TB_FY24!A118",
    }
    body.update(overrides)
    return Item(**body)


@pytest.fixture
def run_inputs(blobs: LocalContentStore, plan: CompiledGraph) -> dict[str, ContentRef]:
    names = {ref.name for step in plan.steps for ref in step.inputs if ref.from_run}
    return {name: blobs.put_json({"run_input": name}, name=name) for name in sorted(names)}


class Blocks:
    """A runner that succeeds until `at`, where it needs a person."""

    def __init__(self, blobs: LocalContentStore, at: str, items: int = 1) -> None:
        self.blobs = blobs
        self.at = at
        self.items = items
        self.calls: list[str] = []

    def __call__(self, attempt: Attempt) -> ContentRef:
        self.calls.append(attempt.step_id)
        if attempt.step_id == self.at:
            raise Blocked("item_1", "Prof fees - Q3 special: category?")
        return self.blobs.put_json(
            {"step": attempt.step_id, "inputs": sorted(attempt.inputs)}, name=attempt.step_id
        )


class Recorder:
    def __init__(self, blobs: LocalContentStore) -> None:
        self.blobs = blobs
        self.calls: list[str] = []

    def __call__(self, attempt: Attempt) -> ContentRef:
        self.calls.append(attempt.step_id)
        return self.blobs.put_json(
            {"step": attempt.step_id, "inputs": sorted(attempt.inputs)}, name=attempt.step_id
        )


@pytest.fixture
def executor_with(
    store: SqlRunStore, bus: EventBus, blobs: LocalContentStore
) -> Callable[[Any], StepExecutor]:
    def build(runner: Any) -> StepExecutor:
        return StepExecutor(store, bus, runner, blobs=blobs)

    return build


def events_of(store: SqlRunStore, run_id: str, event_type: str) -> list[Any]:
    return [e for e in store.events(run_id) if e.type == event_type]
