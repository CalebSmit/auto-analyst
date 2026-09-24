"""P102 - asking the model whether it is there.

The analyst wants to enter a key, pick a spend limit and press go. Everything in that
sentence existed except the first half: the page reported `live` or `no spend` from the
adapter's *name*, so the first evidence that a key was wrong was a run that quarantined
after paying for the steps before it.

P88 built this shape for Box and ShareFile - four questions asked in order, each answered
separately, because "connection failed" does not say whether to open `.env`, the provider's
console, or a folder's URL. The model door never had one.

**This is the one connection test that spends money**, and that changes two things. It
checks the key is set before it calls, asking the Secrets Port with `has()` so the absence
is reported without a request and without the value being read. And it reports what the
test itself cost, because somebody pressing this a dozen times while getting a key right
should not have to wait for an invoice to find out what that came to.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from admin.connection import MODEL_STEPS, THE_SMALLEST_QUESTION, probe_model
from ports.llm import LLMResponse, ModelPin, TransportFailure, Usage
from registries.errors import MISSING_CREDENTIAL, DiagnosticError, diagnose

ROOT = Path(__file__).resolve().parents[2]


class Secrets:
    def __init__(self, *, key: bool = True) -> None:
        self._key = key

    def has(self, name: str) -> bool:
        return self._key


class Model:
    """A stand-in for the adapter, so the probe can be asked about every outcome without
    an API key and without spending anything."""

    def __init__(self, name: str = "anthropic_messages", **behaviour: object) -> None:
        self.name = name
        self.behaviour = behaviour
        self.asked: list[object] = []

    def complete(self, request: object) -> LLMResponse:
        self.asked.append(request)
        if self.behaviour.get("refuses"):
            raise DiagnosticError(
                diagnose(MISSING_CREDENTIAL, "the provider says: invalid x-api-key")
            )
        if self.behaviour.get("drops"):
            raise TransportFailure("the connection was reset")
        served = str(self.behaviour.get("serves") or request.pin.model)  # type: ignore[attr-defined]
        return LLMResponse(
            text="ready",
            model=served,
            stop_reason="end_turn",
            usage=Usage(input_tokens=24, output_tokens=3),
        )


def steps_of(report: object) -> dict[str, str]:
    return {s.id: s.status for s in report.steps}  # type: ignore[attr-defined]


def detail(report: object, step: str) -> str:
    return next(s.detail for s in report.steps if s.id == step)  # type: ignore[attr-defined]


# ============================================================ nothing is spent by accident


def test_a_missing_key_is_named_and_nothing_is_called() -> None:
    """The commonest first state, and the one where a call would be pure waste."""
    model = Model()
    report = probe_model(model, Secrets(key=False))
    assert steps_of(report) == {
        "adapter": "pass", "credentials": "fail", "call": "not reached", "cost": "not reached"
    }
    assert "ANTHROPIC_API_KEY" in detail(report, "credentials")
    assert model.asked == [], "a call was made with no key set"


def test_the_key_is_asked_about_rather_than_read() -> None:
    """`has()` on the Secrets Port. A test that read the value to check it would be one
    more place a key can be logged, and this one prints its findings to a web page."""
    source = (ROOT / "admin" / "connection.py").read_text(encoding="utf-8")
    # Asked of the whole module rather than of `probe_model`, because the check moved into
    # `_named_credentials` when the boundary test refused the direct import - and a test
    # pinned to one function's body would have gone red on a refactor that kept the
    # property exactly.
    assert "secrets.has(" in source
    assert "secrets.get(" not in source, "a value is read somewhere in this module"

    body = source[source.index("def probe_model") : source.index("def _not_reached")]
    assert "_named_credentials(" in body, "the key check is delegated, not re-implemented"
    assert "ANTHROPIC_API_KEY" not in body, (
        "the name is asked of the ports registry; hard-coding it here is how it goes stale"
    )


def test_a_stand_in_adapter_fails_the_first_step_and_calls_nothing() -> None:
    """`fake` replays fixtures and `scripted` answers from a stand-in. Both would pass a
    key check and neither tells anybody whether the door opens."""
    for name in ("fake", "scripted"):
        model = Model(name=name)
        report = probe_model(model, Secrets())
        assert steps_of(report)["adapter"] == "fail", name
        assert "AA_LLM_ADAPTER" in detail(report, "adapter")
        assert model.asked == []


def test_the_test_call_carries_nothing_about_anybody() -> None:
    """It crosses the same boundary a client payload would. A connection test is not a
    reason to send one."""
    model = Model()
    probe_model(model, Secrets())
    (request,) = model.asked
    assert request.messages[0].content == THE_SMALLEST_QUESTION  # type: ignore[attr-defined]
    assert request.max_tokens <= 16  # type: ignore[attr-defined]
    assert "ready" in THE_SMALLEST_QUESTION
    assert request.metadata == {"purpose": "connection_test"}  # type: ignore[attr-defined]


# ============================================================ what a good answer says


def test_a_working_key_reports_the_model_that_answered() -> None:
    """"mid" is not an answer to "which AI is this using". The tier is a per-skill
    budgeting decision; what a person wants from this button is the model's own name."""
    report = probe_model(Model(), Secrets())
    assert steps_of(report)["call"] == "pass"
    assert "claude-haiku" in detail(report, "call")


def test_a_substituted_model_is_reported_rather_than_passed_over() -> None:
    """A provider serving a different model is the commonest way reproducibility is lost
    without anybody choosing it - `LLMResponse.model` exists to catch exactly this."""
    report = probe_model(Model(serves="claude-something-else"), Secrets())
    said = detail(report, "call")
    assert "claude-something-else" in said
    assert "asked for" in said


def test_it_says_what_the_test_itself_cost() -> None:
    """Arithmetic over the usage the API reported and the published rates - the same rule
    the cost meter follows. A figure that only appears on a monthly invoice is not an
    answer to "what does pressing this cost"."""
    report = probe_model(Model(), Secrets())
    said = detail(report, "cost")
    assert "24 in, 3 out" in said
    assert said.count("$") == 1
    assert "$0.00" in said


def test_an_unpriced_model_says_so_rather_than_reporting_zero() -> None:
    """A model this build has no published rate for would otherwise cost $0.000000, which
    reads as free."""
    report = probe_model(Model(serves="claude-unreleased-9"), Secrets())
    said = detail(report, "cost")
    assert "no published rate" in said
    assert "$" not in said


# ============================================================ what a bad answer says


def test_a_refusal_from_the_provider_is_reported_in_its_own_words() -> None:
    """The provider knows why it said no. Replacing that with "the call failed" is how a
    person ends up checking a key that was fine and a network that was up."""
    report = probe_model(Model(refuses=True), Secrets())
    assert steps_of(report)["call"] == "fail"
    assert "invalid x-api-key" in detail(report, "call")


def test_a_dropped_connection_is_a_failed_call_and_not_a_crash() -> None:
    """A transport failure is a normal outcome of pressing a button on a laptop. It must
    reach the page as a red step rather than as a 500."""
    report = probe_model(Model(drops=True), Secrets())
    assert steps_of(report)["call"] == "fail"
    assert "connection was reset" in detail(report, "call")


def test_a_step_after_a_failure_is_not_reached_rather_than_failed() -> None:
    """P88's rule, and the whole value of the button. Reporting the cost as *failed* when
    the call never happened would send somebody to look at billing."""
    report = probe_model(Model(refuses=True), Secrets())
    assert steps_of(report)["cost"] == "not reached"
    assert "call did not pass" in detail(report, "cost")


def test_a_green_test_does_not_imply_runs_are_using_it() -> None:
    """P88's trap, closed again here. The probe is handed an adapter, so it can pass while
    `AA_LLM_ADAPTER` still says `fake` - and a person would have no reason to suspect it."""
    report = probe_model(Model(), Secrets(), in_use=False)
    assert report.connected
    assert not report.in_use


# ============================================================ what it may not become


def test_the_probe_is_not_reachable_from_a_run() -> None:
    """It spends money and nothing but a person pressing a button may cause that. A run
    that could call it would be a run that pays for a self-test nobody asked for."""
    for module in ("workers/driver.py", "graph/execute.py", "harness/dispatch.py"):
        source = (ROOT / module).read_text(encoding="utf-8")
        assert "probe_model" not in source, module


def test_it_is_named_probe_rather_than_test() -> None:
    """P88's dull lesson, kept: pytest collects any function whose name starts with
    `test`, so a production function called `test_model` becomes a broken test case in
    every module that imports it."""
    tree = ast.parse((ROOT / "admin" / "connection.py").read_text(encoding="utf-8"))
    named = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "probe_model" in named
    assert not [n for n in named if n.startswith("test")]


def test_the_console_asks_the_selected_adapter_rather_than_building_one() -> None:
    """The storage probes build the adapter named by the service, because the point there
    is to test Box before switching to it. Here that would mean charging for a call to a
    door no run uses - so the model probe asks whichever adapter is selected, and reports
    `in_use` instead."""
    source = (ROOT / "admin" / "console.py").read_text(encoding="utf-8")
    body = source[source.index("def test_connection") : source.index("# -- plumbing")]
    assert "ports.get_llm()" in body
    assert 'ports.build_port("llm"' not in body


@pytest.mark.parametrize("step", [s[0] for s in MODEL_STEPS])
def test_every_declared_step_is_reported(step: str) -> None:
    """Four questions declared, four answered - whatever happened. A probe that stopped
    reporting a step on failure would leave a gap where the reason should be."""
    for model, secrets in (
        (Model(), Secrets()),
        (Model(refuses=True), Secrets()),
        (Model(name="fake"), Secrets()),
        (Model(), Secrets(key=False)),
    ):
        assert step in steps_of(probe_model(model, secrets))


def test_the_pin_can_be_chosen_so_a_person_can_test_the_model_they_will_pay_for() -> None:
    """It defaults to the cheapest tier, because a connection test should not cost what an
    Opus call costs. But "does my key work for Opus" is a different question from "does my
    key work", and a key can be entitled to one model and not another."""
    model = Model()
    probe_model(model, Secrets(), pin=ModelPin.for_tier("high"))
    (request,) = model.asked
    assert request.pin.model == "claude-opus-5"  # type: ignore[attr-defined]

    cheap = Model()
    probe_model(cheap, Secrets())
    assert cheap.asked[0].pin.model == "claude-haiku-4-5"  # type: ignore[attr-defined]
