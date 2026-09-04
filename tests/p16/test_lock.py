"""The engagement lock: one run at a time per deal, a visible queue, a timeout that alerts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intake import Intake
from intake.lock import EngagementLock
from ops.models import RunState
from ops.run_store import SqlRunStore
from tests.p16.conftest import HEND, LAUNCH, PLAN_HASH, ROOT, VERSIONS, Clock, drop, events_of, hend


def start(store: SqlRunStore, run_id: str, engagement_id: str = HEND) -> str:
    store.start_run(
        run_id=run_id, engagement_id=engagement_id, plan_hash=PLAN_HASH, versions=VERSIONS
    )
    return run_id


def test_two_runs_launched_in_the_same_second_serialise_on_the_lock(
    lock: EngagementLock, store: SqlRunStore, clock: Clock
) -> None:
    """The exit criterion. The first insert wins; the second is queued, visibly, with the
    code the fixture expects - and its run stays queued rather than running alongside."""
    start(store, "run_a")
    start(store, "run_b")
    first = lock.acquire(HEND, "run_a")
    clock.advance(seconds=0.4)
    second = lock.acquire(HEND, "run_b")

    assert first.acquired and store.run("run_a").state is RunState.QUEUED, "granted, not running"
    assert not second.acquired and second.position == 1
    assert second.code == "PROCESS.ENGAGEMENT_LOCKED"
    assert store.run("run_b").state is RunState.QUEUED
    assert lock.holder(HEND).run_id == "run_a"  # type: ignore[union-attr]
    assert [q.run_id for q in lock.queue(HEND)] == ["run_b"]
    queued = events_of(store, "run_b", "lock.queued")
    assert queued and queued[0].payload["holder"] == "run_a"


def test_releasing_hands_the_lock_to_the_next_in_the_queue(
    lock: EngagementLock, store: SqlRunStore
) -> None:
    for run_id in ("run_a", "run_b", "run_c"):
        start(store, run_id)
        lock.acquire(HEND, run_id)
    assert [q.run_id for q in lock.queue(HEND)] == ["run_b", "run_c"]
    promoted = lock.release(HEND, "run_a")
    assert promoted is not None and promoted.acquired and promoted.run_id == "run_b"
    assert store.run("run_b").state is RunState.QUEUED, "the lock grants; a worker's pass runs"
    assert [q.run_id for q in lock.queue(HEND)] == ["run_c"]
    assert lock.release(HEND, "run_b") is not None
    assert lock.release(HEND, "run_c") is None
    assert lock.holder(HEND) is None


def test_only_the_holder_can_release(lock: EngagementLock, store: SqlRunStore) -> None:
    start(store, "run_a")
    start(store, "run_b")
    lock.acquire(HEND, "run_a")
    with pytest.raises(PermissionError, match="does not hold"):
        lock.release(HEND, "run_b")
    assert lock.holder(HEND).run_id == "run_a"  # type: ignore[union-attr]


def test_a_lock_held_past_its_timeout_is_an_incident_not_a_release(
    lock: EngagementLock, store: SqlRunStore, clock: Clock
) -> None:
    start(store, "run_a")
    lock.acquire(HEND, "run_a")
    clock.advance(hours=5, minutes=59)
    assert lock.overdue() == ()
    clock.advance(minutes=2)
    (late,) = lock.overdue()
    assert late.run_id == "run_a"
    assert lock.holder(HEND).run_id == "run_a", "never force-released"  # type: ignore[union-attr]
    alert = events_of(store, "run_a", "lock.timeout")
    assert len(alert) == 1 and alert[0].diagnostic_code == "PROCESS.RUN_STALLED"
    assert alert[0].level == "error"


def test_there_is_no_way_to_force_release() -> None:
    for forbidden in ("force", "clear", "break", "steal", "expire"):
        assert not any(forbidden in name for name in dir(EngagementLock)), forbidden


def test_the_fixture_fires_engagement_locked(
    lock: EngagementLock, store: SqlRunStore, clock: Clock
) -> None:
    body = json.loads(
        (ROOT / "fixtures" / "guards" / "engagement_lock_double_launch.json").read_text(
            encoding="utf-8"
        )
    )
    results = []
    for launch in body["launches"]:
        start(store, launch["run_id"], body["engagement_id"])
        results.append(lock.acquire(body["engagement_id"], launch["run_id"]))
    assert results[0].acquired and results[1].code == "PROCESS.ENGAGEMENT_LOCKED"


def test_a_release_while_a_run_holds_the_lock_queues_the_new_run(
    inbox: Path, intake: Intake, clock: Clock, store: SqlRunStore
) -> None:
    """The window releases; the lock decides whether it runs now. A second intake set on
    an engagement mid-run queues behind the run in flight."""
    drop(inbox, hend("TB_FY25.xlsx"), "tb")
    drop(inbox, hend("financials FY25.pdf"), "fs")
    intake.sweep(LAUNCH)
    clock.advance(minutes=31)
    (first,) = intake.sweep(LAUNCH).launched
    assert first.lock.acquired

    drop(inbox, hend("TB_FY24.xlsx"), "prior year, late")
    intake.sweep(LAUNCH)
    clock.advance(minutes=31)
    (second,) = intake.sweep(LAUNCH).launched
    assert second.queued and second.lock.position == 1
    assert store.run(second.run_id).state is RunState.QUEUED
    assert store.run(first.run_id).state is RunState.QUEUED, "holds the lock; no worker yet"
