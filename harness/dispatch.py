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
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from graph.compile import Step
from graph.execute import Blocked
from graph.resolve import ResolvedScope
from guards import GuardFailed
from guards.provenance import ProvenanceGate
from guards.schema import SchemaGate
from guards.tieout import Recompute, TieoutGate
from guards.untrusted import SENTINEL_RULE, UntrustedBoundary
from harness.context import AssembledContext, ContextBuilder, ContextRequest
from harness.door import ModelDoor
from harness.policy import RunScope
from harness.repair import as_repair, feedback_document
from harness.runtime import BoundTools, GuardedRuntime
from ops.blobs import ContentRef, ContentStore
from ops.events import EventBus
from ops.source_parse import SourceParseStore
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
        parse_store: SourceParseStore | None = None,
        sources_for: Callable[[str], Mapping[str, int]] | None = None,
        recompute: Recompute | None = None,
        tolerance_for: Callable[[str], float] | None = None,
    ) -> None:
        """`parse_store` and `sources_for` (run id -> the intake manifest's source_id to
        version) switch on the Provenance Check for every output; with `recompute` and
        `tolerance_for` (run id -> the run's tie-out tolerance) as well, the Tie-Out Check.
        The composition root passes all four; a component test that builds a dispatcher
        for one skill may not. The recompute engine is handed in rather than imported,
        because binding a tool implementation is the composition root's job."""
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
        self.provenance = (
            ProvenanceGate(contracts, parse_store, bus) if parse_store is not None else None
        )
        self.sources_for = sources_for
        self.recompute = recompute
        self.tolerance_for = tolerance_for

    def _repair(
        self,
        step: Step,
        failed: GuardFailed,
        run_id: str,
        engagement_id: str,
        identifiers: Iterable[Identifier],
    ) -> Exception:
        """The guard's rejection, as the loop the plan declares for it - or as itself.

        Here, and not in the executor or the runner, for one reason: the feedback is a
        `ContentRef` whose bytes reach the model. A tie-out failure carries stated and
        recomputed figures, locators and source ids; a provenance failure carries source ids
        and filenames. This method is inside the only object that holds the masker, the
        engagement id and the run's identifiers together - the same three the payload was
        masked with, so the door's scan sees one consistent text. Neither the runner nor the
        executor holds a masker, and text that reaches the door unmasked quarantines the run.
        """
        document = json.dumps(feedback_document(failed), sort_keys=True, separators=(",", ":"))
        masked = self.masker.mask(document, engagement_id, list(identifiers), run_id=run_id)
        ref = self.blobs.put(
            masked.text.encode("utf-8"),
            media_type="application/json",
            name=f"guard_feedback:{step.id}",
        )
        asked = as_repair(step, failed, ref)
        if asked is None:
            return failed  # no declared region on this step: quarantine, as before
        self._emit(
            run_id,
            engagement_id,
            step.id,
            "skill.repair_requested",
            f"{failed.result.guard} rejected {step.id}; the plan declares {asked.loop}",
            level="warn",
        )
        return asked

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
        repair_feedback: ContentRef | None = None,
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

        # The profile travels beside the payload and was not masked with it: an engagement
        # id that carries a client's word, or a name typed into a free-text field, reached
        # the scan unmasked and quarantined the run. Same masker, same identifiers, same
        # tokens - so the scan sees one consistent text.
        profile_text = self.blobs.get(engagement_profile).decode("utf-8")
        masked_profile = self.masker.mask(
            profile_text, engagement_id, list(identifiers), run_id=run_id
        )
        if masked_profile.substitutions:
            engagement_profile = self.blobs.put(
                masked_profile.text.encode("utf-8"),
                media_type="application/json",
                name="engagement_profile",
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
                # On a repair pass, what the guard said. The Context Builder has assembled
                # this section since P09 and nothing had ever passed one, so every repair
                # iteration would have sent a byte-identical payload - the same bad answer,
                # twice, with both iterations spent.
                repair_feedback=repair_feedback,
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
            metadata={
                "run_id": run_id,
                "context_ref": built.context_ref,
                "step_id": step.id,
                "skill": caller,
            },
        )
        call = self.door.send(
            request, masked.identifiers, run_id, step_id=step.id, estimated_cost_usd=0.05
        )

        # 5. A mapping, never a number - checked before a tool runs.
        proposal = procedure.parse(call.response.text)
        try:
            self.schema.run(proposal, procedure.proposal_contract, run_id, engagement_id, step.id)
        except GuardFailed as failed:
            raise self._repair(step, failed, run_id, engagement_id, identifiers) from None

        # 6. Through the tools the registry allows this skill, and no others.
        tools = self.runtime.bound(run_scope, caller, step.id)
        output = procedure.apply(proposal, tools, inputs, str(pin))
        contract = step.output_schema or resolved.skill.output_contract
        try:
            self.schema.run(output, contract, run_id, engagement_id, step.id)
        except GuardFailed as failed:
            raise self._repair(step, failed, run_id, engagement_id, identifiers) from None

        # 7. Every figure traced to a file this run read - and, read off the page, found
        #    there. The schema proves the envelope's shape; this proves what it claims.
        if self.provenance is not None and self.sources_for is not None:
            try:
                self.provenance.run(
                    output, run_id, engagement_id, self.sources_for(run_id), step.id
                )
            except GuardFailed as failed:
                raise self._repair(step, failed, run_id, engagement_id, identifiers) from None
        # 8. Every derived figure recomputed from the rows it cites, within the run's
        #    tolerance. The guard reads the tolerance; nothing in the step can change it.
        if self.provenance is not None and self.recompute and self.tolerance_for is not None:
            try:
                TieoutGate(
                    self.provenance.parse_store,
                    self.recompute,
                    self.tolerance_for(run_id),
                    self.bus,
                ).run(output, run_id, engagement_id, step.id)
            except GuardFailed as failed:
                raise self._repair(step, failed, run_id, engagement_id, identifiers) from None

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
