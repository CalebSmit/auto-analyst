"""Fixtures for P18: the whole harness around one real skill, and the golden cases.

`world` wires what C4 wired - vault, masker, context builder, door, gate, runtime - plus
the dispatcher and the timing tool bound by name. `load_case` reads a golden case into
the inputs the procedure takes. `ProposalPort` says what a case's proposal.json says,
so the model's half is replayed and the tool's half is real.
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
from harness.procedures.timing_normalization import SourceFile, TimingInputs, TimingNormalization
from harness.runtime import GuardedRuntime
from ops.blobs import ContentRef, LocalContentStore
from ops.cost import CostMeter
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from ops.source_parse import Row, SourceParseStore
from ports.llm import LLMRequest, LLMResponse, ModelPin, Usage
from privacy.mask import Masker
from privacy.payload_scan import PayloadScan
from privacy.vault import KEY_NAME, open_vault
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.skills import SkillTree
from tests.p15.conftest import profile
from tools.normalize import timing_normalizer

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "fixtures" / "skills" / "timing-normalization" / "cases"
ENGAGEMENT = "HEND-2026-04"
CLIENT = "client_henderson"
RUN_ID = "run_p18"
PIN = ModelPin.for_tier("mid")


# ------------------------------------------------------------------ cases


def load_case(name: str) -> tuple[TimingInputs, dict[str, Any] | None, dict[str, Any]]:
    folder = CASES / name
    body = json.loads((folder / "case.json").read_text(encoding="utf-8"))
    files = tuple(
        SourceFile(
            source_id=f["source_id"],
            filename=f["filename"],
            document_type=f["document_type"],
            blocks=f["blocks"],
            scale=f["scale"],
            currency=f["currency"],
            period_type=f["period_type"],
            period_ends=tuple(f["period_ends"]),
            ambiguous=tuple(f["ambiguous"]),
            source_version=f.get("source_version", 1),
            block_periods=f.get("block_periods", {}),
        )
        for f in body["files"]
    )
    proposal_path = folder / "proposal.json"
    proposal = (
        json.loads(proposal_path.read_text(encoding="utf-8")) if proposal_path.is_file() else None
    )
    expected = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    return TimingInputs(files=files), proposal, expected


def tool_inputs(inputs: TimingInputs) -> tuple[dict[str, Any], dict[str, Any]]:
    """What the procedure hands the tool, for tests that call the tool directly."""
    sources = {f.source_id: f.blocks for f in inputs.files}
    files = {
        f.source_id: {"scale": f.scale, "currency": f.currency, "source_version": f.source_version}
        for f in inputs.files
    }
    return sources, files


def write_blocks(parse_store: SourceParseStore, run_id: str, inputs: TimingInputs) -> None:
    for f in inputs.files:
        for locator, rows in f.blocks.items():
            parse_store.write(run_id, f.source_id, locator, [Row(**r) for r in rows])


class ProposalPort:
    """A port that answers with a case's proposal - the model's half, replayed."""

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
            usage=Usage(input_tokens=2400, output_tokens=900),
        )


# ------------------------------------------------------------------ world


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="session")
def constraints() -> ConstraintRegistry:
    return ConstraintRegistry.load()


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


@pytest.fixture(scope="session")
def timing_step(plan: CompiledGraph) -> Step:
    return plan.step("timing")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p18.db').as_posix()}")
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
def started(store: SqlRunStore, plan: CompiledGraph) -> str:
    store.start_run(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
        plan_hash=plan.plan_hash,
        versions={
            "model_pin": str(PIN),
            "skills": ["timing-normalization@0.1.0"],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": "coa-taxonomy@1.0.0",
        },
        tieout_tolerance=1.0,
    )
    store.transition(RUN_ID, RunState.RUNNING)
    store.start_clock(RUN_ID)
    return RUN_ID


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
    started: str,
) -> Iterator[dict[str, Any]]:
    monkeypatch.setenv(KEY_NAME, Fernet.generate_key().decode())
    ports.reset()
    vault = open_vault(ports.get_secrets(), f"sqlite:///{(tmp_path / 'vault.db').as_posix()}")
    meter = CostMeter(store)
    governor = BudgetGovernor(constraints, meter, bus, store)
    runtime = GuardedRuntime(
        PolicyGate(constraints, bus), constraints, bus, {"timing_normalizer": timing_normalizer}
    )
    run_scope = RunScope(
        run_id=started,
        engagement_id=ENGAGEMENT,
        engagement_root=f"engagements/{ENGAGEMENT}",
        scope_path="valuation/esop/repeat",
        versions={},
        budget_remaining_usd=governor.remaining_usd(started),
    )
    engagement_profile = blobs.put_json(profile(), name="engagement_profile")

    def dispatcher_for(port: Any) -> SkillDispatcher:
        return SkillDispatcher(
            tree=tree,
            context=ContextBuilder(tree, blobs, bus, store=store),
            door=ModelDoor(port, PayloadScan(bus), governor, meter, bus),
            runtime=runtime,
            contracts=contracts,
            boundary=UntrustedBoundary(bus),
            masker=Masker(vault),
            bus=bus,
            blobs=blobs,
        )

    yield {
        "store": store,
        "bus": bus,
        "blobs": blobs,
        "vault": vault,
        "runtime": runtime,
        "run_scope": run_scope,
        "engagement_profile": engagement_profile,
        "dispatcher_for": dispatcher_for,
        "procedure": TimingNormalization(),
        "run_id": started,
    }
    vault.close()


def dispatch(
    world: dict[str, Any], step: Step, scope: ResolvedScope, port: Any, inputs: TimingInputs
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
        procedure=world["procedure"],
        pin=PIN,
    )


def events_of(store: SqlRunStore, run_id: str, event_type: str) -> list[Any]:
    return [e for e in store.events(run_id) if e.type == event_type]


__all__ = ["ContentRef"]
