"""The one door to a model.

Structurally the only way to reach a model. Everything the blueprint says happens "on
the way out" happens here, in this order, and none of it can be skipped by what a caller
passes:

    1. one turn - a request shaped like a second turn raises before it is sent
    2. the outbound payload scan - a hit stops the run, a pass is recorded
    3. the budget governor - is there room for this call
    4. the port - one request, one response
    5. the pin - the model that answered is the model that was pinned
    6. the meter - the usage the API reported, priced and written to the run

**max_turns == 1 is enforced here, not merely asserted in the plan.** The compiler and the
plan assertions refuse a step that *declares* more than one turn. This refuses a request
that *is* one: a conversation carrying a prior assistant message is turn two of something,
and it does not leave. A skill proposes; if it needs a tool result, that is another step.

A test walks the import graph and asserts that nothing outside this module calls
`.complete()` on a port. That is what "the only way" means in a codebase rather than in a
sentence.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.budget import BudgetGovernor
from ops.cost import Charge, CostMeter
from ops.events import EventBus
from ports.llm import LLMPort, LLMRequest, LLMResponse, ModelPin
from privacy.payload_scan import IdentifierList, PayloadScan
from registries.errors import MODEL_PIN_UNAVAILABLE, MULTI_TURN_STEP, RegistryError, diagnose

__all__ = ["ModelCall", "ModelDoor"]


@dataclass(frozen=True)
class ModelCall:
    """What came back, what it cost, and the request hash that names the call."""

    response: LLMResponse
    charge: Charge
    request_hash: str
    scan_checked: int


class ModelDoor:
    """Send one request to a model. There is no other method."""

    def __init__(
        self,
        port: LLMPort,
        scan: PayloadScan,
        governor: BudgetGovernor,
        meter: CostMeter,
        bus: EventBus,
    ) -> None:
        self.port = port
        self.scan = scan
        self.governor = governor
        self.meter = meter
        self.bus = bus

    def send(
        self,
        request: LLMRequest,
        identifiers: IdentifierList,
        run_id: str,
        step_id: str | None = None,
        estimated_cost_usd: float = 0.0,
    ) -> ModelCall:
        engagement_id = identifiers.engagement_id

        # 1. One turn.
        _require_single_turn(request, step_id)

        # 2. The scan, over everything that leaves: the system prompt and every message.
        # One scan, one event. The false positive this once produced - a client whose
        # name contains an ordinary word, quarantined on that word in the firm's own
        # skill text - is handled where the identifier list is built: a word the firm's
        # methodology uses is not treated as identifying on its own.
        outbound = "\n".join([request.system, *(m.content for m in request.messages)])
        scanned = self.scan.scan(outbound, identifiers, run_id=run_id, step_id=step_id)

        # 3. Room for it.
        self.governor.check(
            run_id,
            engagement_id,
            about_to_spend_usd=estimated_cost_usd,
            about_to_call=True,
            step_id=step_id,
        )

        # 4. The call.
        request_hash = request.content_hash()
        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id="llm_port",
            type="model.called",
            message=f"{request.pin} · {request_hash[:19]}",
            step_id=step_id,
            payload={"request_hash": request_hash, "pin": str(request.pin)},
        )
        response = self.port.complete(request)

        # 5. The pin held.
        _require_pin_held(request.pin, response)

        # 6. The meter, from the usage the API reported.
        charge = self.meter.record(run_id, request.pin, response.usage)
        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id="cost_meter",
            type="model.answered",
            message=f"{response.model}: ${charge.usd:.4f}",
            step_id=step_id,
            cost_usd=charge.usd,
            payload={
                "request_hash": request_hash,
                "model": response.model,
                "input_tokens": charge.input_tokens,
                "output_tokens": charge.output_tokens,
                # Split out rather than folded into input_tokens, which is what the run
                # store gets for its ceiling. The ceiling wants the total; a person asking
                # whether caching is doing anything wants the two apart, and the whole
                # point of turning it on is that the answer is measured rather than
                # assumed. A read is priced at a tenth of input and a write at 1.25x.
                "cache_read_tokens": charge.cache_read_tokens,
                "cache_write_tokens": charge.cache_write_tokens,
                "stop_reason": response.stop_reason,
            },
        )
        # After the call, too: this one may have been the one that crossed a line.
        self.governor.check(run_id, engagement_id, step_id=step_id)

        return ModelCall(
            response=response,
            charge=charge,
            request_hash=request_hash,
            scan_checked=scanned.checked,
        )


def _require_single_turn(request: LLMRequest, step_id: str | None) -> None:
    """A request is one turn iff it carries no assistant message and exactly one user
    message. Anything else is a conversation in progress, and a skill does not have one
    of those."""
    roles = [m.role for m in request.messages]
    if roles != ["user"]:
        raise RegistryError(
            diagnose(
                MULTI_TURN_STEP,
                f"the request carries {len(roles)} message(s) with roles {roles}; one turn "
                f"is exactly one user message and no assistant message. This is turn "
                f"{roles.count('assistant') + 1} of a conversation, and it does not leave.",
                locator=step_id or "model_door",
            )
        )


def _require_pin_held(pin: ModelPin, response: LLMResponse) -> None:
    if response.model and not response.model.startswith(pin.model):
        raise RegistryError(
            diagnose(
                MODEL_PIN_UNAVAILABLE,
                f"pinned {pin.model!r}, answered by {response.model!r}. A provider "
                f"substituting a model is the most common way reproducibility is lost "
                f"without anyone choosing it, and the answer is not used.",
                locator=pin.model,
            )
        )
