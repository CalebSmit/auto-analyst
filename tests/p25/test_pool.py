"""The exit criteria: several engagements at once while one still serialises; a queued run
with a visible position and a stopped clock; a worker dying mid-step leaving a run that
resumes rather than a record that lies."""

from __future__ import annotations

import threading
from typing import Any

from fastapi.testclient import TestClient

from ops.console import Console, create_app
from ops.models import RunState, StepStatus
from ops.run_store import SqlRunStore
from ports.queue import JobState
from review.surface import ReviewSurface
from tests.p25.conftest import (
    HEND,
    MERC,
    NOVK,
    Stepper,
    events_of,
    max_concurrent_runs,
    overlap,
    plan_for,
    start,
)


def test_several_engagements_run_at_once_while_one_engagement_still_serialises(
    store: SqlRunStore, blobs: Any, make_pool: Any
) -> None:
    runner = Stepper(blobs, delay=0.005)
    pool = make_pool(runner, workers=2)
    hend_a = start(store, "run_hend_a", HEND)
    merc = start(store, "run_merc", MERC)
    novk = start(store, "run_novk", NOVK)
    hend_b = start(store, "run_hend_b", HEND)
    # The first two jobs must be inside a step at the same moment, or the step fails.
    barrier = runner.meet_at(plan_for(HEND).order[1], hend_a, merc)

    placed = {p.run_id: p for p in pool.submit_all([hend_a, merc, novk, hend_b])}
    assert placed[hend_b].waiting_on == "lock" and placed[hend_b].position == 1
    assert placed[hend_b].holder == hend_a
    assert [placed[r].position for r in (hend_a, merc, novk)] == [1, 2, 3]
    assert all(placed[r].waiting_on == "worker" for r in (hend_a, merc, novk))
    assert store.run(hend_a).state is RunState.QUEUED, "holds the lock; nothing allocated"
    assert pool.pressure().as_dict() == {
        "capacity": 2,
        "in_flight": 0,
        "waiting": 3,
        "behind_locks": 1,
        "saturated": False,
        "adapter": "in_process",
        "target": "local_process",
    }

    pool.work()

    for run_id in (hend_a, merc, novk, hend_b):
        assert store.run(run_id).state is RunState.HALTED, run_id
        assert len(events_of(store, run_id, "run.manifest.written")) == 1
        assert len(store.ledger(run_id)) == len(plan_for(HEND).order)
        assert store.run(run_id).active_seconds > 0
    assert not barrier.broken, "Henderson and Mercer were inside a step together"
    assert max_concurrent_runs(runner.intervals) <= 2, "never three at once"
    assert overlap(runner.span(hend_a), runner.span(hend_b)) == 0, "one engagement serialised"
    assert runner.span(hend_b)[0] >= runner.span(hend_a)[1]

    types = [e.type for e in store.events(hend_b)]
    order = [
        types.index(t) for t in ("lock.queued", "lock.acquired", "run.enqueued", "worker.started")
    ]
    assert order == sorted(order), types
    (started,) = events_of(store, hend_b, "worker.started")
    assert started.payload["target"] == {
        "kind": "local_process",
        "image": None,
        "max_parallelism": 2,
    }
    assert started.node_id == "queue_port" and started.payload["adapter"] == "in_process"
    assert events_of(store, hend_a, "lock.released") and pool.lock.holder(HEND) is None
    assert pool.placement(hend_b) is None, "finished runs are not placed anywhere"


def test_a_run_past_the_pools_capacity_waits_visibly_with_its_clock_stopped(
    store: SqlRunStore, bus: Any, blobs: Any, make_pool: Any
) -> None:
    runner = Stepper(blobs)
    pool = make_pool(runner, workers=1)
    first, second, third = (start(store, f"run_{e[:4].lower()}", e) for e in (HEND, MERC, NOVK))
    entered, release = runner.hold_at(first, plan_for(HEND).order[0])
    pool.submit_all([first, second, third])

    worker = threading.Thread(target=pool.work, name="the-pool")
    worker.start()
    try:
        assert entered.wait(10), "the first run never reached its first step"
        pressure = pool.pressure()
        assert (pressure.capacity, pressure.in_flight, pressure.waiting) == (1, 1, 2)
        assert pressure.saturated
        assert pool.placement(first).active and pool.placement(first).position == 0
        assert (pool.placement(second).position, pool.placement(third).position) == (1, 2)
        assert store.run(first).state is RunState.RUNNING, "a worker holds it"
        assert store.run(second).state is RunState.QUEUED, "nothing allocated"
        assert store.steps(second) == () and store.run(second).active_seconds == 0.0

        console = Console(store, bus, queue=pool)
        api = TestClient(create_app(console))
        page = api.get(f"/api/runs/{second}").json()
        assert page["state"] == "queued"
        assert page["queue"]["waiting_on"] == "worker" and page["queue"]["position"] == 1
        assert page["trace"]["nodes"]["queue_port"] == "active"
        rows = {r["run_id"]: r for r in api.get("/api/runs").json()}
        assert rows[third]["queue"]["position"] == 2 and rows[first]["queue"]["active"]
        view = api.get("/api/queue").json()
        assert view["attached"] and view["pressure"]["saturated"]
        assert [(w["run_id"], w["position"]) for w in view["waiting"]] == [(second, 1), (third, 2)]
        assert "behind the worker" in api.get("/").text or "queue" in api.get("/").text
    finally:
        release.set()
        worker.join(30)
    assert not worker.is_alive()
    for run_id in (first, second, third):
        assert store.run(run_id).state is RunState.HALTED
    assert pool.pressure().waiting == 0 and pool.pressure().in_flight == 0
    assert TestClient(create_app(Console(store, bus))).get("/api/queue").json()["attached"] is False


def test_a_worker_dying_mid_step_leaves_a_resumable_run_not_a_corrupt_one(
    store: SqlRunStore, blobs: Any, make_pool: Any
) -> None:
    runner = Stepper(blobs)
    pool = make_pool(runner, workers=1)
    run_id = start(store, "run_killed", HEND)
    order = plan_for(HEND).order
    lost_step = order[2]
    runner.kill.add((run_id, lost_step))

    job_id = pool.submit(run_id).job_id
    pool.work()

    # -- what the death left behind: two steps in the ledger, one started and never ended
    status = pool.queue.status(job_id)
    assert status.state is JobState.FAILED and status.worker_lost, status
    assert store.run(run_id).state is RunState.RUNNING, "the record still says a worker had it"
    assert pool.lock.holder(HEND).run_id == run_id  # type: ignore[union-attr]
    steps = {s.step_id: s for s in store.steps(run_id)}
    assert [steps[s].status for s in order[:2]] == [StepStatus.COMPLETED] * 2
    assert steps[lost_step].started_at and not steps[lost_step].ended_at
    assert steps[lost_step].status is not StepStatus.COMPLETED
    assert len(store.ledger(run_id)) == 2
    assert events_of(store, run_id, "worker.finished") == []
    completed = [e.step_id for e in store.events(run_id) if e.type == "step.completed"]
    assert lost_step not in completed

    # -- found from the record and the port, raised once, decided nothing
    (stranded,) = pool.stranded()
    assert stranded.step_id == lost_step and stranded.attempt == 1 and stranded.job_id == job_id
    assert "killed during" in stranded.error
    (lost,) = events_of(store, run_id, "worker.lost")
    assert lost.diagnostic_code == "PROCESS.WORKER_LOST" and lost.level == "error"
    assert "resume" in lost.payload["what_now"] and lost.payload["step_id"] == lost_step
    assert pool.stranded() and len(events_of(store, run_id, "worker.lost")) == 1
    assert store.run(run_id).state is RunState.RUNNING

    # -- resume is replay: the same job, the lost step re-attempted, nothing before it
    placed = pool.resume(run_id)
    assert placed.job_id == job_id and placed.waiting_on == "worker"
    (resumed,) = [e for e in events_of(store, run_id, "run.enqueued") if e.payload["resumed"]]
    assert resumed.payload["job_id"] == job_id
    pool.work()

    assert store.run(run_id).state is RunState.HALTED
    assert len(events_of(store, run_id, "run.manifest.written")) == 1
    ledger = store.ledger(run_id)
    assert len(ledger) == len(order) and len({e.step_key for e in ledger}) == len(order)
    steps = {s.step_id: s for s in store.steps(run_id)}
    assert steps[lost_step].attempts == 2 and steps[lost_step].status is StepStatus.COMPLETED
    assert all(steps[s].attempts == 1 for s in order if s != lost_step)
    assert [runner.calls[(run_id, s)] for s in order] == [1, 1, 2] + [1] * (len(order) - 3)
    assert [e.payload["attempt"] for e in events_of(store, run_id, "worker.started")] == [1, 2]
    (finished,) = events_of(store, run_id, "worker.finished")
    assert finished.payload["satisfied"] == 2 and finished.payload["executed"] == len(order) - 2
    assert pool.lock.holder(HEND) is None and pool.stranded() == ()


def test_a_blocked_run_holds_nothing_and_comes_back_through_resume(
    store: SqlRunStore, blobs: Any, make_pool: Any
) -> None:
    runner = Stepper(blobs)
    pool = make_pool(runner, workers=1)
    order = plan_for(HEND).order
    waiting = start(store, "run_waiting", HEND)
    runner.block.add((waiting, order[1]))
    pool.submit(waiting)
    pool.work()

    assert store.run(waiting).state is RunState.WAITING
    assert pool.lock.holder(HEND) is None, "a waiting run holds no lock"
    assert events_of(store, waiting, "lock.released")
    placed = pool.placement(waiting)
    assert placed is not None and placed.waiting_on is None and not placed.active

    # Another run on the same engagement takes the lock straight away.
    other = start(store, "run_other", HEND)
    assert pool.submit(other).waiting_on == "worker"
    assert pool.lock.holder(HEND).run_id == other  # type: ignore[union-attr]
    pool.work()
    assert store.run(other).state is RunState.HALTED

    # The person answered; the run comes back at the frontier.
    resumed = pool.resume(waiting)
    assert resumed.waiting_on == "worker" and resumed.holder == waiting
    assert store.run(waiting).state is RunState.WAITING, "re-enqueued, not yet taken up"
    pool.work()
    assert store.run(waiting).state is RunState.HALTED
    passes = events_of(store, waiting, "worker.finished")
    assert len(passes) == 2 and passes[-1].payload["satisfied"] == 1
    assert {s.step_id: s.attempts for s in store.steps(waiting)}[order[1]] == 2


def test_the_review_surfaces_resume_job_is_a_pass_like_any_other(
    store: SqlRunStore, bus: Any, blobs: Any, make_pool: Any
) -> None:
    """The surface submits `run.resume` through the port when the last open item is
    decided. The pool registered for that kind; the job holds the lock, runs one pass
    and lets go, the same as a fresh launch."""
    runner = Stepper(blobs)
    pool = make_pool(runner, workers=1)
    order = plan_for(HEND).order
    run_id = start(store, "run_reviewed", HEND)
    runner.block.add((run_id, order[1]))
    pool.submit(run_id)
    pool.work()
    assert store.run(run_id).state is RunState.WAITING

    surface = ReviewSurface(store, bus, pool.queue)
    (item,) = store.open_review_items(HEND)
    from ops.models import DecisionKind

    surface.decide(
        run_id,
        item.item_id,
        decided_by="Dana Whitfield",
        decision=DecisionKind.ACCEPTED,
        expected_version=item.version,
    )
    (resumed,) = events_of(store, run_id, "run.resumed")
    assert resumed.payload["job"] == "run.resume"
    assert store.run(run_id).state is RunState.WAITING
    pool.work()
    assert store.run(run_id).state is RunState.HALTED
    assert pool.queue.status(resumed.payload["job_id"]).state is JobState.SUCCEEDED
    assert pool.lock.holder(HEND) is None


def test_a_job_that_finds_the_lock_held_is_deferred_not_run(
    store: SqlRunStore, blobs: Any, make_pool: Any
) -> None:
    """A `run.resume` can arrive while another run has the deal. The job ends without
    running a pass; the run joins the lock's queue and is enqueued when the holder is
    done."""
    runner = Stepper(blobs)
    pool = make_pool(runner, workers=1)
    holder = start(store, "run_holder", HEND)
    latecomer = start(store, "run_late", HEND)
    pool.lock.acquire(HEND, holder)
    pool.queue.submit("run.resume", {"run_id": latecomer}, engagement_id=HEND)
    pool.submit(holder)
    pool.work()
    (deferred,) = events_of(store, latecomer, "worker.deferred")
    assert deferred.payload["holder"] == holder
    assert store.run(holder).state is RunState.HALTED
    assert store.run(latecomer).state is RunState.HALTED, "handed the lock, then run"
    assert runner.calls[(latecomer, plan_for(HEND).order[0])] == 1
