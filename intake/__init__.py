"""Intake: what gets looked at, when a run actually starts, and the guarantee that an
inactive engagement is unreachable rather than merely unchecked.

Eight blueprint nodes, in the order a file meets them:

* `roster.py`      - the Active Project Roster: active, paused, archived. The Sweep
                     Planner reads nothing else.
* `config.py`      - the Configuration Store and its append-only Change Log: watches
                     and their patterns, intake timing, destinations, overrides.
* `sweep.py`       - the Sweep Planner: (location, engagement_id) pairs to sweep tonight.
                     A folder that matches no active engagement is reported, never guessed.
* `local.py`       - the Local Intake Folder: a watched directory behind the Storage Port.
* `bind.py`        - Engagement Binding: every file resolves to exactly one engagement
                     before anything reads it, and to a declared document type or is held.
* `fingerprint.py` - File Intake & Fingerprint: sha256 source_id, size, mime, path, and a
                     monotonic source_version on re-upload.
* `window.py`      - the Intake Window: quiet and complete enough, then exactly one run
                     over the whole current set. Never a delta.
* `lock.py`        - the Engagement Lock: one run at a time per deal; a second queues.

`Intake` in this module runs one sweep end to end. Deterministic Python throughout;
nothing here calls a model, and nothing here reads a file's bytes before the file is
bound to an engagement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from graph.recipes import Recipe, load_recipe
from intake.bind import Bound, EngagementBinder
from intake.config import ConfigStore
from intake.fingerprint import Fingerprinter, IntakeRecord
from intake.launch import Launched, RunLauncher
from intake.local import LocalIntake
from intake.roster import ProjectRoster
from intake.store import IntakeStore
from intake.sweep import SweepPlan, SweepPlanner
from intake.window import IntakeWindow, Verdict
from ports.storage import StoragePort
from registries.errors import DiagnosticError

__all__ = ["Intake", "SweepResult"]


@dataclass
class SweepResult:
    """What one sweep did. Everything is on the record; this is the summary."""

    plan: SweepPlan
    arrived: list[IntakeRecord] = field(default_factory=list)
    held: list[IntakeRecord] = field(default_factory=list)
    refused: list[tuple[str, str]] = field(default_factory=list)
    """(path, code) for every file that failed to bind or to read. Nothing read it."""
    verdicts: dict[str, Verdict] = field(default_factory=dict)
    launched: list[Launched] = field(default_factory=list)

    @property
    def runs(self) -> list[str]:
        return [item.run_id for item in self.launched]


class Intake:
    def __init__(
        self,
        port: StoragePort,
        roster: ProjectRoster,
        config: ConfigStore,
        intake_store: IntakeStore,
        launcher: RunLauncher,
        clock: Callable[[], datetime] | None = None,
        recipes: Callable[[str], Recipe] = load_recipe,
    ) -> None:
        self.port = port
        self.roster = roster
        self.config = config
        self.intake_store = intake_store
        self.launcher = launcher
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        self._recipes = recipes
        self.planner = SweepPlanner(roster, config, port, intake_store, clock=self._clock)
        self.source = LocalIntake(port)
        self.binder = EngagementBinder(roster, config)
        self.fingerprinter = Fingerprinter(port, intake_store, clock=self._clock)
        self.window = IntakeWindow(intake_store, config, clock=self._clock)

    def sweep(self, launch_context: dict[str, Any] | None = None) -> SweepResult:
        """One pass: plan, bind, fingerprint, decide, release. Files under a folder that
        is not an active engagement's are never listed, let alone read."""
        plan = self.planner.plan()
        result = SweepResult(plan=plan)
        touched: dict[str, str] = {}

        for target in plan.targets:
            for ref in self.source.arrivals(target):
                try:
                    bound: Bound = self.binder.bind(ref, target)
                    record = self.fingerprinter.take(bound)
                except DiagnosticError as refused:
                    result.refused.append((ref.path, refused.diagnostic.code))
                    continue
                if record is None:
                    continue
                (result.held if record.state == "held" else result.arrived).append(record)
            touched[target.engagement_id] = target.recipe

        for engagement_id, recipe_name in touched.items():
            recipe = self._recipes(recipe_name)
            verdict = self.window.evaluate(engagement_id, recipe)
            result.verdicts[engagement_id] = verdict
            if verdict.release:
                result.launched.append(
                    self.launcher.launch(engagement_id, recipe, verdict, **(launch_context or {}))
                )
        return result
