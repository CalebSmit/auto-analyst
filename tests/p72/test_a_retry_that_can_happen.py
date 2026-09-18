"""P72: a retry that can happen.

`TransportFailure` is described in the executor as the only kind of failure a retry is
for. The executor catches it, emits `step.transport_failed` on it, and ends a run with
`PROCESS.TRANSPORT_EXHAUSTED` when the attempts run out. Every shipped recipe declares
`retries`.

None of it had ever run. The class was declared beside the executor, which meant the
adapter could not raise it without `ports` importing `graph`; so the adapter translated
`NotFoundError` and `BadRequestError` and re-raised everything else unchanged. A
connection error, a timeout, a 429 or a 500 went to the executor's general handler and
quarantined the step on its first attempt.

No rehearsal could have found this: the fake and scripted adapters have no network. It
came from extending P71's scan from functions to exception classes - the shape P55 found
by hand, where `RepairNeeded` was raised in exactly one place and that place was a test
double.

The load-bearing pair is `test_a_connection_error_becomes_a_transport_failure` and
`test_a_bad_request_is_not_retried`. Either alone is satisfied by a rule that is wrong in
the other direction - retry everything, or retry nothing.
"""

from __future__ import annotations

import pytest

from ports.llm import TransportFailure
from ports.llm.anthropic_messages import AnthropicMessagesLLM, _is_transient
from registries.errors import RegistryError


class FakeSDKError(Exception):
    """An SDK exception, named as the real ones are. The adapter reads the class name so
    that listing adapters still does not need the SDK installed."""

    def __init__(self, name: str, status: int | None = None) -> None:
        super().__init__(f"{name} happened")
        self.__class__ = type(name, (FakeSDKError,), {})  # type: ignore[misc]
        if status is not None:
            self.status_code = status


def erroring(exc: BaseException) -> AnthropicMessagesLLM:
    """An adapter whose client raises `exc` on every call."""

    class Messages:
        @staticmethod
        def create(**_: object) -> object:
            raise exc

    class Client:
        messages = Messages()

    port = AnthropicMessagesLLM()
    port._client = Client()  # noqa: SLF001 - standing in for a connected client
    return port


def request() -> object:
    from ports.llm import LLMRequest, Message, ModelPin

    return LLMRequest(
        system="s",
        messages=(Message(role="user", content="c"),),
        pin=ModelPin(model="claude-sonnet-5", effort="high"),
        max_tokens=16,
    )


# ------------------------------------------------------------------ what is transient


@pytest.mark.parametrize(
    "name",
    ["APIConnectionError", "APITimeoutError", "RateLimitError", "InternalServerError",
     "ServiceUnavailableError", "OverloadedError"],
)
def test_the_failures_a_second_attempt_might_fix(name: str) -> None:
    assert _is_transient(FakeSDKError(name))


def test_a_server_error_with_no_class_of_its_own_is_still_transient() -> None:
    """A 5xx the SDK has not named is still the server's problem."""
    assert _is_transient(FakeSDKError("SomeNewError", status=503))


@pytest.mark.parametrize("status", [400, 401, 403, 404, 418, 422])
def test_a_client_error_is_never_transient(status: int) -> None:
    """The request was understood and rejected. Sending it again produces the same answer
    more slowly."""
    assert not _is_transient(FakeSDKError("SomeClientError", status=status))


def test_an_unrelated_exception_is_not_transient() -> None:
    assert not _is_transient(ValueError("nothing to do with transport"))


# ------------------------------------------------------------------ through the adapter


def test_a_connection_error_becomes_a_transport_failure() -> None:
    """The point of the phase: this is what the executor's retry loop waits for, and what
    it never received."""
    port = erroring(FakeSDKError("APIConnectionError"))
    with pytest.raises(TransportFailure) as raised:
        port.complete(request())  # type: ignore[arg-type]
    assert "APIConnectionError" in str(raised.value)


def test_a_rate_limit_becomes_a_transport_failure() -> None:
    port = erroring(FakeSDKError("RateLimitError"))
    with pytest.raises(TransportFailure):
        port.complete(request())  # type: ignore[arg-type]


def test_a_server_error_becomes_a_transport_failure() -> None:
    port = erroring(FakeSDKError("SomethingElse", status=500))
    with pytest.raises(TransportFailure):
        port.complete(request())  # type: ignore[arg-type]


def test_a_bad_request_is_not_retried() -> None:
    """The other side. A rule that retries everything would turn a permanent refusal into
    the same refusal several times, and hide it behind the retry count."""
    port = erroring(FakeSDKError("BadRequestError"))
    with pytest.raises(RegistryError) as raised:
        port.complete(request())  # type: ignore[arg-type]
    assert "MODEL_PIN" in str(raised.value) or "claude-sonnet-5" in str(raised.value)


def test_an_unknown_model_still_names_the_pin() -> None:
    port = erroring(FakeSDKError("NotFoundError"))
    with pytest.raises(RegistryError):
        port.complete(request())  # type: ignore[arg-type]


def test_an_unexpected_error_is_left_alone() -> None:
    """Not everything is transport. An error this adapter does not recognise keeps its own
    type, so it reaches the executor as the ending it is rather than as a retry."""
    port = erroring(ValueError("something else entirely"))
    with pytest.raises(ValueError):
        port.complete(request())  # type: ignore[arg-type]


# ------------------------------------------------------------------ and the seam is joined


def test_the_executor_catches_the_type_the_port_raises() -> None:
    """The defect was two declarations of the same idea that could never meet: the class
    beside the executor, the exception in the adapter's hand, and `ports` below `graph` so
    the adapter could not name it. One class now, seen from both ends."""
    from graph.execute import TransportFailure as CaughtByExecutor

    assert CaughtByExecutor is TransportFailure


def test_the_port_owns_it_so_an_adapter_can_raise_it() -> None:
    assert TransportFailure.__module__ == "ports.llm"
