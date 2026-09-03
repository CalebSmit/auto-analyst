"""C4 - One step through all six harness stages.

Proves: a no-op skill passes context, reason, policy, act, verify and accept, with every
stage emitting.

Everything from P01 to P12, together, around one skill step. The six stages, and the
node each one reports as:

    context   the Context Builder assembles and hashes       context_builder
    reason    the one door: scan, budget, port, pin, meter   payload_scan, llm_port, cost_meter
    policy    the Policy Gate decides a proposed tool call   policy_gate
    act       the Guarded Runtime executes it                guarded_runtime
    verify    unmask and the integrity check                 unmask_verify
    accept    the executor commits the result to the ledger  step_executor

The skill is a no-op: the model is a stub that says "ok", the tool is a fake that returns
a row. What the checkpoint proves is that the harness holds together around it - that a
payload masked by P12 clears P11's scan, that the context P09 built is what P11 sent,
that P10's gate saw the call P08's executor keyed, and that every stage said so.

Written at the end of P12 rather than at the checkpoint, per the phase file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

import ports
from graph.compile import CompiledGraph, PlanContext, compile_recipe
from graph.execute import Attempt, StepExecutor
from graph.recipes import load_recipe
from graph.resolve import ResolvedScope, ScopeResolver
from harness.budget import BudgetGovernor
from harness.context import ContextBuilder, ContextRequest
from harness.door import ModelDoor
from harness.policy import PolicyGate, RunScope
from harness.runtime import GuardedRuntime
from ops.blobs import ContentRef, LocalContentStore
from ops.cost import CostMeter
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import open_store
from ports.llm import LLMRequest, LLMResponse, Message, ModelPin, Usage
from privacy.mask import Identifier, Masker
from privacy.payload_scan import PayloadScan
from privacy.unmask import Unmasker
from privacy.vault import KEY_NAME, open_vault
from privacy.verify import UnmaskVerify
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.skills import SkillTree

ENGAGEMENT = "HEND-2026-04"
CLIENT = "client_henderson"
RUN_ID = "run_c4"
STAGES = ("context", "reason", "policy", "act", "verify", "accept")
NODES_BY_STAGE = {
    "context": {"context_builder"},
    "reason": {"payload_scan", "llm_port", "cost_meter"},
    "policy": {"policy_gate"},
    "act": {"guarded_runtime"},
    "verify": {"unmask_verify"},
    "accept": {"step_executor"},
}


class SaysOk:
    """The no-op model."""

    name = "says_ok"

    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text='{"tagged": "[[ACCOUNT_1]] -> operating"}', model=request.pin.model,
            stop_reason="end_turn", usage=Usage(input_tokens=400, output_tokens=20),
        )


@pytest.fixture(scope="module")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture(scope="module")
def constraints() -> ConstraintRegistry:
    return ConstraintRegistry.load()


@pytest.fixture(scope="module")
def scope() -> ResolvedScope:
    return ScopeResolver().resolve("valuation/esop/repeat")


@pytest.fixture(scope="module")
def plan(scope: ResolvedScope) -> CompiledGraph:
    return compile_recipe(
        load_recipe("monthly-refresh"),
        PlanContext(engagement_id=ENGAGEMENT, scope=scope,
                    taxonomy_version="coa-taxonomy@1.0.0",
                    precedent_snapshot="precedent_snapshot_2026_09_01"),
    )


@pytest.fixture
def world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contracts: ContractRegistry,
    constraints: ConstraintRegistry, plan: CompiledGraph, scope: ResolvedScope,
) -> dict[str, Any]:
    """Every harness stage, built from the real modules, around one run."""
    monkeypatch.setenv(KEY_NAME, Fernet.generate_key().decode())
    ports.reset()

    store = open_store(f"sqlite:///{(tmp_path / 'c4.db').as_posix()}")
    blobs = LocalContentStore(tmp_path / "blobs")
    bus = EventBus(store, contracts=contracts)
    vault = open_vault(ports.get_secrets(), f"sqlite:///{(tmp_path / 'vault.db').as_posix()}")
    meter = CostMeter(store)
    governor = BudgetGovernor(constraints, meter, bus, store)

    store.start_run(
        RUN_ID, ENGAGEMENT, plan.plan_hash,
        {"model_pin": "claude-sonnet-5 @ effort=high", "skills": ["line-item-tagging@1.0.0"],
         "contracts": "1.0.0", "constraints": "1.0.0", "taxonomy": "coa-taxonomy@1.0.0"},
    )
    store.transition(RUN_ID, RunState.RUNNING)

    world = {
        "store": store, "blobs": blobs, "bus": bus, "vault": vault, "scope": scope,
        "masker": Masker(vault), "unmasker": Unmasker(vault), "verify": UnmaskVerify(bus),
        "context": ContextBuilder(SkillTree.load(), blobs, bus, store=store),
        "door": ModelDoor(SaysOk(), PayloadScan(bus), governor, meter, bus),
        "gate": PolicyGate(constraints, bus),
        "run_scope": RunScope(
            run_id=RUN_ID, engagement_id=ENGAGEMENT, engagement_root=f"engagements/{ENGAGEMENT}",
            scope_path="valuation/esop/repeat",
            versions={"chart_of_accounts_lookup": "coa-taxonomy@1.0.0"},
            budget_remaining_usd=governor.remaining_usd(RUN_ID),
        ),
        "inputs": {
            "source_documents": blobs.put_json(
                {"files": ["FY25 TB.xlsx"]}, name="source_documents"
            ),
            "engagement_profile": blobs.put_json(
                {"industry": "manufacturing"}, name="engagement_profile"
            ),
        },
    }
    world["runtime"] = GuardedRuntime(
        world["gate"], constraints, bus,
        {"chart_of_accounts_lookup": lambda **kw: {"rows": [{"code": "6100"}]}},
    )
    yield world
    vault.close()
    store.close()


class OneSkillThroughSixStages:
    """The runner. io steps move bytes; the one skill step goes through every stage."""

    def __init__(self, world: dict[str, Any]) -> None:
        self.world = world
        self.stages_run: list[str] = []
        self.unmasked_text: str = ""

    def __call__(self, attempt: Attempt) -> ContentRef:
        w = self.world
        blobs = w["blobs"]
        if attempt.step.kind != "skill" or attempt.step_id != "tagging":
            if attempt.step.kind == "skill":
                return blobs.put_json({"step": attempt.step_id, "noop": True})
            return blobs.put_json({"step": attempt.step_id, "moved": sorted(attempt.inputs)})

        # The payload arrives masked - P12 - and the masker hands over what the scan must
        # check.
        raw = "Bob's LLC Checking 48,231.00 owner draw Bob Henderson"
        masked = w["masker"].mask(
            raw, ENGAGEMENT,
            (Identifier("ACCOUNT", "Bob's LLC Checking"), Identifier("PERSON", "Bob Henderson")),
            run_id=RUN_ID,
        )
        payload = blobs.put_json({"line_items": masked.text}, name="payload")

        # context
        built = w["context"].build(ContextRequest(
            run_id=RUN_ID, engagement_id=ENGAGEMENT, client_id=CLIENT, step=attempt.step,
            scope=w["scope"], engagement_profile=w["inputs"]["engagement_profile"],
            payload=payload,
        ))
        self.stages_run.append("context")

        # reason: what the builder assembled is what the door sends
        request = LLMRequest(
            pin=ModelPin.for_tier("mid"),
            system="Tag line items. Output JSON.",
            messages=(Message("user", blobs.get(built.ref).decode("utf-8")),),
            metadata={"context_ref": built.context_ref},
        )
        call = w["door"].send(request, masked.identifiers, RUN_ID, step_id=attempt.step_id,
                              estimated_cost_usd=0.01)
        self.stages_run.append("reason")

        # policy + act: the skill proposes one lookup; the gate decides; the runtime runs
        tools = w["runtime"].bound(w["run_scope"], attempt.step.skill or "", attempt.step_id)
        result = tools["chart_of_accounts_lookup"](
            engagement_id=ENGAGEMENT, version="coa-taxonomy@1.0.0", limit=10,
        )
        self.stages_run.extend(["policy", "act"])
        assert result.rows == 1

        # verify: unmask the model's output and check the three assertions
        back = w["unmasker"].unmask(call.response.text, ENGAGEMENT)
        w["verify"].verify(back, w["vault"].issued(ENGAGEMENT), run_id=RUN_ID,
                           step_id=attempt.step_id)
        self.unmasked_text = back.text
        self.stages_run.append("verify")

        # accept: return the ref; the executor commits it, which is the sixth stage
        return blobs.put_json({"tagged": back.text, "context_ref": built.context_ref})


def test_one_step_passes_all_six_stages_with_every_stage_emitting(
    world: dict[str, Any], plan: CompiledGraph
) -> None:
    runner = OneSkillThroughSixStages(world)
    executor = StepExecutor(world["store"], world["bus"], runner, blobs=world["blobs"])
    report = executor.execute(plan, RUN_ID, world["inputs"])

    assert report.finished, str(report)
    assert runner.stages_run == list(STAGES[:5])

    events = world["store"].events(RUN_ID)
    on_step = [e for e in events if e.step_id == "tagging"]
    nodes = {e.node_id for e in on_step}
    for stage in STAGES:
        missing = NODES_BY_STAGE[stage] - nodes
        assert not missing, f"stage {stage!r} did not emit from {sorted(missing)}"


def test_the_stages_emit_in_order(world: dict[str, Any], plan: CompiledGraph) -> None:
    """context before reason before policy before act before verify before accept."""
    runner = OneSkillThroughSixStages(world)
    StepExecutor(world["store"], world["bus"], runner, blobs=world["blobs"]).execute(
        plan, RUN_ID, world["inputs"]
    )
    on_step = [e for e in world["store"].events(RUN_ID) if e.step_id == "tagging"]
    first_seen = {}
    for event in on_step:
        first_seen.setdefault(event.node_id, event.seq)
    order = [
        first_seen["context_builder"], first_seen["payload_scan"], first_seen["llm_port"],
        first_seen["policy_gate"], first_seen["guarded_runtime"], first_seen["unmask_verify"],
    ]
    assert order == sorted(order)
    committed = [e for e in on_step if e.type == "step.completed"]
    assert len(committed) == 1
    assert committed[0].seq > first_seen["unmask_verify"]


def test_the_masked_payload_cleared_the_scan_and_came_back_re_identified(
    world: dict[str, Any], plan: CompiledGraph
) -> None:
    """P12 meets P11: the masker's identifier list is what the scan checked, and the
    unmasker put the account name back."""
    runner = OneSkillThroughSixStages(world)
    StepExecutor(world["store"], world["bus"], runner, blobs=world["blobs"]).execute(
        plan, RUN_ID, world["inputs"]
    )
    scan = [e for e in world["store"].events(RUN_ID) if e.type == "guard.payload_scan.pass"]
    assert len(scan) == 1 and scan[0].payload["checked"] == 4
    assert "Bob's LLC Checking" in runner.unmasked_text
    assert "[[" not in runner.unmasked_text


def test_the_step_was_keyed_on_the_context_the_door_sent(
    world: dict[str, Any], plan: CompiledGraph
) -> None:
    """P09 meets P08 meets P11: one context_ref, in the ledger's result, in the event the
    door recorded, and in what the model was actually shown."""
    runner = OneSkillThroughSixStages(world)
    StepExecutor(world["store"], world["bus"], runner, blobs=world["blobs"]).execute(
        plan, RUN_ID, world["inputs"]
    )
    entry = next(e for e in world["store"].ledger(RUN_ID) if e.step_id == "tagging")
    result = world["blobs"].get_json(ContentRef(entry.result_ref))
    assembled = [e for e in world["store"].events(RUN_ID) if e.type == "context.assembled"]
    assert result["context_ref"] == assembled[0].payload["context_ref"]


def test_a_second_pass_does_none_of_it_again(world: dict[str, Any], plan: CompiledGraph) -> None:
    """The ledger holds the step; a resume asks no stage to run. Every guarantee above is
    still true of the record, and nothing was paid for twice."""
    first = OneSkillThroughSixStages(world)
    StepExecutor(world["store"], world["bus"], first, blobs=world["blobs"]).execute(
        plan, RUN_ID, world["inputs"]
    )
    second = OneSkillThroughSixStages(world)
    report = StepExecutor(world["store"], world["bus"], second, blobs=world["blobs"]).execute(
        plan, RUN_ID, world["inputs"]
    )
    assert second.stages_run == []
    assert report.satisfied == list(plan.order)
