"""The Bounded Loop Controller: owns every loop in the system, and the ceiling on each.

Six loops are declared in the graph. Four are in-run - guard repair, tie-out repair,
self-verification, conflict resolution - and those are the ones that run here, as
declared regions of a compiled plan. Human clarification is a suspend-and-resume and
drift re-review is human-paced across runs; neither is a cycle, and implementing all
three in one mechanism is the mistake the scope column prevents.

Three rules, each a test:

* **Input must change.** An iteration whose input is byte-identical to a previous
  attempt is refused. The test is the step key - everything that could change the
  answer, hashed - so "the same call at the same price" is a lookup, not a judgement.
  A skill that returns the same figure to the same feedback is stopped after one go, not
  after the ceiling.
* **Every iteration counts twice.** Against the region's own maximum, and against the
  run's global loop ceiling, so several loops cannot conspire to run long. The global
  count is read from the event stream, the same place the Cost Meter reads it, so the
  governor and the manifest cannot disagree.
* **Exhaustion always produces an artifact.** A quarantine record holding the full
  context, and a review item carrying both positions. There is no path where a loop
  quietly gives up and the run carries on as though nothing happened.

A repair may change the input to the step. It may never change the guard, the tolerance
or the schema - the controller hands back inputs and nothing else.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from graph.compile import CompiledGraph, LoopRegion, Step
from ops.blobs import ContentRef
from ops.events import EventBus
from ops.models import now_iso
from ops.run_store import QuarantineRecord, RunStore
from registries.constraints import ConstraintRegistry
from registries.errors import (
    BUDGET_EXCEEDED,
    INPUT_UNCHANGED,
    LOOP_EXHAUSTED,
    Diagnostic,
    diagnose,
)

__all__ = ["Admission", "Iteration", "LoopController", "RepairNeeded"]

NODE = "loop_controller"


class RepairNeeded(Exception):
    """A guard rejected a step's output, and the plan may declare a loop that repairs it.

    Raised by a runner, decided by the controller. Carries the guard's structured
    failure as content (`feedback`) - the thing that is appended to the step input for
    the next pass - and both positions for the review item exhaustion would open.
    """

    def __init__(
        self,
        loop: str,
        diagnostic: Diagnostic,
        feedback: ContentRef,
        *,
        feedback_name: str = "feedback",
        positions: Mapping[str, Any] | None = None,
        guard_output: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(str(diagnostic))
        self.loop = loop
        self.diagnostic = diagnostic
        self.feedback = feedback
        self.feedback_name = feedback_name
        self.positions = dict(positions or {})
        self.guard_output = dict(guard_output or {})


@dataclass(frozen=True)
class Iteration:
    """One admitted pass around a region, on the record."""

    loop: str
    region: str
    step_id: str
    number: int
    step_key: str
    trigger: str
    inputs: dict[str, str] = field(default_factory=dict)
    at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "loop": self.loop,
            "region": self.region,
            "step_id": self.step_id,
            "iteration": self.number,
            "step_key": self.step_key,
            "trigger": self.trigger,
            "inputs": dict(self.inputs),
            "at": self.at,
        }


@dataclass(frozen=True)
class Admission:
    """The controller's answer to "may this iteration run"."""

    allowed: bool
    iteration: int
    ceiling: int
    diagnostic: Diagnostic | None = None

    @property
    def code(self) -> str | None:
        return None if self.diagnostic is None else self.diagnostic.code


class LoopController:
    def __init__(self, constraints: ConstraintRegistry, store: RunStore, bus: EventBus) -> None:
        self.constraints = constraints
        self.store = store
        self.bus = bus
        self._global_ceiling = int(constraints.ceilings["per_run"]["loop_iterations_max"])
        self._history: dict[tuple[str, str], list[Iteration]] = {}

    # -- reading

    def region(self, plan: CompiledGraph, step_id: str, loop: str) -> LoopRegion | None:
        """The declared region this loop would run under, or None if the plan declares
        no such loop on this step. An undeclared loop has a ceiling of zero."""
        return next(
            (r for r in plan.loops if r.loop == loop and r.head == step_id), None
        )

    def history(self, run_id: str, region_id: str) -> tuple[Iteration, ...]:
        return tuple(self._history.get((run_id, region_id), ()))

    def iterations_so_far(self, run_id: str) -> int:
        """Every iteration of every loop in this run, from the record."""
        return sum(1 for e in self.store.events(run_id) if e.level == "loop")

    # -- deciding

    def admit(
        self,
        run_id: str,
        plan: CompiledGraph,
        step: Step,
        loop: str,
        current_key: str,
        next_key: str,
        next_inputs: Mapping[str, ContentRef | str],
        trigger: Diagnostic,
    ) -> Admission:
        """May the next iteration run? Three refusals, in the order they are cheapest
        to check: unchanged input, the region's ceiling, the run's ceiling."""
        region = self.region(plan, step.id, loop)
        region_id = region.id if region else f"{loop}:{step.id}"
        ceiling = region.max_iterations if region else 0
        history = self._history.setdefault((run_id, region_id), [])
        number = len(history) + 1
        seen = {current_key, *(it.step_key for it in history)}

        if next_key in seen:
            return self._refuse(
                run_id, plan, step, loop, number, ceiling,
                diagnose(
                    INPUT_UNCHANGED,
                    f"iteration {number} of {loop} would carry byte-identical input to a "
                    f"previous attempt (key {next_key[:19]}...). The skill returned the "
                    f"same output to the same feedback; stopping rather than paying for "
                    f"the same answer again.",
                    locator=step.id,
                    step_id=step.id,
                    skill=step.skill or "",
                    expected="changed input",
                    found="the same input",
                ),
                "loop.refused",
            )
        if number > ceiling:
            why = (
                f"{loop} is not declared on {step.id} in this plan, so it may not iterate"
                if region is None
                else f"{loop} on {step.id} reached its ceiling of {ceiling}"
            )
            return self._refuse(
                run_id, plan, step, loop, number, ceiling,
                diagnose(
                    LOOP_EXHAUSTED,
                    f"{why}; the exit condition was not met ({trigger.code}).",
                    locator=step.id,
                    step_id=step.id,
                    skill=step.skill or "",
                    expected=f"at most {ceiling} iteration(s)",
                    found=f"iteration {number} requested",
                ),
                "loop.exhausted",
            )
        used = self.iterations_so_far(run_id)
        if used + 1 > self._global_ceiling:
            return self._refuse(
                run_id, plan, step, loop, number, ceiling,
                diagnose(
                    BUDGET_EXCEEDED,
                    f"the run has used {used} of {self._global_ceiling} loop iterations "
                    f"across every loop; {loop} on {step.id} may not have another.",
                    locator=step.id,
                    step_id=step.id,
                    skill=step.skill or "",
                    expected=f"at most {self._global_ceiling} loop iterations per run",
                    found=f"{used + 1}",
                ),
                "loop.exhausted",
            )

        iteration = Iteration(
            loop=loop,
            region=region_id,
            step_id=step.id,
            number=number,
            step_key=next_key,
            trigger=trigger.code,
            inputs={
                name: (ref.content_hash if isinstance(ref, ContentRef) else str(ref))
                for name, ref in sorted(next_inputs.items())
            },
            at=now_iso(),
        )
        history.append(iteration)
        # The one event per iteration at level "loop" - the Cost Meter and the Budget
        # Governor count these, so an iteration that was admitted is an iteration that
        # was paid for, in the same record.
        self.bus.emit(
            run_id=run_id,
            engagement_id=plan.engagement_id,
            node_id=NODE,
            type=f"loop.{loop}.iteration",
            message=(
                f"{loop} on {step.id}: iteration {number} of {ceiling} admitted "
                f"({trigger.code}); {used + 1} of {self._global_ceiling} run-wide"
            ),
            level="loop",
            step_id=step.id,
            payload={
                **iteration.as_dict(),
                "ceiling": ceiling,
                "run_iterations": used + 1,
                "run_ceiling": self._global_ceiling,
            },
        )
        return Admission(allowed=True, iteration=number, ceiling=ceiling)

    # -- exhaustion

    def exhaust(
        self,
        run_id: str,
        plan: CompiledGraph,
        step: Step,
        repair: RepairNeeded,
        admission: Admission,
        current_key: str,
        inputs: Mapping[str, ContentRef],
    ) -> QuarantineRecord:
        """Quarantine with full context and open a review item carrying both positions.

        Two artifacts, always both. The quarantine is for the record and the re-run; the
        review item is for the person - and it names the quarantine, so neither is an
        orphan.
        """
        assert admission.diagnostic is not None
        region = self.region(plan, step.id, repair.loop)
        region_id = region.id if region else f"{repair.loop}:{step.id}"
        attempts = [it.as_dict() for it in self.history(run_id, region_id)]
        stopped = admission.diagnostic
        item_id = f"quarantine:{step.id}:{current_key[7:19]}"

        record = QuarantineRecord(
            step_id=step.id,
            step_key=current_key,
            loop=repair.loop,
            code=stopped.code,
            owner=stopped.owner,
            reason=stopped.detail,
            inputs={name: ref.content_hash for name, ref in sorted(inputs.items())},
            attempts=attempts,
            guard_output={
                "diagnostic": repair.diagnostic.as_dict(),
                **repair.guard_output,
            },
            diagnostic=stopped.as_dict(),
            review_item_id=item_id,
            held_at=now_iso(),
        )
        self.store.hold(run_id, record)
        self.store.open_review_item(
            run_id,
            item_id,
            kind="loop_exhausted",
            subject=(
                f"{step.label or step.id}: {repair.loop} stopped after "
                f"{len(attempts)} iteration(s) - {stopped.code}"
            ),
            detail={
                "positions": dict(repair.positions),
                "guard": repair.diagnostic.as_dict(),
                "stopped_by": stopped.as_dict(),
                "iterations": len(attempts),
                "step_key": current_key,
                "quarantine": True,
            },
        )
        self.bus.emit(
            run_id=run_id,
            engagement_id=plan.engagement_id,
            node_id="review_queue",
            type="hitl.item.queued",
            message=f"{step.id}: {repair.loop} exhausted; both positions queued for review",
            level="warn",
            step_id=step.id,
            payload={"item_id": item_id, "positions": list(repair.positions)},
        )
        return record

    # -- plumbing

    def _refuse(
        self,
        run_id: str,
        plan: CompiledGraph,
        step: Step,
        loop: str,
        number: int,
        ceiling: int,
        diagnostic: Diagnostic,
        event_type: str,
    ) -> Admission:
        self.bus.emit(
            run_id=run_id,
            engagement_id=plan.engagement_id,
            node_id=NODE,
            type=event_type,
            message=f"{loop} on {step.id}: {diagnostic.detail}",
            level="error",
            step_id=step.id,
            diagnostic_code=diagnostic.code,
            payload={"iteration": number, "ceiling": ceiling, **diagnostic.as_dict()},
        )
        return Admission(allowed=False, iteration=number, ceiling=ceiling, diagnostic=diagnostic)
