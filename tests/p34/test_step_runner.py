"""P34: a step of a compiled plan is executed by something other than a test.

`graph.execute.StepRunner` is the seam the executor was built against in P08, on the
understanding that P09 would fill it with the Context Builder and the Dispatcher. Nothing
did. Both sides were built and tested; the join existed only inside tests, each of which
wired it up its own way, one step at a time, choosing the procedure by hand.

Four claims:

1. A skill step of a compiled plan executes through the SkillDispatcher, carrying the
   run's scope, engagement profile and identifiers.
2. Which procedure a step runs is derived from the plan and the skill, in one place.
3. Blocked, RepairNeeded and TransportFailure reach the executor meaning what it defines
   them to mean.
4. Nothing under skills/ is imported by the runner.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from graph.execute import Attempt, Blocked, StepExecutor, StepOutcome, StepRunner
from harness.inputs import InputsUnavailable, build_inputs
from harness.runner import RunContext, SkillStepRunner
from tests.checkpoints.c07 import test_c7_deliverable as c7
from tests.p34.conftest import ENGAGEMENT, RUN_ID

ROOT = Path(__file__).resolve().parents[2]


Replayed = c7.Replayed
"""The model port C07 replays fixtures through. The same one, because a second port shaped
slightly differently is a second thing to keep true."""


def attempt_for(plan: Any, step_id: str, **inputs: Any) -> Attempt:
    step = plan.step(step_id)
    return Attempt(
        step=step,
        attempt=1,
        step_key=f"{step_id}:1",
        inputs=inputs,
        context_ref="context:none",
        timeout_s=step.timeout_s,
        run_id=RUN_ID,
    )


# ------------------------------------------------------------- it runs


def test_a_skill_step_executes_through_the_dispatcher(
    world: dict[str, Any], runner_for: Any, case: dict[str, Any]
) -> None:
    """The first exit criterion, and the whole phase in one assertion.

    Nothing here chooses a procedure, builds an inputs object or names a skill. The plan
    says which step; everything else follows from it.
    """
    port = Replayed(case["timing_proposal"])
    runner = runner_for(port)
    assert isinstance(runner, StepRunner), "it satisfies the protocol the executor takes"

    ref = runner(attempt_for(world["plan"], "timing"))

    assert ref.content_hash.startswith("sha256:")
    output = world["blobs"].get(ref)
    assert b"normalized_historicals" in output
    assert port.requests, "the model was reached, through the door and the masker"


def test_the_run_context_travels_to_the_dispatcher(
    world: dict[str, Any], context: RunContext, case: dict[str, Any]
) -> None:
    """Scope, engagement profile and identifiers are the run's, not the step's - so they
    are on the context and cannot be different for two steps of one run."""
    seen: dict[str, Any] = {}

    class Watching:
        def run(self, **kwargs: Any) -> Any:
            seen.update(kwargs)

            class Done:
                output_ref = world["blobs"].put_json({"ok": True}, name="watched")

            return Done()

    runner = SkillStepRunner(Watching(), world["blobs"], context)  # type: ignore[arg-type]
    runner(attempt_for(world["plan"], "timing"))

    assert seen["run_id"] == RUN_ID and seen["engagement_id"] == ENGAGEMENT
    assert seen["scope"] is context.scope
    assert seen["engagement_profile"] is context.engagement_profile
    assert seen["identifiers"] is context.identifiers
    assert seen["run_scope"] is context.run_scope
    assert seen["pin"] is context.pin
    assert seen["step"].id == "timing"


# ------------------------------------------------------------- the procedure


def test_the_procedure_comes_from_the_plan_not_from_the_caller(
    world: dict[str, Any], context: RunContext
) -> None:
    """The second exit criterion.

    A runner that took a procedure as an argument would put "what does this step actually
    do" in the hands of whoever wired it up, and production, the evaluator and the tests
    would each answer differently.
    """
    chosen: list[str] = []

    class Watching:
        def run(self, **kwargs: Any) -> Any:
            chosen.append(kwargs["procedure"].name)

            class Done:
                output_ref = world["blobs"].put_json({"ok": True}, name="watched")

            return Done()

    runner = SkillStepRunner(Watching(), world["blobs"], context)  # type: ignore[arg-type]
    runner(attempt_for(world["plan"], "timing"))
    assert chosen == ["timing-normalization"], "the skill the plan compiled"

    import inspect

    from harness import runner as module

    source = inspect.getsource(module)
    assert "procedure_for(step.skill)" in source
    assert "procedure: " not in source.split("class SkillStepRunner")[1].split("def __call__")[0]


def test_a_verification_iteration_uses_the_verifier(
    world: dict[str, Any], context: RunContext, case: dict[str, Any], runner_for: Any
) -> None:
    """The same step, seen twice. Which pass it is on comes from what the loop controller
    handed over, not from anything the runner decides."""
    first = runner_for(Replayed(case["proposal"]))(
        attempt_for(
            world["plan"],
            "ebitda",
            timing=_timing_ref(world, case, runner_for),
            tagging=_tagging_ref(world, case, runner_for),
        )
    )

    chosen: list[str] = []

    class Watching:
        def run(self, **kwargs: Any) -> Any:
            chosen.append(type(kwargs["procedure"]).__name__)

            class Done:
                output_ref = first

            return Done()

    runner = SkillStepRunner(Watching(), world["blobs"], context)  # type: ignore[arg-type]
    runner(
        attempt_for(
            world["plan"],
            "ebitda",
            timing=_timing_ref(world, case, runner_for),
            tagging=_tagging_ref(world, case, runner_for),
            schedule=first,
        )
    )
    assert chosen == ["EbitdaVerification"]


# ------------------------------------------------------------- the endings


def test_an_escalation_reaches_the_executor_as_blocked(
    world: dict[str, Any], runner_for: Any, facts: Any, context: RunContext, case: dict[str, Any]
) -> None:
    """The third exit criterion. `Blocked` means a person, and the executor stops the pass
    at the frontier rather than failing the run - so it has to arrive as itself."""
    import dataclasses

    ambiguous = dataclasses.replace(facts.sources[0], ambiguous=("scale: 000s or units",))
    stalled = dataclasses.replace(
        context, facts=dataclasses.replace(facts, sources=(ambiguous, *facts.sources[1:]))
    )
    runner = SkillStepRunner(
        world["dispatcher"](Replayed(case["timing_proposal"])), world["blobs"], stalled
    )
    with pytest.raises(Blocked):
        runner(attempt_for(world["plan"], "timing"))


def test_the_executor_drives_the_runner_and_records_what_it_did(
    world: dict[str, Any], runner_for: Any, case: dict[str, Any]
) -> None:
    """Not the runner in isolation - the executor walking a plan and calling it, which is
    the arrangement the whole seam exists for.

    The io steps - intake, mask, release - are P35's half of this. Here they are stood in
    for, so that what is being tested is the skill seam under the real executor rather
    than the executor stopping at the first step this phase does not cover.
    """
    skills = runner_for(Replayed(case["timing_proposal"]))
    io_ref = world["blobs"].put_json({"stood_in_for": "P35"}, name="io")

    def drive(attempt: Any) -> Any:
        return skills(attempt) if attempt.step.kind == "skill" else io_ref

    executor = StepExecutor(
        world["store"],
        world["bus"],
        drive,
        blobs=world["blobs"],
        constraints=world["constraints"],
    )
    report = executor.execute(
        world["plan"],
        RUN_ID,
        run_inputs={
            "source_documents": world["blobs"].put_json({"files": []}, name="sources"),
            "engagement_profile": world["engagement_profile"],
        },
    )
    assert report.outcomes["timing"] in (StepOutcome.EXECUTED, StepOutcome.SATISFIED_FROM_LEDGER)
    assert "timing" in report.executed or "timing" in report.satisfied
    assert report.outcomes["intake"] is StepOutcome.EXECUTED, "the io step ran, stood in for"


def test_a_step_the_plan_did_not_route_here_is_refused(
    world: dict[str, Any], runner_for: Any, case: dict[str, Any]
) -> None:
    """An io step is not this runner's business. It says so rather than half-running it."""
    runner = runner_for(Replayed(case["timing_proposal"]))
    with pytest.raises(InputsUnavailable, match="is a io step"):
        runner(attempt_for(world["plan"], "intake"))


def test_a_missing_upstream_output_says_which_one(
    world: dict[str, Any], facts: Any
) -> None:
    """A step whose producer did not run is a wiring fault, and the message names the
    step, what it wanted and what it had."""
    with pytest.raises(InputsUnavailable, match="needs the output of 'timing'"):
        build_inputs("line-item-tagging", "tagging", {}, facts, world["blobs"])


def test_a_skill_with_no_procedure_says_so(world: dict[str, Any], facts: Any) -> None:
    with pytest.raises(InputsUnavailable, match="no mechanical half yet"):
        build_inputs("qc-tieout", "qc", {}, facts, world["blobs"])


# ------------------------------------------------------------- the boundary


def test_the_runner_imports_nothing_from_skills() -> None:
    """The fourth exit criterion. A skill proposes; it never acts, and the thing that
    invokes one must not be able to reach into what it is invoking."""
    for module in ("harness/runner.py", "harness/inputs.py"):
        tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("skills"), (module, node.module)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("skills"), (module, alias.name)


def test_the_seam_is_one_place_and_the_readiness_check_finds_it() -> None:
    """`tools/serve.py` derives whether execution is wired by looking for an
    implementation of the protocol. That only works while there is one to find."""
    from tools.serve import steps_are_wired

    assert steps_are_wired(), "the runner is where the readiness check looks"


def _timing_ref(world: dict[str, Any], case: dict[str, Any], runner_for: Any) -> Any:
    return runner_for(Replayed(case["timing_proposal"]))(attempt_for(world["plan"], "timing"))


def _tagging_ref(world: dict[str, Any], case: dict[str, Any], runner_for: Any) -> Any:
    timing = _timing_ref(world, case, runner_for)
    output = __import__("json").loads(world["blobs"].get(timing).decode("utf-8"))
    by_ref = {t["line_item_ref"]: t for t in case["tagging"]["tagged_line_items"]}
    from harness.procedures.line_item_tagging import TaggingInputs

    built = TaggingInputs.from_normalized(
        output["normalized_historicals"],
        taxonomy_version="coa-taxonomy@1.0.0",
        auto_accept_confidence=0.85,
        always_review_categories=frozenset({"owner_related"}),
    )
    proposal = {
        "schema_version": "skills/line-item-tagging-proposal@1.0.0",
        "produced_by": "line-item-tagging@0.1.0",
        "items": [
            {
                "line_item_ref": i.line_item_ref,
                "category": by_ref[i.line_item_ref]["category"],
                "excluded_from_al": by_ref[i.line_item_ref]["excluded_from_al"],
                "include_in_nwc": by_ref[i.line_item_ref]["include_in_nwc"],
                "confidence": 0.95,
                "rationale": "the description says so",
            }
            for i in built.items
        ],
    }
    return runner_for(Replayed(proposal))(attempt_for(world["plan"], "tagging", timing=timing))
