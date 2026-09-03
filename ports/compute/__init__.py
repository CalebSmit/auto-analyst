"""The Compute Target Port: where a run executes, as an interface rather than an
assumption.

One Docker image, driven by config. Local process, Docker, or any container host - the
deployment choice is an environment, not an architecture, and no managed-service
primitive is depended on anywhere in the code.

Making this a port rather than a comment is what keeps that true. The run manifest
records the target it ran on, and the worker pool asks it how much concurrency is
available instead of assuming. Both of those would otherwise be places where "we always
run locally" quietly hard-codes itself.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ComputeTarget:
    """What the run manifest records about where the work happened."""

    kind: str
    """local_process | docker | container_host"""

    image: str | None
    """The image and tag, or None outside a container. A deliverable produced by an
    unknown build is one nobody can reproduce."""

    max_parallelism: int
    """How many runs may execute at once here. The Engagement Lock already serialises
    within one deal, so this is cross-engagement concurrency."""

    workdir: str
    """Where scratch space lives. Never inside the repo."""

    def describe(self) -> str:
        return f"{self.kind}" + (f" ({self.image})" if self.image else "")


@runtime_checkable
class ComputePort(Protocol):
    name: str

    def target(self) -> ComputeTarget:
        """What this environment is. Read once at startup and recorded."""
        ...

    def is_containerised(self) -> bool:
        """Whether the process is running in a container. P28 asserts the whole suite
        passes both ways, which is only checkable if the code can tell."""
        ...


def env_int(name: str, default: int) -> int:
    """Read a positive integer from config, or fall back. A malformed value is the
    default rather than a crash at startup - but never silently zero, which would stop
    the pool without saying so."""
    raw = os.environ.get(name, "")
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default
