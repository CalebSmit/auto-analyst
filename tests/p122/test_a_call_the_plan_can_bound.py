"""P122 - a call the plan can bound, and no loop the graph does not own.

Two things the plan declared and nothing enforced, both of which decide what happens when
a call is slow.

**The timeout.** Every step carries `timeout_s`; `graph/execute.py` computes
`min(step.timeout_s, the firm ceiling)` and puts it on the `Attempt`. Nothing between
there and the provider read it, so the bound actually in force was one the SDK computed
from `max_tokens`.

**The retries.** The SDK was constructed with its default `max_retries=2`, and those two
sit *inside* a step the executor will itself retry. One step could make six HTTP attempts
while the run's own count said one. That is not a tuning preference: *the graph owns every
loop*, declared with an integer maximum the compiler checks, and a retry the transport
performs is a loop nothing counts and nothing can see.

Worst case on a slow night was an hour inside a single step, with nothing in the event
stream to say so.
"""

from __future__ import annotations

import ast
import inspect
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from ports.llm import LLMRequest, Message, ModelPin
from ports.llm.anthropic_messages import AnthropicMessagesLLM

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "ports" / "llm" / "anthropic_messages.py"


class Recorder:
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


def a_request(**over: Any) -> LLMRequest:
    fields: dict[str, Any] = {
        "pin": ModelPin(model="claude-sonnet-5", effort="high"),
        "system": "s",
        "messages": (Message("user", "{}"),),
    }
    fields.update(over)
    return LLMRequest(**fields)


def sent(request: LLMRequest, raises: BaseException | None = None) -> Recorder:
    adapter = AnthropicMessagesLLM()
    recorder = Recorder(raises)
    adapter._client = recorder  # noqa: SLF001
    with suppress(Exception):
        adapter.complete(request)
    return recorder


# ============================================================ the bound reaches the call


def test_the_step_s_timeout_is_what_bounds_the_call() -> None:
    assert sent(a_request(timeout_s=300.0)).kwargs["timeout"] == 300.0


def test_a_request_with_no_bound_leaves_the_sdk_to_it() -> None:
    """Rather than sending `None`, which would mean *no* timeout - the dangerous reading.
    The SDK computes one from `max_tokens` when it is not told, which is a worse bound
    than the plan's and a far better one than none."""
    assert "timeout" not in sent(a_request()).kwargs


def test_zero_is_not_read_as_no_timeout() -> None:
    """A step that somehow declared zero would otherwise send `timeout=0` and fail every
    call instantly, or be dropped and mean forever depending on the reading."""
    assert "timeout" not in sent(a_request(timeout_s=0)).kwargs


# ============================================================ the plumbing it came down


def test_the_request_carries_it() -> None:
    assert a_request(timeout_s=12.5).timeout_s == 12.5


def test_it_is_not_part_of_what_the_call_is() -> None:
    """How long a call was allowed to take is not what was asked. Two calls that differ
    only in patience are the same call for replay, for the ledger and for the idempotency
    key - and if this entered the hash, a re-run under a different ceiling would pay for
    a response it already had."""
    assert a_request(timeout_s=30).content_hash() == a_request(timeout_s=600).content_hash()


def test_the_runner_hands_over_the_attempt_s_own_bound() -> None:
    """Not the step's declared one. The executor takes the smaller of the step's and the
    firm ceiling, and the smaller is the one in force."""
    source = (ROOT / "harness" / "runner.py").read_text(encoding="utf-8")
    assert "timeout_s=float(attempt.timeout_s)," in source


def test_the_dispatcher_puts_it_on_the_request(world: Any, model_step: Any, scope: Any) -> None:
    """Through the real dispatcher, onto the real request, recorded by the port that
    stands in for the provider. A signature check would have passed with the argument
    accepted and dropped."""
    from harness.dispatch import SkillDispatcher
    from tests.p21.conftest import ProposalPort, dispatch

    assert "timeout_s" in inspect.signature(SkillDispatcher.run).parameters
    port = ProposalPort(world["proposal"])
    dispatch(world, model_step, scope, port, timeout_s=97.0)
    assert port.requests and port.requests[0].timeout_s == 97.0


def test_the_executor_still_takes_the_smaller_of_the_two() -> None:
    """Unchanged, and the reason the value handed down is worth trusting."""
    source = (ROOT / "graph" / "execute.py").read_text(encoding="utf-8")
    assert 'timeout = min(step.timeout_s, int(self._ceilings["timeout_s"]))' in source


# ============================================================ no loop the graph cannot see


def test_the_transport_retries_nothing() -> None:
    """*The graph owns every loop.* The SDK's default is two attempts inside a step the
    executor will retry, so one step could make six HTTP calls while the run's own count
    said one."""
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Anthropic"
    ]
    assert calls, "the adapter no longer constructs a client"
    for call in calls:
        given = {kw.arg: kw.value for kw in call.keywords}
        retries = given.get("max_retries")
        assert isinstance(retries, ast.Constant) and retries.value == 0, (
            "the transport must not retry inside a step"
        )


def test_the_executor_is_the_one_that_retries() -> None:
    """And it is capped by a declared ceiling, which is what makes the count checkable."""
    source = (ROOT / "graph" / "execute.py").read_text(encoding="utf-8")
    assert 'allowed = min(step.retries, int(self._ceilings["transport_retries_max"]))' in source


# ============================================================ what a slow call becomes


def test_a_timeout_is_a_transport_failure() -> None:
    """So the graph retries it by its own count, rather than the adapter turning a slow
    night into a refusal about the model."""
    from ports.llm import TransportFailure

    timed_out = type("APITimeoutError", (Exception,), {})()
    adapter = AnthropicMessagesLLM()
    adapter._client = Recorder(timed_out)  # noqa: SLF001
    with pytest.raises(TransportFailure):
        adapter.complete(a_request(timeout_s=1))


def test_and_is_not_mistaken_for_a_missing_model() -> None:
    """The failure this module keeps having: a 400 or a hiccup reported as a model that
    was never missing."""
    from registries.errors import RegistryError

    timed_out = type("APITimeoutError", (Exception,), {})()
    adapter = AnthropicMessagesLLM()
    adapter._client = Recorder(timed_out)  # noqa: SLF001
    with pytest.raises(Exception) as raised:  # noqa: B017, PT011
        adapter.complete(a_request(timeout_s=1))
    assert not isinstance(raised.value, RegistryError)


@pytest.mark.parametrize("name", ["APIConnectionError", "RateLimitError", "InternalServerError"])
def test_the_other_hiccups_are_still_worth_another_attempt(name: str) -> None:
    """Dropping the SDK's retries must not mean nothing is retried - it means the graph
    does the retrying, and it only does it for the failures that are worth it."""
    from ports.llm import TransportFailure

    adapter = AnthropicMessagesLLM()
    adapter._client = Recorder(type(name, (Exception,), {})())  # noqa: SLF001
    with pytest.raises(TransportFailure):
        adapter.complete(a_request())


def test_a_refusal_is_still_a_refusal_and_is_not_retried() -> None:
    """A 4xx is understood and rejected; sending it again produces the same answer more
    slowly. That distinction is what makes dropping the transport's blind retries safe."""
    from registries.errors import RegistryError

    refused = type("BadRequestError", (Exception,), {})()
    Exception.__init__(refused, "metadata.run_id: Extra inputs are not permitted")
    adapter = AnthropicMessagesLLM()
    adapter._client = Recorder(refused)  # noqa: SLF001
    with pytest.raises(RegistryError):
        adapter.complete(a_request())
