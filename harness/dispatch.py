"""The Skill Dispatcher: loads one skill into a clean context and runs it.

Invoked by the Step Executor for one compiled step. Everything a skill declares about
itself, this is the node responsible for making true:

* **One model call.** The procedure produces one request; the door sends it once.
* **The escalation comes first.** A procedure's `escalate` runs before the payload is
  even masked. A file the Period Detector flagged ambiguous never reaches a model.
* **`data_sensitivity: masked_only`** - the payload is masked by the vault before it is
  a blob, and the door's scan refuses anything the masker missed.
* **The tool allowlist is the registry's**, bound by the Guarded Runtime for exactly
  this skill; the procedure gets closures by name and nothing else.
* **A proposal is a mapping, never a number.** The proposal contract is checked before
  any tool runs; the output contract is checked before anything is returned.
* **Every document is data.** The assembled context goes to the model between the
  boundary's sentinels; the system prompt carries the rule.

A `Procedure` is the mechanical half of one skill: what to send, how to read the answer,
and how to turn the answer into the output through the tools. It lives under
`harness/procedures/`, beside the harness that runs it, because the skill tree holds
SKILL.md files and no Python at all - P10 made that a test.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from graph.compile import Step
from graph.execute import Blocked
from graph.resolve import ResolvedScope
from guards.schema import SchemaGate
from guards.untrusted import SENTINEL_RULE, UntrustedBoundary
from harness.context import AssembledContext, ContextBuilder, ContextRequest
from harness.door import ModelDoor
from harness.policy import RunScope
from harness.runtime import BoundTools, GuardedRuntime
from ops.blobs import ContentRef, ContentStore
from ops.events import EventBus
from ports.llm import LLMRequest, Message, ModelPin
from privacy.mask import Identifier, Masker
from registries.contracts import ContractRegistry
from registries.skills import SkillTree

__all__ = ["Dispatched", "Procedure", "SkillDispatcher"]

NODE = "dispatcher"


def _canonical(value: Any) -> bytes:
    """Canonical JSON of an inputs object or a proposal. A dataclass is recorded field
    by field; a set becomes a sorted list; anything else is the JSON it already is."""
    body = (
        dataclasses.asdict(value)
        if dataclasses.is_dataclass(value) and not isinstance(value, type)
        else value
    )

    def plain(x: Any) -> Any:
        if isinstance(x, frozenset | set):
            return sorted(x)
        raise TypeError(f"{type(x).__name__} is not recordable")

    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=plain).encode("utf-8")


def _summary(procedure: Any, output: dict[str, Any]) -> dict[str, Any]:
    """A procedure may describe its output for the record - `summary(output)` - and
    most do not. Labels and counts only; the scorecard reads it, nothing acts on it."""
    describe = getattr(procedure, "summary", None)
    if describe is None:
        return {}
    described: dict[str, Any] = describe(output)
    return described


class Procedure(Protocol):
    """The mechanical half of one skill. A procedure may also offer `summary(output)`,
    a dict of labels and counts describing what it produced, for the event record."""

    name: str
    proposal_contract: str

    def escalate(self, inputs: Any) -> str | None:
        """A reason to stop before any model call, or None."""
        ...

    def terms(self, inputs: Any) -> tuple[str, ...]:
        """What the precedent query ranks by - the descriptions the step is about.
        Masked by the dispatcher before the query sees them. Empty for a skill that
        retrieves no precedents."""
        ...

    def payload(self, inputs: Any) -> str:
        """The data the model sees - labels and locators, never a figure it could
        repeat. Masked by the dispatcher before it becomes a blob."""
        ...

    def parse(self, text: str) -> dict[str, Any]:
        """The proposal, from the model's text."""
        ...

    def apply(
        self, proposal: dict[str, Any], tools: BoundTools, inputs: Any, pin: str
    ) -> dict[str, Any]:
        """The output, through the tools. No arithmetic here or in the model."""
        ...


@dataclass(frozen=True)
class Dispatched:
    step_id: str
    skill: str
    output: dict[str, Any]
    output_ref: ContentRef
    proposal: dict[str, Any]
    context: AssembledContext
    request_hash: str
    model_calls: int = 1
    inputs_ref: ContentRef | None = None
    proposal_ref: ContentRef | None = None


class SkillDispatcher:
    def __init__(
        self,
        tree: SkillTree,
        context: ContextBuilder,
        door: ModelDoor,
        runtime: GuardedRuntime,
        contracts: ContractRegistry,
        boundary: UntrustedBoundary,
        masker: Masker,
        bus: EventBus,
        blobs: ContentStore,
    ) -> None:
        self.tree = tree
        self.context = context
        self.door = door
        self.runtime = runtime
        self.contracts = contracts
        self.boundary = boundary
        self.masker = masker
        self.bus = bus
        self.blobs = blobs
        self.schema = SchemaGate(contracts, bus)

    def run(
        self,
        *,
        step: Step,
        run_id: str,
        engagement_id: str,
        client_id: str,
        scope: ResolvedScope,
        engagement_profile: ContentRef,
        inputs: Any,
        identifiers: Iterable[Identifier],
        run_scope: RunScope,
        procedure: Procedure,
        pin: ModelPin,
    ) -> Dispatched:
        if step.kind != "skill" or not step.skill:
            raise ValueError(f"{step.id} is not a skill step")
        skill_name = step.skill.split("@", 1)[0]
        resolved = scope.skill(skill_name)
        caller = resolved.skill.key

        # 1. Escalate before anything else. A person, not a model, settles ambiguity.
        reason = procedure.escalate(inputs)
        if reason:
            self._emit(run_id, engagement_id, step.id, "skill.escalated", reason, level="warn")
            raise Blocked(f"escalate:{step.id}", f"{skill_name}: {reason}", kind=resolved.hitl)

        # 2. The payload, masked before it is a blob.
        masked = self.masker.mask(
            procedure.payload(inputs), engagement_id, list(identifiers), run_id=run_id
        )
        payload_ref = self.blobs.put(
            masked.text.encode("utf-8"), media_type="text/plain", name="payload"
        )
        # What the precedent query ranks by, masked the same way the payload was, so a
        # description reaches the store's index only as the model would see it.
        terms = tuple(
            self.masker.mask(term, engagement_id, list(identifiers), run_id=run_id).text
            for term in procedure.terms(inputs)
        )

        # 3. The context, assembled and hashed by the one place that may.
        built = self.context.build(
            ContextRequest(
                run_id=run_id,
                engagement_id=engagement_id,
                client_id=client_id,
                step=step,
                scope=scope,
                engagement_profile=engagement_profile,
                payload=payload_ref,
                precedent_terms=terms,
            )
        )
        self._emit(
            run_id,
            engagement_id,
            step.id,
            "skill.dispatched",
            f"{caller} · tier {resolved.skill.tier} · {len(resolved.references)} reference(s)"
            f" + {len(built.precedent_ids)} precedent(s)",
            payload={
                "context_ref": built.context_ref,
                "skill": caller,
                "precedents": list(built.precedent_ids),
            },
        )

        # 4. One call. The skill's own text is the instruction; everything assembled is data.
        system = "\n\n".join(
            [
                f"You are running the skill {caller}. Follow its procedure exactly and answer "
                f"with JSON that satisfies {procedure.proposal_contract}, and nothing else.",
                self.tree.body(resolved.skill),
                *(
                    self.tree.reference(
                        resolved.skill, name, declared=resolved.references, layers=scope.layers
                    )
                    for name in resolved.references
                ),
                SENTINEL_RULE,
            ]
        )
        wrapped = self.boundary.wrap(
            self.blobs.get(built.ref).decode("utf-8"),
            source_id=built.context_ref,
            label=f"context:{step.id}",
            run_id=run_id,
            engagement_id=engagement_id,
            step_id=step.id,
        )
        request = LLMRequest(
            pin=pin,
            system=system,
            messages=(Message("user", wrapped.text),),
            metadata={"context_ref": built.context_ref, "step_id": step.id, "skill": caller},
        )
        call = self.door.send(
            request, masked.identifiers, run_id, step_id=step.id, estimated_cost_usd=0.05
        )

        # 5. A mapping, never a number - checked before a tool runs.
        proposal = procedure.parse(call.response.text)
        self.schema.run(proposal, procedure.proposal_contract, run_id, engagement_id, step.id)

        # 6. Through the tools the registry allows this skill, and no others.
        tools = self.runtime.bound(run_scope, caller, step.id)
        output = procedure.apply(proposal, tools, inputs, str(pin))
        contract = step.output_schema or resolved.skill.output_contract
        self.schema.run(output, contract, run_id, engagement_id, step.id)

        output_ref = self.blobs.put(
            json.dumps(output, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            media_type="application/json",
            name=f"output:{step.id}",
        )
        # What the step was given and what the model answered, on the record beside the
        # output: the Replay Harness restores a step from exactly these.
        inputs_ref = self.blobs.put(
            _canonical(inputs), media_type="application/json", name=f"inputs:{step.id}"
        )
        proposal_ref = self.blobs.put(
            _canonical(proposal), media_type="application/json", name=f"proposal:{step.id}"
        )
        self._emit(
            run_id,
            engagement_id,
            step.id,
            "skill.completed",
            f"{caller}: output {output_ref.content_hash[:19]}",
            payload={
                "output_ref": output_ref.content_hash,
                "inputs_ref": inputs_ref.content_hash,
                "proposal_ref": proposal_ref.content_hash,
                "request_hash": call.request_hash,
                "skill": caller,
                # What the skill says about its own output, for the scorecard and
                # the console: labels and counts, never a figure (the payload scan
                # has not seen this and no figure may travel in an event).
                "summary": _summary(procedure, output),
            },
        )
        return Dispatched(
            step_id=step.id,
            skill=caller,
            output=output,
            output_ref=output_ref,
            proposal=proposal,
            context=built,
            request_hash=call.request_hash,
            inputs_ref=inputs_ref,
            proposal_ref=proposal_ref,
        )

    def _emit(  # noqa: PLR0913 - one call, one record
        self,
        run_id: str,
        engagement_id: str,
        step_id: str,
        event_type: str,
        message: str,
        level: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type=event_type,
            message=f"{step_id}: {message}",
            level=level,
            step_id=step_id,
            payload=payload or {},
        )
