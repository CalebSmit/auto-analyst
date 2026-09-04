"""The Job Queue Port: submission, status, retry and position behind one interface.

Phase 1 needs no queue at all. Having the interface from the start means adding Redis in
phase 3 is not a refactor of the pipeline - and it was not: P25 added the Redis + RQ
adapter beside the in-process one and the pipeline did not change a line.

Retry here means transport retry - a job that never ran, or died mid-flight. It is not
the loop controller, which is a different thing at a different level: a guard failure is
a bounded loop iteration that must change its input, never a re-submission.

**Behind the port sits a bounded worker pool.** How many jobs run at once is the Compute
Target's `max_parallelism`, asked for rather than assumed, and it is cross-engagement
concurrency only: the Engagement Lock serialises within one deal, and the in-process
adapter refuses to run two jobs of one engagement at the same time even if asked.

**Position and depth are part of the interface.** A run that is waiting can say where it
is in the line and the console can show it - the blueprint's queued state is "nothing is
allocated; position is visible", and a queue that cannot answer "how far back" cannot
support that state honestly. Backpressure is the same fact from the other side: `depth`
says how many are waiting against how many can run.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class Job:
    """A unit of work. The payload is data, never a closure - a queue that can only
    carry callables cannot be swapped for one that survives a process restart."""

    id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    engagement_id: str = ""
    attempts: int = 0


@dataclass(frozen=True)
class JobStatus:
    job: Job
    state: JobState
    result: Any = None
    error: str = ""

    @property
    def worker_lost(self) -> bool:
        """The job did not fail; the thing running it did. A handler that raised is a
        failure with a message; a worker that died leaves this marker instead, and the
        pool treats the two differently - one is resumed, the other is looked at."""
        return self.state is JobState.FAILED and self.error.startswith(WORKER_LOST_PREFIX)


WORKER_LOST_PREFIX = "worker lost:"


@dataclass(frozen=True)
class QueueDepth:
    """How much is waiting against how much can run. The backpressure signal."""

    queued: int
    running: int
    workers: int
    """The bound: how many jobs this pool executes at once."""

    @property
    def saturated(self) -> bool:
        return self.running >= self.workers and self.queued > 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "queued": self.queued,
            "running": self.running,
            "workers": self.workers,
            "saturated": self.saturated,
        }


@runtime_checkable
class QueuePort(Protocol):
    name: str

    def register(self, kind: str, handler: Callable[[Job], Any]) -> None:
        """Bind a job kind to what runs it. Handlers are registered by name so the
        payload stays serialisable."""
        ...

    def submit(self, kind: str, payload: dict[str, Any], engagement_id: str = "") -> str:
        """Enqueue and return the job id."""
        ...

    def status(self, job_id: str) -> JobStatus:
        """Where a job got to."""
        ...

    def retry(self, job_id: str) -> str:
        """Re-run a failed job. Returns the id - the same one, because a retry that
        produces a new identity is how duplicate work becomes invisible."""
        ...

    def position(self, job_id: str) -> int:
        """Where a queued job stands: 1 is next, 0 means it is not waiting - it is
        running, finished, or failed."""
        ...

    def depth(self) -> QueueDepth:
        """How many are queued, how many are running, how many may run at once."""
        ...

    def drain(self) -> None:
        """Run everything queued, in this process, with as many workers as the pool
        allows. A broker-backed adapter runs a burst worker over its queue; the
        long-lived workers are started separately and drain nothing."""
        ...
