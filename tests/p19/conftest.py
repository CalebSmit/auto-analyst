"""Fixtures for P19: the tagging skill, the taxonomy, the precedent store and its writer.

`world` wires what P18 wired plus the two read tools bound by name and a Context Builder
whose precedent source is the real store. `load_fixture` reads the 400-item fixture.
`decide` walks a tagged item through the real review path - router, queue, surface - so
a decision exists the way one exists in production, and `writeback` is the only thing
that turns it into a precedent.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

import ports
from graph.compile import CompiledGraph, PlanContext, Step, compile_recipe
from graph.recipes import load_recipe
from graph.resolve import ResolvedScope, ScopeResolver
from guards.untrusted import UntrustedBoundary
from harness.budget import BudgetGovernor
from harness.context import ContextBuilder
from harness.dispatch import SkillDispatcher
from harness.door import ModelDoor
from harness.policy import PolicyGate, RunScope
from harness.procedures.line_item_tagging import (
    PRODUCED_BY,
    PROPOSAL_CONTRACT,
    LineItem,
    LineItemTagging,
    TaggingInputs,
)
from harness.runtime import BoundTools, GuardedRuntime
from ops.blobs import LocalContentStore
from ops.cost import CostMeter
from ops.events import EventBus
from ops.models import DecisionKind, RunState
from ops.run_store import DecisionRecord, SqlRunStore, open_store
from ports.llm import LLMRequest, LLMResponse, ModelPin, Usage
from ports.queue.in_process import InProcessQueue
from precedent import PrecedentStore, PrecedentWriteback
from privacy.mask import Identifier, Masker
from privacy.payload_scan import PayloadScan
from privacy.vault import KEY_NAME, open_vault
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.scopes import ScopeRegistry
from registries.skills import SkillTree
from review import CheckpointPolicy, ConfidenceRouter, Item, ReviewQueue, ReviewSurface
from tests.p15.conftest import profile
from tools.coa import chart_of_accounts_lookup
from tools.precedent import precedent_lookup_tool

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "skills" / "line-item-tagging"
ENGAGEMENT = "HEND-2026-04"
CLIENT = "client_henderson"
SCOPE_PATH = "valuation/esop/repeat"
RUN_ID = "run_p19"
PIN = ModelPin.for_tier("mid")
TAXONOMY = "coa-taxonomy@1.0.0"
SKILL = "line-item-tagging@0.1.0"
HITL = "confidence_below_threshold_requires_review"
REVIEWER = "Dana Whitfield"
BAR = 0.85


# ------------------------------------------------------------------ fixture data


def load_fixture() -> tuple[list[LineItem], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    items = [
        LineItem(
            line_item_ref=i["line_item_ref"],
            description=i["description"],
            source_labels=tuple(i["source_labels"]),
            statement_hint=i["statement_hint"],
            periods=tuple(i["periods"]),
        )
        for i in json.loads((FIXTURE / "items.json").read_text(encoding="utf-8"))
    ]
    gold = json.loads((FIXTURE / "gold.json").read_text(encoding="utf-8"))
    batches = json.loads((FIXTURE / "proposals.json").read_text(encoding="utf-8"))
    return items, gold, batches


def inputs_for(
    items: list[LineItem] | tuple[LineItem, ...],
    *,
    bar: float | None = BAR,
    always_review: tuple[str, ...] = (),
) -> TaggingInputs:
    return TaggingInputs(
        items=tuple(items),
        taxonomy_version=TAXONOMY,
        auto_accept_confidence=bar,
        always_review_categories=frozenset(always_review),
    )


def proposal_of(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": PROPOSAL_CONTRACT, "produced_by": PRODUCED_BY, "items": items}


def tag(
    ref: str,
    category: str,
    *,
    confidence: float = 0.93,
    excluded: bool | None = None,
    nwc: bool | None = None,
    rationale: str = "the description says so",
    **extra: Any,
) -> dict[str, Any]:
    """One proposal item with the taxonomy's default flags unless told otherwise."""
    from registries.taxonomy import load_taxonomy

    spec = load_taxonomy(TAXONOMY).categories.get(category)
    default_excluded = spec.excluded_from_al if spec else False
    default_nwc = spec.include_in_nwc if spec else False
    body: dict[str, Any] = {
        "line_item_ref": ref,
        "category": category,
        "excluded_from_al": default_excluded if excluded is None else excluded,
        "include_in_nwc": default_nwc if nwc is None else nwc,
        "confidence": confidence,
        "rationale": rationale,
    }
    body.update(extra)
    return body


class ProposalPort:
    """A port that answers with a proposal - the model's half, replayed."""

    name = "proposal"

    def __init__(self, proposal: dict[str, Any]) -> None:
        self.proposal = proposal
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            text=json.dumps(self.proposal),
            model=request.pin.model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=6000, output_tokens=1500),
        )


# ------------------------------------------------------------------ registries


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
def tree() -> SkillTree:
    return SkillTree.load()


@pytest.fixture(scope="session")
def scope() -> ResolvedScope:
    return ScopeResolver().resolve(SCOPE_PATH)


def compile_for(scope: ResolvedScope, snapshot: str = "precedent_snapshot_empty") -> CompiledGraph:
    return compile_recipe(
        load_recipe("monthly-refresh"),
        PlanContext(
            engagement_id=ENGAGEMENT,
            scope=scope,
            taxonomy_version=TAXONOMY,
            precedent_snapshot=snapshot,
        ),
    )


@pytest.fixture(scope="session")
def plan(scope: ResolvedScope) -> CompiledGraph:
    return compile_for(scope)


@pytest.fixture(scope="session")
def tagging_step(plan: CompiledGraph) -> Step:
    return plan.step("tagging")


# ------------------------------------------------------------------ the record


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p19.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def blobs(tmp_path: Path) -> LocalContentStore:
    return LocalContentStore(tmp_path / "blobs")


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


@pytest.fixture
def precedents(store: SqlRunStore) -> PrecedentStore:
    return PrecedentStore(store)


def start(
    store: SqlRunStore,
    plan: CompiledGraph,
    run_id: str = RUN_ID,
    engagement_id: str = ENGAGEMENT,
) -> str:
    store.start_run(
        run_id=run_id,
        engagement_id=engagement_id,
        plan_hash=plan.plan_hash,
        versions={
            "model_pin": str(PIN),
            "skills": [SKILL],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": TAXONOMY,
        },
        tieout_tolerance=1.0,
    )
    store.transition(run_id, RunState.RUNNING)
    store.start_clock(run_id)
    return run_id


@pytest.fixture
def started(store: SqlRunStore, plan: CompiledGraph) -> str:
    return start(store, plan)


# ------------------------------------------------------------------ review


@pytest.fixture
def policy(constraints: ConstraintRegistry) -> CheckpointPolicy:
    return CheckpointPolicy.from_profile(profile(), constraints)


@pytest.fixture
def router(policy: CheckpointPolicy, scopes: ScopeRegistry, bus: EventBus) -> ConfidenceRouter:
    return ConfidenceRouter(policy, scopes, bus)


@pytest.fixture
def queue(store: SqlRunStore, bus: EventBus, policy: CheckpointPolicy) -> ReviewQueue:
    return ReviewQueue(store, bus, policy_for=lambda engagement: policy)


@pytest.fixture
def surface(store: SqlRunStore, bus: EventBus) -> ReviewSurface:
    return ReviewSurface(store, bus, InProcessQueue())


def decide(
    *,
    router: ConfidenceRouter,
    queue: ReviewQueue,
    surface: ReviewSurface,
    run_id: str,
    tagged: dict[str, Any],
    decision: DecisionKind = DecisionKind.ACCEPTED,
    answer: dict[str, Any] | None = None,
    rationale: str = "",
    decided_by: str = REVIEWER,
    engagement_id: str = ENGAGEMENT,
) -> DecisionRecord:
    """A tagged item through the real review path: routed, queued, decided by a person."""
    item = Item(
        item_id=tagged["line_item_ref"],
        skill=SKILL,
        question=f"{tagged['description']}: {tagged['category']}?",
        source_excerpt=tagged["description"],
        proposal=tagged,
        confidence=tagged["confidence"],
        category=tagged["category"],
        review_required=True,
    )
    routing = router.route(
        item, HITL, run_id=run_id, engagement_id=engagement_id, step_id="tagging"
    )
    queue.enqueue(run_id, engagement_id, item, routing, step_id="tagging")
    return surface.decide(
        run_id,
        item.item_id,
        decided_by=decided_by,
        decision=decision,
        expected_version=1,
        rationale=rationale,
        answer=answer,
    )


# ------------------------------------------------------------------ world


@pytest.fixture
def world(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    store: SqlRunStore,
    bus: EventBus,
    blobs: LocalContentStore,
    contracts: ContractRegistry,
    constraints: ConstraintRegistry,
    tree: SkillTree,
    scope: ResolvedScope,
    precedents: PrecedentStore,
    started: str,
) -> Iterator[dict[str, Any]]:
    monkeypatch.setenv(KEY_NAME, Fernet.generate_key().decode())
    ports.reset()
    vault = open_vault(ports.get_secrets(), f"sqlite:///{(tmp_path / 'vault.db').as_posix()}")
    meter = CostMeter(store)
    governor = BudgetGovernor(constraints, meter, bus, store)
    runtime = GuardedRuntime(
        PolicyGate(constraints, bus),
        constraints,
        bus,
        {
            "chart_of_accounts_lookup": chart_of_accounts_lookup,
            "precedent_lookup": precedent_lookup_tool(precedents),
        },
    )
    run_scope = RunScope(
        run_id=started,
        engagement_id=ENGAGEMENT,
        engagement_root=f"engagements/{ENGAGEMENT}",
        scope_path=SCOPE_PATH,
        versions={"chart_of_accounts_lookup": TAXONOMY},
        budget_remaining_usd=governor.remaining_usd(started),
    )
    masker = Masker(vault)
    engagement_profile = blobs.put_json(profile(), name="engagement_profile")

    def dispatcher_for(port: Any) -> SkillDispatcher:
        return SkillDispatcher(
            tree=tree,
            context=ContextBuilder(tree, blobs, bus, store=store, precedents=precedents),
            door=ModelDoor(port, PayloadScan(bus), governor, meter, bus),
            runtime=runtime,
            contracts=contracts,
            boundary=UntrustedBoundary(bus),
            masker=masker,
            bus=bus,
            blobs=blobs,
        )

    def tools_for(step_id: str = "tagging") -> BoundTools:
        return runtime.bound(run_scope, SKILL, step_id)

    yield {
        "store": store,
        "bus": bus,
        "blobs": blobs,
        "vault": vault,
        "masker": masker,
        "runtime": runtime,
        "run_scope": run_scope,
        "engagement_profile": engagement_profile,
        "dispatcher_for": dispatcher_for,
        "tools_for": tools_for,
        "procedure": LineItemTagging(),
        "precedents": precedents,
        "writeback": PrecedentWriteback(store, precedents, masker, PayloadScan(bus), bus),
        "run_id": started,
    }
    vault.close()


def dispatch(
    world: dict[str, Any],
    step: Step,
    scope: ResolvedScope,
    port: Any,
    inputs: TaggingInputs,
    identifiers: tuple[Identifier, ...] = (),
) -> Any:
    return world["dispatcher_for"](port).run(
        step=step,
        run_id=world["run_id"],
        engagement_id=ENGAGEMENT,
        client_id=CLIENT,
        scope=scope,
        engagement_profile=world["engagement_profile"],
        inputs=inputs,
        identifiers=identifiers,
        run_scope=world["run_scope"],
        procedure=world["procedure"],
        pin=PIN,
    )


def events_of(store: SqlRunStore, run_id: str, event_type: str) -> list[Any]:
    return [e for e in store.events(run_id) if e.type == event_type]
