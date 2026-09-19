"""C48 - The setup a beginner can finish.

P80 renamed and resequenced the Setup surface and left everything behind it alone. That is
exactly the change that goes wrong quietly: a console that describes a walk nobody can
take reads correctly and passes its own tests, because its tests are about the words.

So this checkpoint takes the walk instead. It assembles a scope path the way the page now
assembles one - a practice group from one control and a disposition from another, joined
on submit - registers an engagement with it, reads the checklist's own step conditions off
the console, and carries the engagement to active. Each step's claim is checked against
the thing that would refuse it, not against the text of the step.

`test_the_profile_step_and_preflight_agree_about_what_is_missing` is the one worth having.
The defect it prevents is the checklist saying seven of seven done while activation
refuses - one condition written twice, in two places, drifting apart the first time either
is edited. It is only safe today because both call `_profile_gaps`, and that is an
invariant rather than a coincidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from admin.console import AdminRefused
from intake.roster import RosterState
from registries.scopes import ScopePath
from tests.p24.conftest import WHO, entry, profile_for

GROUP = "valuation/non-esop"
AGAIN = "AGAIN-2026-01"


def assembled(console, group: str, kind: str) -> str:
    """What `addEngagement` sends: the two answers joined, in that order.

    Written out here rather than imported because the point is that the page's join and
    the registry's parse have to agree about the order of the three segments, and a
    checkpoint that reused the joining code would prove only that it equals itself.
    """
    choices = console.scope_choices()
    assert group in {g["group"] for g in choices["groups"]}
    assert kind in {d["id"] for d in choices["dispositions"]}
    return group + "/" + kind


# ------------------------------------------------------- the two answers make one path


def test_the_two_controls_assemble_a_path_the_registry_accepts(console) -> None:
    path = assembled(console, GROUP, "repeat")
    parsed = ScopePath.parse(path)
    assert (parsed.practice, parsed.segment, parsed.disposition) == (
        "valuation",
        "non-esop",
        "repeat",
    )
    assert path in {p["scope_path"] for p in console.scope_choices()["paths"]}


def test_every_offered_combination_assembles_into_an_offered_path(console) -> None:
    """Not just the focus one. If a group and a disposition can both be chosen, the pair
    has to be a scope path that resolves - otherwise the page offers a combination that
    registers and then fails at preflight for a reason nobody typed."""
    choices = console.scope_choices()
    real = {p["scope_path"] for p in choices["paths"]}
    for group in choices["groups"]:
        for kind in choices["dispositions"]:
            assert f"{group['group']}/{kind['id']}" in real


def test_a_registered_engagement_carries_the_path_the_two_controls_made(console) -> None:
    path = assembled(console, GROUP, "repeat")
    console.register_engagement(
        entry(AGAIN, client="Again Industrial", scope_path=path, folder="Again Industrial/2026"),
        profile=None,
        who=WHO,
        reason="engagement letter signed",
    )
    row = next(r for r in console.setup()["roster"] if r["engagement_id"] == AGAIN)
    assert row["scope_path"] == path
    assert row["is_repeat"] is True, "the console, not the page, decides what repeat means"


# ------------------------------------------------- the step and the refusal are one thing


def test_the_profile_step_and_preflight_agree_about_what_is_missing(console) -> None:
    """The checklist's step is `profile_gaps` being empty; activation's refusal is
    preflight's `profile_complete`. Two names for one condition, and they must be one
    computation - a step that says done while activation refuses is worse than no step.

    Preflight is asked the way activation asks it - for this engagement by name - because
    a whole-environment run only considers active engagements, and the one being set up is
    by definition not active yet."""
    path = assembled(console, GROUP, "repeat")
    console.register_engagement(
        entry(AGAIN, client="Again Industrial", scope_path=path, folder="Again Industrial/2026"),
        profile=None,
        who=WHO,
        reason="engagement letter signed",
    )

    def step_is_done() -> bool:
        row = next(r for r in console.setup()["roster"] if r["engagement_id"] == AGAIN)
        return not row["profile_gaps"]

    def preflight_lets_it_through() -> bool:
        check = next(c for c in console.preflight.run(AGAIN).checks if c.id == "profile_complete")
        return check.status == "pass"

    # 1. nothing recorded at all.
    assert not step_is_done()
    assert not preflight_lets_it_through()
    check = next(c for c in console.preflight.run(AGAIN).checks if c.id == "profile_complete")
    said = " ".join(f.diagnostic.detail for f in check.failures)
    assert AGAIN in said, "the refusal has to name the engagement the step named"

    # 2. a profile recorded and incomplete - the leg that matters. "Has a profile" and
    # "has a usable profile" agree at both ends and differ only here, so a step checking
    # the easy one would pass every test that never recorded a half-filled profile.
    #
    # The one the contract permits: `checkpoint_policy` is not in the profile's required
    # list, so a profile with every fact about the company and nobody named to review the
    # work is valid, writes cleanly, and cannot run. That is not a contrived case - it is
    # the one field that is somebody else's answer rather than the analyst's.
    half = profile_for(AGAIN, path)
    half.pop("checkpoint_policy")
    console.set_profile(AGAIN, half, who=WHO, reason="started it")
    assert not step_is_done(), "the checklist shows done on a profile a run cannot use"
    assert not preflight_lets_it_through()

    # 3. and complete.
    console.set_profile(AGAIN, profile_for(AGAIN, path), who=WHO, reason="filled in")
    assert step_is_done()
    assert preflight_lets_it_through(), "the step is done and preflight still refuses"


def test_a_profile_scoped_to_the_wrong_path_is_a_gap_rather_than_a_silent_mismatch(
    console,
) -> None:
    """The slip the two-control form makes newly possible: the group chosen in setup and
    the practice/segment/disposition written into the profile are the same three values
    entered twice."""
    path = assembled(console, GROUP, "repeat")
    console.register_engagement(
        entry(AGAIN, client="Again Industrial", scope_path=path, folder="Again Industrial/2026"),
        profile=profile_for(AGAIN, "valuation/non-esop/non-repeat"),
        who=WHO,
        reason="engagement letter signed",
    )
    gaps = next(r for r in console.setup()["roster"] if r["engagement_id"] == AGAIN)["profile_gaps"]
    assert any("non-repeat" in g and "repeat" in g for g in gaps), gaps


# --------------------------------------------------------- and the walk reaches the end


def test_the_checklist_can_be_finished(console, tmp_path: Path) -> None:
    """Empty roster to an active engagement, doing only what the steps say to do."""
    setup = console.setup()
    assert setup["watches"] and setup["destinations"], "the environment steps are done"

    path = assembled(console, GROUP, "repeat")
    console.register_engagement(
        entry(AGAIN, client="Again Industrial", scope_path=path, folder="Again Industrial/2026"),
        profile=profile_for(AGAIN, path),
        who=WHO,
        reason="engagement letter signed",
    )

    book = tmp_path / "Again 2025 valuation.xlsx"
    book.write_bytes(b"last year")
    console.set_prior_model(AGAIN, str(book), who=WHO, reason="setup")
    assert not console.needs_a_prior_model(AGAIN)

    console.activate(AGAIN, who=WHO, reason="ready")
    row = next(r for r in console.setup()["roster"] if r["engagement_id"] == AGAIN)
    assert row["state"] == RosterState.ACTIVE.value


def test_the_last_step_refuses_while_an_earlier_one_is_undone(console) -> None:
    """The order in the checklist is a claim about what blocks what."""
    path = assembled(console, GROUP, "repeat")
    console.register_engagement(
        entry(AGAIN, client="Again Industrial", scope_path=path, folder="Again Industrial/2026"),
        profile=None,
        who=WHO,
        reason="engagement letter signed",
    )
    with pytest.raises(AdminRefused) as refused:
        console.activate(AGAIN, who=WHO, reason="ready")
    assert "profile" in str(refused.value).lower()


# ------------------------------------------------------------------------- and undone


def test_retiring_stops_the_work_without_removing_the_record(console, henderson) -> None:
    """What the confirmation dialog promises in words, checked against what happens."""
    console.activate(henderson.engagement_id, who=WHO, reason="ready")
    before = len(console.config.document()["engagements"])

    console.archive(henderson.engagement_id, who=WHO, reason="valuation issued")

    row = next(
        r for r in console.setup()["roster"] if r["engagement_id"] == henderson.engagement_id
    )
    assert row["state"] == RosterState.ARCHIVED.value
    assert len(console.config.document()["engagements"]) == before, "the record was removed"


def test_a_retired_engagement_is_not_swept(console, henderson) -> None:
    """The other half of what the dialog promises: it stops being swept, and no new run
    starts."""
    console.activate(henderson.engagement_id, who=WHO, reason="ready")
    assert henderson.engagement_id in {e.engagement_id for e in console.roster.active()}
    console.archive(henderson.engagement_id, who=WHO, reason="valuation issued")
    assert henderson.engagement_id not in {e.engagement_id for e in console.roster.active()}


# ------------------------------------------------------- and the page still says so truly


def checklist_actions() -> set[str]:
    """The name each step's button is rendered with: `go[1]`, which becomes `data-act`."""
    import re

    from admin.page import PAGE

    body = PAGE.replace("{{", "{").replace("}}", "}")
    steps = body[body.index("const steps = [") : body.index("const next = steps.findIndex")]
    return set(re.findall(r"\['[^']*', '([^']+)'", steps))


def dispatch_table() -> set[str]:
    import re

    from admin.page import PAGE

    return set(re.findall(r"ACTIONS\.(\w+)\s*=", PAGE))


def test_every_action_the_checklist_offers_is_in_the_dispatch_table() -> None:
    """This found a live one. The first step of a fresh install rendered
    `data-act="initialise()"`, and the dispatcher looks the name up in ACTIONS - so
    `ACTIONS['initialise()']` was undefined, the listener returned, and the button on the
    only screen a new machine can show did nothing at all.

    Every other button on the page went through a name that was in the table, which is
    why nothing caught it: the defect is not a missing function, it is a name with two
    spellings. Checking that `function initialise(` exists passes either way.
    """
    offered = checklist_actions()
    assert "initialise" in offered, "the first step no longer offers to set the machine up"
    assert offered <= dispatch_table(), (
        f"the checklist offers actions the dispatcher cannot find: "
        f"{sorted(offered - dispatch_table())}"
    )


def test_every_action_in_the_table_reaches_a_function_that_exists() -> None:
    """The other direction: a name in the table whose body calls something undefined."""
    import re

    from admin.page import PAGE

    body = PAGE.replace("{{", "{").replace("}}", "}")
    defined = set(re.findall(r"(?:async )?function (\w+)\(", body))
    wired = re.findall(r"ACTIONS\.(\w+)\s*=\s*[^=]*=>\s*\{?\s*(\w+)\(", body)
    # A loop over nothing passes. The table has more entries than this matches - one has a
    # block body - so the floor is what the checklist itself needs to reach.
    assert len(wired) >= len(dispatch_table()) - 1, f"only {len(wired)} entries were read"
    for name, call in wired:
        assert call in defined, f"ACTIONS.{name} calls {call}(), which is not defined"


def test_the_ai_model_the_page_names_is_the_one_a_run_would_use(console) -> None:
    """The row exists so somebody can answer "which AI is this using" without asking. It
    has to be read from the ports, not declared beside them."""
    import ports

    said = console.setup()["ai_model"]
    assert said["adapter"] == ports.selected("llm")
    assert said["reaches_a_model"] is (said["adapter"] not in ("fake", "scripted"))
