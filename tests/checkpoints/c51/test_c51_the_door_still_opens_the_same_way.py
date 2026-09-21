"""C51 - The door still opens the same way.

P83 refuses a call before it is made; P84 changes the shape of what is sent. Both act at
the one boundary in this build where a mistake leaves the repo, and the two interact:
P83's ceiling decides which calls happen at all, and P84's marker sits on the part of the
call P83 measures.

What each phase could not check about itself is here. P83's tests build contexts and P84's
send requests, and neither watched a real call go through both. A refusal that ate a legal
call and a marker that changed the question would each pass their own phase.

`test_the_content_that_reaches_the_port_is_byte_for_byte_what_it_was` is the one worth
having. Caching is a claim about billing and it must be nothing else: the same system
prompt, the same message, the same model, the same answer. If the marker ever changes what
the model is asked, the cheaper bill is the least of it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from ops.cost import CostMeter
from ports.llm import Message, Usage
from ports.llm.anthropic_messages import _is_too_long, _system
from privacy.payload_scan import ScanFailed
from registries.constraints import ConstraintRegistry
from registries.errors import CONTEXT_TOO_LARGE, MODEL_PIN_UNAVAILABLE, RegistryError
from tests.p11.conftest import masked_request

# ------------------------------------------------- the call is unchanged by the marker


def test_the_content_that_reaches_the_port_is_byte_for_byte_what_it_was(
    door: Any, port: Any, identifiers: Any, started: str
) -> None:
    """Through the real door, twice, differing only in whether the prefix may be cached.
    The port records what it was handed."""
    request = masked_request()
    door.send(request, identifiers, started, step_id="a", estimated_cost_usd=0.01)
    door.send(
        replace(request, cache_system=False), identifiers, started,
        step_id="b", estimated_cost_usd=0.01,
    )

    first, second = port.requests[-2], port.requests[-1]
    assert first.system == second.system
    assert [m.content for m in first.messages] == [m.content for m in second.messages]
    assert first.pin == second.pin
    assert first.max_tokens == second.max_tokens


def test_the_question_asked_is_the_same_question() -> None:
    """The content hash is what the idempotency key folds in and what the replay harness
    finds a recorded answer by. If caching moved it, a cached call and an uncached one
    would be two different questions and a resumed run could not reuse either."""
    request = masked_request()
    assert request.content_hash() == replace(request, cache_system=False).content_hash()


def test_only_the_system_prompt_carries_the_marker_at_the_wire() -> None:
    """Read at the adapter, which is where the shape is decided. The message holds the
    client's document and varies every call; a marker there writes a cache entry per
    document and reads none of them back."""
    request = masked_request()
    sent = _system(request)
    assert isinstance(sent, list)
    assert sent[0]["cache_control"] == {"type": "ephemeral"}
    for message in request.messages:
        assert message.content not in sent[0]["text"]


# ------------------------------------------------- the ceiling and the marker agree


def test_the_part_that_is_cached_is_inside_the_part_that_is_measured() -> None:
    """P83 measures the assembled context; P84 marks the system prompt. If the marker sat
    on something the ceiling did not count, a call could be refused for a size that
    excluded the largest cached block - or cached a block that was never weighed."""
    ceiling = ConstraintRegistry.load().context_ceiling()
    request = masked_request()
    assert len(_system(request)[0]["text"].encode("utf-8")) < ceiling


def test_a_refusal_before_the_call_costs_nothing(
    request_for: Any, tree: Any, blobs: Any, bus: Any, store: Any, port: Any
) -> None:
    """P83 refuses in the context builder, which runs before the door. Nothing reaches the
    port and nothing is metered - the difference between a refusal and a failed call.

    The first version of this compared two values captured either side of a comment and
    asserted they were equal, which they were, having done nothing in between. It passed
    for the same reason an empty test passes.
    """
    from harness.context import ContextBuilder

    line = b"Accounts receivable, net of allowance   1,482,113\n"
    payload = blobs.put(line * 12000, media_type="text/plain", name="masked_payload")

    before = len(port.requests)
    with pytest.raises(RegistryError):
        ContextBuilder(tree, blobs, bus, store).build(request_for(payload=payload))
    assert len(port.requests) == before, "a refused context still reached the model"


# ------------------------------------------------- and the two 400s stay apart


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("prompt is too long: 214253 tokens > 200000 maximum", CONTEXT_TOO_LARGE),
        ("Input is too long for requested model", CONTEXT_TOO_LARGE),
        ("model: claude-opus-7 not found", MODEL_PIN_UNAVAILABLE),
        ("The model `claude-sonnet-9` does not exist", MODEL_PIN_UNAVAILABLE),
    ],
)
def test_the_provider_s_two_refusals_reach_different_people(message: str, expected: str) -> None:
    """Both arrive as a 400 and this build used to read every one as a missing model. The
    two diagnostics have different owners, so getting it wrong sends the wrong person."""

    class BadRequestError(Exception):
        pass

    code = CONTEXT_TOO_LARGE if _is_too_long(BadRequestError(message)) else MODEL_PIN_UNAVAILABLE
    assert code == expected


def test_a_length_refusal_is_not_retried() -> None:
    """A 400 is never transient and a long request stays long. Retrying one spends the
    per-step retry budget on an answer that cannot change."""
    from ports.llm.anthropic_messages import _is_transient

    class BadRequestError(Exception):
        status_code = 400

    assert not _is_transient(BadRequestError("prompt is too long"))


# ------------------------------------------------- and the accounting still adds up


def test_a_cached_call_is_still_charged_against_the_run_s_ceiling(
    door: Any, port: Any, store: Any, identifiers: Any, started: str
) -> None:
    """A cache read is cheaper, not free, and it is still a token the run consumed. The
    governor's ceiling is in tokens, so folding cache reads out of the total would let a
    run exceed a ceiling by reading."""
    port.usage = Usage(input_tokens=10, output_tokens=5, cache_read_input_tokens=9000)
    before = CostMeter(store).spend(started).tokens
    door.send(masked_request(), identifiers, started, step_id="c", estimated_cost_usd=0.01)
    after = CostMeter(store).spend(started).tokens
    assert after - before >= 9000, "cache reads vanished from the run's token total"


def test_what_was_read_and_what_was_written_survive_to_the_breakdown(
    door: Any, port: Any, store: Any, identifiers: Any, started: str
) -> None:
    port.usage = Usage(input_tokens=10, output_tokens=5, cache_creation_input_tokens=2000)
    door.send(masked_request(), identifiers, started, step_id="d", estimated_cost_usd=0.01)
    port.usage = Usage(input_tokens=10, output_tokens=5, cache_read_input_tokens=6000)
    door.send(masked_request(), identifiers, started, step_id="e", estimated_cost_usd=0.01)

    breakdown = CostMeter(store).breakdown(started)
    assert breakdown.cache_write_tokens == 2000
    assert breakdown.cache_read_tokens == 6000
    assert breakdown.cache_hit_rate == 0.75


def test_a_run_with_no_caching_reports_no_rate_rather_than_a_bad_one(
    door: Any, port: Any, store: Any, identifiers: Any, started: str
) -> None:
    port.usage = Usage(input_tokens=100, output_tokens=20)
    door.send(masked_request(), identifiers, started, step_id="f", estimated_cost_usd=0.01)
    assert CostMeter(store).breakdown(started).cache_hit_rate is None


# ------------------------------------------------- and nothing else at the door moved


def test_the_door_still_refuses_a_second_turn(door: Any, identifiers: Any, started: str) -> None:
    """One model turn per invocation is a blueprint non-negotiable and both phases touched
    the request. A request carrying a conversation must still be refused."""
    two_turns = replace(
        masked_request(),
        messages=(Message("user", "one"), Message("assistant", "two"), Message("user", "three")),
    )
    with pytest.raises(Exception) as refused:  # noqa: B017 - the type is the door's
        door.send(two_turns, identifiers, started, step_id="g", estimated_cost_usd=0.01)
    assert "turn" in str(refused.value).lower()


def test_the_door_still_scans_what_it_sends(door: Any, identifiers: Any, started: str) -> None:
    """The payload scan is the guard between this build and a client's name reaching a
    model. P84 changed how the system prompt is packaged, so the scan must still be given
    it - the scan reads `request.system`, which is the string P84 now wraps in a block.

    Two versions of this passed for the wrong reason before it said anything true. The
    first used `pytest.raises(Exception)`, which caught whatever the door threw. The
    second named `ScanFailed` but leaked a name in a prompt that had also lost
    `[[CLIENT_1]]` - and the scan refuses text missing its expected tokens, so it raised
    for the missing token whether or not the system prompt was scanned at all.

    So the prompt below is well-formed: every expected token present, one real client name
    beside them. The only thing that can refuse it is the hit, and the hit is only found
    if the system prompt reaches the scan.
    """
    leaking = replace(
        masked_request(),
        system="You are tagging line items for [[CLIENT_1]]. Henderson Manufacturing pays.",
    )
    with pytest.raises(ScanFailed) as caught:
        door.send(leaking, identifiers, started, step_id="h", estimated_cost_usd=0.01)

    assert "Henderson Manufacturing" in caught.value.result.hits
    assert not caught.value.result.missing_tokens, (
        "refused for a missing token, which would happen with or without the system prompt"
    )


def test_a_context_that_fits_still_produces_a_context_ref(
    request_for: Any, tree: Any, blobs: Any, bus: Any, store: Any
) -> None:
    """P83's ceiling must not have made the ordinary path conditional. The builder is
    imported here rather than in p83 so the two phases are exercised in one process."""
    from harness.context import ContextBuilder

    built = ContextBuilder(tree, blobs, bus, store).build(request_for())
    assert built.context_ref.startswith("sha256:")
    assert built.sections


def test_an_oversized_context_names_the_document_and_stores_nothing(
    request_for: Any, tree: Any, blobs: Any, bus: Any, store: Any
) -> None:
    from harness.context import ContextBuilder

    line = b"Accounts receivable, net of allowance   1,482,113\n"
    payload = blobs.put(line * 12000, media_type="text/plain", name="masked_payload")
    with pytest.raises(RegistryError) as refused:
        ContextBuilder(tree, blobs, bus, store).build(request_for(payload=payload))
    assert refused.value.diagnostic.code == CONTEXT_TOO_LARGE
    assert "payload" in refused.value.diagnostic.detail
