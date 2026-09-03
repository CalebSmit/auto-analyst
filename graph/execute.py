"""The Step Executor: runs one step, keyed, timed, retried, and safe to run twice.

A retry, a crash resume and a manual re-run after a fix are the same operation. That is
the whole phase, and it rests on one idea: a step's identity is a hash of everything that
could change its answer, so asking "has this been done" is a lookup rather than a
judgement.

    step_key = sha256(step_id, input content hashes, skill@version, model_pin,
                      context_ref, output_schema_version)

The compiler knows four of those six. Content hashes and `context_ref` do not exist until
something has run, which is why `Step.key_material()` stops where it does and this module
finishes the job.

**Resume is replay, not recovery.** There is no separate restart path to get wrong: a
resumed run walks the same order, and every step whose key is already in the ledger is
satisfied from it. Killing a run mid-flight and starting it again re-executes nothing that
completed - not because a recovery routine reconstructs state, but because the question
"do I need to run this" has the same answer either way.

**Retries cover transport failures only.** A schema or guard failure is not a retry; it is
a repair loop with changed input, and the Loop Controller decides whether it may run. A
repair iteration is a new key - the guard's feedback is part of the input - so the same
lookup that makes resume safe is what makes "byte-identical input" a fact rather than an
opinion.

**Blocking is an ending, not a pause.** A run that needs a person checkpoints and exits -
no process, no lock, no context window held, and the wall clock stops. That is what makes
the "four hours excluding time waiting on a human" budget an honest number rather than a
measure of how fast people answer email.

**A quarantine halts what depends on it, and nothing else.** Independent branches finish;
their results are kept. Nothing is released - the run is quarantined, and a quarantined
run has no transition to delivered.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from graph.compile import CompiledGraph, Step
from graph.plan_assertions import check_plan
from harness.loops import LoopController, RepairNeeded
from ops.blobs import ContentRef, ContentStore, LocalContentStore
from ops.events import EventBus
from ops.models import RunState, StepStatus
from ops.run_store import LateResult, RunStore
from registries.constraints import ConstraintRegistry
from registries.errors import RegistryError

__all__ = [
    "Attempt",
    "Blocked",
    "ExecutionReport",
    "RepairNeeded",
    "StepExecutor",
    "StepOutcome",
    "StepRunner",
    "TransportFailure",
    "step_key",
]


class TransportFailure(Exception):
    """The step could not be reached or did not answer in time.

    The only kind of failure a retry is for. Deliberately not a subclass of
    `DiagnosticError`: it is an infrastructure hiccup on its way to becoming either a
    successful second attempt or a quarantine record, and only the ending carries a
    diagnostic.
    """


class Blocked(Exception):
    """The step needs a person before the run can go further.

    Raised by a runner, caught by the executor, and turned into a checkpoint-and-exit.
    Not a failure: the run is fine, it is simply not this process's business any more.
    """

    def __init__(self, item_id: str, subject: str, kind: str = "clarification") -> None:
        super().__init__(subject)
        self.item_id = item_id
        self.subject = subject
        self.kind = kind


class StepOutcome(StrEnum):
    """What became of one step in this pass."""

    EXECUTED = "executed"
    SATISFIED_FROM_LEDGER = "satisfied_from_ledger"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"
    NOT_REACHED = "not_reached"


@dataclass(frozen=True)
class Attempt:
    """What a runner is handed, and the token its result has to come back with.

    `inputs` are refs. Never values - see `ops.blobs` for the three guarantees that rests
    on. A runner that wants the bytes asks the content store for them, which is a
    deliberate extra step: it makes "this step read that blob" a thing that happened
    rather than a thing that was implied.

    On a repair iteration `inputs` carries one more ref than the plan declares - the
    guard's feedback, under the name the `RepairNeeded` gave it. Everything else about
    the attempt is the same object: the step, its schema, its ceilings.
    """

    step: Step
    attempt: int
    step_key: str
    inputs: Mapping[str, ContentRef]
    context_ref: str
    timeout_s: int
    run_id: str
    iteration: int = 0
    """0 for the first pass; n for the n-th admitted loop iteration."""

    @property
    def step_id(self) -> str:
        return self.step.id


@runtime_checkable
class StepRunner(Protocol):
    """Whatever actually does the work of one step.

    The seam between the executor and everything downstream of it. In P08 that is a
    test double; from P09 it is the Context Builder and the Dispatcher. Keeping it a
    Protocol is what lets the executor's guarantees - keying, timing, retry, ledger - be
    finished and tested before there is a model call anywhere near them.

    Raises `TransportFailure` for something a second attempt might fix, `Blocked` when it
    needs a person, `RepairNeeded` when a guard rejected the output and a declared loop
    might repair it, and anything else for a failure that is not a retry.
    """

    def __call__(self, attempt: Attempt) -> ContentRef: ...


@dataclass
class ExecutionReport:
    """What one pass of the executor did. Enough to decide what happens next."""

    run_id: str
    plan_hash: str
    outcomes: dict[str, StepOutcome] = field(default_factory=dict)
    executed: list[str] = field(default_factory=list)
    satisfied: list[str] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)
    halted: list[str] = field(default_factory=list)
    """Steps never started because something they depend on was quarantined."""
    blocked_on: str | None = None
    state: RunState = RunState.RUNNING
    active_seconds: float = 0.0

    @property
    def finished(self) -> bool:
        """Every step reached a completed ending, so the run has nothing left to do."""
        return not self.quarantined and self.blocked_on is None and all(
            outcome in (StepOutcome.EXECUTED, StepOutcome.SATISFIED_FROM_LEDGER)
            for outcome in self.outcomes.values()
        )

    def __str__(self) -> str:
        return (
            f"{self.run_id}: {len(self.executed)} executed, "
            f"{len(self.satisfied)} from the ledger, "
            f"{len(self.quarantined)} quarantined, {len(self.halted)} halted"
            + (f", blocked on {self.blocked_on}" if self.blocked_on else "")
        )


def step_key(
    step: Step,
    inputs: Mapping[str, ContentRef],
    context_ref: str,
) -> str:
    """The idempotency key. Everything that could change this step's answer, hashed.

    The compiler's half - step id, pinned skill, model pin, output schema - plus the two
    halves it cannot know: the content hashes of the actual inputs, and the context_ref
    of everything the model will be shown. Retrieved precedents live in that last one,
    which is why a changed precedent snapshot has to change the key.

    Inputs are sorted by name, so the key is a property of the step rather than of the
    order a dictionary happened to iterate in.
    """
    parts = [
        *step.key_material(),
        context_ref,
        *(f"{name}={inputs[name].content_hash}" for name in sorted(inputs)),
    ]
    body = "\n".join(parts).encode("utf-8")
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


class StepExecutor:
    """Walks a compiled plan, executing only what has not been done."""

    def __init__(
        self,
        store: RunStore,
        bus: EventBus,
        runner: StepRunner,
        blobs: ContentStore | None = None,
        constraints: ConstraintRegistry | None = None,
        clock: Callable[[], float] | None = None,
        loops: LoopController | None = None,
    ) -> None:
        self.store = store
        self.bus = bus
        self.runner = runner
        self.blobs = blobs or LocalContentStore()
        self.constraints = constraints or ConstraintRegistry.load()
        self._ceilings = self.constraints.ceilings["per_step"]
        self._clock = clock
        self.loops = loops or LoopController(self.constraints, store, bus)

    # -- the pass

    def execute(
        self,
        plan: CompiledGraph,
        run_id: str,
        run_inputs: Mapping[str, ContentRef] | None = None,
        context_ref: str = "context:none",
    ) -> ExecutionReport:
        """One pass over the plan. Idempotent: running it twice does the work once.

        Returns rather than raises on a block or a quarantine. Both are ordinary endings
        for a pass - the run is not over, this process's part in it is - and an exception
        would make the caller decide whether an ending was an error.
        """
        # Plan assertions gate every pass, the resume included. A plan mutated after it
        # was compiled, or read back from a checkpoint, gets the same check the compiler
        # gave it - nothing executes that has not been through them, and a resume is an
        # execution.
        check_plan(plan)

        report = ExecutionReport(run_id=run_id, plan_hash=plan.plan_hash)
        available: dict[str, ContentRef] = dict(run_inputs or {})
        halted: set[str] = set()
        self.store.start_clock(run_id)

        for step_id in plan.order:
            step = plan.step(step_id)
            if report.blocked_on or step_id in halted:
                # Blocked: this pass is over, and the frontier is where the next one
                # resumes from. Halted: something this step needs was quarantined, and
                # a step whose input never arrived did not fail - it never started.
                report.outcomes[step_id] = StepOutcome.NOT_REACHED
                if step_id in halted:
                    # No row: a step that never started has no key, and the manifest
                    # records it as not_reached from the plan rather than the table.
                    report.halted.append(step_id)
                continue

            base = self._inputs_for(step, available)
            outcome = self._run_with_loops(plan, run_id, step, base, context_ref, available)
            report.outcomes[step_id] = outcome
            if outcome is StepOutcome.EXECUTED:
                report.executed.append(step_id)
            elif outcome is StepOutcome.SATISFIED_FROM_LEDGER:
                report.satisfied.append(step_id)
            elif outcome is StepOutcome.QUARANTINED:
                report.quarantined.append(step_id)
                halted |= dependents(plan, step_id)
            elif outcome is StepOutcome.BLOCKED:
                report.blocked_on = step_id

        return self._close_pass(run_id, report)

    # -- one step, and the loop around it

    def _run_with_loops(
        self,
        plan: CompiledGraph,
        run_id: str,
        step: Step,
        base: Mapping[str, ContentRef],
        context_ref: str,
        available: dict[str, ContentRef],
    ) -> StepOutcome:
        """Run the step; if a guard rejects it and a loop is declared, run it again with
        the feedback appended - as many times as the Loop Controller admits, and not once
        more. Every iteration is a new key, so a resumed run replays it from the ledger
        like any other step."""
        inputs: dict[str, ContentRef] = dict(base)
        iteration = 0

        while True:
            key = step_key(step, inputs, context_ref)

            entry = self.store.ledger_entry(key)
            if entry is not None:
                available[step.id] = ContentRef(
                    content_hash=entry.result_ref,
                    media_type=entry.media_type,
                    size_bytes=entry.size_bytes,
                    name=step.id,
                )
                self._emit(run_id, plan, step, "step.satisfied", "already in the ledger", key)
                return StepOutcome.SATISFIED_FROM_LEDGER

            # Registered here rather than by the caller, because here is where the key
            # exists: it needs the content hashes of the inputs, which needed the
            # producers to have run.
            self.store.ensure_step(
                run_id, step.id, key, step.kind, skill=step.skill,
                loop=step.loops[0] if step.loops else None,
            )
            try:
                return self._run_step(
                    plan, run_id, step, key, inputs, context_ref, available, iteration
                )
            except RepairNeeded as repair:
                next_inputs = {**base, repair.feedback_name: repair.feedback}
                next_key = step_key(step, next_inputs, context_ref)
                admission = self.loops.admit(
                    run_id, plan, step, repair.loop, key, next_key, next_inputs,
                    repair.diagnostic,
                )
                if not admission.allowed:
                    record = self.loops.exhaust(
                        run_id, plan, step, repair, admission, key, inputs
                    )
                    return self._quarantine(
                        run_id, plan, step, record.reason, key,
                        diagnostic_code=record.code, review_item_id=record.review_item_id,
                    )
                inputs = next_inputs
                iteration = admission.iteration

    def _run_step(
        self,
        plan: CompiledGraph,
        run_id: str,
        step: Step,
        key: str,
        inputs: Mapping[str, ContentRef],
        context_ref: str,
        available: dict[str, ContentRef],
        iteration: int = 0,
    ) -> StepOutcome:
        allowed = min(step.retries, int(self._ceilings["transport_retries_max"]))
        timeout = min(step.timeout_s, int(self._ceilings["timeout_s"]))
        last: Exception | None = None

        for _ in range(allowed + 1):
            attempt_number = self.store.begin_attempt(run_id, step.id)
            attempt = Attempt(
                step=step,
                attempt=attempt_number,
                step_key=key,
                inputs=dict(inputs),
                context_ref=context_ref,
                timeout_s=timeout,
                run_id=run_id,
                iteration=iteration,
            )
            self._emit(
                run_id, plan, step, "step.started", f"attempt {attempt_number}", key,
                attempt=attempt_number, iteration=iteration,
            )
            try:
                result = self.runner(attempt)
            except Blocked as blocked:
                return self._block(run_id, plan, step, blocked, key)
            except RepairNeeded:
                # Not this method's decision. The controller's, one level up.
                raise
            except TransportFailure as failure:
                last = failure
                # Every attempt writes an event, including the ones that succeeded first
                # time - so "it worked eventually" is visible rather than inferred.
                self._emit(
                    run_id, plan, step, "step.transport_failed", str(failure), key,
                    attempt=attempt_number,
                )
                continue
            except Exception as failure:  # noqa: BLE001 - not a retry; it is an ending
                return self._quarantine(run_id, plan, step, str(failure), key)

            try:
                self.store.commit_step(
                    run_id, step.id, key, result.content_hash, attempt_number,
                    media_type=result.media_type, size_bytes=result.size_bytes,
                )
            except LateResult as late:
                # The result is not wrong, it is simply not the one that counts. Nothing
                # is overwritten, and the run continues on what the ledger holds.
                self._emit(
                    run_id, plan, step, "step.result_discarded",
                    str(late.diagnostic.detail), key, attempt=attempt_number,
                    diagnostic_code=late.diagnostic.code,
                )
                held = self.store.ledger_entry(key)
                if held is None:
                    return self._quarantine(run_id, plan, step, str(late), key)
                available[step.id] = ContentRef(
                    content_hash=held.result_ref, media_type=held.media_type,
                    size_bytes=held.size_bytes, name=step.id,
                )
                return StepOutcome.EXECUTED

            available[step.id] = result
            self._emit(
                run_id, plan, step, "step.completed", str(result), key,
                attempt=attempt_number, iteration=iteration,
            )
            return StepOutcome.EXECUTED

        return self._quarantine(
            run_id, plan, step,
            f"{allowed + 1} transport attempt(s) failed: {last}", key,
        )

    # -- endings

    def _block(
        self, run_id: str, plan: CompiledGraph, step: Step, blocked: Blocked, key: str
    ) -> StepOutcome:
        """Checkpoint and exit. The run holds nothing while a person thinks."""
        self.store.open_review_item(run_id, blocked.item_id, blocked.kind, blocked.subject)
        self.store.finish_step(run_id, step.id, StepStatus.NOT_REACHED)
        self._emit(
            run_id, plan, step, "hitl.item.queued", blocked.subject, key,
            item_id=blocked.item_id,
        )
        return StepOutcome.BLOCKED

    def _quarantine(
        self,
        run_id: str,
        plan: CompiledGraph,
        step: Step,
        reason: str,
        key: str,
        **payload: Any,
    ) -> StepOutcome:
        """Nothing is deleted. A quarantined step can be re-run by key once the cause is
        fixed, and the ledger makes that safe rather than duplicative."""
        self.store.finish_step(run_id, step.id, StepStatus.QUARANTINED, reason=reason)
        self._emit(run_id, plan, step, "step.quarantined", reason, key, level="error", **payload)
        return StepOutcome.QUARANTINED

    def _close_pass(self, run_id: str, report: ExecutionReport) -> ExecutionReport:
        report.active_seconds = self.store.stop_clock(run_id)
        if report.blocked_on:
            self.store.transition(
                run_id, RunState.WAITING, reason=f"blocked on {report.blocked_on}"
            )
            report.state = RunState.WAITING
        elif report.quarantined:
            self.store.transition(
                run_id,
                RunState.QUARANTINED,
                reason=f"quarantined: {', '.join(report.quarantined)}",
            )
            report.state = RunState.QUARANTINED
        else:
            report.state = self.store.run(run_id).state
        return report

    # -- plumbing

    def _inputs_for(
        self, step: Step, available: Mapping[str, ContentRef]
    ) -> dict[str, ContentRef]:
        """Refs, by the name the step calls them.

        A missing input is a defect in the compiler or the caller rather than a runtime
        condition - the plan's order guarantees producers run first - so it raises here
        rather than becoming a quarantine that reads like a data problem.
        """
        found: dict[str, ContentRef] = {}
        for ref in step.inputs:
            source = ref.name if ref.from_run else ref.producer
            if source not in available:
                raise RegistryError(
                    _missing(step.id, ref.name, sorted(available)),
                )
            found[ref.name] = available[source]
        return found

    def _emit(
        self,
        run_id: str,
        plan: CompiledGraph,
        step: Step,
        event_type: str,
        message: str,
        key: str,
        level: str | None = None,
        diagnostic_code: str | None = None,
        **payload: Any,
    ) -> None:
        self.bus.emit(
            run_id=run_id,
            engagement_id=plan.engagement_id,
            node_id="step_executor",
            type=event_type,
            message=f"{step.id}: {message}",
            level=level,
            step_id=step.id,
            diagnostic_code=diagnostic_code,
            payload={
                "step_key": key,
                "plan_hash": plan.plan_hash,
                **({"diagnostic_code": diagnostic_code} if diagnostic_code else {}),
                **payload,
            },
        )


def dependents(plan: CompiledGraph, step_id: str) -> set[str]:
    """Every step downstream of `step_id`, transitively. What a quarantine halts."""
    found: set[str] = set()
    frontier = [step_id]
    while frontier:
        current = frontier.pop()
        for step in plan.steps:
            if step.id in found or step.id == step_id:
                continue
            if any(not ref.from_run and ref.producer == current for ref in step.inputs):
                found.add(step.id)
                frontier.append(step.id)
    return found


def _missing(step_id: str, name: str, available: list[str]) -> Any:
    from registries.errors import PLAN_REFUSED, diagnose

    return diagnose(
        PLAN_REFUSED,
        f"{step_id} needs {name!r} and nothing has produced it (have: "
        f"{', '.join(available) or 'nothing'}). The compiled order guarantees producers "
        f"run first, so this is a defect above the executor rather than a data problem.",
        locator=step_id,
    )
