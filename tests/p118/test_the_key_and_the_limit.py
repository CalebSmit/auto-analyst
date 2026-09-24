"""P118 - the key it never checked and the limit it mislabelled.

Two claims the Setup page made about the two things that cost money.

**The key.** The AI-model step read done from the adapter's *name* —
`reaches_a_model` was `adapter not in ("fake", "scripted")` — so a machine with
`AA_LLM_ADAPTER=anthropic_messages` and a missing, revoked or wrong-account key showed
*"Ready to run — a run would mask, ask a model and write a workbook."* P107 was written
precisely to stop that sentence being said on a machine that could not say it, and it
opened the vault to check the masking key and then took the model on trust.

**The limit.** It was labelled *"Spend limit per run (USD)"* with the hint *"This is per
run, not per month"*, and `harness/budget.py` checks the number against the engagement's
cumulative spend across every run it has ever had. Set fifty dollars as a generous
per-run allowance and the third run halts at a ceiling nobody meant to set. It fails in
the safe direction for money, and a control whose label lies about what it does is a
finding by this repo's own rule rather than a preference.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.reading import page_code, page_script, python_code

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "admin" / "page.py"
BUDGET = ROOT / "harness" / "budget.py"


def script() -> str:
    return page_script(PAGE.read_text(encoding="utf-8"))


def reported(monkeypatch: pytest.MonkeyPatch, adapter: str, *, holds: tuple[str, ...]) -> Any:
    """`_ai_model` with that adapter selected and those credentials present."""
    import ports
    from admin.console import AdminConsole

    monkeypatch.setenv("AA_LLM_ADAPTER", adapter)
    ports.reset()
    console = object.__new__(AdminConsole)
    secrets = type("S", (), {"has": lambda self, name: name in holds})()
    console.preflight = type("P", (), {"secrets": secrets})()  # type: ignore[attr-defined]
    return AdminConsole._ai_model(console)  # noqa: SLF001


def environment(monkeypatch: pytest.MonkeyPatch, adapter: str, *, holds: tuple[str, ...]) -> Any:
    """What the checklist reads, which is the sentence a person acts on."""
    from cryptography.fernet import Fernet

    import ports
    from admin.console import AdminConsole

    monkeypatch.setenv("AA_LLM_ADAPTER", adapter)
    ports.reset()
    console = object.__new__(AdminConsole)
    key = Fernet.generate_key().decode()
    values = {"AA_VAULT_KEY": key, **{n: "x" for n in holds}}
    secrets = type(
        "S",
        (),
        {"has": lambda self, n: n in values, "get": lambda self, n: values[n]},
    )()
    console.preflight = type("P", (), {"secrets": secrets})()  # type: ignore[attr-defined]
    return AdminConsole._environment(console)  # noqa: SLF001


# ============================================================ the key


def test_the_adapter_alone_is_no_longer_enough(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bug. Pointed at the API, no key, and the page said Ready to run."""
    said = reported(monkeypatch, "anthropic_messages", holds=())
    assert said["reaches_a_model"] is False
    assert said["missing_credentials"] == ["ANTHROPIC_API_KEY"]


def test_with_the_key_it_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    said = reported(monkeypatch, "anthropic_messages", holds=("ANTHROPIC_API_KEY",))
    assert said["reaches_a_model"] is True
    assert said["missing_credentials"] == []


def test_the_checklist_step_says_which_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"Not connected" sends somebody to guess. Naming the variable is the difference
    between a sentence and a task."""
    env = environment(monkeypatch, "anthropic_messages", holds=())
    assert env["model"]["ready"] is False
    assert "ANTHROPIC_API_KEY" in env["model"]["detail"]


def test_a_stand_in_is_still_not_ready_and_says_why(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unchanged from P107, and the two reasons stay distinguishable: nothing is wrong and
    nothing is happening are different problems."""
    env = environment(monkeypatch, "fake", holds=("ANTHROPIC_API_KEY",))
    assert env["model"]["ready"] is False
    assert "fixtures" in env["model"]["detail"]


def test_the_credential_is_the_adapter_s_to_declare() -> None:
    """Not this page's to know. A console that hard-coded `ANTHROPIC_API_KEY` would be
    naming a concrete adapter from outside `ports/`, which is the boundary P102 had to
    unpick once already."""
    console = python_code((ROOT / "admin" / "console.py").read_text(encoding="utf-8"))
    body = console[console.index("def _ai_model") : console.index("def _entry_row")]
    assert 'ports.credentials_for("llm", adapter)' in body
    assert "ANTHROPIC_API_KEY" not in body, "named by the adapter, not by this page"


def test_an_adapter_nobody_registered_still_counts_as_costing_money(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dangerous default, kept. An unrecognised name is far likelier to be a real
    adapter somebody added than a stand-in - and asking the registry what it needs raises,
    so the check has to survive not knowing."""
    said = reported(monkeypatch, "some_future_adapter", holds=())
    assert said["answers_from_a_model"] is True
    assert said["missing_credentials"] == [], "nothing is known to be missing"


# ============================================================ the limit


def test_the_label_says_what_the_code_caps() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "Spend limit for this engagement (USD, all runs)" in page
    assert "across every run it has" in page


def test_the_old_claim_is_gone() -> None:
    """It was written down twice, in the label and in the hint, and both were false."""
    code = page_code(PAGE.read_text(encoding="utf-8"))
    assert "per run, not per month" not in code
    assert "Spend limit per run" not in code


def test_the_code_still_means_the_engagement() -> None:
    """The label was changed to match the code and not the other way round: the cumulative
    check is the only cap this build has across runs, and making it per-run would remove
    it."""
    budget = BUDGET.read_text(encoding="utf-8")
    assert "self.meter.rollup(engagement_id)" in budget
    assert "a budget is the" in budget and "engagement's, not a run's" in budget


def test_the_standing_ceiling_is_said_out_loud() -> None:
    """What a run costs when nobody sets a limit is the question somebody asks before
    pressing go, and the page knew the answer and did not say it."""
    body = script()
    assert "firm ceiling of $' + SETUP.firm_ceiling_usd" in body


# ============================================================ on the checklist


def test_setting_a_limit_is_a_step() -> None:
    """It lived behind a small settings button on a roster row, so a first-time user
    would never find it."""
    body = script()
    assert "t: 'Set a spend limit'" in body


def test_it_is_done_when_every_engagement_has_one() -> None:
    body = script()
    step = body[body.index("t: 'Set a spend limit'") - 120 : body.index("t: 'Set a spend limit'")]
    assert "roster.every(r => Number(r.budget_usd) > 0)" in step


def test_it_names_the_engagement_that_has_none() -> None:
    """Plus what that costs. "Set a spend limit" without saying whose, or what happens if
    you do not, is a checkbox rather than a warning."""
    body = script()
    step = body[body.index("t: 'Set a spend limit'") : body.index("t: 'Register an engagement'")]
    assert "open[0].client" in step
    assert "no limit on the total" in step


def test_it_offers_the_settings_dialog_that_already_exists() -> None:
    """Rather than a second place to type the number."""
    body = script()
    step = body[body.index("t: 'Set a spend limit'") : body.index("t: 'Register an engagement'")]
    assert "'settings'" in step
    assert "ACTIONS.settings = d => settings(d.id);" in body


def test_the_count_beside_the_list_still_follows_it() -> None:
    from tests.counting import in_words

    page = PAGE.read_text(encoding="utf-8")
    steps = page.count("{{done:")
    assert f"{in_words(steps)} steps, in order." in page
