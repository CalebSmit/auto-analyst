"""Retries, late results, quarantine, and the run that stops to wait for a person.

Three exit criteria live here. The middle one is the interesting one: a step times out,
the executor starts a second attempt, and the *first* one finishes anyway. Its answer is
not wrong - it is simply no longer the one anything downstream was built on - and letting
it land would put a result in the ledger that nothing else agrees with.
"""

from __future__ import annotations

from graph.compile import CompiledGraph
from graph.execute import Blocked, StepExecutor, StepOutcome, TransportFailure, step_key
from ops.blobs import ContentRef, LocalContentStore
from ops.models import RunState, StepStatus
from ops.run_store import LateResult, SqlRunStore
from tests.p08.conftest import CONTEXT_REF, Recorder

# ---------------------------------------------------------------- retries


class FlakyThenFine:
    """Fails one named step with a transport error N times, then lets it through.

    Named rather than "the first step" because how many attempts a step gets is the
    recipe's business: monthly-refresh gives its skill steps one retry and its io steps
    none, which is a real difference and the tests should be about the right step.
    """

    def __init__(self, blobs: LocalContentStore, failures: int, at: str = "timing") -> None:
        self.blobs = blobs
        self.failures = failures
        self.at = at
        self.attempts: list[int] = []

    def __call__(self, attempt):  # noqa: ANN001 - a test double
        if attempt.step_id != self.at:
            return self.blobs.put_json({"step": attempt.step_id}, name=attempt.step_id)
        self.attempts.append(attempt.attempt)
        if len(self.attempts) <= self.failures:
            raise TransportFailure("the connection dropped")
        return self.blobs.put_json({"step": attempt.step_id}, name=attempt.step_id)


def test_a_transport_failure_is_retried(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore, store: SqlRunStore,
) -> None:
    """monthly-refresh gives its skill steps one retry, and the constraint registry
    caps any step at two. One transport failure is survivable."""
    runner = FlakyThenFine(blobs, failures=1, at="timing")
    report = executor_with(runner).execute(plan, started, run_inputs, CONTEXT_REF)

    assert report.finished
    assert runner.attempts[:2] == [1, 2], "the second attempt carried a new token"
    failures = [e for e in store.events(started) if e.type == "step.transport_failed"]
    assert len(failures) == 1


def test_exhausting_the_retries_quarantines_the_step(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore, store: SqlRunStore,
) -> None:
    """Never a silent give-up. The step is held with its reason, dependent work stops,
    and the run says which state it is in."""
    report = executor_with(FlakyThenFine(blobs, failures=99)).execute(
        plan, started, run_inputs, CONTEXT_REF
    )

    assert report.quarantined == ["timing"]
    assert report.state is RunState.QUARANTINED
    assert not report.finished
    assert store.run(started).state is RunState.QUARANTINED
    quarantined = [e for e in store.events(started) if e.type == "step.quarantined"]
    assert len(quarantined) == 1
    assert quarantined[0].level == "error"


def test_a_failure_that_is_not_transport_is_not_retried(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], store: SqlRunStore,
) -> None:
    """A schema or guard failure is not a retry - it is a repair loop with changed input,
    and it belongs to the Loop Controller. Retrying a step whose input has not changed is
    the single most common way these systems waste money."""
    tries: list[int] = []

    def explodes(attempt):  # noqa: ANN001
        tries.append(attempt.attempt)
        raise ValueError("the output did not match its schema")

    report = executor_with(explodes).execute(plan, started, run_inputs, CONTEXT_REF)

    assert tries == [1], "a non-transport failure was retried"
    assert report.quarantined == ["intake"], "and it quarantined instead"


def test_the_retry_ceiling_comes_from_the_constraints(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore,
) -> None:
    """The recipe asks for retries and the constraint registry caps them. A recipe that
    wanted more would be raising a ceiling in the file that wants the extra go."""
    skill_step = FlakyThenFine(blobs, failures=99, at="timing")
    executor_with(skill_step).execute(plan, started, run_inputs, CONTEXT_REF)
    assert skill_step.attempts == [1, 2], "timing declares one retry, so two attempts"


def test_a_step_that_quarantined_leaves_nothing_in_the_ledger(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore, store: SqlRunStore,
) -> None:
    """So a resume re-runs it rather than believing it finished."""
    executor_with(FlakyThenFine(blobs, failures=99)).execute(
        plan, started, run_inputs, CONTEXT_REF
    )
    assert {e.step_id for e in store.ledger(started)} == {"intake", "mask"}
    by_id = {s.step_id: s for s in store.steps(started)}
    assert by_id["timing"].status is StepStatus.QUARANTINED


def test_dependent_work_stops_at_a_quarantine(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore,
) -> None:
    report = executor_with(FlakyThenFine(blobs, failures=99)).execute(
        plan, started, run_inputs, CONTEXT_REF
    )
    for step_id in plan.order[3:]:
        assert report.outcomes[step_id] is StepOutcome.NOT_REACHED


# ------------------------------------------------------------ late results


def test_a_late_result_cannot_overwrite_the_retry_that_replaced_it(
    store: SqlRunStore, plan: CompiledGraph, started: str, blobs: LocalContentStore,
) -> None:
    """The exit criterion, at the store level where the guarantee actually lives.

    A step times out, attempt two starts, and attempt one finishes anyway. The ledger
    takes attempt two's answer, because that is the one the run continued on.
    """
    key = step_key(plan.step("intake"), {}, CONTEXT_REF)
    store.ensure_step(started, "intake", key, "io")

    first = store.begin_attempt(started, "intake")   # times out
    second = store.begin_attempt(started, "intake")  # the retry
    assert (first, second) == (1, 2)

    store.commit_step(started, "intake", key, "sha256:" + "b" * 64, second)

    # ... and now attempt one comes back.
    try:
        store.commit_step(started, "intake", key, "sha256:" + "a" * 64, first)
        raise AssertionError("the late result was accepted")
    except LateResult as late:
        assert late.diagnostic.code == "PROCESS.LATE_RESULT"

    assert store.ledger_entry(key).result_ref == "sha256:" + "b" * 64
    assert store.ledger_entry(key).attempt == 2


def test_a_second_result_for_a_key_is_refused_by_the_database(
    store: SqlRunStore, plan: CompiledGraph, started: str,
) -> None:
    """A key is written once. That is what makes a retry, a resume and a manual re-run
    the same operation, and it is the primary key rather than a check somebody has to
    remember to write."""
    key = step_key(plan.step("intake"), {}, CONTEXT_REF)
    store.ensure_step(started, "intake", key, "io")
    attempt = store.begin_attempt(started, "intake")
    store.commit_step(started, "intake", key, "sha256:" + "c" * 64, attempt)

    try:
        store.commit_step(started, "intake", key, "sha256:" + "d" * 64, attempt)
        raise AssertionError("a key was written twice")
    except LateResult as late:
        assert "written once" in str(late)


def test_the_executor_survives_a_late_result(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore, store: SqlRunStore,
) -> None:
    """End to end: the run continues on what the ledger holds, and says out loud that it
    discarded something."""
    class CommitsBehindItsBack:
        """Writes a result for the key directly, then returns a different one - which is
        what a late first attempt looks like from the executor's side."""

        def __init__(self) -> None:
            self.done = False

        def __call__(self, attempt):  # noqa: ANN001
            if attempt.step_id == "intake" and not self.done:
                self.done = True
                store.commit_step(
                    attempt.run_id, "intake", attempt.step_key,
                    "sha256:" + "f" * 64, attempt.attempt,
                )
            return blobs.put_json({"step": attempt.step_id}, name=attempt.step_id)

    report = executor_with(CommitsBehindItsBack()).execute(
        plan, started, run_inputs, CONTEXT_REF
    )

    discarded = [e for e in store.events(started) if e.type == "step.result_discarded"]
    assert len(discarded) == 1
    assert discarded[0].payload["diagnostic_code"] == "PROCESS.LATE_RESULT"
    assert report.finished, "the run continued on what the ledger held"


# --------------------------------------------------- checkpoint and exit


class Blocks:
    """Succeeds until it reaches one step, then needs a person."""

    def __init__(self, blobs: LocalContentStore, at: str) -> None:
        self.blobs = blobs
        self.at = at
        self.calls: list[str] = []

    def __call__(self, attempt):  # noqa: ANN001 - a test double
        self.calls.append(attempt.step_id)
        if attempt.step_id == self.at:
            raise Blocked("item_1", "Is Bob's LLC Checking owner compensation?")
        return self.blobs.put_json({"step": attempt.step_id}, name=attempt.step_id)


def test_a_blocked_run_checkpoints_and_exits(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore, store: SqlRunStore,
) -> None:
    """The exit criterion. A run waiting on a person holds no process, no lock and no
    context window - which is what makes "four hours excluding time waiting on a human"
    an honest number rather than a measure of how fast people answer email."""
    report = executor_with(Blocks(blobs, "tagging")).execute(
        plan, started, run_inputs, CONTEXT_REF
    )

    assert report.blocked_on == "tagging"
    assert report.state is RunState.WAITING
    assert store.run(started).state is RunState.WAITING
    assert store.run(started).ended_at is None, "a blocked run has not ended"


def test_blocking_opens_a_review_item_and_says_so(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore, store: SqlRunStore,
) -> None:
    """A block that queued nothing would be a run waiting for something nobody was asked
    to do."""
    executor_with(Blocks(blobs, "tagging")).execute(plan, started, run_inputs, CONTEXT_REF)

    items = store.review_items(started)
    assert [i.item_id for i in items] == ["item_1"]
    assert items[0].state == "open"
    queued = [e for e in store.events(started) if e.type == "hitl.item.queued"]
    assert len(queued) == 1
    assert queued[0].payload["item_id"] == "item_1"


def test_the_wall_clock_stops_while_a_person_is_thinking(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore, store: SqlRunStore,
) -> None:
    """The phase note, as a test. The clock banks what the run actually spent and then
    stops - so the budget measures the work, not the queue."""
    import time

    executor_with(Blocks(blobs, "tagging")).execute(plan, started, run_inputs, CONTEXT_REF)

    banked = store.run(started).active_seconds
    assert banked > 0, "the run spent some time and none of it was recorded"
    assert store.run(started).resumed_at is None, "the clock is still running"

    time.sleep(0.05)  # a person, thinking
    assert store.run(started).active_seconds == banked, "waiting burned budget"


def test_the_work_already_done_before_a_block_is_kept(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore, store: SqlRunStore,
) -> None:
    """Blocking is an ending for this pass, not a rollback. Everything before the block
    is in the ledger, and the resume starts at the step that stopped."""
    blocker = Blocks(blobs, "tagging")
    executor_with(blocker).execute(plan, started, run_inputs, CONTEXT_REF)

    assert blocker.calls == ["intake", "mask", "timing", "tagging"]
    assert len(store.ledger(started)) == 3

    store.transition(started, RunState.RUNNING)
    survivor = Recorder(blobs)
    report = executor_with(survivor).execute(plan, started, run_inputs, CONTEXT_REF)

    assert survivor.calls == list(plan.order[3:]), "the resume did not start where it stopped"
    assert report.satisfied == ["intake", "mask", "timing"]


def test_the_steps_after_a_block_are_not_reached(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore,
) -> None:
    """Recorded as not reached rather than absent, so the manifest can show where the run
    stopped instead of implying it finished."""
    report = executor_with(Blocks(blobs, "tagging")).execute(
        plan, started, run_inputs, CONTEXT_REF
    )
    for step_id in plan.order[4:]:
        assert report.outcomes[step_id] is StepOutcome.NOT_REACHED


def test_the_clock_runs_while_the_run_runs(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], store: SqlRunStore,
) -> None:
    """The other half. A clock that never ran would pass the test above trivially."""
    report = executor.execute(plan, started, run_inputs, CONTEXT_REF)
    assert report.active_seconds > 0
    assert store.run(started).active_seconds == report.active_seconds
