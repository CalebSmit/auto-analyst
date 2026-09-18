"""LLM adapter: the Anthropic Messages API.

One request, one response, adaptive thinking, effort from the pin. The SDK import is
deferred to the first call so that importing this module - which the adapter registry
does when listing what exists - never requires the package or a credential.

The API key comes through the Secrets Port, not from os.environ. That is the whole
reason the secrets port exists on day one: at handoff, moving to the firm's Anthropic
account is a .env change and nothing else.
"""

from __future__ import annotations

from typing import Any

from ports.llm import LLMRequest, LLMResponse, TransportFailure, Usage
from ports.secrets import SecretsPort
from registries.errors import MISSING_CREDENTIAL, MODEL_PIN_UNAVAILABLE, RegistryError, diagnose

API_KEY = "ANTHROPIC_API_KEY"

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
                system=request.system,
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                thinking={"type": "adaptive"},
                output_config={"effort": request.pin.effort},
                **({"stop_sequences": list(request.stop_sequences)}
                   if request.stop_sequences else {}),
                **({"metadata": request.metadata} if request.metadata else {}),
            )
        except Exception as exc:  # noqa: BLE001 - re-raised as a diagnostic below
            if type(exc).__name__ in {"NotFoundError", "BadRequestError"}:
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
        self._client = anthropic.Anthropic(api_key=str(secrets.get(API_KEY)))
        return self._client


def build() -> AnthropicMessagesLLM:
    return AnthropicMessagesLLM()
