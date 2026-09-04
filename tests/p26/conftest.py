"""Fixtures for P26: a real door, a real compiler, and the model's half scripted.

Everything the orchestrator's call passes through is the production object - the payload
scan, the budget governor, the pin check, the cost meter, the schema gate, the untrusted
boundary, the compiler and the plan assertions. Only the port is a double, and it answers
with a proposal the test chose, which is the one thing a test has to control to ask "what
happens when the model proposes *this*".
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

import ports
from graph.compile import PlanContext
from graph.recipes import RecipeInput, load_recipe, recipe_names
from graph.resolve import ResolvedScope, ScopeResolver
from guards.untrusted import UntrustedBoundary
from harness.budget import BudgetGovernor
from harness.door import ModelDoor
from ops.blobs import LocalContentStore
from ops.cost import CostMeter
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from orchestrate import (
    DocumentSummary,
    JobManifest,
    Orchestrator,
    RecipeOption,
    RunPlanner,
    Triage,
)
from ports.llm import LLMRequest, LLMResponse, Usage
from privacy.mask import Masker
from privacy.payload_scan import PayloadScan
from privacy.vault import KEY_NAME, open_vault
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.skills import SkillTree

ENGAGEMENT = "HEND-2026-04"
RUN_ID = "run_p26"
SCOPE_PATH = "valuation/esop/repeat"
TAXONOMY = "coa-taxonomy@1.0.0"
SNAPSHOT = "precedent_snapshot_2026_09_01"
FALLBACK = "monthly-refresh"
RUN_INPUTS = (
    RecipeInput(name="engagement_profile", schema="engagement_profile@1.0.0"),
    RecipeInput(name="source_documents", schema=None),
)


class ScriptedPort:
    """The model's half. Answers each call in turn with what the test wrote."""

    name = "scripted"

    def __init__(self, *answers: Any) -> None:
        self.answers = [a if isinstance(a, str) else json.dumps(a) for a in answers]
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        text = self.answers.pop(0) if self.answers else "{}"
        return LLMResponse(
            text=text,
            model=request.pin.model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=1800, output_tokens=400),
        )

    @property
    def last(self) -> LLMRequest:
        return self.requests[-1]

    def sent(self) -> str:
        """Everything that left, for the call just made: system prompt and messages."""
        return "\n".join([self.last.system, *(m.content for m in self.last.messages)])


# ------------------------------------------------------------------ proposals


def proposal(**overrides: Any) -> dict[str, Any]:
    """A composed plan: the monthly refresh's shape, proposed rather than named."""
    body: dict[str, Any] = {
        "schema_version": "run_plan_proposal@1.0.0",
        "produced_by": "orchestrator@1.0.0",
        "match": "composed",
        "recipe": None,
        "rationale": (
            "Two statements and a trial balance for a returning ESOP engagement, with no "
            "census: the routine shape without the participant work."
        ),
        "steps": [
            {"id": "intake", "kind": "io", "label": "Intake & fingerprint",
             "needs": [], "run_inputs": ["source_documents"], "on_failure": "halt"},
            {"id": "mask", "kind": "io", "label": "Mask & scan payload",
             "needs": ["intake"], "on_failure": "halt"},
            {"id": "timing", "kind": "skill", "skill": "timing-normalization",
             "label": "Timing normalization", "needs": ["mask"], "on_failure": "quarantine"},
            {"id": "tagging", "kind": "skill", "skill": "line-item-tagging",
             "label": "Line-item tagging", "needs": ["timing"], "on_failure": "quarantine"},
            {"id": "ebitda", "kind": "skill", "skill": "ebitda-normalization",
             "label": "EBITDA normalization", "needs": ["timing", "tagging"],
             "run_inputs": ["engagement_profile"], "on_failure": "quarantine"},
            {"id": "qc", "kind": "skill", "skill": "qc-tieout", "label": "QC / tie-out",
             "needs": ["timing", "tagging", "ebitda"], "on_failure": "review"},
            {"id": "release", "kind": "io", "label": "Unmask, verify, release",
             "needs": ["qc"], "on_failure": "halt"},
        ],
    }
    body.update(overrides)
    return body


def names_the_recipe(**overrides: Any) -> dict[str, Any]:
    return proposal(
        match="recipe",
        recipe=FALLBACK,
        rationale="A returning engagement with the declared set: this is the monthly refresh.",
        steps=[],
        **overrides,
    )


def nothing_fits(**overrides: Any) -> dict[str, Any]:
    return proposal(
        match="none",
        steps=[],
        rationale="The set does not resemble any recipe I have.",
        escalation_reason=(
            "The documents describe a two-tier holding structure with a management "
            "incentive unit plan, and no skill in the index covers unit-based awards."
        ),
        **overrides,
    )


def assessment(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "triage@1.0.0",
        "produced_by": "triage@1.0.0",
        "category": "unusual_structure",
        "assessment": (
            "A two-tier holding structure with management incentive units. The valuation "
            "skills in scope assume a single operating entity and common equity, so "
            "tagging and EBITDA would run on a structure they do not describe."
        ),
        "suggested_skill": None,
        "escalation_reason": (
            "Unit-based awards in a two-tier structure: a person decides whether this is "
            "in scope before anything runs."
        ),
    }
    body.update(overrides)
    return body


# ------------------------------------------------------------------ the world


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
    return ScopeResolver().resolve(SCOPE_PATH)


@pytest.fixture
def context(scope: ResolvedScope) -> PlanContext:
    return PlanContext(
        engagement_id=ENGAGEMENT,
        scope=scope,
        taxonomy_version=TAXONOMY,
        precedent_snapshot=SNAPSHOT,
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p26.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


@pytest.fixture
def blobs(tmp_path: Path) -> LocalContentStore:
    return LocalContentStore(tmp_path / "blobs")


@pytest.fixture
def started(store: SqlRunStore) -> str:
    store.start_run(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
        plan_hash="sha256:" + "7c" * 32,
        versions={
            "model_pin": "claude-sonnet-5 @ effort=high",
            "skills": ["timing-normalization@0.1.0"],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": TAXONOMY,
        },
    )
    store.transition(RUN_ID, RunState.RUNNING, reason="a worker holds it")
    return RUN_ID


@pytest.fixture
def manifest() -> JobManifest:
    return job_manifest()


def job_manifest(**overrides: Any) -> JobManifest:
    fields: dict[str, Any] = {
        "engagement_id": ENGAGEMENT,
        "scope_path": SCOPE_PATH,
        "documents": (
            DocumentSummary("TB_FY25.xlsx", "trial_balance", ("FY2025",)),
            DocumentSummary("income statement FY25.xlsx", "financial_statements",
                            ("FY2025", "FY2024")),
            DocumentSummary("balance sheet FY25.xlsx", "financial_statements", ("FY2025",)),
        ),
        "profile": {
            "engagement_id": ENGAGEMENT,
            "industry": "manufacturing",
            "fiscal_year_end": "12-31",
            "review_level": "elevated",
        },
        "recipes": tuple(
            RecipeOption(
                name=name,
                title=load_recipe(name).title,
                description=load_recipe(name).description,
                required_types=load_recipe(name).required_types,
            )
            for name in recipe_names()
        ),
        "fallback_recipe": FALLBACK,
        "run_inputs": ("engagement_profile", "source_documents"),
    }
    fields.update(overrides)
    return JobManifest(**fields)


@pytest.fixture
def world(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    store: SqlRunStore,
    bus: EventBus,
    blobs: LocalContentStore,
    contracts: ContractRegistry,
    constraints: ConstraintRegistry,
    started: str,
) -> Iterator[dict[str, Any]]:
    monkeypatch.setenv(KEY_NAME, Fernet.generate_key().decode())
    ports.reset()
    vault = open_vault(ports.get_secrets(), f"sqlite:///{(tmp_path / 'vault.db').as_posix()}")
    meter = CostMeter(store)
    governor = BudgetGovernor(constraints, meter, bus, store)
    masker = Masker(vault)
    boundary = UntrustedBoundary(bus)

    def door_for(port: Any) -> ModelDoor:
        return ModelDoor(port, PayloadScan(bus), governor, meter, bus)

    def orchestrator_for(port: Any) -> Orchestrator:
        return Orchestrator(door_for(port), contracts, boundary, masker, bus, blobs)

    def triage_for(port: Any) -> Triage:
        return Triage(door_for(port), contracts, boundary, masker, bus, blobs, store)

    yield {
        "store": store,
        "bus": bus,
        "blobs": blobs,
        "vault": vault,
        "meter": meter,
        "run_id": started,
        "orchestrator_for": orchestrator_for,
        "triage_for": triage_for,
        "planner": RunPlanner(store, bus, blobs, contracts, constraints),
    }
    vault.close()


def events_of(store: SqlRunStore, run_id: str, event_type: str) -> list[Any]:
    return [e for e in store.events(run_id) if e.type == event_type]
