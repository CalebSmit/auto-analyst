"""Queue adapter: in-process. A bounded thread pool in the process that submitted.

Jobs are held in a list and executed on drain() rather than at submit(), so submission
stays non-blocking and the ordering is the same as a real broker's - which is what makes
the conformance suite meaningful for both.

drain() runs up to `workers` jobs at once, and `workers` comes from the Compute Target
rather than from a constant here: the pool asks how much concurrency exists instead of
assuming. Two jobs that name the same engagement never run together - the Engagement
Lock already guarantees that at the run level, and this adapter guarantees it again at
the job level, because two guarantees that cost nothing are cheaper than one plausible
wrong answer.

A job whose thread dies - anything that is not an ordinary exception - is recorded as a
lost worker rather than a failed job. The difference matters to whoever resumes it: a
handler that raised has a message to read; a worker that vanished leaves a step started
and never ended, and the executor's ledger is what makes picking that up safe.
"""

from __future__ import annotations

import itertools
import threading
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Any

from ports.queue import WORKER_LOST_PREFIX, Job, JobState, JobStatus, QueueDepth


class InProcessQueue:
    name = "in_process"

    def __init__(self, workers: int = 1) -> None:
        self.workers = max(1, int(workers))
        self._handlers: dict[str, Callable[[Job], Any]] = {}
        self._status: dict[str, JobStatus] = {}
        self._pending: list[str] = []
        self._ids = itertools.count(1)
        self._lock = threading.RLock()

    def __repr__(self) -> str:
        return (
            f"InProcessQueue(workers={self.workers}, pending={len(self._pending)}, "
            f"known={len(self._status)})"
        )

    # -- the port

    def register(self, kind: str, handler: Callable[[Job], Any]) -> None:
        self._handlers[kind] = handler

    def submit(self, kind: str, payload: dict[str, Any], engagement_id: str = "") -> str:
        with self._lock:
            job_id = f"job_{next(self._ids):05d}"
            job = Job(id=job_id, kind=kind, payload=dict(payload), engagement_id=engagement_id)
            self._status[job_id] = JobStatus(job=job, state=JobState.QUEUED)
            self._pending.append(job_id)
            return job_id

    def status(self, job_id: str) -> JobStatus:
        with self._lock:
            if job_id not in self._status:
                raise KeyError(f"no such job: {job_id}")
            return self._status[job_id]

    def retry(self, job_id: str) -> str:
        with self._lock:
            current = self.status(job_id)
            self._status[job_id] = JobStatus(job=current.job, state=JobState.QUEUED)
            if job_id not in self._pending:
                self._pending.append(job_id)
            return job_id

    def position(self, job_id: str) -> int:
        with self._lock:
            self.status(job_id)
            return self._pending.index(job_id) + 1 if job_id in self._pending else 0

    def depth(self) -> QueueDepth:
        with self._lock:
            running = sum(1 for s in self._status.values() if s.state is JobState.RUNNING)
            return QueueDepth(queued=len(self._pending), running=running, workers=self.workers)

    def drain(self) -> None:
        """Run everything queued, `workers` at a time, never two of one engagement.

        Jobs submitted while the drain is running are picked up by it, so a handler that
        enqueues the next run of an engagement (the lock handing over) does not need a
        second drain to see it done.
        """
        busy: set[str] = set()
        in_flight: dict[Future[None], str] = {}
        with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="aa-worker") as pool:
            while True:
                while len(in_flight) < self.workers:
                    job_id = self._next_runnable(busy)
                    if job_id is None:
                        break
                    engagement = self._status[job_id].job.engagement_id
                    if engagement:
                        busy.add(engagement)
                    in_flight[pool.submit(self._run, job_id)] = engagement
                if not in_flight:
                    # Nothing running, so nothing is busy, so nothing pending was
                    # skipped: the queue is empty.
                    return
                done, _ = wait(list(in_flight), return_when=FIRST_COMPLETED)
                for finished in done:
                    busy.discard(in_flight.pop(finished))
                    finished.result()  # _run never raises; this surfaces it if that changes

    # -- the work

    def _next_runnable(self, busy: set[str]) -> str | None:
        with self._lock:
            for job_id in self._pending:
                if self._status[job_id].job.engagement_id not in busy:
                    self._pending.remove(job_id)
                    return job_id
            return None

    def _run(self, job_id: str) -> None:
        with self._lock:
            current = self._status[job_id]
            job = Job(
                id=current.job.id,
                kind=current.job.kind,
                payload=current.job.payload,
                engagement_id=current.job.engagement_id,
                attempts=current.job.attempts + 1,
            )
            self._status[job_id] = JobStatus(job=job, state=JobState.RUNNING)
        handler = self._handlers.get(job.kind)
        if handler is None:
            self._set(job, JobState.FAILED, error=f"no handler registered for {job.kind!r}")
            return
        try:
            result = handler(job)
        except Exception as exc:  # noqa: BLE001 - a job failing must not kill the drain
            self._set(job, JobState.FAILED, error=str(exc))
            return
        except BaseException as lost:  # noqa: BLE001 - the worker died; record it, do not hide it
            self._set(job, JobState.FAILED, error=f"{WORKER_LOST_PREFIX} {lost!r}")
            return
        self._set(job, JobState.SUCCEEDED, result=result)

    def _set(self, job: Job, state: JobState, result: Any = None, error: str = "") -> None:
        with self._lock:
            self._status[job.id] = JobStatus(job=job, state=state, result=result, error=error)


def build() -> InProcessQueue:
    # The pool asks the Compute Target how much concurrency exists rather than assuming.
    import ports

    return InProcessQueue(workers=ports.get_compute().target().max_parallelism)
