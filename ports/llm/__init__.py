"""The LLM Provider Port: one request, one response.

A skill invocation is one model turn. `max_turns == 1` is not a setting here, it is the
shape of the interface: there is a `complete()` and there is no loop, so a skill that
needs a tool result cannot get one by asking again - that is another step in the plan,
compiled, keyed and visible.

This is also the single choke point where the Outbound Payload Scan sits. Exactly one way
to reach a model means exactly one place to check what leaves and one place to record it.

Provider choice is configuration, not a rewrite: Bedrock or Vertex are adapters beside
the Anthropic one, and the Claude Agent SDK - if it is ever wanted - is an adapter too
rather than a dependency.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Role = Literal["user", "assistant"]
Effort = Literal["low", "medium", "high", "xhigh", "max"]


class TransportFailure(Exception):
    """The model could not be reached, or did not answer in time.

    The only kind of failure a retry is for. Deliberately not a `DiagnosticError`: it is an
    infrastructure hiccup on its way to becoming either a successful second attempt or a
    quarantine record, and only the ending carries a diagnostic.

    It lives here rather than beside the executor that catches it because the adapter is
    the only thing holding the provider's own exception, and `ports` sits below both
    `graph` and `harness` - so this is the one place both ends can see. It was declared
    beside the executor for a long time, which meant the adapter could not raise it, which
    meant nothing did: the retry loop, the `step.transport_failed` event and
    `PROCESS.TRANSPORT_EXHAUSTED` were all reachable only from a test.
    """

# The blueprint prices its tiers at $1/$5, $2/$10 and $5/$25 per MTok. Those are the
# current Haiku, Sonnet and Opus rates, so the tiers resolve as below. A tier is a
# budgeting decision made per skill; the pin recorded in the manifest is always the
# concrete model id, never the tier - "mid" six months from now is a different model.
TIER_MODELS: dict[str, str] = {
    "low": "claude-haiku-4-5",
    "mid": "claude-sonnet-5",
    "high": "claude-opus-5",
}

# USD per million tokens, (input, output), by concrete model. The cost meter prices
# usage from this table and nothing else, so "what did that step cost" is arithmetic over
# the usage the API reported rather than an estimate somebody made. Cache reads are
# priced at a tenth of input and cache writes at 1.25x, per the published rates.
RATES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
}
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25


@dataclass(frozen=True)
class ModelPin:
    """The exact model and effort a run is pinned to, for its whole life.

    A pinned model that is no longer available fails the run at startup rather than
    silently substituting a different one - a workfile that cannot say which model
    produced a figure is a workfile that cannot be defended.
    """

    model: str
    effort: Effort = "high"

    @classmethod
    def for_tier(cls, tier: str, effort: Effort = "high") -> ModelPin:
        if tier not in TIER_MODELS:
            raise ValueError(f"unknown tier {tier!r} - expected one of {sorted(TIER_MODELS)}")
        return cls(model=TIER_MODELS[tier], effort=effort)

    def __str__(self) -> str:
        """The form the figure envelope and the run manifest record."""
        return f"{self.model} @ effort={self.effort}"


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class LLMRequest:
    """Everything that goes to the model, assembled in one place and recorded.

    The Context Builder produces this and nothing else may. Any call can then be
    reconstructed exactly, which is what makes replay and eval possible at all.
    """

    pin: ModelPin
    system: str
    messages: tuple[Message, ...]
    max_tokens: int = 16000
    timeout_s: float | None = None
    """How long this call may take, from the step that asked for it.

    The plan has always declared one - `graph/execute.py` computes
    `min(step.timeout_s, the firm ceiling)` and puts it on the `Attempt` - and until P122
    nothing between there and the provider read it, so the bound in force was one the SDK
    computed from `max_tokens`. Deliberately not part of `content_hash`: how long a call
    was allowed to take is not what was asked, and two calls that differ only in patience
    are the same call for replay and for the ledger."""

    stop_sequences: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)
    """Non-content labels - run_id, step_id, skill. Never client data: this crosses the
    same boundary the payload scan guards."""
    cache_system: bool = True
    """Whether the system prompt may be cached by the provider.

    On the request rather than in the adapter, because which part of a call is stable is
    something the caller knows and the transport does not. Here it is stable by
    construction: the dispatcher's system prompt is a skill body plus the references that
    skill declares plus a constant rule, so two calls of one skill in one scope share it
    byte for byte, while everything that varies - the methodology, the precedents, the
    profile, the client's document - is in the message.

    It changes no content. The same bytes are sent either way; this only marks where the
    provider may stop re-reading them. A caller with a system prompt it has assembled
    per-call sets this False and pays full price, which is the right answer for one.
    """

    def content_hash(self) -> str:
        """Content address of the call. The idempotency key folds this in, so an
        identical call is never paid for twice, and the replay harness finds a recorded
        response by it."""
        canonical = json.dumps(
            {
                "model": self.pin.model,
                "effort": self.pin.effort,
                "system": self.system,
                "messages": [{"role": m.role, "content": m.content} for m in self.messages],
                "max_tokens": self.max_tokens,
                "stop_sequences": list(self.stop_sequences),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    """What actually answered. Compared against the pin - a provider substituting a
    model is the most common way reproducibility is lost without anyone choosing it."""

    stop_reason: str
    usage: Usage = field(default_factory=Usage)
    request_id: str = ""


@runtime_checkable
class LLMPort(Protocol):
    name: str

    def complete(self, request: LLMRequest) -> LLMResponse:
        """One turn. There is deliberately no other method."""
        ...
