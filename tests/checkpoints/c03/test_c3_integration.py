"""C3 - A run survives being killed.

Proves: kill mid-flight, resume, zero completed steps re-execute, and plan assertions
gate the resume.

Everything from P01 to P09, together. What this checkpoint would catch is the seam
between the executor and the context builder: a step key computed from one context_ref
and a resume that assembled a different one, which would make every resume re-execute
everything and read as "resume works, slowly". So the runner here is the real shape - it
asks the Context Builder for the step's context, uses the ref it gets back, and the key
is computed from that.

Written at the end of P09 rather than at the checkpoint, per the phase file.
"""

from __future__ import annotations

import contextlib
import dataclasses
from pathlib import Path
from typing import Any

import pytest

from graph.compile import CompiledGraph, PlanContext, compile_recipe
from graph.execute import Attempt, StepExecutor
from graph.plan_assertions import PlanRefused
from graph.recipes import load_recipe
from graph.resolve import ResolvedScope, ScopeResolver
from harness.context import ContextBuilder, ContextRequest
from ops.blobs import ContentRef, LocalContentStore
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import open_store
from registries.contracts import ContractRegistry
from registries.skills import SkillTree

ENGAGEMENT = "HEND-2026-04"
CLIENT = "client_henderson"
RUN_ID = "run_c3"


@pytest.fixture(scope="module")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="module")
def scope() -> ResolvedScope:
    return ScopeResolver().resolve("valuation/esop/repeat")


@pytest.fixture(scope="module")
def plan(scope: ResolvedScope) -> CompiledGraph:
    return compile_recipe(
        load_recipe("monthly-refresh"),
        PlanContext(
            engagement_id=ENGAGEMENT, scope=scope,
            taxonomy_version="coa-taxonomy@1.0.0",
            precedent_snapshot="precedent_snapshot_2026_09_01",
        ),
    )


@pytest.fixture
def world(tmp_path: Path, contracts: ContractRegistry, plan: CompiledGraph) -> dict[str, Any]:
    """Everything a run needs, built once per test from the real modules."""
    store = open_store(f"sqlite:///{(tmp_path / 'c3.db').as_posix()}")
    blobs = LocalContentStore(tmp_path / "blobs")
    bus = EventBus(store, contracts=contracts)
    store.start_run(
        RUN_ID, ENGAGEMENT, plan.plan_hash,
        {"model_pin": "claude-opus-5 @ effort=high", "skills": ["ebitda-normalization@1.0.0"],
         "contracts": "1.0.0", "constraints": "1.0.0", "taxonomy": "coa-taxonomy@1.0.0"},
    )
    store.transition(RUN_ID, RunState.RUNNING)
    inputs = {
        "source_documents": blobs.put_json({"files": ["FY25 TB.xlsx"]}, name="source_documents"),
        "engagement_profile": blobs.put_json(
            {"industry": "manufacturing"}, name="engagement_profile"
        ),
    }
    yield {"store": store, "blobs": blobs, "bus": bus, "inputs": inputs}
    store.close()


class RealShape:
    """A runner shaped like the dispatcher will be: skill steps go through the Context
    Builder; io steps just move bytes. Records what it ran, and can be told to die."""

    def __init__(
        self, world: dict[str, Any], scope: ResolvedScope, die_after: int | None = None
    ) -> None:
        self.world = world
        self.scope = scope
        self.die_after = die_after
        self.ran: list[str] = []
        self.contexts: dict[str, str] = {}
        self.builder = ContextBuilder(
            SkillTree.load(), world["blobs"], world["bus"], store=world["store"]
        )

    def __call__(self, attempt: Attempt) -> ContentRef:
        if self.die_after is not None and len(self.ran) >= self.die_after:
            raise KeyboardInterrupt("killed")
        self.ran.append(attempt.step_id)
        blobs = self.world["blobs"]
        if attempt.step.kind == "skill":
            payload = blobs.put_json(
                {"from": {n: r.content_hash for n, r in attempt.inputs.items()}}, name="payload"
            )
            built = self.builder.build(ContextRequest(
                run_id=attempt.run_id, engagement_id=ENGAGEMENT, client_id=CLIENT,
                step=attempt.step, scope=self.scope,
                engagement_profile=self.world["inputs"]["engagement_profile"], payload=payload,
            ))
            self.contexts[attempt.step_id] = built.context_ref
            return blobs.put_json({"step": attempt.step_id, "context": built.context_ref})
        return blobs.put_json({"step": attempt.step_id, "moved": sorted(attempt.inputs)})


def executor_for(world: dict[str, Any], runner: RealShape) -> StepExecutor:
    return StepExecutor(world["store"], world["bus"], runner, blobs=world["blobs"])


# ------------------------------------------------------------ kill and resume


def test_killed_mid_flight_and_resumed_re_executes_zero_completed_steps(
    world: dict[str, Any], plan: CompiledGraph, scope: ResolvedScope
) -> None:
    """The checkpoint's whole claim, through the real modules."""
    first = RealShape(world, scope, die_after=5)
    with contextlib.suppress(KeyboardInterrupt):
        executor_for(world, first).execute(plan, RUN_ID, world["inputs"])
    assert first.ran == list(plan.order[:5])
    assert len(world["store"].ledger(RUN_ID)) == 5

    second = RealShape(world, scope)
    report = executor_for(world, second).execute(plan, RUN_ID, world["inputs"])

    assert second.ran == list(plan.order[5:]), "resume did not start at the frontier"
    assert report.satisfied == list(plan.order[:5])
    assert report.finished
    assert not set(first.ran) & set(second.ran), "a completed step was re-executed"


def test_a_third_pass_executes_nothing_at_all(
    world: dict[str, Any], plan: CompiledGraph, scope: ResolvedScope
) -> None:
    executor_for(world, RealShape(world, scope)).execute(plan, RUN_ID, world["inputs"])
    third = RealShape(world, scope)
    report = executor_for(world, third).execute(plan, RUN_ID, world["inputs"])
    assert third.ran == []
    assert report.satisfied == list(plan.order)


def test_every_skill_step_went_through_the_context_builder(
    world: dict[str, Any], plan: CompiledGraph, scope: ResolvedScope
) -> None:
    """P08 meets P09. Each skill step's context is recorded, resolvable, and distinct."""
    runner = RealShape(world, scope)
    executor_for(world, runner).execute(plan, RUN_ID, world["inputs"])
    skill_steps = [s.id for s in plan.steps_where(kind="skill")]
    assert sorted(runner.contexts) == sorted(skill_steps)
    assert len(set(runner.contexts.values())) == len(skill_steps)
    for ref in runner.contexts.values():
        assert world["blobs"].has(ContentRef(ref))
    assembled = [e for e in world["store"].events(RUN_ID) if e.type == "context.assembled"]
    assert len(assembled) == len(skill_steps)


# ------------------------------------------------ assertions gate the resume


def test_plan_assertions_gate_the_resume(
    world: dict[str, Any], plan: CompiledGraph, scope: ResolvedScope
) -> None:
    """A plan read back or mutated between passes gets the same check the compiler gave
    it. Here: the run is half done, and the plan handed to the resume declares a step
    with two model turns. Nothing executes."""
    first = RealShape(world, scope, die_after=3)
    with contextlib.suppress(KeyboardInterrupt):
        executor_for(world, first).execute(plan, RUN_ID, world["inputs"])

    two_turns = dataclasses.replace(plan.steps[4], max_turns=2)
    tampered = dataclasses.replace(
        plan, steps=(two_turns, *plan.steps[:4], *plan.steps[5:])
    )
    second = RealShape(world, scope)
    with pytest.raises(PlanRefused) as raised:
        executor_for(world, second).execute(tampered, RUN_ID, world["inputs"])

    assert raised.value.diagnostic.code == "POLICY.MULTI_TURN_STEP"
    assert second.ran == [], "the resume executed something before the check"
    assert len(world["store"].ledger(RUN_ID)) == 3, "and the ledger is as the kill left it"


def test_an_undeclared_loop_gates_the_resume_too(
    world: dict[str, Any], plan: CompiledGraph, scope: ResolvedScope
) -> None:
    tampered = dataclasses.replace(
        plan, edges=(*plan.edges[:-1], dataclasses.replace(plan.edges[-1], loop="nobody_declared"))
    )
    runner = RealShape(world, scope)
    with pytest.raises(PlanRefused, match="LOOP.UNDECLARED_CYCLE"):
        executor_for(world, runner).execute(tampered, RUN_ID, world["inputs"])
    assert runner.ran == []
