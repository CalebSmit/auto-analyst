"""What a quarantined run leaves behind, which until now was nothing.

`constraints.yaml` has said since it was written that exhaustion always produces an
artifact - a quarantine record or a review item. `RunStore.hold()` is the only writer of a
quarantine record, and it was reachable from exactly one place: `LoopController.exhaust`,
behind a path nothing in production could enter. So the quarantine store was permanently
empty. A run stopped, an event was emitted, and nobody was told: no record, no review item,
nobody assigned, nothing in the queue.

Beside it, `on_failure` - parsed, validated, carried on every `Step`, folded into every plan
hash, rendered on every plan - was read zero times by anything that executes. `monthly-refresh`
declares `halt` on intake, mask and release, `review` on qc, and `quarantine` on the rest,
and all eight behaved identically.
"""

from __future__ import annotations

from typing import Any

from graph.execute import Blocked, TransportFailure
from ops.models import RunState
from tests.p08.conftest import CONTEXT_REF


def runner_failing(step_id: str, blobs: Any, how: type[Exception] = ValueError) -> Any:
    """Succeeds at everything except `step_id`."""
    from tests.p08.conftest import Recorder

    good = Recorder(blobs)

    def run(attempt: Any) -> Any:
        if attempt.step_id == step_id:
            raise how(f"{step_id} could not be done")
        return good(attempt)

    return run


# ------------------------------------------------------------------- the artifact


def test_a_quarantined_step_leaves_a_record(
    executor_with: Any, plan: Any, started: str, run_inputs: Any, blobs: Any, store: Any
) -> None:
    """The rule `constraints.yaml` states and nothing honoured. Before this, `quarantines()`
    was empty on every run that had ever quarantined - which was all of them that failed."""
    report = executor_with(runner_failing("timing", blobs)).execute(
        plan, started, run_inputs, CONTEXT_REF
    )

    assert report.quarantined == ["timing"]
    (held,) = store.quarantines(started)
    assert held.step_id == "timing"
    assert held.step_key, "a record with no key cannot be matched to the step that failed"
    assert held.reason, "and one with no reason says only that something went wrong"
    assert held.held_at


def test_a_resumed_pass_over_the_same_step_does_not_write_a_second(
    executor_with: Any, plan: Any, started: str, run_inputs: Any, blobs: Any, store: Any
) -> None:
    """A quarantined step is not in the ledger, so a resumed pass re-reaches it and
    quarantines it again. The first version of this hit the table's own unique constraint
    and the exception came back up through the executor."""
    for _ in range(2):
        executor_with(runner_failing("timing", blobs)).execute(
            plan, started, run_inputs, CONTEXT_REF
        )

    assert len(store.quarantines(started)) == 1, "an artifact, not an artifact pile"


def test_every_ending_that_quarantines_leaves_one(
    executor_with: Any, plan: Any, started: str, run_inputs: Any, blobs: Any, store: Any
) -> None:
    """Transport exhaustion is the other way in, and it wrote nothing either."""
    executor_with(runner_failing("timing", blobs, TransportFailure)).execute(
        plan, started, run_inputs, CONTEXT_REF
    )

    (held,) = store.quarantines(started)
    assert held.code == "PROCESS.TRANSPORT_EXHAUSTED"
    (event,) = [e for e in store.events(started) if e.type == "step.quarantined"]
    assert event.diagnostic_code == "PROCESS.TRANSPORT_EXHAUSTED"


# --------------------------------------------------------------- on_failure, finally read


def test_a_step_declaring_review_opens_a_review_item(
    executor_with: Any, plan: Any, started: str, run_inputs: Any, blobs: Any, store: Any
) -> None:
    """`qc` declares `on_failure: review`, which said a person should look at this and told
    nobody. The item is what puts it in front of somebody."""
    executor_with(runner_failing("qc", blobs)).execute(plan, started, run_inputs, CONTEXT_REF)

    items = [i for i in store.review_items(started) if i.kind == "quarantined"]
    assert len(items) == 1, "the step that says review opened no review item"
    # The step's label, not its id: "QC / tie-out review" is what a person reading a queue
    # needs, and the id is on the item.
    assert items[0].subject.startswith(plan.step("qc").label)
    assert items[0].item_id.startswith("quarantine:qc:")
    assert items[0].detail["quarantine"] is True


def test_a_step_declaring_quarantine_opens_none(
    executor_with: Any, plan: Any, started: str, run_inputs: Any, blobs: Any, store: Any
) -> None:
    """The three policies have to differ, or reading `on_failure` has changed nothing."""
    executor_with(runner_failing("timing", blobs)).execute(plan, started, run_inputs, CONTEXT_REF)

    assert [i for i in store.review_items(started) if i.kind == "quarantined"] == []
    assert store.quarantines(started), "a record either way, though"


def test_the_policy_is_on_the_event_so_it_can_be_read_back(
    executor_with: Any, plan: Any, started: str, run_inputs: Any, blobs: Any, store: Any
) -> None:
    executor_with(runner_failing("qc", blobs)).execute(plan, started, run_inputs, CONTEXT_REF)
    (event,) = [e for e in store.events(started) if e.type == "step.quarantined"]
    assert event.payload["on_failure"] == "review"


# ------------------------------------------------------------------------- halt


def test_a_step_declaring_halt_ends_the_pass(
    executor_with: Any, plan: Any, started: str, run_inputs: Any, blobs: Any, store: Any
) -> None:
    """`intake` and `mask` declare `halt` in every shipped recipe, and it behaved as an
    ordinary quarantine a later pass could pick up again. Nothing partial escapes: every
    remaining step is not reached, including branches that do not depend on it."""
    from graph.execute import StepOutcome

    report = executor_with(runner_failing("intake", blobs)).execute(
        plan, started, run_inputs, CONTEXT_REF
    )

    assert report.halt_on == "intake"
    assert report.quarantined == ["intake"]
    later = [s for s in plan.order if s != "intake"]
    assert all(report.outcomes[s] is StepOutcome.NOT_REACHED for s in later)


def test_the_executor_never_moves_a_run_to_a_terminal_state(
    executor_with: Any, plan: Any, started: str, run_inputs: Any, blobs: Any, store: Any
) -> None:
    """There is exactly one door out of a run and a manifest is behind it.
    `store.transition` refuses a terminal state for that reason, so a halt that the executor
    tried to finish itself would raise rather than end the run. The driver closes it out."""
    executor_with(runner_failing("intake", blobs)).execute(
        plan, started, run_inputs, CONTEXT_REF
    )
    assert store.run(started).state is not RunState.HALTED
    assert store.run(started).state is RunState.QUARANTINED


def test_halt_is_not_the_blocked_path(
    executor_with: Any, plan: Any, started: str, run_inputs: Any, blobs: Any, store: Any
) -> None:
    """They are opposite endings that share only "the pass stops here". `Blocked` is
    `WAITING`, not terminal, a question in somebody's inbox, and the run resumes when it is
    answered. `halt` is an ending and nothing partial escapes."""

    def blocks(attempt: Any) -> Any:
        if attempt.step_id == "intake":
            raise Blocked("item-1", "somebody has to say")
        raise AssertionError("unreachable")

    report = executor_with(blocks).execute(plan, started, run_inputs, CONTEXT_REF)
    assert report.blocked_on == "intake"
    assert report.halt_on is None
    assert store.run(started).state is RunState.WAITING
    assert store.quarantines(started) == (), "a question is not a failure"
