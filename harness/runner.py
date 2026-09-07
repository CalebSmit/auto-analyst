"""The seam between the executor and the harness.

`graph.execute.StepExecutor` walks a compiled plan and hands each step to a `StepRunner`:
an `Attempt` in, a `ContentRef` out. It was written in P08 against a test double, on the
understanding that P09 would fill it with the Context Builder and the Dispatcher. Nothing
did. Every component on both sides was built and tested, and the join between them existed
only inside tests - each of which wired it up its own way, one step at a time, choosing the
procedure by hand.

That is what this is. It is deliberately thin: it holds no domain logic, makes no decision
a plan has not already made, and its whole job is to turn what the executor knows into what
the dispatcher needs.

**Which procedure a step runs is not a choice made here.** It comes from the skill the plan
compiled, through `procedures.procedure_for`, in one place. A runner that took a procedure
as an argument would put "what does this step actually do" in the hands of whoever wired it
up, and the answer would differ between production, the evaluator and the tests.

**The three exceptions the executor defines mean what it defines them to mean.** `Blocked`
is a person, `RepairNeeded` is a guard with a declared loop behind it, `TransportFailure` is
something a second attempt might fix. They are raised by what this calls and pass through
untouched: catching one to add context here would turn an ending the executor knows how to
handle into one it does not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from graph.execute import Attempt
from harness.dispatch import SkillDispatcher
from harness.inputs import InputsUnavailable, RunFacts, build_inputs
from harness.procedures import procedure_for, verifier_for
from ops.blobs import ContentRef, ContentStore

__all__ = ["RunContext", "SkillStepRunner"]

VERIFICATION_INPUT = "schedule"
"""The name a self-verification iteration's extra input arrives under. The loop controller
names it when it admits the iteration; the runner reads it to know which pass it is on."""


@dataclass(frozen=True)
class RunContext:
    """Everything about the run that does not change between its steps.

    One object rather than nine arguments, because these travel together to every step and
    a signature with nine positional facts in it is one somebody eventually fills in the
    wrong order.
    """

    run_id: str
    engagement_id: str
    client_id: str
    scope: Any
    """The `ResolvedScope`: which skills this engagement has, at which versions."""
    engagement_profile: ContentRef
    identifiers: tuple[Any, ...]
    """What the masker must not let through. Built once from the engagement, because a
    step that assembled its own would be a step that could miss one."""
    run_scope: Any
    pin: Any
    facts: RunFacts


class SkillStepRunner:
    """A skill step of a compiled plan, executed through the harness.

    Satisfies `graph.execute.StepRunner`. Not registered anywhere and not a singleton: one
    is built per run, because a `RunContext` is about one run and sharing one between two
    would be sharing an engagement's identifiers with another engagement.
    """

    def __init__(
        self,
        dispatcher: SkillDispatcher,
        blobs: ContentStore,
        context: RunContext,
    ) -> None:
        self.dispatcher = dispatcher
        self.blobs = blobs
        self.context = context

    def __call__(self, attempt: Attempt) -> ContentRef:
        step = attempt.step
        if step.kind != "skill" or not step.skill:
            raise InputsUnavailable(
                f"{step.id} is a {step.kind} step; this runner executes skill steps and "
                f"the plan should not have routed it here"
            )

        # A self-verification iteration is the same step, seen twice, with the first
        # pass's output as an extra input. The plan says so by what it hands over; nothing
        # here decides to verify.
        verifying = VERIFICATION_INPUT in attempt.inputs
        procedure = (
            verifier_for(step.skill) if verifying else procedure_for(step.skill)
        )

        inputs = build_inputs(
            step.skill,
            step.id,
            dict(attempt.inputs),
            self.context.facts,
            self.blobs,
            verifying=verifying,
        )

        done = self.dispatcher.run(
            step=step,
            run_id=self.context.run_id,
            engagement_id=self.context.engagement_id,
            client_id=self.context.client_id,
            scope=self.context.scope,
            engagement_profile=self.context.engagement_profile,
            inputs=inputs,
            identifiers=self.context.identifiers,
            run_scope=self.context.run_scope,
            procedure=procedure,
            pin=self.context.pin,
        )
        return done.output_ref
