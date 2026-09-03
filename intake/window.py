"""The Intake Window: decides when enough has arrived to be worth starting a run.

Holds arriving files until the intake set is **quiet** and **complete enough**, then
releases exactly one run over the whole current set. Quiet means no new file for the
configured period. Complete enough means the recipe's required document types are
present - or the wait has passed its SLA, and the run proceeds with an explicit,
recorded coverage gap.

Three settings per engagement, from the Configuration Store: `quiet_period` (default
30 min), `required_types` (from the job recipe), `max_wait` (default 24 h).

A run consumes **the whole current intake set, never a delta**. Tagging needs the full
historical table, and a delta alone is not a valid input to it. So the set a run is
released over is every bound file at its latest version, whether or not an earlier run
already read it - and the earlier run is then superseded, not overwritten.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from graph.recipes import Recipe
from intake.config import ConfigStore
from intake.store import IntakeRow, IntakeStore

__all__ = ["IntakeWindow", "Verdict"]


@dataclass(frozen=True)
class Verdict:
    engagement_id: str
    release: bool
    reason: str
    current_set: tuple[IntakeRow, ...] = ()
    pending: tuple[IntakeRow, ...] = ()
    missing_types: tuple[str, ...] = ()
    """Required types absent from the set. Recorded as coverage gaps on a release."""
    held: tuple[IntakeRow, ...] = ()
    """Files bound to no declared type. Never in the set; reported with it."""
    quiet_for: timedelta = timedelta(0)
    waiting_for: timedelta = timedelta(0)

    @property
    def complete(self) -> bool:
        return not self.missing_types


class IntakeWindow:
    def __init__(
        self,
        intake_store: IntakeStore,
        config: ConfigStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.intake_store = intake_store
        self.config = config
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    def evaluate(self, engagement_id: str, recipe: Recipe) -> Verdict:
        now = self._clock()
        timing = self.config.timing(engagement_id)
        pending = self.intake_store.pending(engagement_id)
        current = self.intake_store.current_set(engagement_id)
        held = self.intake_store.held(engagement_id)
        present = {row.document_type for row in current}
        missing = tuple(t for t in recipe.required_types if t not in present)

        if not pending:
            return Verdict(
                engagement_id, False, "nothing new has arrived", current, (), missing, held
            )

        last = max(_parse(row.received_at) for row in pending)
        first = min(_parse(row.received_at) for row in pending)
        quiet_for = now - last
        waiting_for = now - first
        quiet = quiet_for >= timedelta(minutes=timing.quiet_period_minutes)
        overdue = waiting_for >= timedelta(hours=timing.max_wait_hours)

        if not quiet:
            reason = (
                f"not quiet: last arrival {_minutes(quiet_for)} ago, quiet period is "
                f"{timing.quiet_period_minutes:g} min"
            )
            return Verdict(
                engagement_id,
                False,
                reason,
                current,
                pending,
                missing,
                held,
                quiet_for,
                waiting_for,
            )
        if missing and not overdue:
            reason = (
                f"quiet but incomplete: missing {', '.join(missing)}; waiting "
                f"{_hours(waiting_for)} of {timing.max_wait_hours:g} h before proceeding with a gap"
            )
            return Verdict(
                engagement_id,
                False,
                reason,
                current,
                pending,
                missing,
                held,
                quiet_for,
                waiting_for,
            )
        if missing:
            reason = (
                f"quiet and past max_wait ({timing.max_wait_hours:g} h): proceeding with a "
                f"recorded coverage gap for {', '.join(missing)}"
            )
        else:
            reason = (
                f"quiet for {_minutes(quiet_for)} and complete: one run over {len(current)} file(s)"
            )
        return Verdict(
            engagement_id, True, reason, current, pending, missing, held, quiet_for, waiting_for
        )


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def _minutes(delta: timedelta) -> str:
    return f"{delta.total_seconds() / 60:.0f} min"


def _hours(delta: timedelta) -> str:
    return f"{delta.total_seconds() / 3600:.1f} h"
