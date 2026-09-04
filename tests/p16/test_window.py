"""The intake window: quiet and complete enough, then exactly one run over the whole set.

A file arrives when a sweep first sees it - the system's clock, not the client's file
system - so every test drops a file, sweeps, and only then moves the clock.
"""

from __future__ import annotations

from pathlib import Path

import ports
from graph.recipes import load_recipe
from intake import Intake
from intake.store import IntakeStore
from intake.window import IntakeWindow
from ops.manifest import close_out, manifest_path
from ops.models import Outcome, RunState
from ops.run_store import SqlRunStore
from tests.p16.conftest import HEND, LAUNCH, Clock, drop, events_of, hend


def test_six_files_over_ten_minutes_produce_one_run(
    inbox: Path, intake: Intake, clock: Clock, store: SqlRunStore
) -> None:
    """The exit criterion. A sweep after each arrival finds the set not yet quiet; the
    sweep thirty minutes after the last arrival releases one run over all six."""
    names = [
        "TB_FY25.xlsx",
        "income statement FY25.pdf",
        "balance sheet FY25.pdf",
        "TB_FY24.xlsx",
        "income statement FY24.pdf",
        "balance sheet FY24.pdf",
    ]
    for n, name in enumerate(names):
        drop(inbox, hend(name), f"file {n}")
        result = intake.sweep(LAUNCH)
        assert result.runs == [], f"a run started after file {n}"
        assert result.verdicts[HEND].reason.startswith("not quiet")
        clock.advance(minutes=2)

    clock.advance(minutes=27)  # 29 minutes after the sixth arrival
    assert intake.sweep(LAUNCH).runs == [], "29 minutes is not quiet yet"
    clock.advance(minutes=1)
    result = intake.sweep(LAUNCH)

    assert len(result.runs) == 1
    (launched,) = result.launched
    assert launched.sources == 6 and launched.lock.acquired and launched.gaps == ()
    run = store.run(launched.run_id)
    assert run.state is RunState.QUEUED, "launched and holding the lock; no worker yet"
    assert sorted(s["filename"] for s in run.sources) == sorted(names)
    assert all(s["source_version"] == 1 for s in run.sources)
    assert len(store.runs(HEND)) == 1

    again = intake.sweep(LAUNCH)
    assert again.runs == [] and again.verdicts[HEND].reason == "nothing new has arrived"


def test_a_run_waits_for_the_recipes_required_types(
    inbox: Path, intake: Intake, clock: Clock, intake_store: IntakeStore, store: SqlRunStore
) -> None:
    """Only a trial balance arrives. monthly-refresh also needs financial statements, so
    the window waits - then at max_wait proceeds with a recorded coverage gap and a
    review item, never treating what arrived as what exists."""
    drop(inbox, hend("TB_FY25.xlsx"), "tb")
    intake.sweep(LAUNCH)
    clock.advance(minutes=31)
    result = intake.sweep(LAUNCH)
    assert result.runs == []
    assert result.verdicts[HEND].reason.startswith(
        "quiet but incomplete: missing financial_statements"
    )

    clock.advance(hours=23, minutes=27)  # 23h58 after arrival
    assert intake.sweep(LAUNCH).runs == []
    clock.advance(minutes=3)
    result = intake.sweep(LAUNCH)

    (launched,) = result.launched
    assert launched.gaps == ("financial_statements",)
    run = store.run(launched.run_id)
    assert len(run.coverage_gaps) == 1
    assert run.coverage_gaps[0]["what"] == "required document type financial_statements"
    assert "explicit" in run.coverage_gaps[0]["why"]
    (item,) = store.review_items(launched.run_id)
    assert item.kind == "coverage_gap" and item.item_id == launched.review_item_id
    assert item.detail["missing_types"] == ["financial_statements"]
    assert events_of(store, launched.run_id, "hitl.item.queued")


def test_a_reupload_becomes_version_two_and_supersedes_without_overwriting(
    inbox: Path, intake: Intake, clock: Clock, store: SqlRunStore, bus, intake_store: IntakeStore
) -> None:
    """The exit criterion. Run 1 delivers over TB v1 + financials; the TB is re-uploaded;
    run 2 consumes the whole set - TB v2 and the untouched financials - and run 1 is
    superseded with its manifest exactly where and as it was."""
    drop(inbox, hend("TB_FY25.xlsx"), "tb v1")
    drop(inbox, hend("financials FY25.pdf"), "fs")
    intake.sweep(LAUNCH)
    clock.advance(minutes=31)
    (first,) = intake.sweep(LAUNCH).launched
    delivery = ports.get_delivery()
    store.transition(first.run_id, RunState.RUNNING, reason="a worker holds it")  # this test is one
    # Nothing read these sources - no reader ran - so the record cannot support `clean`;
    # since P23 the outcome has to be one the scorecard computes.
    closed = close_out(
        store, first.run_id, RunState.DELIVERED, Outcome.RELEASED_WITH_REVIEW, delivery, bus=bus
    )
    path = manifest_path(HEND, first.run_id)
    on_disk = delivery.root / path
    before = on_disk.read_bytes()
    intake.launcher.lock.release(HEND, first.run_id)

    clock.advance(hours=2)
    v2 = drop(inbox, hend("TB_FY25.xlsx"), "tb v2 - client corrected the FY25 close")
    intake.sweep(LAUNCH)
    clock.advance(minutes=31)
    result = intake.sweep(LAUNCH)

    (second,) = result.launched
    assert second.superseded == (first.run_id,)
    run2 = store.run(second.run_id)
    by_name = {s["filename"]: s for s in run2.sources}
    assert by_name["TB_FY25.xlsx"]["source_version"] == 2
    assert by_name["TB_FY25.xlsx"]["source_id"] == v2
    assert by_name["financials FY25.pdf"]["source_version"] == 1, "the whole set, never a delta"

    run1 = store.run(first.run_id)
    assert run1.state is RunState.SUPERSEDED and run1.superseded_by == second.run_id
    assert run1.outcome is Outcome.RELEASED_WITH_REVIEW and run1.ended_at is not None, (
        "kept what it reached"
    )
    assert [a.path for a in store.artifacts(first.run_id)] == [path]
    assert on_disk.read_bytes() == before, "the manifest was not overwritten"
    assert manifest_path(HEND, second.run_id) != path
    assert closed.manifest["run_id"] == first.run_id
    superseded = events_of(store, first.run_id, "run.superseded")
    assert superseded[0].payload["superseded_by"] == second.run_id


def test_the_window_evaluates_deterministically(
    inbox: Path, intake: Intake, clock: Clock, intake_store: IntakeStore, config
) -> None:
    window = IntakeWindow(intake_store, config, clock=clock)
    recipe = load_recipe("monthly-refresh")
    assert recipe.required_types == ("trial_balance", "financial_statements")
    assert not window.evaluate(HEND, recipe).release
    drop(inbox, hend("TB_FY25.xlsx"), "tb")
    drop(inbox, hend("financials FY25.pdf"), "fs")
    intake.sweep(LAUNCH)
    v = window.evaluate(HEND, recipe)
    assert not v.release and v.complete and v.pending and v.quiet_for.total_seconds() == 0
    clock.advance(minutes=30)
    v = window.evaluate(HEND, recipe)
    assert v.release and v.reason.endswith("one run over 2 file(s)")


def test_pending_files_are_consumed_by_the_run_that_took_them(
    inbox: Path, intake: Intake, clock: Clock, intake_store: IntakeStore
) -> None:
    drop(inbox, hend("TB_FY25.xlsx"), "tb")
    drop(inbox, hend("financials FY25.pdf"), "fs")
    intake.sweep(LAUNCH)
    clock.advance(minutes=31)
    (launched,) = intake.sweep(LAUNCH).launched
    assert {r.state for r in intake_store.files(HEND)} == {"consumed"}
    assert {r.consumed_by for r in intake_store.files(HEND)} == {launched.run_id}
