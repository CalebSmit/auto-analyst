"""C66 - what five reviewers found about the first real run, and what it costs.

* **P116** — every live model call carried `metadata={run_id, context_ref, step_id, skill}`.
  The Messages API takes one key there, `user_id`, and rejects the rest with a 400. So the
  first call on a machine with a real key fails, and reports itself as a missing model.
* **P117** — the watch form pre-selected `mature-company-valuation`, whose own test asserts
  it cannot finish. The default path pays a real provider for timing, tagging and EBITDA
  and quarantines at a skill nobody wrote.
* **P118** — the AI-model step read done from the adapter's *name*, so a machine with no
  key said "Ready to run"; and the spend limit was labelled per-run while the code checks
  it against the engagement's spend across every run.

Each is green alone. What ties them is a single sentence: **the first time somebody spends
real money on this, what happens?** P116 decides whether the call is accepted at all, P117
decides whether the work it pays for can reach a workbook, and P118 decides whether the
screen told the truth before they pressed go.

So the question here is whether the three agree about one machine: that it can reach a
model, that what it would run can finish, and that the page says both of those things
honestly rather than by inference from a name.
"""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from harness.procedures import PROCEDURES
from ports.llm import LLMRequest, Message, ModelPin
from ports.llm.anthropic_messages import AnthropicMessagesLLM
from registries.recipes import RECIPES_DIR, RecipeRegister, unbuilt_skills
from tests.reading import page_code, page_script

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "admin" / "page.py"


class Recorder:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}
        self.messages = self

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        block = type("B", (), {"type": "text", "text": "{}"})()
        usage = type("U", (), {"input_tokens": 1, "output_tokens": 1})()
        return type("R", (), {"content": [block], "usage": usage, "stop_reason": "end_turn"})()


def on_the_wire() -> dict[str, Any]:
    """What the adapter would actually send, with everything this build puts on a request."""
    adapter = AnthropicMessagesLLM()
    recorder = Recorder()
    adapter._client = recorder  # noqa: SLF001
    with suppress(Exception):
        adapter.complete(
            LLMRequest(
                pin=ModelPin(model="claude-sonnet-5", effort="high"),
                system="s",
                messages=(Message("user", "{}"),),
                metadata={"run_id": "r", "step_id": "timing", "skill": "timing@0.1.0"},
            )
        )
    return recorder.kwargs


def reported(monkeypatch: pytest.MonkeyPatch, adapter: str, *, holds: tuple[str, ...]) -> Any:
    import ports
    from admin.console import AdminConsole

    monkeypatch.setenv("AA_LLM_ADAPTER", adapter)
    ports.reset()
    console = object.__new__(AdminConsole)
    secrets = type("S", (), {"has": lambda self, name: name in holds})()
    console.preflight = type("P", (), {"secrets": secrets})()  # type: ignore[attr-defined]
    return AdminConsole._ai_model(console)  # noqa: SLF001


# ============================================================ can it reach a model


def test_the_request_is_one_the_provider_would_take() -> None:
    """Asked of the SDK's own signature, which is generated from the API's spec and is the
    closest thing to the provider's answer that exists on this machine."""
    import inspect

    from anthropic.resources.messages import Messages

    takes = set(inspect.signature(Messages.create).parameters) - {"self"}
    for name in on_the_wire():
        assert name in takes, name


def test_and_nothing_this_build_invented_is_in_it() -> None:
    assert "metadata" not in on_the_wire()


def test_the_page_says_it_can_only_when_a_key_is_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P118 against P116: one decides whether the call would be accepted, the other
    whether the screen should have said so. A machine with the adapter and no key is the
    case where they had to agree and did not."""
    assert reported(monkeypatch, "anthropic_messages", holds=())["reaches_a_model"] is False
    said = reported(monkeypatch, "anthropic_messages", holds=("ANTHROPIC_API_KEY",))
    assert said["reaches_a_model"] is True


# ============================================================ can what it runs finish


def test_the_default_workflow_can_finish() -> None:
    """The one the form now offers. Derived from the procedures that exist, so it stays
    true when somebody builds another."""
    review = {r.name: r for r in RecipeRegister().review()}
    finishable = [r for r in review.values() if r.can_finish and r.state == "registered"]
    assert finishable, "nothing approved can finish"
    assert review["valuation-input-prep"].can_finish


def test_the_form_would_pick_one_of_those() -> None:
    body = page_code(PAGE.read_text(encoding="utf-8"))
    assert "const finishable = (r.recipes || []).filter(x => x.can_finish !== false" in body
    assert "'mature-company-valuation'" not in body


def test_and_says_where_each_of_the_others_stops() -> None:
    body = page_script(PAGE.read_text(encoding="utf-8"))
    assert "will stop at" in body
    for name in ("full-ddr-intake", "monthly-refresh", "mature-company-valuation"):
        assert unbuilt_skills(RECIPES_DIR / f"{name}.yaml"), f"{name} still cannot finish"


def test_every_skill_the_default_names_has_a_procedure() -> None:
    """The thing `can_finish` is a proxy for, asserted directly so the proxy cannot drift
    from it."""
    import yaml

    doc = yaml.safe_load((RECIPES_DIR / "valuation-input-prep.yaml").read_text(encoding="utf-8"))
    for step in doc["steps"]:
        if step.get("kind") == "skill":
            assert str(step["skill"]).split("@", 1)[0] in PROCEDURES, step["skill"]


# ============================================================ did the page say so honestly


def test_the_money_the_page_promises_is_the_money_the_code_enforces() -> None:
    """The label and `harness/budget.py` had to be made to agree, and the direction
    mattered: the cumulative check is the only cap across runs, so the label moved."""
    page = PAGE.read_text(encoding="utf-8")
    budget = (ROOT / "harness" / "budget.py").read_text(encoding="utf-8")
    assert "Spend limit for this engagement (USD, all runs)" in page
    assert "per run, not per month" not in page_code(page)
    assert "self.meter.rollup(engagement_id)" in budget


def test_the_checklist_covers_all_three_before_anything_is_spent() -> None:
    """A model that answers, a workflow that finishes, and a limit on what it costs — the
    three this checkpoint is about, each a step somebody sees rather than a thing they
    were supposed to know."""
    body = page_script(PAGE.read_text(encoding="utf-8"))
    for step in ("Connect the AI model", "Approve a workflow", "Set a spend limit"):
        assert f"t: '{step}'" in body, step


def test_the_count_beside_the_checklist_is_still_the_count() -> None:
    """Three phases added steps to one list. This is the assertion that caught the last
    three roll-call tests and it is the one that keeps catching them."""
    from tests.counting import in_words

    page = PAGE.read_text(encoding="utf-8")
    steps = page.count("{{done:")
    assert f"{in_words(steps)} steps, in order." in page


def test_a_clean_machine_can_build_its_own_deliverable() -> None:
    """P117's third part, and the reason the other two would not have helped on a fresh
    clone: `templates/*.xlsx` is generated and gitignored."""
    start = (ROOT / "tools" / "start.ps1").read_text(encoding="utf-8")
    assert "synthesize_templates.py" in start
    assert (ROOT / "templates" / "Chartwell_Input_Help_v1.xlsx").is_file()
