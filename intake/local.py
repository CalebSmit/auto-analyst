"""The Local Intake Folder: a watched directory on your machine. This is how phase 1 runs.

Identical downstream behaviour to any other source: the Sweep Planner says where to
look, this lists what is there through the Storage Port, and binding and fingerprinting
do the rest. Local-first is a requirement, not a fallback - until a run can be
reproduced on one machine from a folder of files, no cloud decision is worth making.

This module lists. It never reads: a file's bytes are not touched until Engagement
Binding has said whose they are.
"""

from __future__ import annotations

from intake.sweep import SweepTarget
from ports.storage import FileRef, StoragePort

__all__ = ["LocalIntake"]


class LocalIntake:
    name = "local_intake"

    def __init__(self, port: StoragePort) -> None:
        self.port = port

    def arrivals(self, target: SweepTarget) -> tuple[FileRef, ...]:
        """Every file under the target's location, in the port's stable order."""
        return self.port.list(target.location)
