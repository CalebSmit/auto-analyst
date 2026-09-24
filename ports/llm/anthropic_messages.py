"""LLM adapter: the Anthropic Messages API.

One request, one response, adaptive thinking, effort from the pin. The SDK import is
deferred to the first call so that importing this module - which the adapter registry
does when listing what exists - never requires the package or a credential.

The API key comes through the Secrets Port, not from os.environ. That is the whole
reason the secrets port exists on day one: at handoff, moving to the firm's Anthropic
account is a .env change and nothing else.
"""

from __future__ import annotations

import re
from typing import Any

from ports.llm import LLMRequest, LLMResponse, TransportFailure, Usage
from ports.secrets import SecretsPort
from registries.errors import (
    CONTEXT_TOO_LARGE,
    MISSING_CREDENTIAL,
    MODEL_PIN_UNAVAILABLE,
    PROVIDER_REFUSED_A_FIELD,
    RegistryError,
    diagnose,
)

API_KEY = "ANTHROPIC_API_KEY"

CREDENTIALS = (API_KEY,)
"""What this adapter needs from the Secrets Port, declared for `ports.credentials_for`.

One name, and it is still declared here rather than known by the caller: nothing outside
`ports/` may name a concrete adapter module, so a connection test that hard-coded
`ANTHROPIC_API_KEY` would be importing this file by another route. The Box three already
went stale once that way."""

# What a second attempt might fix. Named rather than imported, so that listing adapters
# still does not need the SDK - the same reason `_connect` defers its import.
#
# `APITimeoutError` subclasses `APIConnectionError` in the SDK, and both are named anyway:
# a subclass relationship is the SDK's to change, and this list is a statement about which
# failures are worth retrying rather than about its class tree.
_TRANSIENT = frozenset(
    {
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
        "ServiceUnavailableError",
        "OverloadedError",
    }
)


# What the provider says when the request was too long rather than the model wrong. Both
# arrive as a 400 and this build used to read every 400 as a missing model - so a scan
# nobody could shrink reported itself as "claude-opus-5 is unavailable" and sent whoever
# read it to the model registry. Matched on the text because the SDK gives both the same
# class, and kept broad on purpose: a phrase that stops matching costs the old wrong
# answer, so the test below holds the real message shapes.
_TOO_LONG = ("prompt is too long", "context length", "context_length", "too many tokens",
             "maximum context", "exceeds the maximum", "input is too long")


# What the provider says when the request's *shape* is wrong rather than its model or its
# length. Pydantic phrasings first, because that is what the API answers with, then the
# plainer ones. Every entry is a phrase about a field, never about a model.
_REFUSED_A_FIELD = (
    "extra inputs are not permitted",
    "unexpected keyword",
    "unrecognized request argument",
    "field required",
    "input should be",
    "is not supported by",
    "unsupported parameter",
    "invalid request argument",
)

# Where in the message the field's own name tends to sit: `metadata.run_id: Extra inputs`.
_FIELD_NAME = re.compile(
    r"['\"]?([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*)['\"]?"
    r"\s*:\s*(?:Extra|Field|Input|Unsupported)"
)


def _refused_a_field(exc: BaseException) -> str:
    """The field the provider rejected, or an empty string if this is not that.

    The name is dug out of the message rather than guessed, because "the provider
    rejected a field" without saying which one is the same unhelpful answer as blaming
    the model - just differently unhelpful. When the phrasing changes and the name
    cannot be found, "a field in the request" is still a truer sentence than "the model
    is unavailable".
    """
    said = str(exc)
    if not any(phrase in said.lower() for phrase in _REFUSED_A_FIELD):
        return ""
    found = _FIELD_NAME.search(said)
    return found.group(1) if found else "a field in the request"


def _is_too_long(exc: BaseException) -> bool:
    said = str(exc).lower()
    return any(phrase in said for phrase in _TOO_LONG)


def _system(request: LLMRequest) -> Any:
    """The system prompt, marked cacheable when the caller says it is stable.

    A plain string when it is not, because that is what the API took before any of this
    and a request that opts out should look exactly as it did. The marker changes no
    content: the same bytes go either way, and a prefix the provider has not seen before
    is simply written to cache and charged as a write - there is no miss to lose.
    """
    if not request.cache_system:
        return request.system
    return [
        {
            "type": "text",
            "text": request.system,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _is_transient(exc: BaseException) -> bool:
    """Whether this is an infrastructure hiccup rather than a refusal.

    By name, and then by status: a 5xx the SDK has no dedicated class for is still the
    server's problem and still worth another attempt. A 4xx never is - the request was
    understood and rejected, and sending it again produces the same answer more slowly.
    429 is the exception and is named above, because a rate limit *is* a wait.
    """
    if type(exc).__name__ in _TRANSIENT:
        return True
    status = getattr(exc, "status_code", None)
    return isinstance(status, int) and status >= 500



class AnthropicMessagesLLM:
    name = "anthropic_messages"

    def __init__(self, secrets: SecretsPort | None = None) -> None:
        self._secrets = secrets
        self._client: Any = None

    def __repr__(self) -> str:
        return f"AnthropicMessagesLLM(connected={self._client is not None})"

    def complete(self, request: LLMRequest) -> LLMResponse:
        client = self._connect()
        try:
            response = client.messages.create(
                model=request.pin.model,
                max_tokens=request.max_tokens,
                system=_system(request),
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                thinking={"type": "adaptive"},
                output_config={"effort": request.pin.effort},
                **({"stop_sequences": list(request.stop_sequences)}
                   if request.stop_sequences else {}),
                # The step's own bound, not the SDK's guess from `max_tokens`. Without it
                # a slow night could spend an hour inside one step that declared five
                # minutes, with nothing in the event stream saying so.
                **({"timeout": request.timeout_s} if request.timeout_s else {}),
            )
        except Exception as exc:  # noqa: BLE001 - re-raised as a diagnostic below
            if type(exc).__name__ in {"NotFoundError", "BadRequestError"}:
                # Length first: a 400 about length is not a statement about the model, and
                # the ceiling in constraints.yaml is deliberately below the provider's, so
                # reaching here at all means the two disagree and the provider's is lower.
                if _is_too_long(exc):
                    raise RegistryError(
                        diagnose(
                            CONTEXT_TOO_LARGE,
                            f"{request.pin.model} refused the request as too long: {exc}",
                            locator=request.pin.model,
                        )
                    ) from exc
                # Then a field: a 400 about the shape of the request is this build's
                # mistake and says nothing about the model. Reporting it as a missing pin
                # sends whoever reads it to the model registry to debug a model that was
                # never missing - which is the same wrong turn the length case above was
                # written to stop, and it happened again. Every call this build would have
                # made carried four keys in `metadata`, where the API takes only `user_id`.
                refused = _refused_a_field(exc)
                if refused:
                    raise RegistryError(
                        diagnose(
                            PROVIDER_REFUSED_A_FIELD,
                            f"the provider rejected {refused} in the request - the model "
                            f"pin {request.pin.model} is fine and is not the problem: {exc}",
                            locator=refused,
                        )
                    ) from exc
                raise RegistryError(
                    diagnose(MODEL_PIN_UNAVAILABLE, f"{request.pin.model}: {exc}")
                ) from exc
            if _is_transient(exc):
                raise TransportFailure(f"{type(exc).__name__}: {exc}") from exc
            raise

        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        usage = response.usage
        return LLMResponse(
            text=text,
            model=response.model,
            stop_reason=response.stop_reason or "",
            usage=Usage(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            ),
            request_id=getattr(response, "_request_id", "") or "",
        )

    def _connect(self) -> Any:
        if self._client is not None:
            return self._client
        import anthropic  # deferred: listing adapters must not need the SDK

        secrets = self._secrets
        if secrets is None:
            from ports import get_secrets

            secrets = get_secrets()
        if not secrets.has(API_KEY):
            raise RegistryError(
                diagnose(MISSING_CREDENTIAL, f"{API_KEY} is not set")
            )
        # `max_retries=0`: **the graph owns every loop.** The SDK's default is two, and
        # those two sit inside a step the executor will itself retry - so one step could
        # make six HTTP attempts while the run's own count said one, which is a loop
        # nothing declared and nothing could count. The executor's `retries`, capped by
        # `transport_retries_max`, is now the whole of the retry policy.
        self._client = anthropic.Anthropic(
            api_key=str(secrets.get(API_KEY)), max_retries=0
        )
        return self._client


def build() -> AnthropicMessagesLLM:
    return AnthropicMessagesLLM()
