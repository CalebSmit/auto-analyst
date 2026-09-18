"""The declared loops, entered by something other than a test double.

`guard_repair`, `tieout_repair` and `self_verification` are declared on every shipped
recipe, given integer ceilings the compiler checks, and compiled into regions on every plan.
Not one had ever run. `RepairNeeded` - which has a docstring describing the whole mechanism,
a controller that can admit and exhaust it, and a ceiling the compiler checks - was raised in
exactly one place in the repository: `tests/p14/conftest.py`, a test double.

Every real guard failure raised `GuardFailed`, which is not that, and landed in the
executor's bare `except Exception`, which quarantines at once. So "the graph owns every
loop" - a non-negotiable - described a mechanism that was complete, tested in isolation, and
unreachable.

The bug behind the bug is the one worth keeping in view: `ContextRequest.repair_feedback`
has existed and been assembled into its own context section since P09, and nothing ever
passed one. `build_inputs` does not reject an unknown input name, it ignores it. So raising
`RepairNeeded` without also carrying the feedback would have sent the model a byte-identical
payload on the repair pass - the same bad answer twice, both iterations spent, and
`LOOP.INPUT_UNCHANGED` blind to it because the step key hashes the feedback ref. A loop that
looks like it works and cannot.
"""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pytest

from graph.compile import Step
from harness.loops import RepairNeeded
from harness.repair import LOOP_FOR, REPAIR_INPUT, as_repair
from harness.runner import VERIFICATION_INPUT
from tests.checkpoints.c07 import test_c7_deliverable as c7

ROOT = Path(__file__).resolve().parents[2]
Replayed = c7.Replayed


def step_with(loops: tuple[str, ...], step_id: str = "ebitda") -> Step:
    return Step(
        id=step_id,
        kind="skill",
        skill="ebitda-normalization@1.0.0",
        inputs=(),
        output_schema=None,
        timeout_s=60,
        retries=0,
        loops=loops,
        on_failure="quarantine",
    )


class Failed(Exception):
    """A GuardFailed shaped like the real one, without a registry round trip."""

    def __init__(self, guard: str, code: str = "SKILL.SCHEMA_INVALID") -> None:
        super().__init__(code)
        self.result = type(
            "R", (), {"guard": guard, "code": code, "checked": 3, "failed": 1, "reasons": ("x",),
                      "detail": {}}
        )()
        self.diagnostic = type("D", (), {"code": code, "what_now": "fix it"})()


# ------------------------------------------------------- what may ask for an iteration


@pytest.mark.parametrize(("guard", "loop"), sorted(LOOP_FOR.items()))
def test_a_guard_failure_asks_for_the_region_its_recipe_declares(guard: str, loop: str) -> None:
    asked = as_repair(step_with((f"{loop}:ebitda",)), Failed(guard), None)  # type: ignore[arg-type]
    assert isinstance(asked, RepairNeeded)
    assert asked.loop == loop
    assert asked.feedback_name == REPAIR_INPUT


@pytest.mark.parametrize("guard", sorted(LOOP_FOR))
def test_a_step_that_declares_no_region_asks_for_nothing(guard: str) -> None:
    """Today's behaviour, and the safe default. `guard_repair` is declared on `ebitda` and
    nowhere else, so a schema failure on `tagging` or `timing` still ends the step."""
    assert as_repair(step_with(()), Failed(guard), None) is None  # type: ignore[arg-type]


def test_no_loop_can_be_substituted_for_another() -> None:
    """A tie-out failure on a step that declares `guard_repair` but not `tieout_repair`
    quarantines. It does not fall through to the region that happens to exist.

    If the dispatcher may choose among loops it is deciding, and the recipe stops being the
    statement of what may iterate.
    """
    declared_but_wrong = step_with(("guard_repair:ebitda",))
    assert as_repair(declared_but_wrong, Failed("tieout", "GUARD.TIEOUT_MISMATCH"), None) is None  # type: ignore[arg-type]


def test_a_member_that_is_not_the_head_does_not_match() -> None:
    """`LoopRegion.id` is `loop:head`, and the executor re-runs the head. A step inside a
    region but not at its start cannot ask for the region."""
    assert as_repair(step_with(("guard_repair:tagging",)), Failed("schema"), None) is None  # type: ignore[arg-type]


def test_an_unknown_guard_asks_for_nothing() -> None:
    assert as_repair(step_with(("guard_repair:ebitda",)), Failed("something_new"), None) is None  # type: ignore[arg-type]


def test_nothing_here_touches_a_ceiling() -> None:
    """The controller reads `max_iterations` from the plan and refuses past it. A raiser
    that could raise a ceiling would be an agent deciding whether to try again."""
    import inspect

    from harness import repair

    # Read as code, not as text: the module's prose explains the rule, and a test that
    # failed on its own documentation would be the third one of those tonight.
    tree = ast.parse(inspect.getsource(repair))
    reads = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    reads |= {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "max_iterations" not in reads, "the raiser reads a ceiling it has no business reading"


# ---------------------------------------------------- the tripwire, for the next time


def test_repair_needed_is_raised_in_production_code() -> None:
    """The test that would have caught the original defect on the day it was introduced.

    `RepairNeeded` was raised in one place in the whole repository - a test double - for as
    long as the loops existed. Everything around it was green.

    Construction rather than `raise`: production builds one in `as_repair` and the
    dispatcher raises what it returns, so looking for a `raise RepairNeeded(...)` literal
    would have found nothing and passed for the wrong reason - which is the failure mode of
    the test this replaces.
    """
    builders: list[str] = []
    for path in ROOT.rglob("*.py"):
        if "tests" in path.parts or ".venv" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "RepairNeeded"
            ):
                builders.append(path.relative_to(ROOT).as_posix())

    assert builders, (
        "nothing in production builds a RepairNeeded, so no declared loop can be entered "
        "and every guard failure quarantines at once - the defect this phase fixed"
    )
    assert all(b.startswith("harness/") for b in builders), (
        f"a loop is requested from outside the harness: {builders}. The dispatcher holds "
        f"the masker, and the feedback's bytes reach the model."
    )

    # And it reaches the executor: something has to actually raise it.
    dispatcher = (ROOT / "harness" / "dispatch.py").read_text(encoding="utf-8")
    assert "raise self._repair(" in dispatcher


def test_every_declared_region_can_be_entered_or_is_recorded_as_not() -> None:
    """A region nothing can trigger is the state this phase found. Each is either reachable
    or named here as a known gap - silence is what let all four sit unreachable."""
    import yaml

    from graph.recipes import RECIPES_DIR

    triggered = set(LOOP_FOR.values())
    unreachable: set[str] = set()
    for recipe in sorted(RECIPES_DIR.glob("*.yaml")):
        if recipe.stem == "registered":
            continue
        body = yaml.safe_load(recipe.read_text(encoding="utf-8")) or {}
        for region in body.get("loops", ()) or ():
            if str(region["loop"]) not in triggered:
                unreachable.add(str(region["loop"]))

    assert unreachable == {"conflict_resolution", "self_verification"}, (
        f"the set of loops nothing can enter has changed: {unreachable}. Two are known "
        f"gaps, each recorded in BUILD/OPEN.md: conflict_resolution needs guards/reconcile "
        f"to be called in production and spans two steps while the executor re-runs only "
        f"the head; self_verification needs a verification procedure for line-item-tagging. "
        f"Anything else here is a region that was declared and forgotten."
    )


def test_self_verification_is_declared_on_a_skill_that_cannot_verify() -> None:
    """The finding this phase turned up by trying to fix it, kept where it cannot go quiet.

    Making the runner demand the pass is two lines. Doing it quarantines every run at
    tagging with "no verification pass for 'line-item-tagging'" - which is the system
    correctly refusing to pretend a declared control ran, and is also every run stopping.

    The blueprint's loop table says the trigger is "every DDR tagging and EBITDA output,
    always". The recipes declare it. Only `ebitda-normalization` has a verifier. So the
    control has never run on any output, and whether the declaration or the skill set is
    wrong is a person's call - build the verifier through the governance chain, or drop the
    declaration and move the plan hash.

    This fails when somebody closes the gap, which is the point: then the raiser goes in.
    """
    import yaml

    from graph.recipes import RECIPES_DIR
    from harness.procedures import VERIFIERS

    declared: set[str] = set()
    for recipe in sorted(RECIPES_DIR.glob("*.yaml")):
        if recipe.stem == "registered":
            continue
        body = yaml.safe_load(recipe.read_text(encoding="utf-8")) or {}
        steps = {str(s["id"]): str(s.get("skill", "")) for s in body.get("steps", ()) or ()}
        for region in body.get("loops", ()) or ():
            if str(region["loop"]) == "self_verification":
                declared.add(steps.get(str(region["head"]), "").split("@", 1)[0])

    assert declared, "no recipe declares self-verification any more; the note above is stale"
    assert "line-item-tagging" in declared - set(VERIFIERS), (
        "line-item-tagging now has a verifier, so the gap this test records is closed. "
        "The runner should demand the pass: see the note at the end of "
        "SkillStepRunner.__call__, and BUILD/OPEN.md."
    )


def test_no_step_is_named_after_a_loop_input() -> None:
    """An input name is a step id everywhere else in the executor. A step called `schedule`
    or `guard_feedback` would collide with the name an iteration's extra input arrives
    under, and the collision would look like a missing input rather than a name clash."""
    import yaml

    from graph.recipes import RECIPES_DIR

    reserved = {REPAIR_INPUT, VERIFICATION_INPUT}
    for recipe in sorted(RECIPES_DIR.glob("*.yaml")):
        if recipe.stem == "registered":
            continue
        body = yaml.safe_load(recipe.read_text(encoding="utf-8")) or {}
        ids = {str(s["id"]) for s in body.get("steps", ()) or ()}
        assert not (ids & reserved), f"{recipe.name} has a step named after a loop input"


# ------------------------------------------------- and the loop actually turns, end to end


def test_a_rejected_proposal_runs_the_step_again_with_the_guard_in_its_context(
    world: dict[str, Any], case: dict[str, Any], runner_for: Any
) -> None:
    """The headline. A real dispatcher, a real plan, a real guard - and the second pass sees
    something the first did not.

    The model returns an invalid proposal (an amount on a candidate, which the contract
    forbids) and then a valid one. Before this phase the first rejection ended the step.
    """
    bad = copy.deepcopy(case["proposal"])
    bad["candidates"][0]["amount"] = 285000

    from tests.p34.test_step_runner import _tagging_ref, _timing_ref, attempt_for

    timing = _timing_ref(world, case, runner_for)
    tagging = _tagging_ref(world, case, runner_for)

    with pytest.raises(RepairNeeded) as demanded:
        runner_for(Replayed(bad))(
            attempt_for(world["plan"], "ebitda", timing=timing, tagging=tagging)
        )

    asked = demanded.value
    assert asked.loop == "guard_repair", "the region the recipe declares on this step"
    assert asked.diagnostic.code == "SKILL.SCHEMA_INVALID"
    assert asked.feedback is not None, "a repair pass with nothing new is not a repair"

    # What the next pass would be shown, as the executor assembles it.
    said = json.loads(world["blobs"].get(asked.feedback).decode("utf-8"))
    assert said["guard"] == "schema"
    assert said["code"] == "SKILL.SCHEMA_INVALID"
    assert said["reasons"], "the model is told what was wrong, not merely that it was"


def test_the_feedback_is_masked_before_it_becomes_a_blob(
    world: dict[str, Any], case: dict[str, Any], runner_for: Any
) -> None:
    """It travels into the model's context beside the payload, and it carries figures and
    locators out of the client's own documents. Text that reaches the door unmasked is what
    the payload scan quarantines runs for - which is why this is raised where the masker is
    and not in the executor."""
    bad = copy.deepcopy(case["proposal"])
    bad["candidates"][0]["amount"] = 285000

    from tests.p34.test_step_runner import _tagging_ref, _timing_ref, attempt_for

    timing = _timing_ref(world, case, runner_for)
    tagging = _tagging_ref(world, case, runner_for)
    with pytest.raises(RepairNeeded) as demanded:
        runner_for(Replayed(bad))(
            attempt_for(world["plan"], "ebitda", timing=timing, tagging=tagging)
        )

    text = world["blobs"].get(demanded.value.feedback).decode("utf-8")
    assert c7.CLIENT not in text, "the client's name reached the model's context unmasked"


def test_the_repair_pass_is_told_something_the_first_pass_was_not(
    world: dict[str, Any], case: dict[str, Any], runner_for: Any, context: Any
) -> None:
    """The bug behind the bug.

    `build_inputs` ignores an input name it does not know, so a repair iteration would have
    handed the model the identical payload - and the step key would still have changed,
    because it hashes the feedback ref, so `LOOP.INPUT_UNCHANGED` would not have caught it.
    Two iterations, one answer, no way to tell.
    """
    from harness.runner import SkillStepRunner
    from tests.p34.test_step_runner import _tagging_ref, _timing_ref, attempt_for

    seen: list[Any] = []

    class Watching:
        def run(self, **kwargs: Any) -> Any:
            seen.append(kwargs.get("repair_feedback"))

            class Done:
                output_ref = world["blobs"].put_json({"ok": True}, name="watched")

            return Done()

    runner = SkillStepRunner(Watching(), world["blobs"], context)
    timing = _timing_ref(world, case, runner_for)
    tagging = _tagging_ref(world, case, runner_for)

    feedback = world["blobs"].put_json({"guard": "schema"}, name="feedback")
    runner(attempt_for(world["plan"], "ebitda", timing=timing, tagging=tagging))
    runner(
        attempt_for(
            world["plan"],
            "ebitda",
            timing=timing,
            tagging=tagging,
            **{REPAIR_INPUT: feedback},
        )
    )

    assert seen[0] is None, "the first pass has no guard feedback"
    assert seen[1] is feedback, (
        "the repair pass reached the dispatcher without the guard's failure, so the model "
        "would have been sent the same payload that was just rejected"
    )
