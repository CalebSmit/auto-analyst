"""Whether a guard's rejection may ask for an iteration, and which one.

`RepairNeeded` has described this mechanism since P14: "a guard rejected a step's output,
and the plan may declare a loop that repairs it. Raised by a runner, decided by the
controller." The controller was built, the ceilings were declared on every recipe, the
compiler checked them - and the exception was raised in exactly one place in the repository,
a test double in `tests/p14/conftest.py`. Every real guard failure went through
`guards.report()`, raised `GuardFailed`, and landed in the executor's bare `except
Exception`, which quarantines at once. So `guard_repair`, `tieout_repair` and
`self_verification` were declared on every shipped recipe and not one of them had ever run.

This is the decision that was missing, and it is deliberately the whole of it: one table,
one membership check, one function. Where that decision lives matters more than it looks.

**It cannot invent a loop.** The check is `f"{loop}:{step.id}" in step.loops`, and
`step.loops` is the compiler's - `LoopRegion.id` is `f"{loop}:{head}"`, so a match means the
recipe declared this loop with this step as its head. The same predicate `LoopController`
uses when it looks the region up. A step that is a *member* of a region but not its head
does not match, because the executor re-runs the head.

**It cannot substitute one loop for another.** A tie-out failure on a step that declares
`guard_repair` but not `tieout_repair` quarantines; it does not fall through to the region
that happens to exist. One guard, one loop. If the dispatcher may choose among loops it is
deciding, and the recipe stops being the statement of what may iterate.

**It cannot raise a ceiling.** Nothing here touches `max_iterations`. `LoopController.admit`
reads that from the plan and refuses past it, as it always has.

What it returns is a request. The controller still decides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from harness.loops import RepairNeeded
from registries.errors import Diagnostic

if TYPE_CHECKING:  # pragma: no cover
    from graph.compile import Step
    from guards import GuardFailed
    from ops.blobs import ContentRef

__all__ = ["LOOP_FOR", "REPAIR_INPUT", "as_repair"]

REPAIR_INPUT = "guard_feedback"
"""The name the guard's failure arrives under on the next pass.

Deliberately not `feedback`: an input name is a step id everywhere else in the executor
(`available[step.id]`), so this has to be one no step will ever be called.
`graph.plan_assertions` refuses a plan that uses it as a step id.
"""

LOOP_FOR: dict[str, str] = {
    "schema": "guard_repair",
    "provenance": "guard_repair",
    "tieout": "tieout_repair",
}
"""`GuardResult.guard` -> the declared loop that repairs it.

`provenance` maps to `guard_repair` on the blueprint's own reading: its LOOPS table gives
guard repair's trigger as "output schema **or provenance check** rejects a skill output".
The CONNECTIONS array has no `provenance_gate -> loop_controller` edge, which is a
disagreement inside the blueprint rather than between the blueprint and the code; it is
recorded in BUILD/OPEN.md and follows the table, because the table states the trigger and
the drawing omits routes elsewhere too.
"""


def as_repair(step: Step, failed: GuardFailed, feedback: ContentRef) -> RepairNeeded | None:
    """The declared region this guard's failure may iterate, or None.

    None means the plan declares no such region on this step, and the caller re-raises the
    `GuardFailed` unchanged - today's behaviour, which is an immediate quarantine. That is
    the majority of steps and it is the safe default: `guard_repair` is declared on `ebitda`
    and nowhere else, so a schema failure on `tagging` or `timing` still ends the step.
    """
    guard = getattr(getattr(failed, "result", None), "guard", None)
    loop = LOOP_FOR.get(str(guard))
    if loop is None or f"{loop}:{step.id}" not in step.loops:
        return None
    return RepairNeeded(
        loop,
        failed.diagnostic,
        feedback,
        feedback_name=REPAIR_INPUT,
        guard_output=_detail(failed),
    )


def _detail(failed: GuardFailed) -> dict[str, Any]:
    result = getattr(failed, "result", None)
    return {
        "guard": getattr(result, "guard", ""),
        "code": getattr(result, "code", None),
        "failed": getattr(result, "failed", 0),
    }


def feedback_document(failed: GuardFailed) -> dict[str, Any]:
    """What the model is shown on the repair pass: the guard's verdict, structured.

    Not prose, and not the exception's `str()`. The tie-out guard already produces exactly
    what the blueprint says tie-out repair hands back - the recomputed value and the cited
    source rows - and the provenance guard the unsourced figures. Handing those over as they
    are is the difference between "your output was rejected" and something a second pass can
    act on.

    Masked by the caller before it becomes a blob. It carries figures and locators from the
    client's own documents, and it travels into the model's context beside the payload; text
    that reaches the door unmasked is what the payload scan quarantines runs for.
    """
    result = getattr(failed, "result", None)
    diagnostic: Diagnostic | None = getattr(failed, "diagnostic", None)
    return {
        "guard": getattr(result, "guard", ""),
        "code": getattr(result, "code", None) or getattr(diagnostic, "code", None),
        "checked": getattr(result, "checked", 0),
        "failed": getattr(result, "failed", 0),
        "reasons": list(getattr(result, "reasons", ()) or ()),
        "detail": dict(getattr(result, "detail", {}) or {}),
        "what_now": getattr(diagnostic, "what_now", "") or "",
    }
