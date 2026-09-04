"""Queue adapter: Redis + RQ. For when runs outlive the process that submitted them.

The same interface as the in-process adapter, over a broker. A job is enqueued as data -
its kind, its payload and its engagement - against a module-level trampoline that is
importable by name, so a worker in another process, started hours later, finds the same
function and looks the kind up in its own handler table. Handlers are therefore
registered per process: the sweep process registers what it needs to submit, and a
worker process registers what it needs to run, and neither has to be the other.

drain() runs a burst worker over the queue in this process - which is what makes the
conformance suite exercise this adapter for real, and what a single-machine deployment
uses when it has no separate workers. Long-lived workers are `rq worker` processes, as
many as the Compute Target allows; they drain nothing here and need nothing here.

Connection from AA_REDIS_URL. `fakeredis://` selects an in-memory Redis for the test
suite, which proves the adapter's use of the broker's API and nothing about a real
server - the session summary says so whenever that is what ran.
"""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Callable
from typing import Any

from ports.queue import WORKER_LOST_PREFIX, Job, JobState, JobStatus, QueueDepth

ENV_URL = "AA_REDIS_URL"
ENV_QUEUE = "AA_REDIS_QUEUE"
DEFAULT_URL = "redis://localhost:6379/0"
DEFAULT_QUEUE = "automated-analyst"
FAKE_SCHEME = "fakeredis://"

# Per process. A worker process fills this at startup with the same names the
# submitting process used; the trampoline reads it at run time.
HANDLERS: dict[str, Callable[[Job], Any]] = {}


def perform(kind: str, payload: dict[str, Any], engagement_id: str) -> Any:
    """What RQ runs. Importable by dotted name, so any process can be the worker."""
    from rq import get_current_job

    current = get_current_job()
    attempts = 1
    if current is not None:
        attempts = int(current.meta.get("attempts", 0)) + 1
        current.meta["attempts"] = attempts
        current.save_meta()  # type: ignore[no-untyped-call]
    handler = HANDLERS.get(kind)
    if handler is None:
        raise LookupError(f"no handler registered for {kind!r} in this process")
    job_id = current.id if current is not None else f"job_{uuid.uuid4().hex[:12]}"
    return handler(
        Job(
            id=job_id,
            kind=kind,
            payload=dict(payload),
            engagement_id=engagement_id,
            attempts=attempts,
        )
    )


class RedisRQQueue:
    name = "redis_rq"

    def __init__(self, connection: Any, *, queue_name: str = DEFAULT_QUEUE, workers: int = 1):
        from rq import Queue

        self._connection = connection
        self.workers = max(1, int(workers))
        self._queue = Queue(queue_name, connection=connection)

    def __repr__(self) -> str:
        return f"RedisRQQueue(queue={self._queue.name!r}, workers={self.workers})"

    # -- the port

    def register(self, kind: str, handler: Callable[[Job], Any]) -> None:
        HANDLERS[kind] = handler

    def submit(self, kind: str, payload: dict[str, Any], engagement_id: str = "") -> str:
        job = self._queue.enqueue(
            perform,
            kind,
            dict(payload),
            engagement_id,
            job_id=f"job_{uuid.uuid4().hex[:12]}",
            description=f"{kind} {engagement_id}".strip(),
            meta={"kind": kind, "engagement_id": engagement_id, "attempts": 0},
            result_ttl=-1,
            failure_ttl=-1,
        )
        return str(job.id)

    def status(self, job_id: str) -> JobStatus:
        from rq.job import JobStatus as RQStatus
        from rq.results import Result

        rq_job = self._fetch(job_id)
        meta = rq_job.get_meta(refresh=True)
        job = Job(
            id=str(rq_job.id),
            kind=str(meta.get("kind", "")),
            payload=dict(rq_job.args[1]) if len(rq_job.args) > 1 else {},
            engagement_id=str(meta.get("engagement_id", "")),
            attempts=int(meta.get("attempts", 0)),
        )
        rq_state = rq_job.get_status(refresh=True)
        state = _state_of(rq_state)
        latest = rq_job.latest_result()
        result: Any = None
        error = ""
        if latest is not None and latest.type == Result.Type.SUCCESSFUL:
            result = latest.return_value
        elif latest is not None and latest.type == Result.Type.FAILED:
            error = _last_line(latest.exc_string or "")
        elif rq_state in (RQStatus.STOPPED, RQStatus.CANCELED):
            error = f"{WORKER_LOST_PREFIX} job {rq_state}"
        if state is JobState.FAILED and not error:
            error = f"{WORKER_LOST_PREFIX} no result recorded for {rq_state}"
        return JobStatus(job=job, state=state, result=result, error=error)

    def retry(self, job_id: str) -> str:
        from rq.job import JobStatus as RQStatus
        from rq.registry import FailedJobRegistry

        rq_job = self._fetch(job_id)
        if rq_job.get_status(refresh=True) == RQStatus.FAILED:
            FailedJobRegistry(queue=self._queue).requeue(job_id)
        else:
            self._queue.enqueue_job(rq_job)
        return job_id

    def position(self, job_id: str) -> int:
        self._fetch(job_id)
        found = self._queue.get_job_position(job_id)
        return int(found) + 1 if found is not None else 0

    def depth(self) -> QueueDepth:
        from rq import Worker
        from rq.registry import StartedJobRegistry

        alive = Worker.count(queue=self._queue)
        return QueueDepth(
            queued=int(self._queue.count),
            running=int(StartedJobRegistry(queue=self._queue).count),
            workers=max(int(alive), self.workers),
        )

    def drain(self) -> None:
        worker = _BurstWorker([self._queue], connection=self._connection)
        worker.work(burst=True, with_scheduler=False)

    # -- plumbing

    def _fetch(self, job_id: str) -> Any:
        from rq.exceptions import NoSuchJobError
        from rq.job import Job as RQJob

        try:
            return RQJob.fetch(job_id, connection=self._connection)
        except NoSuchJobError as missing:
            raise KeyError(f"no such job: {job_id}") from missing


def _last_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


_STATES: dict[Any, JobState] = {}


def _state_of(rq_state: Any) -> JobState:
    """RQ's eight job states folded onto the port's four. Built on first use because
    importing rq at module import would make this adapter's presence cost every port."""
    if not _STATES:
        from rq.job import JobStatus as RQStatus

        _STATES.update(
            {
                RQStatus.QUEUED: JobState.QUEUED,
                RQStatus.DEFERRED: JobState.QUEUED,
                RQStatus.SCHEDULED: JobState.QUEUED,
                RQStatus.STARTED: JobState.RUNNING,
                RQStatus.FINISHED: JobState.SUCCEEDED,
                RQStatus.FAILED: JobState.FAILED,
                RQStatus.STOPPED: JobState.FAILED,
                RQStatus.CANCELED: JobState.FAILED,
            }
        )
    return _STATES.get(rq_state, JobState.FAILED)


def _burst_worker_class() -> Any:
    from rq import SimpleWorker

    class BurstWorker(SimpleWorker):
        """In-process, no fork - the same on Windows and Linux. Signal handlers are only
        installable from the main thread, and a drain may run from any."""

        def _install_signal_handlers(self) -> None:
            if threading.current_thread() is threading.main_thread():
                super()._install_signal_handlers()  # type: ignore[no-untyped-call]

    return BurstWorker


class _BurstWorker:
    def __init__(self, queues: list[Any], connection: Any) -> None:
        self._worker = _burst_worker_class()(queues, connection=connection)

    def work(self, **kw: Any) -> bool:
        return bool(self._worker.work(**kw))


def connect(url: str) -> Any:
    """A Redis client for the URL. `fakeredis://` is the in-memory fake for tests."""
    if url.startswith(FAKE_SCHEME):
        import fakeredis

        name = url[len(FAKE_SCHEME) :] or "default"
        return fakeredis.FakeStrictRedis(server=_fake_server(name))
    import redis

    return redis.Redis.from_url(url)


_FAKES: dict[str, Any] = {}


def _fake_server(name: str) -> Any:
    import fakeredis

    if name not in _FAKES:
        _FAKES[name] = fakeredis.FakeServer()
    return _FAKES[name]


def build() -> RedisRQQueue:
    import ports

    url = os.environ.get(ENV_URL) or DEFAULT_URL
    return RedisRQQueue(
        connect(url),
        queue_name=os.environ.get(ENV_QUEUE) or DEFAULT_QUEUE,
        workers=ports.get_compute().target().max_parallelism,
    )
