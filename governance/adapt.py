"""The Adaptation Bench: where a rough draft is fitted to the contract and given a scope.

A model working from the gap report and the Skill Contract fills what the scan named:
frontmatter, declared inputs and outputs, a tool allowlist valid against the Constraint
Registry, a data sensitivity class, an hitl floor, an output schema, a when-not-to-use
section and escalation rules. It proposes the scope layer, with its reasoning, and a
person confirms it.

**It cannot produce fixtures.** That limit is the important one. Without it, the drop
folder plus a helpful model becomes the route by which unvalidated logic reaches client
work. Fixtures are evidence the skill works, and evidence does not come from the thing
being tested. So the bench outputs a conforming skill *and a fixture request*, there is no
method here that writes a fixture, and the chain will not let a candidate past the eval
harness without one somebody else supplied.

Scope follows one rule - the shallowest layer where the skill is true - proposed with its
reasoning and confirmed by the practice owner, because too deep gets duplicated and too
shallow fires where it should not.

The bench is one model call through the same door as everything else. What it is shown is
the gap report, the draft body and the contract; never an engagement file, because
governance has no path to one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, NoReturn

import yaml

from governance.candidate import Stage
from governance.conformance import GapReport
from governance.record import GovernanceRecord
from guards.untrusted import UntrustedBoundary
from harness.door import ModelDoor
from ops.blobs import ContentStore, put_json
from ports.llm import LLMRequest, Message, ModelPin
from privacy.payload_scan import IdentifierList
from registries.constraints import ConstraintRegistry
from registries.errors import SKILL_INVALID, RegistryError, diagnose
from registries.skills import REQUIRED_FRONTMATTER

__all__ = ["AdaptationBench", "Adapted", "FixtureRequest"]

NODE = "skill_adapt"
TIER = "high"
GOVERNANCE_SCOPE = "governance"
GOVERNANCE_RUN = "gov_bench"
"""The run every bench call is metered under. Governance work costs money and the meter
keys on a run, so it gets its own rather than borrowing an engagement's."""
"""The engagement id every governance model call is made under. There is no such
engagement: it is what the payload scan and the meter key on, and it is deliberately not
any client's, so a governance call cannot be recorded against a deal."""

INSTRUCTIONS = """\
You are fitting a rough skill draft to the Skill Contract. Answer with JSON and nothing
else: {"frontmatter": {...}, "body": "...", "scope_reasoning": "...", "fixture_request":
{"what": "...", "how_many": "...", "who": "..."}}.

Rules:
- Fill every gap the report names. Change the procedure as little as possible: you are
  fitting a draft to a shape, not rewriting somebody's thinking.
- tools may only name tools in the allowlist below. An undeclared tool is refused.
- Propose the scope layer as the shallowest layer where this skill is true, and say why.
  A person confirms it.
- You cannot supply fixtures. Write the fixture request instead: what cases are needed,
  roughly how many, and who should produce them.
- Do not invent an output contract id. Name one from the registry or say which is needed.
"""


@dataclass(frozen=True)
class FixtureRequest:
    """What the bench asks a person for. The chain will not proceed without an answer."""

    what: str
    how_many: str
    who: str

    def line(self) -> str:
        return f"{self.what} ({self.how_many}) - {self.who}"


@dataclass(frozen=True)
class Adapted:
    """A conforming SKILL.md, a proposed scope, and the fixture request."""

    candidate_id: str
    name: str
    version: str
    layer: str
    frontmatter: dict[str, Any]
    body: str
    scope_reasoning: str
    fixture_request: FixtureRequest
    ref: str = ""

    def skill_md(self) -> str:
        """The file as it would be written. Frontmatter then body, nothing else."""
        front = yaml.safe_dump(self.frontmatter, sort_keys=False).strip()
        return f"---\n{front}\n---\n\n{self.body.strip()}\n"


class AdaptationBench:
    def __init__(
        self,
        record: GovernanceRecord,
        door: ModelDoor,
        blobs: ContentStore,
        constraints: ConstraintRegistry | None = None,
        run_id: str = GOVERNANCE_RUN,
    ) -> None:
        self.record = record
        self.door = door
        self.blobs = blobs
        self.run_id = run_id
        self.constraints = constraints or ConstraintRegistry.load()
        self.boundary = UntrustedBoundary()

    def pin(self, effort: str = "high") -> ModelPin:
        return ModelPin.for_tier(TIER, effort=effort)  # type: ignore[arg-type]

    def adapt(self, report: GapReport, *, run_id: str = "", proposed_by: str = NODE) -> Adapted:
        """One call. The gap report goes in; a conforming skill and a fixture request
        come back. The draft body is wrapped as untrusted content, because it is."""
        wrapped = self.boundary.wrap(
            report.body,
            source_id=report.candidate_id,
            label="skill_draft",
            run_id=run_id or self.run_id,
            engagement_id=GOVERNANCE_SCOPE,
        )
        request = LLMRequest(
            pin=self.pin(),
            system="\n\n".join(
                [
                    INSTRUCTIONS,
                    "## The skill contract requires\n"
                    + "\n".join(f"- {key}" for key in REQUIRED_FRONTMATTER),
                    "## Tools that may be declared\n"
                    + "\n".join(f"- {name}" for name in sorted(self.constraints.tools)),
                    "## Gaps to fill\n" + "\n".join(f"- {g.line()}" for g in report.gaps),
                ]
            ),
            messages=(Message("user", wrapped.text),),
            metadata={"node": NODE, "candidate": report.candidate_id},
        )
        call = self.door.send(
            request,
            IdentifierList(engagement_id=GOVERNANCE_SCOPE, identifiers=()),
            run_id or self.run_id,
            step_id=NODE,
            estimated_cost_usd=0.05,
        )
        body = _parse(call.response.text)
        adapted = self._shape(report, body)
        ref = put_json(self.blobs, {"frontmatter": adapted.frontmatter, "body": adapted.body,
                                    "fixture_request": adapted.fixture_request.__dict__},
                       name=f"adapted:{report.candidate_id}")
        self.record.append(
            report.candidate_id,
            Stage.ADAPTED,
            actor=proposed_by,
            ref=ref.content_hash,
            detail={
                "node": NODE,
                "name": adapted.name,
                "version": adapted.version,
                "layer": adapted.layer,
                "scope_reasoning": adapted.scope_reasoning,
                "fixture_request": adapted.fixture_request.line(),
                "request_hash": call.request_hash,
            },
        )
        return Adapted(**{**adapted.__dict__, "ref": ref.content_hash})

    # -- what comes back, checked before it is anything

    def _shape(self, report: GapReport, body: dict[str, Any]) -> Adapted:
        frontmatter = body.get("frontmatter")
        if not isinstance(frontmatter, dict):
            _refuse(report.candidate_id, "the bench returned no frontmatter object")
        request = body.get("fixture_request")
        if not isinstance(request, dict) or not str(request.get("what", "")).strip():
            _refuse(
                report.candidate_id,
                "the bench returned no fixture request. A conforming skill with no request "
                "for evidence is the one output this node may never produce",
            )
        for tool in frontmatter.get("tools") or ():
            if str(tool) not in self.constraints.tools:
                _refuse(
                    report.candidate_id,
                    f"the bench declared {tool!r}, which is not in the constraint "
                    f"registry's namespace",
                )
        missing = [k for k in REQUIRED_FRONTMATTER if not frontmatter.get(k)]
        if missing:
            _refuse(
                report.candidate_id,
                f"the adapted draft still has no {', '.join(missing)}; it does not conform "
                f"and does not move on",
            )
        return Adapted(
            candidate_id=report.candidate_id,
            name=str(frontmatter["name"]),
            version=str(frontmatter["version"]),
            layer=str(frontmatter["scope"]),
            frontmatter=frontmatter,
            body=str(body.get("body", "")),
            scope_reasoning=str(body.get("scope_reasoning", "")),
            fixture_request=FixtureRequest(
                what=str(request["what"]),
                how_many=str(request.get("how_many", "")),
                who=str(request.get("who", "")),
            ),
        )


def _refuse(candidate_id: str, detail: str) -> NoReturn:
    raise RegistryError(diagnose(SKILL_INVALID, detail, locator=candidate_id))


def _parse(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("the bench returned no JSON object")
    body = json.loads(text[start : end + 1])
    if not isinstance(body, dict):
        raise ValueError("the bench's answer is not an object")
    return body
