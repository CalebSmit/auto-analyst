"""P84: the stable prefix, cached.

The cost meter prices cache reads at a tenth of input and cache writes at 1.25x, `Usage`
carries `cache_read_input_tokens` and `cache_creation_input_tokens`, and `Charge` splits
them out - and nothing had ever set `cache_control`, so every one of those fields was zero
on every call this build has made. The accounting for caching was built and the caching
was not.

Meanwhile the system prompt the dispatcher sends is a skill body, the references that
skill declares and a constant rule. That is byte-identical for every call of that skill in
that scope, and it was re-sent and re-charged in full every time. Observation 2 of the
harness study: Claude Code splits its own prompt at a hashed cache boundary for exactly
this reason.

What matters as much as the saving is that the saving is *measured*. Turning caching on
and asserting it helps would be the same shape of defect as the accounting that counted
nothing: `cache_hit_rate` comes off the run's own events, and returns `None` rather than
zero when nothing was cacheable, because those are different answers.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from ops.cost import price
from ports.llm import RATES_USD_PER_MTOK, LLMRequest, Message, ModelPin, Usage
from ports.llm.anthropic_messages import _system


def request(**kw) -> LLMRequest:
    fields = {
        "pin": ModelPin(model="claude-opus-5"),
        "system": "You are running the skill ebitda-normalization. " + ("x" * 4000),
        "messages": (Message("user", "the client's document"),),
    }
    fields.update(kw)
    return LLMRequest(**fields)


# ------------------------------------------------------------ the marker is placed


def test_the_system_prompt_is_sent_as_a_cacheable_block() -> None:
    sent = _system(request())
    assert isinstance(sent, list) and len(sent) == 1
    assert sent[0]["cache_control"] == {"type": "ephemeral"}
    assert sent[0]["type"] == "text"


def test_the_marker_changes_no_content() -> None:
    """The same bytes either way. This is a statement about where the provider may stop
    re-reading, not about what it reads."""
    r = request()
    assert _system(r)[0]["text"] == r.system
    assert _system(replace(r, cache_system=False)) == r.system


def test_a_request_that_opts_out_looks_exactly_as_it_did_before() -> None:
    """A plain string, which is what the API took before any of this. A caller assembling
    its system prompt per call gains nothing from a breakpoint and should not be made to
    carry a different request shape to say so."""
    sent = _system(replace(request(), cache_system=False))
    assert isinstance(sent, str)


def test_only_the_system_prompt_is_marked() -> None:
    """The message carries the methodology, the precedents, the profile and the client's
    document - the parts that vary. Marking those would write a cache entry per document
    and read none of them back, which is the 1.25x write with no tenth-price read after."""
    sent = _system(request())
    assert "the client's document" not in sent[0]["text"]


# ------------------------------------------- what is cacheable is stable by construction


def test_two_calls_of_one_skill_in_one_scope_share_the_prefix_byte_for_byte() -> None:
    """Stable by construction rather than by luck. A prefix that differs in a timestamp or
    a run id is a prefix that is written every time and never read."""
    first = _system(request())[0]["text"]
    second = _system(request(messages=(Message("user", "a different document"),)))[0]["text"]
    assert first == second


def test_the_dispatcher_builds_its_system_prompt_from_stable_parts_only() -> None:
    """Read from the dispatcher rather than asserted about it. The prompt is the skill
    body, the declared references and a constant - and nothing per-run. If a run id or a
    time ever joins it, the prefix stops being shared and this says so."""
    import inspect

    from harness.dispatch import SkillDispatcher

    source = inspect.getsource(SkillDispatcher)
    built = source[source.index('system = "\\n\\n".join(') :]
    built = built[: built.index("wrapped = ")]
    for varying in ("run_id", "engagement_id", "datetime", "time.", "uuid", "context_ref"):
        assert varying not in built, f"the cacheable prefix now carries {varying}"


def test_whether_it_is_cached_is_not_part_of_the_call_s_identity() -> None:
    """Two requests differing only in `cache_system` ask the same question and must get
    the same answer, so the content hash - which the idempotency key folds in, and which
    the replay harness finds a recorded response by - has to ignore it."""
    on = request()
    off = replace(on, cache_system=False)
    assert on.content_hash() == off.content_hash()


# ------------------------------------------------------------ and it is measured


def test_a_cache_read_is_priced_at_a_tenth_and_a_write_at_more_than_input() -> None:
    """The rates the meter already carried and never had anything to apply them to."""
    per_input = RATES_USD_PER_MTOK["claude-opus-5"][0]
    plain = price("claude-opus-5", Usage(input_tokens=1_000_000))
    read = price("claude-opus-5", Usage(cache_read_input_tokens=1_000_000))
    written = price("claude-opus-5", Usage(cache_creation_input_tokens=1_000_000))

    assert plain.usd == pytest.approx(per_input)
    assert read.usd == pytest.approx(per_input * 0.1)
    assert written.usd == pytest.approx(per_input * 1.25)
    assert read.usd < plain.usd < written.usd


def test_the_call_that_answered_says_what_it_read_and_what_it_wrote(store, answered) -> None:
    """On the event, split out. The run store gets the total for its ceiling, which is
    right - a cached token is still a token the run was charged for - but the total alone
    cannot answer "is this doing anything"."""
    run_id = answered(Usage(input_tokens=100, cache_read_input_tokens=4000))
    events = [e for e in store.events(run_id) if e.type == "model.answered"]
    assert events, "the door emitted nothing, so this test could not see a payload"
    assert events[-1].payload["cache_read_tokens"] == 4000
    assert events[-1].payload["cache_write_tokens"] == 0


def test_the_run_reports_a_hit_rate(store, answered) -> None:
    from ops.cost import CostMeter

    run_id = answered(Usage(input_tokens=10, cache_creation_input_tokens=1000))
    answered(Usage(input_tokens=10, cache_read_input_tokens=3000), run_id=run_id)

    breakdown = CostMeter(store).breakdown(run_id)
    assert breakdown.cache_write_tokens == 1000
    assert breakdown.cache_read_tokens == 3000
    assert breakdown.cache_hit_rate == 0.75


def test_nothing_cacheable_reads_as_nothing_rather_than_as_a_miss(store, answered) -> None:
    """`None` and `0.0` are different answers. A run whose every call opted out has no hit
    rate; a run that wrote and never read has one, and it is zero. Reporting the first as
    the second would have somebody tuning a cache that was never asked for."""
    from ops.cost import CostMeter

    run_id = answered(Usage(input_tokens=500))
    assert CostMeter(store).breakdown(run_id).cache_hit_rate is None

    answered(Usage(input_tokens=5, cache_creation_input_tokens=900), run_id=run_id)
    assert CostMeter(store).breakdown(run_id).cache_hit_rate == 0.0
