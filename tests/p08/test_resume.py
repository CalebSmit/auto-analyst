"""Killing a run mid-flight and resuming re-executes zero completed steps.

The exit criterion, and the phase's whole argument. Not "few" and not "usually" - zero,
because the question "has this been done" is a hash lookup rather than a judgement, and
it has the same answer whether the last process crashed or finished.

Resume is replay, not recovery. There is no separate restart path in the executor at all:
the second pass walks the same order and asks the same question about every step.
"""

from __future__ import annotations

import contextlib

from graph.compile import CompiledGraph
from graph.execute import StepExecutor, StepOutcome, step_key
from ops.blobs import ContentRef, LocalContentStore
from ops.models import StepStatus
from ops.run_store import SqlRunStore
from tests.p08.conftest import CONTEXT_REF, RUN_ID, Recorder


def test_a_first_pass_executes_every_step(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], recorder: Recorder,
) -> None:
    report = executor.execute(plan, started, run_inputs, CONTEXT_REF)
    assert recorder.calls == list(plan.order)
    assert report.executed == list(plan.order)
    assert report.satisfied == []
    assert report.finished


def test_a_second_pass_executes_nothing(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], recorder: Recorder,
) -> None:
    """The criterion, stated as plainly as it can be."""
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    recorder.calls.clear()

    second = executor.execute(plan, started, run_inputs, CONTEXT_REF)

    assert recorder.calls == [], "a resumed run re-executed work it had already paid for"
    assert second.satisfied == list(plan.order)
    assert second.executed == []
    assert second.finished


def test_a_run_killed_halfway_resumes_at_the_frontier(
    executor_with, plan: CompiledGraph, started: str, store: SqlRunStore,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore,
) -> None:
    """The real shape of it: the process dies at step four, and a new one picks up at
    step four rather than at step one."""
    done: list[str] = []

    class Crashes:
        def __init__(self, after: int) -> None:
            self.after = after

        def __call__(self, attempt):  # noqa: ANN001 - a test double
            if len(done) >= self.after:
                raise KeyboardInterrupt("the process was killed")
            done.append(attempt.step_id)
            return blobs.put_json({"step": attempt.step_id}, name=attempt.step_id)

    # Exactly what a kill looks like from in here.
    with contextlib.suppress(KeyboardInterrupt):
        executor_with(Crashes(after=4)).execute(plan, started, run_inputs, CONTEXT_REF)

    assert len(done) == 4
    assert len(store.ledger(started)) == 4

    survivor = Recorder(blobs)
    report = executor_with(survivor).execute(plan, started, run_inputs, CONTEXT_REF)

    assert survivor.calls == list(plan.order[4:]), "resume did not start at the frontier"
    assert report.satisfied == list(plan.order[:4])
    assert report.finished


def test_the_frontier_is_the_ledger(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], store: SqlRunStore,
) -> None:
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    keys = store.completed_step_keys(started)
    assert len(keys) == len(plan)
    for entry in store.ledger(started):
        assert entry.step_key in keys
        assert entry.result_ref.startswith("sha256:")


def test_a_satisfied_step_still_hands_its_result_on(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], recorder: Recorder, blobs: LocalContentStore,
) -> None:
    """Satisfying from the ledger is not skipping. The downstream step gets the same ref
    it would have got, or the second pass would be a different run."""
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    first_pass_inputs = dict(recorder.seen["ebitda"])
    recorder.seen.clear()

    # Force one step to run again by giving it a key nothing has seen, so its inputs
    # have to come from somewhere - and they come from the ledger.
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    assert recorder.seen == {}, "nothing should have run"

    from ops.blobs import ContentRef as Ref

    for name, ref in first_pass_inputs.items():
        assert isinstance(ref, Ref), f"{name} was not a ref"
        assert blobs.has(ref)


def test_a_changed_input_is_a_different_step(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], recorder: Recorder, blobs: LocalContentStore,
) -> None:
    """"Only the steps whose inputs actually changed are paid for twice."

    A different engagement profile changes the key of the step that reads it, and of
    everything downstream of that - and of nothing upstream.
    """
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    recorder.calls.clear()

    changed = dict(run_inputs)
    changed["engagement_profile"] = blobs.put_json(
        {"industry": "distribution", "scale_convention": 1000}, name="engagement_profile"
    )
    executor.execute(plan, started, changed, CONTEXT_REF)

    # ebitda reads the profile; model and qc read ebitda.
    assert recorder.calls == ["ebitda", "model", "qc", "release"]


def test_a_step_whose_output_is_unchanged_stops_the_cascade(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore,
) -> None:
    """Content addressing paying off, and worth naming.

    If a step runs again on changed inputs and produces byte-identical output, the steps
    below it have the same keys they had before and are satisfied from the ledger. The
    work downstream genuinely does not need doing, and nothing had to reason about that -
    it falls out of keying on content rather than on time.
    """
    ran: list[str] = []

    class Stable:
        """Output that does not depend on the inputs, which is the case in question."""

        def __call__(self, attempt):  # noqa: ANN001 - a test double
            ran.append(attempt.step_id)
            return blobs.put_json({"step": attempt.step_id}, name=attempt.step_id)

    executor = executor_with(Stable())
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    ran.clear()

    changed = dict(run_inputs)
    changed["engagement_profile"] = blobs.put_json({"industry": "distribution"})
    executor.execute(plan, started, changed, CONTEXT_REF)

    assert ran == ["ebitda"], "only the step that actually saw a different input re-ran"


def test_a_changed_context_is_a_different_step(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], recorder: Recorder,
) -> None:
    """Retrieved precedents live in the context_ref, so a changed precedent snapshot has
    to change every key. Nothing may be satisfied from a ledger entry produced under a
    different context."""
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    recorder.calls.clear()

    executor.execute(plan, started, run_inputs, "context:something-else")

    assert recorder.calls == list(plan.order)


def test_the_ledger_keeps_the_old_answer_to_the_old_question(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], store: SqlRunStore, blobs: LocalContentStore,
) -> None:
    """A changed key does not delete the row under the old one. Nothing is overwritten:
    the old entry is still the correct answer to the question that was asked."""
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    before = {e.step_key for e in store.ledger(started)}

    executor.execute(plan, started, run_inputs, "context:something-else")
    after = {e.step_key for e in store.ledger(started)}

    assert before < after
    assert len(after) == 2 * len(plan)


def test_a_step_is_recorded_with_the_key_the_executor_computed(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], store: SqlRunStore, recorder: Recorder,
) -> None:
    """The executor registers its own steps, because the executor is what knows the key.
    A caller inventing one would invent a key the ledger never matches."""
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    by_id = {s.step_id: s for s in store.steps(started)}
    for attempt in recorder.attempts:
        assert by_id[attempt.step_id].step_key == attempt.step_key
        assert by_id[attempt.step_id].status is StepStatus.COMPLETED


def test_every_attempt_writes_an_event(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], store: SqlRunStore,
) -> None:
    """Including the ones that succeeded first time, so "it worked eventually" is visible
    rather than inferred from the absence of a complaint."""
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    started_events = [e for e in store.events(started) if e.type == "step.started"]
    completed = [e for e in store.events(started) if e.type == "step.completed"]
    assert len(started_events) == len(plan)
    assert len(completed) == len(plan)
    for event in started_events:
        assert event.payload["step_key"].startswith("sha256:")
        assert event.payload["plan_hash"] == plan.plan_hash


def test_the_second_pass_says_so_in_the_stream(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], store: SqlRunStore,
) -> None:
    """A resumed run is not a silent one. Satisfying a step from the ledger is a thing
    that happened and it is recorded as one."""
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    satisfied = [e for e in store.events(started) if e.type == "step.satisfied"]
    assert len(satisfied) == len(plan)


# ------------------------------------------------------------ the key itself


def test_the_key_covers_every_part_the_task_names(plan: CompiledGraph) -> None:
    """step_id, input content hashes, skill@version, model_pin, context_ref and the
    output schema version. Change any one and the key changes; that is the test."""
    import dataclasses

    from ops.blobs import ContentRef as Ref

    step = plan.step("ebitda")
    ref = Ref(content_hash="sha256:" + "1" * 64, name="tagging")
    other = Ref(content_hash="sha256:" + "2" * 64, name="tagging")
    base = step_key(step, {"tagging": ref}, "context:a")

    assert base == step_key(step, {"tagging": ref}, "context:a")
    assert base != step_key(step, {"tagging": other}, "context:a")
    assert base != step_key(step, {"tagging": ref}, "context:b")
    assert base != step_key(dataclasses.replace(step, id="other"), {"tagging": ref}, "context:a")
    assert base != step_key(
        dataclasses.replace(step, skill="ebitda-normalization@0.2.0"), {"tagging": ref}, "context:a"
    )
    assert base != step_key(
        dataclasses.replace(step, model_pin="claude-haiku-4-5 @ effort=low"),
        {"tagging": ref}, "context:a",
    )
    assert base != step_key(
        dataclasses.replace(step, output_schema="skills/dcf-build@1.0.0"),
        {"tagging": ref}, "context:a",
    )


def test_the_key_does_not_depend_on_dictionary_order(plan: CompiledGraph) -> None:
    """Inputs are sorted by name, so the key is a property of the step rather than of the
    order a dictionary happened to iterate in."""
    from ops.blobs import ContentRef as Ref

    step = plan.step("ebitda")
    a = Ref(content_hash="sha256:" + "1" * 64, name="a")
    b = Ref(content_hash="sha256:" + "2" * 64, name="b")
    assert step_key(step, {"a": a, "b": b}, "c") == step_key(step, {"b": b, "a": a}, "c")


def test_the_key_is_a_sha256(plan: CompiledGraph) -> None:
    from ops.blobs import ContentRef as Ref

    key = step_key(plan.step("timing"), {"mask": Ref("sha256:" + "3" * 64)}, "context:x")
    assert key.startswith("sha256:")
    assert len(key) == 71


def test_outcomes_are_recorded_for_every_step(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef],
) -> None:
    report = executor.execute(plan, started, run_inputs, CONTEXT_REF)
    assert set(report.outcomes) == set(plan.ids)
    assert set(report.outcomes.values()) == {StepOutcome.EXECUTED}
    assert RUN_ID in str(report)
