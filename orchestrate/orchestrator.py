"""The Orchestrator Agent: reads what arrived, says which skills to run and in what order.

One model call with structured output, mid tier, through the same door every other model
call goes through - so the payload scan, the budget governor, the pin check and the meter
all apply to it exactly as they apply to a skill. There is nothing special about this call
except what is in its context.

**Its context holds the Skill Index and the job manifest, and never a SKILL.md body.** The
index is Tier 1: name and one-line description, about forty tokens each, built by the
resolved scope. That is the whole skill footprint here, and it is what lets the library
grow into the hundreds while what the orchestrator reads stays about a dozen lines. This
module does not import `SkillTree` and has no way to reach a body; a test asserts both,
because an orchestrator that quietly grew a body in its prompt would work perfectly and
cost more every run.

**It returns a plan, never a value.** `run_plan_proposal@1.0.0` has no numeric property
anywhere - not a figure, not a confidence, not a timeout, not an iteration ceiling. Where
a routing decision needs a "not confident enough", the schema says so categorically:
`match: none` is the answer that sends the job to Triage, rather than a number compared
against a threshold nobody agreed.

**Dispatch is directed, with no path back to itself.** `propose` is called once, before
anything runs. No skill returns here to start a fresh request, so there is no cycle a
build has to bound - which is why the orchestrator is not a loop region anywhere.

What it proposes is not what runs. `orchestrate.plan.RunPlanner` compiles the proposal
with the same compiler and the same plan assertions a named recipe gets, and uses the
recipe instead if it does not survive.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from graph.resolve import ResolvedScope
from guards import GuardFailed
from guards.schema import SchemaGate
from guards.untrusted import UntrustedBoundary
from harness.door import ModelDoor
from ops.blobs import ContentStore, put_json
from ops.events import EventBus
from orchestrate.manifest import JobManifest
from ports.llm import LLMRequest, Message, ModelPin
from privacy.mask import Identifier, Masker
from registries.contracts import ContractRegistry

__all__ = ["ORCHESTRATOR_VERSION", "PROPOSAL_CONTRACT", "Orchestrator", "Proposal"]

PROPOSAL_CONTRACT = "run_plan_proposal@1.0.0"
ORCHESTRATOR_VERSION = "orchestrator@1.0.0"
NODE = "orchestrator"
TIER = "mid"
STEP_ID = "plan"
"""What the orchestrator's call is recorded under. Not a step in the plan - it is what
produces the plan - but the door, the meter and the console all key on a step id, and an
empty one would put the cost of planning nowhere."""

INSTRUCTIONS = """\
You are the orchestrator for one engagement's run. Decide which skills run and in what
order, and answer with JSON satisfying run_plan_proposal@1.0.0 and nothing else.

Rules:
- Choose only from the skill index below. A name that is not in it does not exist for
  this engagement, and naming one refuses the whole plan.
- If a named recipe is the shape of this job, say so: match "recipe" and name it. The
  recipe's own steps are then used; you do not restate them.
- Compose only when no recipe fits: match "composed", with the steps and what each needs.
- If you cannot route this job at all, say match "none" and give the escalation reason. A
  person will read it. Do not guess a plan you do not believe in.
- You have no way to set a timeout, a retry, an iteration ceiling, a model or an output
  contract, and no way to ask for another attempt. Those are the graph's, not yours.
- Propose a plan. Never a figure, a total or an assessment of the numbers: you have not
  been shown them, and there is no field in the schema for one.
"""


@dataclass(frozen=True)
class Proposal:
    """What the model returned, and the identity of the call that produced it."""

    body: dict[str, Any]
    request_hash: str
    proposal_ref: str
    manifest_hash: str
    index: tuple[str, ...]

    @property
    def match(self) -> str:
        return str(self.body.get("match", "none"))

    @property
    def routed(self) -> bool:
        """False when the orchestrator says nothing fits. That is Triage's case."""
        return self.match in ("recipe", "composed")

    @property
    def escalation_reason(self) -> str:
        return str(self.body.get("escalation_reason") or "")


class Orchestrator:
    def __init__(
        self,
        door: ModelDoor,
        contracts: ContractRegistry,
        boundary: UntrustedBoundary,
        masker: Masker,
        bus: EventBus,
        blobs: ContentStore,
        *,
        tier: str = TIER,
    ) -> None:
        self.door = door
        self.contracts = contracts
        self.boundary = boundary
        self.masker = masker
        self.bus = bus
        self.blobs = blobs
        self.tier = tier
        self.schema = SchemaGate(contracts, bus)

    def pin(self, effort: str = "high") -> ModelPin:
        """Mid tier: this is routing over a closed set with good signal, not deep
        reasoning. Triage, which gets the cases where a mistake costs most, is high."""
        return ModelPin.for_tier(self.tier, effort=effort)  # type: ignore[arg-type]

    def propose(
        self,
        *,
        manifest: JobManifest,
        scope: ResolvedScope,
        run_id: str,
        identifiers: Iterable[Identifier] = (),
        effort: str = "high",
    ) -> Proposal:
        """One call. The index and the manifest go in; a plan proposal comes back."""
        index = scope.index()
        masked = self.masker.mask(
            manifest.as_prompt(), manifest.engagement_id, list(identifiers), run_id=run_id
        )
        wrapped = self.boundary.wrap(
            masked.text,
            source_id=manifest.content_hash(),
            label="job_manifest",
            run_id=run_id,
            engagement_id=manifest.engagement_id,
            step_id=STEP_ID,
        )
        request = LLMRequest(
            pin=self.pin(effort),
            system="\n\n".join(
                [
                    INSTRUCTIONS,
                    "## Skill index\n" + index.as_prompt(),
                    f"## Fallback recipe\n{manifest.fallback_recipe}",
                ]
            ),
            messages=(Message("user", wrapped.text),),
            metadata={"step_id": STEP_ID, "node": NODE, "scope": manifest.scope_path},
        )
        self.bus.emit(
            run_id=run_id,
            engagement_id=manifest.engagement_id,
            node_id=NODE,
            type="plan.requested",
            message=(
                f"{len(index)} skill(s) in the index, {len(manifest.documents)} document(s), "
                f"{len(manifest.recipes)} recipe(s) on the menu"
            ),
            step_id=STEP_ID,
            payload={
                "manifest_hash": manifest.content_hash(),
                "index": list(index.names()),
                "scope": manifest.scope_path,
            },
        )
        call = self.door.send(
            request, masked.identifiers, run_id, step_id=STEP_ID, estimated_cost_usd=0.02
        )
        body = _parse(call.response.text)
        try:
            self.schema.run(body, PROPOSAL_CONTRACT, run_id, manifest.engagement_id, STEP_ID)
        except GuardFailed:
            # The gate has already recorded what was wrong with it. A proposal that is
            # not a proposal is refused here rather than compiled into a plan-shaped
            # object that would fail later for a less obvious reason.
            raise
        ref = put_json(self.blobs, body, name="proposal:plan")
        self.bus.emit(
            run_id=run_id,
            engagement_id=manifest.engagement_id,
            node_id=NODE,
            type="plan.proposed",
            message=(
                f"match {body.get('match')}"
                + (f" ({body['recipe']})" if body.get("recipe") else "")
                + f": {len(body.get('steps') or ())} step(s)"
            ),
            step_id=STEP_ID,
            payload={
                "match": body.get("match"),
                "recipe": body.get("recipe"),
                "steps": [str(s.get("id")) for s in body.get("steps") or ()],
                "skills": [str(s["skill"]) for s in body.get("steps") or () if s.get("skill")],
                "proposal_ref": ref.content_hash,
                "request_hash": call.request_hash,
            },
        )
        return Proposal(
            body=body,
            request_hash=call.request_hash,
            proposal_ref=ref.content_hash,
            manifest_hash=manifest.content_hash(),
            index=index.names(),
        )


def _parse(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("the orchestrator returned no JSON object")
    body = json.loads(text[start : end + 1])
    if not isinstance(body, dict):
        raise ValueError("the proposal is not an object")
    return body
