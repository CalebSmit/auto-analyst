"""P80: setup, in the analyst's words.

Reviewing the Setup surface as a beginner would meet it found that the form asks for the
appraiser's vocabulary and omits the analyst's.

The checklist promised six steps in order and the hardest job was not one of them: step six
said preflight has to pass, and preflight refuses until an engagement profile of twelve
required fields is complete - a NAICS code, a size band with an as-of date, an owner
compensation baseline with amount, currency, basis, source and as-of. Five easy ticks, then
a wall nobody was warned about.

Whether a client is repeat or new - the flag three quarters of the work turns on - was the
last segment of a control labelled "Practice group", written as `non-repeat`. The word
"model" meant the Excel template in three places, so somebody looking for which AI model is
used found three controls named model and none of them was it. And `archive` had a route
since P24 and no button, so an engagement could be made and paused but never put away.

None of this is new capability. It is the same settings, named and sequenced the way the
person doing the work thinks about them.

Every test here was run against a targeted revert of the change it is about and required to
go red - a page assembled from f-strings is exactly where an assertion can match some other
part of the page and prove nothing. Three of the reverts are structural rather than a word
swap: the two checklist steps put back in the old order, `adapter` hard-coded instead of
read from the ports, and the confirmation dialog removed so `retire` fires on the click.
"""

from __future__ import annotations

import re
from pathlib import Path

from admin.page import PAGE

ROOT = Path(__file__).resolve().parents[2]


def script() -> str:
    """The page's JavaScript, with the f-string doubling undone so it reads as it ships."""
    return "\n".join(re.findall(r"<script>(.*?)</script>", PAGE, re.S)).replace(
        "{{", "{"
    ).replace("}}", "}")


# ------------------------------------------------------------------ the wall, removed


def test_the_profile_is_a_step_rather_than_a_refusal() -> None:
    """It was the longest job in setup and appeared in none of the six steps."""
    body = script()
    assert "Fill in the engagement profile" in body
    assert "Seven steps, in order." in PAGE, "the count has to follow the steps"


def test_the_profile_step_comes_before_the_step_that_refuses_without_it() -> None:
    """Order is the whole point: activation refuses until the profile is complete, so
    meeting the profile after activation is meeting it as a failure."""
    body = script()
    assert body.index("Fill in the engagement profile") < body.index("Activate it")


def test_the_profile_step_says_what_it_will_cost_somebody() -> None:
    """Twelve fields is a different task from a checkbox, and a step that does not say so
    is a step somebody starts at the wrong moment."""
    body = script()
    assert "ten minutes" in body
    assert "nothing runs without it" in body


def test_the_step_names_the_engagement_that_is_missing_answers() -> None:
    """With several engagements, "a profile is incomplete" is not actionable."""
    assert "still needs" in script()


# ------------------------------------------------------------------ repeat or new


def test_repeat_or_new_is_asked_in_those_words() -> None:
    assert "Is this a repeat client?" in PAGE
    assert "we valued them before" in PAGE
    assert "first time we have valued this client" in PAGE


def test_the_scope_path_follows_from_the_two_answers() -> None:
    """One string in the configuration, two questions in somebody's head. The group is
    offered without its disposition, and the disposition is put back on submit."""
    body = script()
    assert "$('e_scope').value + '/' + $('e_kind').value" in body
    chooser = body[body.index("function showAdd()") : body.index("function suggest()")]
    assert "SCOPES.groups" in chooser and "SCOPES.dispositions" in chooser


def test_the_page_never_takes_a_scope_path_apart(console) -> None:
    """Which segment answers which question is the registry's business. A page slicing
    the string would be a second place to be wrong about it, and C47 holds it to that -
    so the console hands over the groups already separated."""
    assert "scope_path.split" not in PAGE and "scope_path.slice" not in PAGE
    assert "groups" in console.scope_choices()


def test_a_practice_group_is_offered_once_however_many_dispositions_it_has(console) -> None:
    """Two dispositions per group, one entry per group. Listing `valuation/non-esop`
    twice would read as two different things to choose between."""
    groups = [g["group"] for g in console.scope_choices()["groups"]]
    assert len(groups) == len(set(groups))
    assert "valuation/non-esop" in groups
    assert not any(g.count("/") != 1 for g in groups), "a group still carries a disposition"


def test_the_group_list_is_built_from_the_registry_rather_than_the_paths(console) -> None:
    """Every practice group in the registry is offerable, including the ones nobody has
    described yet - they are shown rather than hidden, as the registry's note says."""
    choices = console.scope_choices()
    from_paths = {p["scope_path"].rsplit("/", 1)[0] for p in choices["paths"]}
    assert {g["group"] for g in choices["groups"]} == from_paths


def test_the_focus_group_is_offered_first(console) -> None:
    """The division this build serves. Somebody adding their first engagement should not
    have to find it among the scaffolded ones."""
    groups = console.scope_choices()["groups"]
    assert groups[0]["group"] == "valuation/non-esop"
    assert groups[0]["focus"] is True
    assert groups[-1]["parked"] or not groups[-1]["defined"], "parked and undefined sort last"


def test_a_disposition_added_to_the_registry_would_be_offerable() -> None:
    """The two that exist are in the markup so the control is right before anything loads,
    but the list is still taken from the registry - otherwise adding a disposition to
    scopes.yaml would produce a scope nobody could select."""
    body = script()
    assert "if (kinds.length)" in body, "the registry's list never replaces the markup"
    assert "KIND_SAYS[d.id] || d.name" in body, "an unnamed disposition would render blank"


# ------------------------------------------------------------------ which model


def test_the_excel_template_says_which_model_it_means() -> None:
    assert "Excel model template" in PAGE
    assert "not the AI model" in PAGE


def test_the_spend_limit_is_named_for_what_it_limits() -> None:
    """The old label, `Model budget per run`, read as the Excel model's budget - and
    per-run is not what most people mean by a spend limit, so it says both things now."""
    assert "Spend limit per run (USD)" in PAGE
    assert "per run, not per month" in PAGE


def test_the_ai_model_is_visible_somewhere() -> None:
    """It was on no screen at all. A person cannot be expected to trust output from a
    model the tool will not name."""
    assert "AI model" in script()
    assert "ai_model" in script()


def reported(monkeypatch, adapter: str) -> dict:
    """What the console would say with that adapter selected. Both branches are exercised
    rather than whichever one the test environment happens to be in - a test that asserts
    only under `if adapter == "fake"` asserts nothing on the machine that matters."""
    from admin.console import AdminConsole

    monkeypatch.setenv("AA_LLM_ADAPTER", adapter)
    return AdminConsole._ai_model(object.__new__(AdminConsole))


def test_the_console_reports_which_adapter_answers(monkeypatch) -> None:
    """Read from the ports rather than declared, so the page cannot drift from the run."""
    import ports

    said = reported(monkeypatch, "fake")
    assert said["adapter"] == ports.selected("llm") == "fake"
    assert said["means"], "an adapter with no explanation is a name, not an answer"
    assert set(said["tiers"]) == {"low", "mid", "high"}


def test_the_fake_adapter_is_reported_as_costing_nothing(monkeypatch) -> None:
    """The distinction somebody most wants: is this spending money."""
    said = reported(monkeypatch, "fake")
    assert said["reaches_a_model"] is False
    assert "no spend" in said["means"]


def test_the_real_adapter_is_reported_as_reaching_a_model(monkeypatch) -> None:
    """And the same question answered the other way, on the adapter the work machine will
    run. If both answers were the same the field would be decoration."""
    said = reported(monkeypatch, "anthropic_messages")
    assert said["reaches_a_model"] is True
    assert "the firm's key" in said["means"]


def test_an_adapter_the_page_does_not_know_is_not_reported_as_free(monkeypatch) -> None:
    """The dangerous default. An unrecognised adapter is far likelier to be a real one
    somebody added than a stand-in, so it must not be described as costing nothing."""
    said = reported(monkeypatch, "some_future_adapter")
    assert said["reaches_a_model"] is True
    assert "does not recognise" in said["means"]


# ------------------------------------------------------------------ retiring


def test_an_engagement_can_be_retired_from_the_page_that_made_it() -> None:
    """The route has existed since P24 and nothing called it."""
    body = script()
    assert "ACTIONS.retire" in body
    assert "/archive" in body
    assert 'data-act="retire"' in PAGE


def test_retiring_asks_first() -> None:
    """The only control on this page that ends something."""
    body = script()
    retire = body[body.index("async function retire(") : body.index("function move(")]
    assert "await ask(" in retire
    assert "danger: true" in retire
    assert "required: true" in retire, "a reason is recorded, as with every other change"


def test_retiring_says_what_it_does_not_destroy() -> None:
    """Somebody hesitating over a button needs to know the record survives."""
    assert "Nothing already recorded is removed" in script()


# ------------------------------------------------------------------ and the seams read right


def test_a_seam_waiting_on_software_does_not_read_as_unwired() -> None:
    """P74's distinction, which the admin page did not have: "not wired" about a missing
    OCR engine would send somebody looking for a fault in the build."""
    body = script()
    assert "needs_installing" in body
    assert "not installed" in body
