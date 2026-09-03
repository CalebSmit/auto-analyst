"""Queue adapter: in-process. Phase 1 runs one job at a time in one process.

Jobs are held in a list and executed on drain() rather than at submit(), so submission
stays non-blocking and the ordering is the same as a real broker's - which is what makes
the conformance suite meaningful for both.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any

from ports.queue import Job, JobState, JobStatus


class InProcessQueue:
    name = "in_process"

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[Job], Any]] = {}
        self._status: dict[str, JobStatus] = {}
        self._pending: list[str] = []
        self._ids = itertools.count(1)

    def __repr__(self) -> str:
        return f"InProcessQueue(pending={len(self._pending)}, known={len(self._status)})"

    def register(self, kind: str, handler: Callable[[Job], Any]) -> None:
        self._handlers[kind] = handler

    def submit(self, kind: str, payload: dict[str, Any], engagement_id: str = "") -> str:
        job_id = f"job_{next(self._ids):05d}"
        job = Job(id=job_id, kind=kind, payload=dict(payload), engagement_id=engagement_id)
        self._status[job_id] = JobStatus(job=job, state=JobState.QUEUED)
        self._pending.append(job_id)
        return job_id

    def status(self, job_id: str) -> JobStatus:
        if job_id not in self._status:
            raise KeyError(f"no such job: {job_id}")
        return self._status[job_id]

    def retry(self, job_id: str) -> str:
        current = self.status(job_id)
        job = Job(
            id=current.job.id,
            kind=current.job.kind,
            payload=current.job.payload,
            engagement_id=current.job.engagement_id,
            attempts=current.job.attempts,
        )
        self._status[job_id] = JobStatus(job=job, state=JobState.QUEUED)
        self._pending.append(job_id)
        return job_id

    def drain(self) -> None:
        while self._pending:
            job_id = self._pending.pop(0)
            self._run(job_id)

    def _run(self, job_id: str) -> None:
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
            self._status[job_id] = JobStatus(
                job=job, state=JobState.FAILED, error=f"no handler registered for {job.kind!r}"
            )
            return
        try:
            result = handler(job)
        except Exception as exc:  # noqa: BLE001 - a job failing must not kill the drain
            self._status[job_id] = JobStatus(job=job, state=JobState.FAILED, error=str(exc))
            return
        self._status[job_id] = JobStatus(job=job, state=JobState.SUCCEEDED, result=result)


def build() -> InProcessQueue:
    return InProcessQueue()
