"""Triage & Escalation: when nothing fits, route to a person instead of guessing.

The low-confidence fallback. It runs when the orchestrator answers `match: none`, or when
a proposal was refused and somebody should know why before the fallback recipe runs on a
job that may not be the routine shape after all.

**High tier, deliberately.** The cases that reach here - unusual entity structures, hybrid
instruments, incoherent client data - are exactly the ones where a classification mistake
costs the most, so this is not the place to economise on model quality.

**Its output schema has no numeric property, so it cannot emit a number.** Not "it is
instructed not to": `triage@1.0.0` has no field of type number or integer anywhere in it,
and `additionalProperties` is false at every level, so a figure has nowhere to go. Given
the inputs that reach triage, a plausible invented figure is the single most damaging
thing it could produce, and the schema is what makes it unavailable rather than
discouraged.

**It escalates; it does not start work.** A suggested skill is checked against the Skill
Index and recorded for a person to act on - there is no method here that dispatches one,
and no caller gets a plan back. The review item is the output.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from graph.resolve import ResolvedScope
from guards.schema import SchemaGate
from guards.untrusted import UntrustedBoundary
from harness.door import ModelDoor
from ops.blobs import ContentStore, put_json
from ops.events import EventBus
from ops.run_store import RunStore
from orchestrate.manifest import JobManifest
from ports.llm import LLMRequest, Message, ModelPin
from privacy.mask import Identifier, Masker
from registries.contracts import ContractRegistry
from registries.errors import AMBIGUOUS_SKILL, diagnose

__all__ = ["TRIAGE_CONTRACT", "TRIAGE_VERSION", "Assessment", "Triage"]

TRIAGE_CONTRACT = "triage@1.0.0"
TRIAGE_VERSION = "triage@1.0.0"
NODE = "triage"
TIER = "high"
STEP_ID = "triage"
KIND = "clarification"

INSTRUCTIONS = """\
You are triaging one engagement's run because the orchestrator could not route it. Say
what you are looking at and why nothing fits, and answer with JSON satisfying
triage@1.0.0 and nothing else.

Rules:
- Classify the problem with one of the categories in the schema.
- If a skill from the index below now looks right, name it. A name that is not in the
  index is dropped and the case escalates instead.
- Otherwise give the escalation reason. A person reads it and decides.
- You cannot state a figure, a total, an adjustment or any other number: the schema has
  no field for one. Describe the problem in words.
- You are not starting work. Naming a skill is a suggestion recorded for a person, never
  a dispatch.
"""


@dataclass(frozen=True)
class Assessment:
    """What triage concluded about the routing - and nothing about the numbers."""

    body: dict[str, Any]
    item_id: str
    request_hash: str
    assessment_ref: str
    suggested_skill: str | None = None
    dropped_suggestion: str | None = None
    """A skill the model named that did not resolve into this engagement's scope. Kept
    on the record, kept out of the suggestion."""

    @property
    def category(self) -> str:
        return str(self.body.get("category", ""))

    @property
    def escalation_reason(self) -> str:
        return str(self.body.get("escalation_reason") or "")


class Triage:
    def __init__(
        self,
        door: ModelDoor,
        contracts: ContractRegistry,
        boundary: UntrustedBoundary,
        masker: Masker,
        bus: EventBus,
        blobs: ContentStore,
        store: RunStore,
        *,
        tier: str = TIER,
    ) -> None:
        self.door = door
        self.contracts = contracts
        self.boundary = boundary
        self.masker = masker
        self.bus = bus
        self.blobs = blobs
        self.store = store
        self.tier = tier
        self.schema = SchemaGate(contracts, bus)

    def pin(self, effort: str = "high") -> ModelPin:
        return ModelPin.for_tier(self.tier, effort=effort)  # type: ignore[arg-type]

    def assess(
        self,
        *,
        manifest: JobManifest,
        scope: ResolvedScope,
        run_id: str,
        why: str,
        owner: str | None = None,
        identifiers: Iterable[Identifier] = (),
        effort: str = "high",
    ) -> Assessment:
        """One high-tier call, then a review item. Nothing is dispatched from here."""
        index = scope.index()
        masked = self.masker.mask(
            "\n\n".join([manifest.as_prompt(), f"## Why this reached triage\n{why}"]),
            manifest.engagement_id,
            list(identifiers),
            run_id=run_id,
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
            system="\n\n".join([INSTRUCTIONS, "## Skill index\n" + index.as_prompt()]),
            messages=(Message("user", wrapped.text),),
            metadata={"step_id": STEP_ID, "node": NODE, "scope": manifest.scope_path},
        )
        call = self.door.send(
            request, masked.identifiers, run_id, step_id=STEP_ID, estimated_cost_usd=0.05
        )
        body = _parse(call.response.text)
        self.schema.run(body, TRIAGE_CONTRACT, run_id, manifest.engagement_id, STEP_ID)

        named = body.get("suggested_skill") or None
        suggested = str(named) if named and str(named) in index.names() else None
        dropped = str(named) if named and suggested is None else None
        if dropped:
            d = diagnose(
                AMBIGUOUS_SKILL,
                f"triage suggested {dropped!r}, which did not resolve into "
                f"{manifest.scope_path}. Dropped: a suggestion nobody can act on is "
                f"worse than none.",
                locator=dropped,
            )
            self.bus.emit(
                run_id=run_id,
                engagement_id=manifest.engagement_id,
                node_id=NODE,
                type="triage.suggestion_dropped",
                message=d.detail,
                level="warn",
                step_id=STEP_ID,
                diagnostic_code=d.code,
                payload={"suggested": dropped, "index": list(index.names())},
            )

        ref = put_json(self.blobs, body, name="triage")
        item_id = f"triage:{run_id}"
        subject = _subject(body, suggested, manifest.engagement_id)
        self.store.open_review_item(
            run_id,
            item_id,
            kind=KIND,
            subject=subject,
            detail={
                "category": body.get("category"),
                "assessment": body.get("assessment"),
                "suggested_skill": suggested,
                "dropped_suggestion": dropped,
                "escalation_reason": body.get("escalation_reason"),
                "assessment_ref": ref.content_hash,
                "why": why,
            },
            owner=owner,
        )
        self.bus.emit(
            run_id=run_id,
            engagement_id=manifest.engagement_id,
            node_id=NODE,
            type="triage.escalated",
            message=subject,
            level="warn",
            step_id=STEP_ID,
            payload={
                "item_id": item_id,
                "category": body.get("category"),
                "suggested_skill": suggested,
                "assessment_ref": ref.content_hash,
                "request_hash": call.request_hash,
            },
        )
        return Assessment(
            body=body,
            item_id=item_id,
            request_hash=call.request_hash,
            assessment_ref=ref.content_hash,
            suggested_skill=suggested,
            dropped_suggestion=dropped,
        )


def _subject(body: dict[str, Any], suggested: str | None, engagement_id: str) -> str:
    category = str(body.get("category", "unclear"))
    if suggested:
        return f"{engagement_id}: {category} - triage suggests {suggested}; a person confirms"
    reason = str(body.get("escalation_reason") or body.get("assessment") or "")
    return f"{engagement_id}: {category} - {reason.strip()[:160]}"


def _parse(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("triage returned no JSON object")
    body = json.loads(text[start : end + 1])
    if not isinstance(body, dict):
        raise ValueError("the assessment is not an object")
    return body
