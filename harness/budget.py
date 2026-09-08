"""The Run Budget Governor: four ceilings, and a halt rather than a throttle.

Every run carries four ceilings from `constraints.yaml`: token spend, currency spend,
wall clock, and total loop iterations across every loop. Crossing any one halts the run
and escalates. Halt, not throttle - a run that quietly degrades to a cheaper model is
much harder to reason about afterwards than one that stops and says why.

Checked before every model call, with the call's expected cost added in, and after every
step. Reads live spend from the Cost Meter, which reads it from the record, so the
governor and the manifest cannot disagree about what was spent.

"Escalates" is concrete: a review item is opened naming the ceiling and the number, and
the event carries the code and the owner. The person who raises a ceiling does it in
`constraints.yaml`, deliberately; the run does not get to decide it deserves more.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass

from ops.cost import CostMeter, Spend
from ops.events import EventBus
from ops.run_store import RunStore
from registries.constraints import ConstraintRegistry
from registries.errors import BUDGET_EXCEEDED, DiagnosticError, diagnose

__all__ = ["BudgetExceeded", "BudgetGovernor", "Ceiling", "CEILINGS"]


@dataclass(frozen=True)
class Ceiling:
    """One of the four, and how to read the run's position against it."""

    key: str
    """The key in constraints.yaml per_run."""
    dimension: str
    """The Spend field it compares to."""
    unit: str


# The four. Order is the order they are checked in, and it does not matter which fires
# first: any one is a halt.
CEILINGS: tuple[Ceiling, ...] = (
    Ceiling("usd_max", "usd", "USD"),
    Ceiling("tokens_max", "tokens", "tokens"),
    Ceiling("wall_clock_s", "active_seconds", "seconds of active wall clock"),
    Ceiling("loop_iterations_max", "loop_iterations", "loop iterations"),
)


class BudgetExceeded(DiagnosticError):
    """A ceiling was crossed. The run halts; this says which and by how much."""

    def __init__(self, ceiling: Ceiling, limit: float, position: float, run_id: str) -> None:
        self.ceiling = ceiling
        self.limit = limit
        self.position = position
        super().__init__(
            diagnose(
                BUDGET_EXCEEDED,
                f"{ceiling.key}: {position:g} {ceiling.unit} against a ceiling of {limit:g}",
                locator=run_id,
            )
        )


class BudgetGovernor:
    """Halts at a ceiling. Never lowers one, never raises one, never throttles."""

    def __init__(
        self,
        constraints: ConstraintRegistry,
        meter: CostMeter,
        bus: EventBus,
        store: RunStore,
        budget_for: Callable[[str], float | None] | None = None,
    ) -> None:
        self.constraints = constraints
        self.meter = meter
        self.bus = bus
        self.store = store
        self._limits = {c.key: float(constraints.ceilings["per_run"][c.key]) for c in CEILINGS}
        self.budget_for = budget_for
        """The engagement's own budget, in dollars, when the roster set one. Checked
        against the engagement's spend across every run it has had - a budget is the
        engagement's, not a run's - beside the firm's per-run ceilings. Set on the
        Setup page, shown by preflight, and until this hook existed enforced by
        nothing."""

    def limit(self, ceiling: Ceiling) -> float:
        return self._limits[ceiling.key]

    def remaining_usd(self, run_id: str) -> float:
        """What the Policy Gate's budget predicate reads."""
        return max(0.0, self._limits["usd_max"] - self.meter.spend(run_id).usd)

    def check(
        self,
        run_id: str,
        engagement_id: str,
        *,
        about_to_spend_usd: float = 0.0,
        about_to_spend_tokens: int = 0,
        about_to_call: bool = False,
        step_id: str | None = None,
    ) -> Spend:
        """Before a model call: is there room for it? After a step: is there room left?

        Raises on the first ceiling crossed, having recorded and escalated. Returns the
        spend otherwise, so the caller has the numbers it just checked.
        """
        spend = self.meter.spend(run_id)
        projected = {
            "usd": spend.usd + about_to_spend_usd,
            "tokens": spend.tokens + (about_to_spend_tokens if about_to_call else 0),
            "active_seconds": spend.active_seconds,
            "loop_iterations": spend.loop_iterations,
        }
        for ceiling in CEILINGS:
            position = projected[ceiling.dimension]
            limit = self._limits[ceiling.key]
            if position > limit:
                self._halt(run_id, engagement_id, ceiling, limit, position, step_id)
        budget = self.budget_for(engagement_id) if self.budget_for is not None else None
        if budget is not None and budget > 0:
            total = self.meter.rollup(engagement_id).as_dict().get("total_usd", 0.0)
            across_runs = float(total) if isinstance(total, int | float) else 0.0
            position = across_runs + about_to_spend_usd
            if position > budget:
                usd = next(c for c in CEILINGS if c.dimension == "usd")
                self._halt(
                    run_id,
                    engagement_id,
                    dataclasses.replace(usd, key="engagement_budget_usd"),
                    float(budget),
                    position,
                    step_id,
                )
        return spend

    def _halt(
        self,
        run_id: str,
        engagement_id: str,
        ceiling: Ceiling,
        limit: float,
        position: float,
        step_id: str | None,
    ) -> None:
        failure = BudgetExceeded(ceiling, limit, position, run_id)
        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id="budget_governor",
            type="budget.ceiling_crossed",
            level="error",
            message=str(failure.diagnostic.detail),
            step_id=step_id,
            diagnostic_code=BUDGET_EXCEEDED,
            payload={"ceiling": ceiling.key, "limit": limit, "position": position},
        )
        # Escalate: a person is told, on the record, which ceiling and by how much. The
        # run's state change is the executor's - the governor decides, it does not steer.
        self.store.open_review_item(
            run_id,
            f"budget_{ceiling.key}",
            "budget",
            f"{ceiling.key} crossed: {position:g} {ceiling.unit} against {limit:g}",
            detail={"ceiling": ceiling.key, "limit": limit, "position": position},
        )
        raise failure
