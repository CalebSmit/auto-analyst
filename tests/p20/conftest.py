"""Fixtures for P20: the EBITDA skill, both passes, over the Henderson case.

`prepare` runs the real timing tool over the case so the historical table's figures
carry real derivations, writes the rows into the parse store so tie-out can re-derive
them, and builds the skill's inputs from the two upstream outputs and the engagement
profile - the F1 contract, consumed.
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
from harness.loops import LoopController
from harness.policy import PolicyGate, RunScope
from harness.procedures.ebitda_normalization import (
    EbitdaInputs,
    EbitdaNormalization,
    EbitdaVerification,
    VerificationInputs,
)
from harness.runtime import BoundTools, GuardedRuntime
from ops.blobs import LocalContentStore
from ops.cost import CostMeter
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from ops.source_parse import Row, SourceParseStore
from ports.llm import LLMRequest, LLMResponse, ModelPin, Usage
from ports.queue.in_process import InProcessQueue
from precedent import PrecedentStore, PrecedentWriteback
from privacy.mask import Masker
from privacy.payload_scan import PayloadScan
from privacy.vault import KEY_NAME, open_vault
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.scopes import ScopeRegistry
from registries.skills import SkillTree
from review import CheckpointPolicy, ConfidenceRouter, ReviewQueue, ReviewSurface
from tests.p15.conftest import profile
from tools.coa import chart_of_accounts_lookup
from tools.normalize import timing_normalizer
from tools.precedent import precedent_lookup_tool
from tools.recompute import recompute

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "fixtures" / "skills" / "ebitda-normalization" / "cases"
ENGAGEMENT = "HEND-2026-04"
CLIENT = "client_henderson"
SCOPE_PATH = "valuation/esop/repeat"
RUN_ID = "run_p20"
PIN = ModelPin.for_tier("high")
TAXONOMY = "coa-taxonomy@1.0.0"
SKILL = "ebitda-normalization@0.1.0"
HITL = "material_addbacks_require_review"
REVIEWER = "Dana Whitfield"


# ------------------------------------------------------------------ the case


def load_case(name: str = "henderson") -> dict[str, Any]:
    folder = CASES / name
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8")) for path in folder.glob("*.json")
    }


def blocks_of(case: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    return {f["source_id"]: f["blocks"] for f in case["case"]["files"]}


def timing_output(case: dict[str, Any]) -> dict[str, Any]:
    files = {
        f["source_id"]: {
            "scale": f["scale"],
            "currency": f["currency"],
            "source_version": f.get("source_version", 1),
        }
        for f in case["case"]["files"]
    }
    out: dict[str, Any] = timing_normalizer(case["timing_proposal"], blocks_of(case), files, "pin")[
        "output"
    ]
    return out


def write_blocks(parse_store: SourceParseStore, run_id: str, case: dict[str, Any]) -> None:
    for f in case["case"]["files"]:
        for locator, rows in f["blocks"].items():
            parse_store.write(run_id, f["source_id"], locator, [Row(**r) for r in rows])


def inputs_for(
    case: dict[str, Any],
    policy: CheckpointPolicy,
    *,
    profile_body: dict[str, Any] | None = None,
) -> EbitdaInputs:
    body = profile_body if profile_body is not None else profile()
    return EbitdaInputs.from_outputs(
        timing_output(case),
        case["tagging"],
        body,
        blocks_of(case),
        materiality_amount=policy.materiality.amount,
        materiality_currency=policy.materiality.currency,
        auto_accept_confidence=policy.auto_accept_confidence,
        always_review_categories=policy.always_review_categories,
    )


class ProposalPort:
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
            usage=Usage(input_tokens=9000, output_tokens=2000),
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


@pytest.fixture(scope="session")
def plan(scope: ResolvedScope) -> CompiledGraph:
    return compile_recipe(
        load_recipe("monthly-refresh"),
        PlanContext(
            engagement_id=ENGAGEMENT,
            scope=scope,
            taxonomy_version=TAXONOMY,
            precedent_snapshot="precedent_snapshot_empty",
        ),
    )


@pytest.fixture(scope="session")
def ebitda_step(plan: CompiledGraph) -> Step:
    return plan.step("ebitda")


@pytest.fixture(scope="session")
def case() -> dict[str, Any]:
    return load_case()


# ------------------------------------------------------------------ the record


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p20.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def blobs(tmp_path: Path) -> LocalContentStore:
    return LocalContentStore(tmp_path / "blobs")


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


@pytest.fixture
def parse_store(store: SqlRunStore) -> SourceParseStore:
    return SourceParseStore(store)


@pytest.fixture
def precedents(store: SqlRunStore) -> PrecedentStore:
    return PrecedentStore(store)


@pytest.fixture
def started(store: SqlRunStore, plan: CompiledGraph) -> str:
    store.start_run(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
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
    store.transition(RUN_ID, RunState.RUNNING)
    store.start_clock(RUN_ID)
    return RUN_ID


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


@pytest.fixture
def controller(
    constraints: ConstraintRegistry, store: SqlRunStore, bus: EventBus
) -> LoopController:
    return LoopController(constraints, store, bus)


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
    parse_store: SourceParseStore,
    policy: CheckpointPolicy,
    case: dict[str, Any],
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
            "recompute": recompute,
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
    write_blocks(parse_store, started, case)

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

    def tools_for(step_id: str = "ebitda") -> BoundTools:
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
        "procedure": EbitdaNormalization(),
        "verifier": EbitdaVerification(),
        "precedents": precedents,
        "parse_store": parse_store,
        "policy": policy,
        "inputs": inputs_for(case, policy),
        "writeback": PrecedentWriteback(store, precedents, masker, PayloadScan(bus), bus),
        "run_id": started,
    }
    vault.close()


def dispatch(
    world: dict[str, Any],
    step: Step,
    scope: ResolvedScope,
    port: Any,
    inputs: EbitdaInputs | VerificationInputs,
    *,
    procedure: Any = None,
) -> Any:
    return world["dispatcher_for"](port).run(
        step=step,
        run_id=world["run_id"],
        engagement_id=ENGAGEMENT,
        client_id=CLIENT,
        scope=scope,
        engagement_profile=world["engagement_profile"],
        inputs=inputs,
        identifiers=(),
        run_scope=world["run_scope"],
        procedure=procedure or world["procedure"],
        pin=PIN,
    )


def first_pass(
    world: dict[str, Any], step: Step, scope: ResolvedScope, case: dict[str, Any]
) -> Any:
    return dispatch(world, step, scope, ProposalPort(case["proposal"]), world["inputs"])


def events_of(store: SqlRunStore, run_id: str, event_type: str) -> list[Any]:
    return [e for e in store.events(run_id) if e.type == event_type]
