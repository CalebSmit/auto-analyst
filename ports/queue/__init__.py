"""The Job Queue Port: submission, status and retry behind one interface.

Phase 1 needs no queue at all. Having the interface from the start means adding Redis in
phase 3 is not a refactor of the pipeline.

Retry here means transport retry - a job that never ran, or died mid-flight. It is not
the loop controller, which is a different thing at a different level: a guard failure is
a bounded loop iteration that must change its input, never a re-submission.
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

    def drain(self) -> None:
        """Run everything queued. Present because an in-process queue needs somewhere to
        do the work; a real broker implements it as a no-op wait."""
        ...
