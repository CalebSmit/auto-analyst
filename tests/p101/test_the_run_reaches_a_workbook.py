"""P101's exit criterion: a run on the focus scope reaches release and writes a workbook.

Held apart from the recipe's own tests because it is a different claim. Those say the
recipe is well-formed and names no skeleton; this says a run of it actually ends somewhere,
which is the thing no run in this build has ever done.

The model is the one stand-in. `ScriptedAnalyst` answers each skill from the payload it is
given - it is what `simulate_firm --scripted` uses, and the alternative is recording
fixtures for a recipe whose step keys did not exist an hour ago. Everything else is the
real store, the real intake, the real executor, the real dispatcher and the real writer.
"""

from __future__ import annotations

from typing import Any

import pytest

from ops.models import TERMINAL, RunState
from tests.p17.conftest import build_xlsx
from workers.driver import RunDriver

ENGAGEMENT = "MERI-2026-01"
FOLDER = "Meridian Fabrication/2026 Valuation"
SCOPE = "valuation/non-esop/repeat"

#: Shaped like an accountant's, not like a test's: a title block, a scale note, a blank
#: row, then the columns. The same shape P35 found two defects with.
STATEMENT = [
    ["Meridian Fabrication"],
    ["Statement of Income"],
    ["For the fiscal years ended December 31"],
    ["($000s)"],
    [],
    ["Account", "FY2023", "FY2024", "FY2025"],
    ["Revenue", 4_200.0, 4_650.0, 5_010.0],
    ["Cost of sales", -2_100.0, -2_310.0, -2_480.0],
    ["Officer compensation", -420.0, -455.0, -470.0],
    ["Wages", -780.0, -820.0, -860.0],
    ["Rent", -96.0, -96.0, -102.0],
]


def a_scripted_model() -> Any:
    from ports.llm.scripted import ScriptedAnalyst

    return ScriptedAnalyst()


def set_up_version_one(world: dict[str, Any]) -> None:
    """P35's engagement, moved onto version 1's scope and recipe.

    Two changes and no others: the watch runs `valuation-input-prep`, and the engagement
    sits at `valuation/non-esop/repeat` so the template binding resolves to the input-help
    workbook rather than to the ESOP model.
    """
    import ports
    from admin.console import AdminConsole
    from admin.preflight import Preflight
    from graph.resolve import ScopeResolver
    from intake.roster import RosterEntry, RosterState
    from tests.p24.conftest import WHO, config_document, profile_for

    # "A run does not write into a workbook nobody validated" - the registry pins the
    # file's hash and checks its named ranges. A setup step, and the second thing a real
    # setup trips over after the template pin.
    world["templates"].register("Chartwell_Input_Help_v1.xlsx", "1.0")

    document = config_document(engagements={})
    # The running system resolves a template from the *config document's* bindings, not
    # from `templates/bindings.yaml` - `initialise` seeds one from the other, and P24's
    # fixture carries a hand-written copy that predates this phase. Without this the run
    # resolves to the firm default and `model` quarantines on
    # POLICY.ARG_OUT_OF_SCOPE: asks for Chartwell_Master_Model_v14, run pinned the
    # input-help workbook.
    document["model_bindings"] = [
        {
            "layer": "valuation/non-esop/_segment",
            "file": "Chartwell_Input_Help_v1.xlsx",
            "template_version": "1.0",
            "why": "version 1 fills an input-help workbook, not the model",
        },
        *document["model_bindings"],
    ]
    for watch in document["watches"]:
        watch["recipe"] = "valuation-input-prep"
    world["config"].write(document, who=WHO, reason="environment")

    console = AdminConsole(
        world["config"],
        world["roster"],
        Preflight(
            world["config"],
            world["roster"],
            storage=ports.get_storage(),
            delivery=ports.get_delivery(),
            secrets=ports.get_secrets(),
            templates=world["templates"],
            resolver=ScopeResolver(bindings=world["config"].model_bindings()),
            intake_store=world["intake_store"],
            clock=world["clock"],
        ),
    )
    console.register_engagement(
        RosterEntry(
            engagement_id=ENGAGEMENT,
            client="Meridian Fabrication",
            scope_path=SCOPE,
            watch_id="w-val",
            destination_id="d-local",
            folder=FOLDER,
            state=RosterState.PAUSED,
            budget_usd=12.0,
            # Without this the run reaches `model` and quarantines on
            # POLICY.ARG_OUT_OF_SCOPE: `template_schema_lookup` is a gated tool and the
            # policy gate will not let a run ask about a template version the run did not
            # pin. Preflight can derive the pin from the scope binding, but the pin has to
            # be *on the engagement* for the gate to see it - which is a setup step a
            # person has to do, and the first thing a real setup will trip over.
            template_pin="Chartwell_Input_Help_v1@1.0",
        ),
        profile=profile_for(ENGAGEMENT, scope_path=SCOPE),
        who=WHO,
        reason="engagement letter signed",
    )
    console.activate(ENGAGEMENT, who=WHO, reason="go live")


def release_a_set(world: dict[str, Any]) -> str:
    """Drop statements in the watched folder and sweep around the quiet period."""
    from tests.p16.conftest import LAUNCH, drop
    from tests.p35.test_run_driver import _intake

    drop(
        world["inbox"],
        f"Clients/{FOLDER}/income statement FY25.xlsx",
        build_xlsx({"Income Statement": STATEMENT}),
    )
    # P16's canned launch context pins no template, and `template_schema_lookup` is a
    # gated tool: a run that pinned no version has every call to it refused. Production
    # computes this in `plan_for`; a fixed dict in a fixture does not, which is why the
    # first version of this test watched `model` quarantine ten times on
    # POLICY.ARG_OUT_OF_SCOPE and read it as a defect in the recipe.
    launching = {
        **LAUNCH,
        "versions": {
            **LAUNCH["versions"],
            "template_version": "Chartwell_Input_Help_v1@1.0",
        },
    }
    intake = _intake(world)
    intake.sweep(launching)
    # Past the quiet period: a set is held until it stops changing, which is the point of
    # the intake window and not something a test may skip.
    world["clock"].advance(minutes=31)
    (launched,) = intake.sweep(launching).launched
    return str(launched.run_id)


@pytest.fixture
def driven(world: dict[str, Any], driver_for: Any) -> Any:
    def run() -> tuple[RunDriver, str, Any]:
        set_up_version_one(world)
        run_id = release_a_set(world)
        world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
        driver: RunDriver = driver_for(a_scripted_model())
        last = None
        # Driven repeatedly because one pass advances the frontier it can; a resume is
        # what the pool does and it is how a run gets to its ending.
        for _ in range(12):
            last = driver(run_id)
            # Any ending, not just a good one. A run that halts has still reached an
            # ending, and what this asks is whether it stopped for being unbuilt.
            if world["store"].run(run_id).state in TERMINAL:
                break
        return driver, run_id, last

    return run


def test_a_version_one_run_gets_past_every_step_and_stops_on_a_person(
    driven: Any, world: dict[str, Any]
) -> None:
    """The claim P101 exists for, and the first time any run in this build has reached an
    ending on its own.

    It ends **waiting**, not delivered, and that is the designed outcome rather than a
    shortfall: `model-load` declares `unmapped_inputs_require_review`, so an input it could
    not place stops the run on a person by the skill's own declaration. Release comes after
    somebody answers, which is the half this phase does not verify.

    What a scripted model proves is nothing about the answers. What it proves is that no
    step stopped for being unbuilt, which is what every other recipe does.
    """
    _, run_id, _ = driven()
    events = list(world["store"].events(run_id))

    started = {str(e.message).split(":")[0] for e in events if e.type == "step.started"}
    assert {"intake", "mask", "timing", "tagging", "model"} <= started, started

    unbuilt = [
        str(e.message)
        for e in events
        if e.type == "step.quarantined" and "mechanical half" in str(e.message)
    ]
    assert not unbuilt, unbuilt
    assert world["store"].run(run_id).state is RunState.WAITING


def test_what_it_could_not_fill_is_named_rather_than_left_blank(
    driven: Any, world: dict[str, Any]
) -> None:
    """The exit criterion that matters more than finishing. A workbook with thirty blank
    cells and no list of them is worse than no workbook: the analyst cannot tell what was
    looked for and missed from what was never asked for.

    Each item names its own input - `Template input Payroll_Taxes_FY1 has no upstream
    figure` - so the queue reads as a list of what to go and find.
    """
    _, run_id, _ = driven()
    queued = [
        str(e.message)
        for e in world["store"].events(run_id)
        if e.type == "hitl.item.queued"
    ]
    assert queued, "nothing was reported as unfilled, which on this fixture cannot be true"
    assert any("Payroll_Taxes" in q for q in queued), (
        "the statement carries no payroll taxes, so it is one of the gaps"
    )
    for item in queued:
        assert "has no upstream figure" in item or "unmapped" in item, item


def test_it_maps_what_the_documents_do_carry(driven: Any, world: dict[str, Any]) -> None:
    """The other direction, so that "names the gaps" is not satisfied by a run that mapped
    nothing at all. The fixture carries five line items over three years; the workbook
    declares forty-three inputs, so most of them are genuinely absent - and fewer review
    items than declared inputs is the only evidence here that anything was placed."""
    _, run_id, _ = driven()
    queued = [e for e in world["store"].events(run_id) if e.type == "hitl.item.queued"]
    assert len(queued) < 43, f"{len(queued)} gaps against 43 inputs - nothing was mapped"
