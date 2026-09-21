"""P83: a context that says when it will not fit.

Every document this firm receives is a multi-page scan, and nothing measured the assembled
context before sending it. Over the provider's input limit the SDK raises a 400, and
`ports/llm/anthropic_messages.py` read every 400 as a missing model - so a sixty-page scan
reported itself as *claude-opus-5 is unavailable* and sent whoever read it to the model
registry to look for a model that was never absent.

Two halves, because either alone still misleads. The builder measures what it assembled
against a ceiling declared beside the methodology one and refuses **naming the section**,
because "412,318 bytes" is not something a person can act on and "the payload, 403 KB" is.
And a refusal that still arrives from the provider is diagnosed by what it says, because a
ceiling set here cannot know every provider's limit and the case that matters is the one
where they disagree.

Found comparing this build against the harness-engineering literature; the reasoning is in
`BUILD/proposals/harness-research.md`. It is the reactive half of that field's threshold
compaction (Recommendation 7), and only the reactive half: a skill invocation here is one
model turn, so there is no conversation to compact.
"""

from __future__ import annotations

import pytest

from harness.context import ContextBuilder
from registries.constraints import ConstraintRegistry
from registries.errors import RegistryError


def big(blobs, kb: int, name: str = "masked_payload"):
    """A payload of a given size, shaped like statement text rather than one long line."""
    line = "Accounts receivable, net of allowance   1,482,113\n"
    return blobs.put(
        (line * (kb * 1024 // len(line) + 1))[: kb * 1024].encode("utf-8"),
        media_type="text/plain",
        name=name,
    )


def builder(tree, blobs, bus, store, **kw):
    return ContextBuilder(tree, blobs, bus, store, **kw)


# ------------------------------------------------------------ the ceiling exists


def test_the_ceiling_is_a_decision_in_the_constraints_file() -> None:
    """Beside the methodology ceiling, and for the same reason: what a run costs is a
    decision somebody makes deliberately, not a constant somebody typed in a module."""
    ceiling = ConstraintRegistry.load().context_ceiling()
    assert ceiling > 0
    assert ceiling == 400000


def test_the_ceiling_sits_below_the_methodology_ceiling_by_a_wide_margin() -> None:
    """The two measure different things and the relationship is the point: methodology is
    the standing cost on every call, the context is the whole including the client's
    document. A context ceiling at or under the methodology one would mean the firm's own
    standards could not fit beside anything."""
    reg = ConstraintRegistry.load()
    assert reg.context_ceiling() > reg.methodology_ceiling() * 4


# ------------------------------------------------------------ and it is enforced


def test_a_context_that_fits_is_not_refused(request_for, tree, blobs, bus, store) -> None:
    """The first thing to be sure of. A check that refuses everything passes every test
    about refusing."""
    assembled = builder(tree, blobs, bus, store).build(request_for())
    assert assembled.context_ref


def test_a_context_over_the_ceiling_is_refused_before_it_is_sent(
    request_for, tree, blobs, bus, store
) -> None:
    with pytest.raises(RegistryError) as refused:
        builder(tree, blobs, bus, store).build(request_for(payload=big(blobs, 500)))
    assert refused.value.diagnostic.code == "INTAKE.CONTEXT_TOO_LARGE"


def test_the_refusal_names_the_section_that_is_too_big(
    request_for, tree, blobs, bus, store
) -> None:
    """The whole point. A person told only that the context is too large has to go and
    measure six sections to find out which; a person told it was the payload knows it is
    the document they just dropped in the folder."""
    with pytest.raises(RegistryError) as refused:
        builder(tree, blobs, bus, store).build(request_for(payload=big(blobs, 500)))
    said = refused.value.diagnostic.detail
    assert "payload" in said
    assert "500 KB" in said, said


def test_the_refusal_is_in_sizes_a_person_can_weigh(
    request_for, tree, blobs, bus, store
) -> None:
    """`412318` is a number nobody compares to anything."""
    with pytest.raises(RegistryError) as refused:
        builder(tree, blobs, bus, store).build(request_for(payload=big(blobs, 500)))
    d = refused.value.diagnostic
    assert "KB" in d.detail
    assert "KB" in str(d.expected) and "KB" in str(d.found)
    assert "412318" not in d.detail.replace(",", "")


def test_the_refusal_is_owned_by_whoever_can_act_on_it(
    request_for, tree, blobs, bus, store
) -> None:
    """Not `config`: the ceiling is configuration but the cause is the document, and the
    person who fixes it is the one holding the engagement."""
    with pytest.raises(RegistryError) as refused:
        builder(tree, blobs, bus, store).build(request_for(payload=big(blobs, 500)))
    assert refused.value.diagnostic.owner == "client-data"
    assert refused.value.diagnostic.what_now


def test_the_locator_points_at_the_step_and_the_section(
    request_for, tree, blobs, bus, store
) -> None:
    with pytest.raises(RegistryError) as refused:
        builder(tree, blobs, bus, store).build(request_for(payload=big(blobs, 500)))
    assert refused.value.diagnostic.locator.startswith("ebitda/")
    assert "payload" in refused.value.diagnostic.locator


def test_nothing_is_stored_for_a_call_that_will_not_be_made(
    request_for, tree, blobs, bus, store
) -> None:
    """An oversized context must not get a `context_ref` and a manifest describing a call
    nobody made. The idempotency key is built from that ref, so a stored one is a key that
    could be satisfied from a ledger entry for a step that never ran."""
    payload = big(blobs, 500)  # stored by this line, and by nothing after it
    def stored() -> set[str]:
        return {p.name for p in blobs.root.rglob("*") if p.is_file()}

    before = stored()
    assert before, "the store is empty, so this test could not notice a write"

    with pytest.raises(RegistryError):
        builder(tree, blobs, bus, store).build(request_for(payload=payload))

    assert stored() == before, f"written despite the refusal: {sorted(stored() - before)}"


def test_the_measurement_is_of_the_whole_and_not_of_the_payload_alone(
    request_for, tree, blobs, bus, store
) -> None:
    """A payload comfortably under the ceiling can still be over it once the skill body,
    the methodology and the profile are in front of it. Measuring the payload alone would
    pass exactly the case this exists to catch."""
    ceiling = ConstraintRegistry.load().context_ceiling()
    just_under = big(blobs, ceiling // 1024 - 2)
    with pytest.raises(RegistryError) as refused:
        builder(tree, blobs, bus, store).build(request_for(payload=just_under))
    assert refused.value.diagnostic.code == "INTAKE.CONTEXT_TOO_LARGE"


# ------------------------------------------ and the provider's own refusal reads right


class Refuses(Exception):
    """Stands in for the SDK's BadRequestError, which is what both cases arrive as."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def classify(message: str) -> str:
    """What the adapter would make of a 400 carrying this message."""
    from ports.llm.anthropic_messages import _is_too_long

    Refuses.__name__ = "BadRequestError"
    if _is_too_long(Refuses(message)):
        return "INTAKE.CONTEXT_TOO_LARGE"
    return "SCOPE.MODEL_PIN_UNAVAILABLE"


@pytest.mark.parametrize(
    "message",
    [
        "prompt is too long: 214253 tokens > 200000 maximum",
        "Input is too long for requested model",
        "This request exceeds the maximum context length for this model",
        "context_length_exceeded",
        "too many tokens in the request",
    ],
)
def test_a_provider_refusal_about_length_carries_a_length_diagnostic(message: str) -> None:
    """The real message shapes. Matched on text because the SDK gives a wrong model and an
    over-long request the same class, and the phrases are held here so that one of them
    changing is a failing test rather than a silent return to the old wrong answer."""
    assert classify(message) == "INTAKE.CONTEXT_TOO_LARGE"


@pytest.mark.parametrize(
    "message",
    [
        "model: claude-opus-7 not found",
        "The model `claude-sonnet-9` does not exist",
        "invalid request: unknown parameter 'effort'",
    ],
)
def test_a_real_missing_model_still_carries_the_model_diagnostic(message: str) -> None:
    """The other half. A length check that swallowed every 400 would be the same defect
    pointing the other way."""
    assert classify(message) == "SCOPE.MODEL_PIN_UNAVAILABLE"


def test_the_two_diagnostics_send_a_person_to_different_places() -> None:
    """Which is the whole reason for telling them apart."""
    from registries.errors import CONTEXT_TOO_LARGE, MODEL_PIN_UNAVAILABLE, diagnose

    length = diagnose(CONTEXT_TOO_LARGE, "x")
    missing = diagnose(MODEL_PIN_UNAVAILABLE, "x")
    assert length.owner != missing.owner

    # The instruction, not merely a different paragraph. The first version of this asserted
    # `"document" in length.what_now`, which held under a revert that deleted the entire
    # instruction - because the word appears earlier in the explanation. What has to be
    # true is that this diagnostic tells somebody to make the input smaller, and that the
    # other one does not send them to the model registry in its place.
    assert "Split the document" in length.what_now
    assert "registry" not in length.what_now.lower()
