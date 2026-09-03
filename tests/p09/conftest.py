"""Fixtures for P09.

`Sourced` is a precedent source the tests control: it records the query it was given and
returns whatever a test loaded into it. That is enough to prove the query is scope-built
and the results are checked, without a store that does not exist until P19.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from graph.compile import CompiledGraph, PlanContext, compile_recipe
from graph.recipes import load_recipe
from graph.resolve import ResolvedScope, ScopeResolver
from harness.context import ContextBuilder, ContextRequest, Precedent, PrecedentQuery
from ops.blobs import ContentRef, LocalContentStore
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from registries.contracts import ContractRegistry
from registries.skills import SkillTree

ENGAGEMENT = "HEND-2026-04"
CLIENT = "client_henderson"
RUN_ID = "run_p09"


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def tree() -> SkillTree:
    return SkillTree.load()


@pytest.fixture(scope="session")
def scope() -> ResolvedScope:
    return ScopeResolver().resolve("valuation/esop/repeat")


@pytest.fixture(scope="session")
def plan(scope: ResolvedScope) -> CompiledGraph:
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
    opened = open_store(f"sqlite:///{(tmp_path / 'p09.db').as_posix()}")
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
def profile(blobs: LocalContentStore) -> ContentRef:
    return blobs.put_json(
        {"industry_classification": "manufacturing", "scale_convention": 1},
        name="engagement_profile",
    )


@pytest.fixture
def payload(blobs: LocalContentStore) -> ContentRef:
    return blobs.put_json(
        {"line_items": [{"description": "[[ACCOUNT_17]] checking", "amount": 48231.0}]},
        name="masked_payload",
    )


class Sourced:
    """A precedent source under the test's control."""

    def __init__(self, *precedents: Precedent) -> None:
        self.precedents = tuple(precedents)
        self.queries: list[PrecedentQuery] = []

    def retrieve(self, query: PrecedentQuery) -> tuple[Precedent, ...]:
        self.queries.append(query)
        return self.precedents


def precedent(
    precedent_id: str,
    *,
    scope: str = "valuation/esop/repeat",
    client_id: str = "client_other",
    masked: bool = True,
    category: str = "owner_compensation",
) -> Precedent:
    return Precedent(
        precedent_id=precedent_id,
        engagement_id=f"eng_{precedent_id}",
        client_id=client_id,
        scope=scope,
        masked=masked,
        example={"description": "[[ACCOUNT_3]] draw", "category": category, "rationale": "x"},
    )


@pytest.fixture
def source() -> Sourced:
    return Sourced(precedent("p1"), precedent("p2", client_id=CLIENT), precedent("p3"))


@pytest.fixture
def builder(
    tree: SkillTree, blobs: LocalContentStore, bus: EventBus, store: SqlRunStore, source: Sourced
) -> ContextBuilder:
    return ContextBuilder(tree, blobs, bus, store=store, precedents=source)


@pytest.fixture
def request_for(
    plan: CompiledGraph, scope: ResolvedScope, profile: ContentRef, payload: ContentRef,
    started: str,
) -> Any:
    """A ContextRequest for one step of the real plan."""

    def build(step_id: str = "ebitda", **overrides: Any) -> ContextRequest:
        fields: dict[str, Any] = {
            "run_id": started,
            "engagement_id": ENGAGEMENT,
            "client_id": CLIENT,
            "step": plan.step(step_id),
            "scope": scope,
            "engagement_profile": profile,
            "payload": payload,
        }
        fields.update(overrides)
        return ContextRequest(**fields)

    return build
