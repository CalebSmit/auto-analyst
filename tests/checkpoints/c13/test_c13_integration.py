"""Checkpoint C13 - the system runs.

Proves: a file landing in a watched folder becomes work the system carries, with nothing in
the path that exists only in a test.

Three phases meet here. P34 joined the executor to the dispatcher, so a step of a plan runs
through the harness. P35 joined the pool to a released run, so something carries a whole
run. P36 made the name on every recorded change one the system resolved rather than one the
caller sent. Each is a seam between two finished halves, and the finding this whole block
came from is that a suite of component tests cannot notice a seam that was never made.

What this asks is the question none of those phases asks alone: does a file arriving cause
work to happen, and is what happened attributable afterwards.
"""

from __future__ import annotations

from typing import Any

from graph.execute import StepOutcome
from ops.models import RunState
from tests.p35.test_run_driver import ROWS, release, set_up


def test_a_file_landing_in_a_folder_becomes_work_the_system_carries(
    world: dict[str, Any], driver_for: Any
) -> None:
    """The checkpoint itself, in the order somebody would watch it happen.

    An engagement is set up through the console. Two workbooks land in its folder. The
    sweep holds them through the quiet period and releases a run with the lock taken. The
    pool picks it up. The readers turn the workbooks into rows, the payload is masked, and
    the first real skill runs - and stops, because this workbook does not say whether its
    figures are dollars or thousands, and the system escalates rather than guessing.

    That ending is the point. Every step of it is a component that was already tested; what
    was never tested before this block is that they add up to something that moves.
    """
    from tests.p35.test_run_driver import _replaying

    set_up(world)
    run_id = release(world)
    assert world["store"].run(run_id).state is RunState.QUEUED, "released, holding its lock"

    world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
    report = driver_for(_replaying(world))(run_id)

    assert report.outcomes["intake"] is StepOutcome.EXECUTED, "the workbooks were read"
    assert report.outcomes["mask"] is StepOutcome.EXECUTED
    assert report.blocked_on, "it stopped where a person is needed"

    items = world["store"].review_items(run_id)
    assert items, "and the question is on the record, not in a log line"
    assert all(item.state == "open" for item in items)


def test_what_happened_is_attributable_afterwards(
    world: dict[str, Any], driver_for: Any
) -> None:
    """P36's half of the checkpoint.

    A run that moved and a change log nobody can attribute is worse than no change log:
    it reads as evidence. Every configuration change behind this run carries the name the
    system resolved, and the run's own events carry the run rather than a name at all -
    which is the right split, because a run is not a person.
    """
    from tests.p35.test_run_driver import _replaying

    console = set_up(world)
    run_id = release(world)
    world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
    driver_for(_replaying(world))(run_id)

    changes = console.changes()
    assert changes, "setting the engagement up is on the record"
    assert all(change.who and change.reason for change in changes)

    events = world["store"].events(run_id)
    assert events, "and so is what the run did"
    assert all(event.run_id == run_id for event in events)


def test_the_readers_the_masker_and_the_model_were_all_real(
    world: dict[str, Any], driver_for: Any
) -> None:
    """No test double in the path but the model port, which is what the fake LLM adapter
    is for. The rows are in the parse store, the payload the model saw was masked, and
    neither was arranged by this test."""
    from ops.source_parse import SourceParseStore
    from tests.p35.test_run_driver import _replaying

    set_up(world)
    run_id = release(world)
    world["store"].transition(run_id, RunState.RUNNING, reason="a worker holds it")
    port = _replaying(world)
    driver_for(port)(run_id)

    parse_store = SourceParseStore(world["store"])
    rows = [
        row
        for record in world["intake_store"].files("HEND-2026-04")
        for locator in parse_store.locators(run_id, record.source_id)
        for row in parse_store.rows(run_id, record.source_id, locator)
    ]
    assert rows, "the readers wrote what they read"
    assert {str(r.label) for r in rows} & {str(cell[0]) for cell in ROWS[1:]}

    if port.requests:
        sent = port.requests[0]
        assert "Henderson Manufacturing" not in sent.messages[0].content, "masked"


def test_every_seam_reads_as_joined_and_says_why() -> None:
    """The readiness report is the answer to "does this work yet", and it is derived from
    the code rather than written down - which is how it came to say that step execution was
    joined while run execution was not, in the hour between two phases landing."""
    from tools.serve import readiness

    seams = {seam.name: seam for seam in readiness()}
    assert set(seams) == {
        "admin",
        "ops console",
        "intake",
        "step execution",
        "run execution",
        # P55. It was joined in neither direction: the Precedent Store was built, handed to
        # the lookup tool and to the driver, and not to the thing that reads it - so there
        # was a seam here that nobody had noticed was a seam.
        "precedent retrieval",
        # P74. Reported beside the seams because it is the first thing that matters on a
        # machine doing real work, but it waits on software rather than on wiring - so it
        # is excluded from "every seam is joined" below, or a clone with no OCR engine
        # would read as an unfinished build.
        "reading a scan",
    }
    assert all(seam.ready for seam in seams.values() if not seam.needs_installing), [
        seam.name for seam in seams.values() if not seam.ready and not seam.needs_installing
    ]


def test_the_limit_that_is_left_is_named_where_people_look() -> None:
    """A run cannot finish, because two skills in the shipped recipes have no mechanical
    half. That is a real limit, it is not plumbing, and a system that hid it would be
    claiming to do the job it stops short of."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    for where in ("docs/USING.md", "BUILD/OPEN.md"):
        assert "qc-tieout" in (root / where).read_text(encoding="utf-8"), where

    from harness.procedures import PROCEDURES

    assert "qc-tieout" not in PROCEDURES, "if this now exists, the documents are stale"
    assert "ddr-tagging" not in PROCEDURES
