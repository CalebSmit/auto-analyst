"""P116 - the four keys the API does not take.

Every live model call this build would make carried
`metadata={run_id, context_ref, step_id, skill}`. The Messages API's `metadata` object
accepts exactly one key, `user_id`, and rejects anything else with a 400 — the installed
SDK's own `MetadataParam` declares `user_id` and nothing else.

So on a machine with a real key, the first call fails. And it fails as
`MODEL_PIN_UNAVAILABLE`, reading *"claude-sonnet-5: ..."*, which sends whoever reads it to
the model registry to debug a model that was never missing.

This module had already learned that exact lesson once. The comment above `_TOO_LONG`
records it: a scan nobody could shrink reported itself as *"claude-opus-5 is
unavailable"*. The lesson was applied to one phrase rather than to the shape of the
problem, so the next 400 that was not about a model made the same wrong turn.

Nothing caught it because every test in this build answers from a fixture or a stand-in.
No request it sends has ever reached the API.
"""

from __future__ import annotations

import inspect
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from ports.llm import LLMRequest, Message, ModelPin
from ports.llm.anthropic_messages import AnthropicMessagesLLM, _refused_a_field
from registries.errors import MODEL_PIN_UNAVAILABLE, PROVIDER_REFUSED_A_FIELD, RegistryError

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "ports" / "llm" / "anthropic_messages.py"


def a_request(**over: Any) -> LLMRequest:
    fields: dict[str, Any] = {
        "pin": ModelPin(model="claude-sonnet-5", effort="high"),
        "system": "you are a careful analyst",
        "messages": (Message("user", "{}"),),
        "metadata": {
            "run_id": "run_1",
            "context_ref": "sha256:" + "a" * 64,
            "step_id": "timing",
            "skill": "timing-normalization@0.1.0",
        },
    }
    fields.update(over)
    return LLMRequest(**fields)


class Recorder:
    """Stands in for the SDK client and keeps the call it was given."""

    def __init__(self, raises: BaseException | None = None) -> None:
        self.kwargs: dict[str, Any] = {}
        self.raises = raises
        self.messages = self

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.raises is not None:
            raise self.raises
        block = type("B", (), {"type": "text", "text": "{}"})()
        usage = type("U", (), {"input_tokens": 1, "output_tokens": 1})()
        return type("R", (), {"content": [block], "usage": usage, "stop_reason": "end_turn"})()


def sent(request: LLMRequest, raises: BaseException | None = None) -> Recorder:
    """The kwargs the adapter would put on the wire, without a key or a network."""
    adapter = AnthropicMessagesLLM()
    recorder = Recorder(raises)
    adapter._client = recorder  # noqa: SLF001
    with suppress(Exception):  # the refusal tests inspect the raise themselves
        adapter.complete(request)
    return recorder


# ============================================================ what goes on the wire


def test_nothing_this_build_invented_is_sent_as_metadata() -> None:
    """The bug, named. Four keys, none of them `user_id`, every one rejected."""
    assert "metadata" not in sent(a_request()).kwargs


def test_every_field_sent_is_one_the_sdk_declares() -> None:
    """The general form, so the next field added is checked rather than assumed. The SDK
    is generated from the API's own spec, so its signature is the closest thing to the
    provider's answer that exists on this machine."""
    from anthropic.resources.messages import Messages

    takes = set(inspect.signature(Messages.create).parameters) - {"self"}
    for name in sent(a_request()).kwargs:
        assert name in takes, f"{name!r} is not a parameter the Messages API declares"


def test_the_request_still_carries_what_the_call_is_for() -> None:
    """Dropping a field must not quietly drop the call. Model, messages, system, the
    thinking configuration and the effort from the pin all still go."""
    kwargs = sent(a_request()).kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {"effort": "high"}
    assert kwargs["messages"] and kwargs["system"]


def test_stop_sequences_still_go_when_there_are_some() -> None:
    kwargs = sent(a_request(stop_sequences=("STOP",))).kwargs
    assert kwargs["stop_sequences"] == ["STOP"]


def test_the_metadata_the_api_takes_is_not_invented_either() -> None:
    """`user_id` is the one key it accepts, and this build has no user identifier to
    send. Sending the engagement or the client as one would be putting a name in front of
    the provider to no purpose."""
    # Asked of the call rather than of the file: the comment above the fix names the key
    # precisely because the key is the point, and a grep over the source would be a test
    # that a comment stays unwritten.
    kwargs = sent(a_request()).kwargs
    assert "user_id" not in kwargs
    assert not any("user" in str(v).lower() for v in kwargs.get("metadata", {}).values())


# ============================================================ the internal metadata lives


def test_the_stand_ins_still_route_by_skill() -> None:
    """`LLMRequest.metadata` is this build's own routing, not the provider's: the fake
    adapter keys fixtures on it and the scripted analyst reads `skill` from it. Dropping
    it from the request object would have broken every rehearsal."""
    from ports.llm.scripted import ScriptedAnalyst

    answered = ScriptedAnalyst().complete(a_request(messages=(Message("user", '{"files": []}'),)))
    assert "timing-normalization@0.1.0" in answered.text


def test_the_request_still_carries_it() -> None:
    assert a_request().metadata["skill"] == "timing-normalization@0.1.0"


# ============================================================ what a refusal says


def test_a_rejected_field_is_reported_as_a_field() -> None:
    """Not as a missing model. This is the whole second half of the phase: the message a
    person reads decides which of two completely different things they go and look at."""
    from anthropic import BadRequestError

    refused = BadRequestError.__new__(BadRequestError)
    Exception.__init__(refused, "metadata.run_id: Extra inputs are not permitted")
    adapter = AnthropicMessagesLLM()
    adapter._client = Recorder(refused)  # noqa: SLF001
    with pytest.raises(RegistryError) as raised:
        adapter.complete(a_request())
    assert raised.value.diagnostic.code == PROVIDER_REFUSED_A_FIELD
    assert "metadata.run_id" in str(raised.value)
    assert "is fine and is not the problem" in str(raised.value)
    # The locator too: it is what the console links on, so a refusal that named the field
    # in prose and left the locator empty would be findable by reading and not by clicking.
    assert raised.value.diagnostic.locator == "metadata.run_id"


def test_a_missing_model_is_still_reported_as_a_missing_model() -> None:
    """The case the old branch was right about. Widening a classification until it
    swallows its neighbour is the failure this phase is fixing, not the fix."""
    from anthropic import NotFoundError

    missing = NotFoundError.__new__(NotFoundError)
    Exception.__init__(missing, "model: claude-nonesuch not_found_error")
    adapter = AnthropicMessagesLLM()
    adapter._client = Recorder(missing)  # noqa: SLF001
    with pytest.raises(RegistryError) as raised:
        adapter.complete(a_request())
    assert raised.value.diagnostic.code == MODEL_PIN_UNAVAILABLE


def test_a_length_refusal_is_still_a_length_refusal() -> None:
    """Length is checked first and stays first: it is a statement about the request and
    the ceiling, and the two orderings would disagree on a 400 that said both."""
    from anthropic import BadRequestError

    long = BadRequestError.__new__(BadRequestError)
    Exception.__init__(long, "prompt is too long: 300000 tokens")
    adapter = AnthropicMessagesLLM()
    adapter._client = Recorder(long)  # noqa: SLF001
    from registries.errors import CONTEXT_TOO_LARGE

    with pytest.raises(RegistryError) as raised:
        adapter.complete(a_request())
    assert raised.value.diagnostic.code == CONTEXT_TOO_LARGE


@pytest.mark.parametrize(
    "said,expected",
    [
        ("metadata.run_id: Extra inputs are not permitted", "metadata.run_id"),
        ("thinking: Unsupported parameter for this model", "thinking"),
        ("output_config: Input should be a valid dictionary", "output_config"),
        ("Unrecognized request argument supplied: widget", "a field in the request"),
        ("model claude-nonesuch not found", ""),
        ("prompt is too long", ""),
    ],
)
def test_the_field_is_dug_out_of_the_message(said: str, expected: str) -> None:
    """Named where the provider names it. "The provider rejected a field" without saying
    which one is the same unhelpful answer as blaming the model, differently unhelpful -
    and when the phrasing changes, the fallback is still truer than the old one."""

    class Said(Exception):
        pass

    assert _refused_a_field(Said(said)) == expected


def test_the_code_tells_whoever_reads_it_not_to_touch_the_pin() -> None:
    """The remedy is the point of having a code at all. A person who changes the model
    because of this has made the build worse and fixed nothing."""
    from registries.errors import WHAT_NOW

    owner, remedy = WHAT_NOW[PROVIDER_REFUSED_A_FIELD]
    assert owner == "system", "this build's mistake, not a configuration one"
    assert "do not change it" in remedy.lower()
