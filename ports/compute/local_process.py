"""Compute adapter: this process, on this machine. How phases 1 to 24 run.

Container detection is by observable fact - /.dockerenv, the cgroup, or the image tag
the build stamps in - rather than by a flag somebody sets, because a flag set wrongly is
worse than no flag at all.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ports.compute import ComputeTarget, env_int

ENV_IMAGE = "AA_IMAGE"
ENV_MAX_PARALLELISM = "AA_MAX_PARALLELISM"
ENV_WORKDIR = "AA_WORKDIR"


class LocalProcessCompute:
    name = "local_process"

    def __init__(self) -> None:
        self._detected: ComputeTarget | None = None

    def __repr__(self) -> str:
        return f"LocalProcessCompute(containerised={self.is_containerised()})"

    def target(self) -> ComputeTarget:
        if self._detected is None:
            containerised = self.is_containerised()
            self._detected = ComputeTarget(
                kind="docker" if containerised else "local_process",
                image=os.environ.get(ENV_IMAGE) or None,
                max_parallelism=env_int(ENV_MAX_PARALLELISM, 1),
                workdir=os.environ.get(ENV_WORKDIR) or tempfile.gettempdir(),
            )
        return self._detected

    def is_containerised(self) -> bool:
        if Path("/.dockerenv").exists():
            return True
        cgroup = Path("/proc/self/cgroup")
        try:
            return "docker" in cgroup.read_text(encoding="utf-8")
        except OSError:
            return False


def build() -> LocalProcessCompute:
    return LocalProcessCompute()
