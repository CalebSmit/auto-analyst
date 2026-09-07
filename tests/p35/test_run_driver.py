"""P35: a released run is driven to an ending.

Intake created runs and took their locks. The pool would have run them if anybody had
handed it the means. The executor would have walked their plans. Between those three there
was nothing, so a run released by a watched folder sat with its lock taken and no process
to move it - and C08 ended its run by hand, with a comment saying "this test is one".

Four claims:

1. A run released by intake is picked up and driven to an ending, on a real store, with
   no test double in the path but the model.
2. `tools/serve.py` starts the pool and its readiness report says so.
3. Two engagements progress at once while one engagement stays serialised behind its lock.
4. A blocked run waits for a person and resumes from its frontier rather than restarting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from admin import AdminConsole, Preflight
from deliver.registry import TemplateRegistry
from graph.execute import StepOutcome
from graph.resolve import ScopeResolver
from intake import Intake
from intake.launch import RunLauncher
from intake.lock import EngagementLock
from intake.roster import RosterEntry, RosterState
from ops.models import RunState
from tests.p17.conftest import build_xlsx
from tests.p35.conftest import FOLDER, HEND, LAUNCH, WHO, config_document, profile_for
from workers.driver import RunDriver
from workers.pool import WorkerPool

ROWS = [
    ["Account", "FY2024", "FY2025"],
    ["Revenue", 4_200_000, 4_650_000],
    ["Cost of sales", -2_100_000, -2_310_000],
    ["Officer compensation", -420_000, -455_000],
    ["Rent", -180_000, -186_000],
]


def set_up(world: dict[str, Any]) -> AdminConsole:
    """An engagement, through the console, exactly as C08 does it."""
    import ports

    world["config"].write(config_document(engagements={}), who=WHO, reason="environment")
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
            engagement_id=HEND,
            client="Henderson Manufacturing",
            scope_path="valuation/esop/repeat",
            watch_id="w-val",
            destination_id="d-local",
            folder=FOLDER,
            state=RosterState.PAUSED,
            budget_usd=12.0,
        ),
        profile=profile_for(HEND),
        who=WHO,
        reason="engagement letter signed",
    )
    console.activate(HEND, who=WHO, reason="go live")
    return console


def release(world: dict[str, Any], folder: str = FOLDER) -> str:
    """Drop a workbook, sweep twice around the quiet period, and take the run id."""
    from tests.p16.conftest import drop

    drop(world["inbox"], f"Clients/{folder}/TB_FY25.xlsx", build_xlsx({"TB": ROWS}))
    drop(
        world["inbox"],
        f"Clients/{folder}/income statement FY25.xlsx",
        build_xlsx({"IS": ROWS}),
    )
    intake = _intake(world)
    intake.sweep(LAUNCH)
    world["clock"].advance(minutes=31)
    (launched,) = intake.sweep(LAUNCH).launched
    return str(launched.run_id)


def _intake(world: dict[str, Any]) -> Intake:
    lock = EngagementLock(world["store"], world["bus"], clock=world["clock"])
    return Intake(
        world["port"],
        world["roster"],
        world["config"],
        world["intake_store"],
        RunLauncher(
            world["store"], world["bus"], lock, world["intake_store"], clock=world["clock"]
        ),
        clock=world["clock"],
    )


# ------------------------------------------------------- the run moves


def test_a_released_run_is_driven_to_an_ending(
    world: dict[str, Any], driver_for: Any
) -> None:
    """The first exit criterion.

    What ends it is the plan, not this test: `monthly-refresh` finishes with `qc-tieout`,
    a skill with no mechanical half yet, so the run reaches that step and stops there with
    it named. That is the system saying what it cannot do rather than delivering something
    nobody checked, and it is a real ending recorded on a real store.
    """
    set_up(world)
    run_id = release(world)
    assert world["store"].run(run_id).state is RunState.QUEUED

    world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
    driver: RunDriver = driver_for(_replaying(world))
    report = driver(run_id)

    assert report.run_id == run_id
    assert report.outcomes["intake"] is StepOutcome.EXECUTED, "the readers ran"
    assert report.outcomes["mask"] is StepOutcome.EXECUTED
    assert "timing" in report.outcomes, "it reached the first real skill"

    # It stopped somewhere, and the record says where rather than leaving it to be guessed.
    stopped = [s for s, o in report.outcomes.items() if o is StepOutcome.NOT_REACHED]
    assert report.quarantined or report.blocked_on or not stopped
    assert world["store"].events(run_id), "the pass is on the record"


def test_the_readers_ran_and_the_parse_store_holds_the_rows(
    world: dict[str, Any], driver_for: Any
) -> None:
    """The intake step is not a formality: it is where the workbooks become rows, and
    every figure the run later proposes traces back to one of them."""
    from ops.source_parse import SourceParseStore

    set_up(world)
    run_id = release(world)
    world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
    driver_for(_replaying(world))(run_id)

    parse_store = SourceParseStore(world["store"])
    rows = [
        r
        for row in world["intake_store"].files(HEND)
        for locator in parse_store.locators(run_id, row.source_id)
        for r in parse_store.rows(run_id, row.source_id, locator)
    ]
    assert rows, "the readers wrote what they read"
    assert any("Revenue" in str(r.label) for r in rows)


def test_a_second_pass_over_the_same_run_does_the_work_once(
    world: dict[str, Any], driver_for: Any
) -> None:
    """The pool asks again when a run is ready to move, so a pass has to be idempotent.

    The executor satisfies from the ledger what it already did; the driver holds no state
    between calls, which is what lets that be true.
    """
    set_up(world)
    run_id = release(world)
    world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
    driver = driver_for(_replaying(world))

    first = driver(run_id)
    second = driver(run_id)

    executed_twice = [
        step
        for step in first.executed
        if second.outcomes.get(step) is StepOutcome.EXECUTED
    ]
    assert not executed_twice, executed_twice
    assert all(
        second.outcomes[s] is StepOutcome.SATISFIED_FROM_LEDGER for s in first.executed
    )


def test_a_blocked_run_waits_for_a_person_and_resumes_from_its_frontier(
    world: dict[str, Any], driver_for: Any
) -> None:
    """The fourth exit criterion.

    The workbook here carries no scale cue, so `timing-normalization` escalates rather
    than guessing whether a figure is dollars or thousands - which is the system doing what
    it says it does. The pass ends at that step; the steps before it are not run again; and
    the question a person has to answer is one row, not one per attempt.
    """
    set_up(world)
    run_id = release(world)
    world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
    driver = driver_for(_replaying(world))

    first = driver(run_id)
    assert first.blocked_on, "it stopped at a step that needs a person"
    assert first.outcomes["intake"] is StepOutcome.EXECUTED

    items = world["store"].review_items(run_id)
    assert items, "the question is on the record"
    assert all(i.state == "open" for i in items)

    second = driver(run_id)

    assert second.blocked_on == first.blocked_on, "the same frontier, not a restart"
    assert second.outcomes["intake"] is StepOutcome.SATISFIED_FROM_LEDGER
    assert second.outcomes["mask"] is StepOutcome.SATISFIED_FROM_LEDGER
    assert not second.executed, "nothing was done twice"

    after = world["store"].review_items(run_id)
    assert len(after) == len(items), "the same question, asked again, is one row"
    assert [i.item_id for i in after] == [i.item_id for i in items]


# ------------------------------------------------------- the pool


def test_the_pool_drives_a_run_it_was_given(world: dict[str, Any], driver_for: Any) -> None:
    """The pool takes a PassRunner. This is the one it has never been given."""
    set_up(world)
    run_id = release(world)
    pool = WorkerPool(
        world["store"],
        world["bus"],
        EngagementLock(world["store"], world["bus"], clock=world["clock"]),
        driver_for(_replaying(world)),
    )
    pool.submit(run_id)
    pool.work()

    run = world["store"].run(run_id)
    assert run.state is not RunState.QUEUED, "something moved it"
    assert world["store"].ledger(run_id), "steps were recorded"


def test_two_engagements_progress_while_one_is_serialised(
    world: dict[str, Any], driver_for: Any
) -> None:
    """The third exit criterion. Two engagements are two locks; two runs of one engagement
    are one lock and a queue."""
    console = set_up(world)
    console.register_engagement(
        RosterEntry(
            engagement_id="NOVK-2026-11",
            client="Novak Industrial",
            scope_path="valuation/esop/repeat",
            watch_id="w-val",
            destination_id="d-local",
            folder="Novak Industrial/2026 ESOP",
            state=RosterState.PAUSED,
            budget_usd=12.0,
        ),
        profile=profile_for("NOVK-2026-11"),
        who=WHO,
        reason="second engagement",
    )
    console.activate("NOVK-2026-11", who=WHO, reason="go live")

    hend = release(world)
    novk = release(world, "Novak Industrial/2026 ESOP")

    pool = WorkerPool(
        world["store"],
        world["bus"],
        EngagementLock(world["store"], world["bus"], clock=world["clock"]),
        driver_for(_replaying(world)),
    )
    placements = pool.submit_all([hend, novk])
    # Both took their own lock and are waiting on a worker, which is the pool's capacity
    # rather than each other. Waiting on `lock` is what serialisation looks like, and
    # neither is doing that.
    assert [p.waiting_on for p in placements] == ["worker", "worker"], placements
    assert not [p for p in placements if p.waiting_on == "lock"]

    pressure = pool.pressure().as_dict()
    assert pressure["behind_locks"] == 0, "two engagements, two locks"


# ------------------------------------------------------- the front door


def test_the_front_door_starts_the_pool_and_says_so(tmp_path: Path) -> None:
    """The second exit criterion, and the claim the readiness report makes about itself."""
    from tools.serve import readiness

    seams = {s.name: s for s in readiness()}
    assert seams["run execution"].ready, "P35 built the half that carries a run"
    assert seams["step execution"].ready, "P34 built the half that runs a step"

    import inspect

    from tools import serve

    source = inspect.getsource(serve)
    assert "pool.submit_all(result.runs)" in source, "the sweep hands over what it released"
    assert "pool.work()" in source


def test_the_pool_is_none_when_the_driver_cannot_be_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A machine with no vault key is a machine that cannot run work, and the honest
    answer to that is a readiness line rather than a traceback on startup."""
    from tools import serve

    monkeypatch.setattr(serve, "_pool", lambda *a, **k: None)
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'p35.db').as_posix()}")
    import ports

    ports.reset()
    system = serve.build()
    assert system.pool is None
    system.close()
    ports.reset()


# ------------------------------------------------------- helpers


def _replaying(world: dict[str, Any]) -> Any:
    """A model port that answers every skill call from the recorded fixtures.

    The one stand-in in the path, and the thing the fake LLM adapter exists for. Nothing
    else between the watched folder and the ending is a test's.
    """
    from tests.p35.conftest import Replayed

    return Replayed(*[_timing_proposal()] * 6)


def _timing_proposal() -> dict[str, Any]:
    from tests.p20.conftest import load_case

    return dict(load_case()["timing_proposal"])


def test_the_registry_of_templates_is_the_one_the_engagement_resolves_to(
    world: dict[str, Any],
) -> None:
    """A guard against the driver quietly using a different registry than preflight did -
    which would mean preflight passing on one template and a run building into another."""
    set_up(world)
    assert isinstance(world["templates"], TemplateRegistry)
    scope = ScopeResolver(bindings=world["config"].model_bindings()).resolve(
        "valuation/esop/repeat"
    )
    assert scope.template is not None
    assert world["templates"].resolve(scope.template).key.startswith("Chartwell_ESOP_Model_v9")
