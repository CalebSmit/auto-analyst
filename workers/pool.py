"""The Worker Pool: several engagements at once, one run at a time within each.

A nightly sweep over seven active engagements cannot run one at a time inside a
four-hour per-run ceiling. So a run goes to the Job Queue Port as data - its id and its
engagement, never a closure - and the bounded pool behind the port executes passes on as
many runs at once as the Compute Target allows. The Engagement Lock still serialises
within one deal: a run holds the lock or waits behind it, and only a lock holder is ever
handed to a worker.

What happens, in order, and each step is on the record:

1. `submit(run_id)` takes the lock or joins the lock's queue. A holder is enqueued as a
   `run.pass` job and the record gets `run.enqueued` with its position in the pool. A
   run behind the lock gets nothing more: the lock already recorded `lock.queued` with
   its position, and it is enqueued when the holder is done.
2. A worker takes the job: `worker.started`, then one pass of the executor - which is
   the moment the run becomes *running* - then `worker.finished`. Nothing is allocated
   before that moment, so the wall-clock budget is not ticking while a run waits.
3. After every pass the lock is released, whichever way the pass ended. A pass that
   blocked left the run waiting on a person; one that quarantined left it held; one that
   finished closed it out. None of them holds a process, so none of them holds the lock,
   and the next run queued on that engagement takes it and is enqueued in turn.
4. A worker that dies mid-step leaves a job that ended without a result and a step that
   started and never ended. `stranded()` finds those from the record and the port and
   raises `worker.lost` once per episode; `resume()` retries the job under its own id.
   The executor satisfies every completed step from the ledger, so the resumed pass
   re-attempts exactly the step that was lost and nothing before it.

Backpressure is a fact reported, never a refusal: a run past the pool's capacity waits
with a visible position, and `pressure()` says how many are waiting against how many can
run. Nothing is dropped, and nothing is started that the pool cannot run.

The pool imports no adapter. Which queue answers is `AA_QUEUE_ADAPTER`, and swapping the
in-process pool for Redis + RQ changes nothing here - that is the exit criterion, and the
import-boundary test is what keeps it true.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import ports
from graph.execute import ExecutionReport
from intake.lock import EngagementLock
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import RunRecord, RunStore
from ports.compute import ComputeTarget
from ports.queue import Job, JobState, JobStatus
from registries.errors import WORKER_LOST, diagnose

__all__ = ["PASS_KINDS", "PassRunner", "Placement", "Pressure", "Stranded", "WorkerPool"]

NODE = "queue_port"
PASS_KINDS = ("run.pass", "run.resume")
"""Both kinds run one pass. `run.resume` is what the Review Surface submits when the
last open item on a waiting run is decided; it is the same operation, because resume
is replay."""

PassRunner = Callable[[str], ExecutionReport]
"""One pass of the executor over a run, by id, and whatever ending the host attaches to
a finished pass. Registered by the process that hosts the pool; the payload carries the
run id and nothing else, which is what lets a worker in another process pick it up."""

WAITING_ON_LOCK = "lock"
WAITING_ON_WORKER = "worker"


@dataclass(frozen=True)
class Placement:
    """Where a run stands: on a worker, behind the lock, or behind the pool."""

    run_id: str
    engagement_id: str
    waiting_on: str | None
    """`lock`, `worker`, or None when a worker holds it or nothing is allocated."""
    position: int
    """1 is next. 0 when not waiting."""
    job_id: str | None = None
    holder: str | None = None
    """The run holding the engagement lock."""
    active: bool = False
    """A worker holds it right now."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "engagement_id": self.engagement_id,
            "waiting_on": self.waiting_on,
            "position": self.position,
            "job_id": self.job_id,
            "holder": self.holder,
            "active": self.active,
        }


@dataclass(frozen=True)
class Pressure:
    """How much is waiting against how much can run. The backpressure signal."""

    capacity: int
    in_flight: int
    waiting: int
    """Runs enqueued for a worker and not yet taken up."""
    behind_locks: int
    """Runs queued on an engagement lock. Not the pool's to run yet."""
    adapter: str
    target: str

    @property
    def saturated(self) -> bool:
        return self.in_flight >= self.capacity and self.waiting > 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "capacity": self.capacity,
            "in_flight": self.in_flight,
            "waiting": self.waiting,
            "behind_locks": self.behind_locks,
            "saturated": self.saturated,
            "adapter": self.adapter,
            "target": self.target,
        }


@dataclass(frozen=True)
class Stranded:
    """A run whose worker is gone. The record says a step started; the port says the job
    ended without a result; nothing says the step finished."""

    run_id: str
    engagement_id: str
    job_id: str
    attempt: int
    step_id: str | None
    error: str


class WorkerPool:
    def __init__(
        self,
        store: RunStore,
        bus: EventBus,
        lock: EngagementLock,
        passes: PassRunner,
        *,
        queue: Any | None = None,
        compute: Any | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.bus = bus
        self.lock = lock
        self.passes = passes
        self.queue = queue or ports.get_queue()
        self.compute = compute or ports.get_compute()
        self.target: ComputeTarget = self.compute.target()
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        self._jobs: dict[str, str] = {}
        for kind in PASS_KINDS:
            self.queue.register(kind, self._perform)

    def __repr__(self) -> str:
        return f"WorkerPool(queue={self.queue.name}, capacity={self.target.max_parallelism})"

    # -- in

    def submit(self, run_id: str) -> Placement:
        """This run needs a pass. Take the lock or queue behind it; a holder is enqueued."""
        run = self.store.run(run_id)
        if run.is_finished:
            raise ValueError(f"{run_id} has ended ({run.state}); nothing to run")
        engagement = run.engagement_id
        holder = self.lock.holder(engagement)
        if holder is not None and holder.run_id == run_id:
            return self._enqueue(run_id, engagement)
        if holder is not None and run_id in self._lock_queue(engagement):
            return self._placement(run)
        result = self.lock.acquire(engagement, run_id)
        if result.acquired:
            return self._enqueue(run_id, engagement)
        return self._placement(run)

    def submit_all(self, run_ids: Iterable[str]) -> list[Placement]:
        return [self.submit(run_id) for run_id in run_ids]

    def resume(self, run_id: str) -> Placement:
        """Pick a run back up: a stranded one under the same job id, any other as a
        fresh submission - including one whose job this process's queue has never seen,
        which goes in as a fresh job under the lock the run still holds. Resume is replay
        either way, and the ledger makes the replay idempotent."""
        job_id = self._job_for(run_id)
        status = self._status(job_id) if job_id else None
        if job_id and status is not None and status.state is JobState.FAILED:
            run = self.store.run(run_id)
            holder = self.lock.holder(run.engagement_id)
            if holder is not None and holder.run_id == run_id:
                self.queue.retry(job_id)
                return self._record_enqueued(run, job_id, resumed=True)
        return self.submit(run_id)

    def work(self) -> None:
        """Run everything queued, in this process, as wide as the pool allows."""
        self.queue.drain()

    # -- looking

    def placement(self, run_id: str) -> Placement | None:
        run = self.store.run(run_id)
        return None if run.is_finished else self._placement(run)

    def placements(self) -> list[Placement]:
        found = []
        for run in self.store.runs():
            if run.is_finished:
                continue
            found.append(self._placement(run))
        return found

    def pressure(self) -> Pressure:
        depth = self.queue.depth()
        placed = self.placements()
        return Pressure(
            capacity=self.target.max_parallelism,
            in_flight=depth.running,
            waiting=sum(1 for p in placed if p.waiting_on == WAITING_ON_WORKER),
            behind_locks=sum(1 for p in placed if p.waiting_on == WAITING_ON_LOCK),
            adapter=str(self.queue.name),
            target=self.target.describe(),
        )

    def stranded(self, *, emit: bool = True) -> tuple[Stranded, ...]:
        """Every running run whose worker is gone. Raised on the record once per attempt;
        decided nothing about the run.

        Two ways a worker goes. The job ended without a result - the pass raised, or the
        thread died - and the queue says so. Or **the queue has no memory of the job at
        all**, which is what a run that was mid-pass looks like from the next process: the
        in-process adapter is memory-only, so closing the laptop forgot the job while the
        record still says the run is running and a step is open. Until P168 that second
        case was skipped here, so nothing listed it, the console refused both Resume and
        Halt with RUN.HELD because the run was "running under a worker", nothing picked it
        up at start, and the engagement lock stayed held - every later run on that client
        queued behind it for good.
        """
        found: list[Stranded] = []
        for run in self.store.runs():
            if run.is_finished or run.state is not RunState.RUNNING:
                continue
            job_id = self._job_for(run.run_id)
            if job_id is None:
                continue
            status = self._status(job_id)
            if status is not None and status.state is not JobState.FAILED:
                continue
            open_step = next(
                (
                    s.step_id
                    for s in self.store.steps(run.run_id)
                    if s.started_at and not s.ended_at
                ),
                None,
            )
            if status is None:
                lost = Stranded(
                    run.run_id,
                    run.engagement_id,
                    job_id,
                    0,
                    open_step,
                    f"the queue has no record of job {job_id}; the process that was running "
                    f"it is gone",
                )
            else:
                lost = Stranded(
                    run.run_id,
                    run.engagement_id,
                    job_id,
                    status.job.attempts,
                    open_step,
                    status.error,
                )
            found.append(lost)
            if emit and not self._already_raised(run.run_id, job_id, lost.attempt):
                self._raise(lost, status)
        return tuple(found)

    # -- the work

    def _perform(self, job: Job) -> dict[str, Any]:
        """What a worker does with a job: hold the lock, run one pass, let go."""
        run_id = str(job.payload["run_id"])
        run = self.store.run(run_id)
        engagement = run.engagement_id
        holder = self.lock.holder(engagement)
        if holder is None:
            self.lock.acquire(engagement, run_id)
        elif holder.run_id != run_id:
            # Another run has the deal. This one waits behind the lock and is enqueued
            # again when the holder lets go; the job itself is done.
            if run_id not in self._lock_queue(engagement):
                self.lock.acquire(engagement, run_id)
            self._emit(
                run_id,
                engagement,
                "worker.deferred",
                f"{engagement} is held by {holder.run_id}; queued behind it",
                job_id=job.id,
                holder=holder.run_id,
            )
            return {"run_id": run_id, "deferred_behind": holder.run_id}

        self._emit(
            run_id,
            engagement,
            "worker.started",
            f"attempt {job.attempts} on {self.target.describe()}",
            job_id=job.id,
            attempt=job.attempts,
            adapter=str(self.queue.name),
            target={
                "kind": self.target.kind,
                "image": self.target.image,
                "max_parallelism": self.target.max_parallelism,
            },
        )
        try:
            report = self.passes(run_id)
        except Exception as failed:
            # Whatever the driver did wrong, the lock is this pool's to let go of. A
            # worker that died holding it would strand every later run for the client
            # behind a run that was never going to move - which is exactly what happened
            # the first time a hostile file was refused at intake.
            self._emit(
                run_id,
                engagement,
                "worker.failed",
                f"attempt {job.attempts} raised {failed.__class__.__name__}: {failed}"[:400],
                level="error",
                job_id=job.id,
                attempt=job.attempts,
                error=failed.__class__.__name__,
            )
            if self.store.run(run_id).state is RunState.QUEUED:
                # It was taken up; the record should say so, or `stranded()` - which
                # reads running runs with a failed job - never reports it.
                self.store.transition(
                    run_id, RunState.RUNNING, reason="taken up; the worker failed"
                )
            self._release(run_id, engagement)
            raise
        ended = self.store.run(run_id)
        self._emit(
            run_id,
            engagement,
            "worker.finished",
            f"{report}",
            job_id=job.id,
            attempt=job.attempts,
            state=str(ended.state),
            executed=len(report.executed),
            satisfied=len(report.satisfied),
            quarantined=list(report.quarantined),
            blocked_on=report.blocked_on,
        )
        self._release(run_id, engagement)
        return {
            "run_id": run_id,
            "state": str(ended.state),
            "executed": len(report.executed),
            "satisfied": len(report.satisfied),
        }

    def _release(self, run_id: str, engagement: str) -> None:
        holder = self.lock.holder(engagement)
        if holder is None or holder.run_id != run_id:
            return
        handed = self.lock.release(engagement, run_id)
        if handed is not None and handed.acquired:
            self._enqueue(handed.run_id, engagement)

    # -- placing

    def _enqueue(self, run_id: str, engagement: str) -> Placement:
        run = self.store.run(run_id)
        existing = self._job_for(run_id)
        status = self._status(existing) if existing else None
        if existing and status is not None and status.state in (JobState.QUEUED, JobState.RUNNING):
            return self._placement(run)
        job_id = self.queue.submit(PASS_KINDS[0], {"run_id": run_id}, engagement_id=engagement)
        return self._record_enqueued(run, job_id)

    def _record_enqueued(self, run: RunRecord, job_id: str, *, resumed: bool = False) -> Placement:
        self._jobs[run.run_id] = job_id
        position = self.queue.position(job_id)
        depth = self.queue.depth()
        self._emit(
            run.run_id,
            run.engagement_id,
            "run.enqueued",
            f"{'resumed' if resumed else 'enqueued'} at position {position} "
            f"({depth.running} running of {self.target.max_parallelism}, {depth.queued} waiting)",
            level="warn" if depth.saturated else None,
            job_id=job_id,
            position=position,
            waiting_on=WAITING_ON_WORKER if position else None,
            resumed=resumed,
            depth=depth.as_dict(),
        )
        return self._placement(run)

    def _placement(self, run: RunRecord) -> Placement:
        engagement = run.engagement_id
        holder = self.lock.holder(engagement)
        holder_id = holder.run_id if holder else None
        if holder_id != run.run_id:
            waiting = self._lock_queue(engagement)
            if run.run_id in waiting:
                return Placement(
                    run.run_id,
                    engagement,
                    WAITING_ON_LOCK,
                    waiting.index(run.run_id) + 1,
                    holder=holder_id,
                )
            return Placement(run.run_id, engagement, None, 0, holder=holder_id)
        job_id = self._job_for(run.run_id)
        status = self._status(job_id) if job_id else None
        if job_id is None or status is None:
            return Placement(run.run_id, engagement, None, 0, job_id=job_id, holder=holder_id)
        position = self.queue.position(job_id) if status.state is JobState.QUEUED else 0
        return Placement(
            run.run_id,
            engagement,
            WAITING_ON_WORKER if position else None,
            position,
            job_id=job_id,
            holder=holder_id,
            active=status.state is JobState.RUNNING,
        )

    def _lock_queue(self, engagement: str) -> list[str]:
        return [q.run_id for q in self.lock.queue(engagement)]

    def _job_for(self, run_id: str) -> str | None:
        """The run's latest job, from the record - so a pool in a fresh process finds
        what the one that died had enqueued."""
        if run_id in self._jobs:
            return self._jobs[run_id]
        for e in reversed(self.store.events(run_id)):
            if e.type == "run.enqueued" and e.payload.get("job_id"):
                self._jobs[run_id] = str(e.payload["job_id"])
                return self._jobs[run_id]
        return None

    def _status(self, job_id: str) -> JobStatus | None:
        try:
            return self.queue.status(job_id)  # type: ignore[no-any-return]
        except KeyError:
            return None  # enqueued by a pool over a queue this process cannot see

    # -- raising

    def _already_raised(self, run_id: str, job_id: str, attempt: int) -> bool:
        return any(
            e.type == "worker.lost"
            and e.payload.get("job_id") == job_id
            and e.payload.get("attempt") == attempt
            for e in self.store.events(run_id)
        )

    def _raise(self, lost: Stranded, status: JobStatus | None) -> None:
        if status is None:
            how = "the worker's process is gone"
        else:
            how = "the worker died" if status.worker_lost else "the pass raised"
        d = diagnose(
            WORKER_LOST,
            f"{how} on attempt {lost.attempt}"
            + (f" during {lost.step_id}" if lost.step_id else "")
            + f": {lost.error}",
            locator=f"{lost.run_id}/{lost.step_id or '?'}",
            step_id=lost.step_id or "",
        )
        self._emit(
            lost.run_id,
            lost.engagement_id,
            "worker.lost",
            d.detail,
            level="error",
            diagnostic_code=d.code,
            job_id=lost.job_id,
            attempt=lost.attempt,
            step_id=lost.step_id,
            error=lost.error,
            what_now=d.what_now,
        )

    def _emit(
        self,
        run_id: str,
        engagement_id: str,
        event_type: str,
        message: str,
        *,
        level: str | None = None,
        diagnostic_code: str | None = None,
        **payload: Any,
    ) -> None:
        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type=event_type,
            message=message,
            level=level,
            diagnostic_code=diagnostic_code,
            payload=payload,
        )
