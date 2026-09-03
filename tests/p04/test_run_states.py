"""The seven run states, and the one door out of a run.

The phase asks that all seven be reachable and asserted. Reachable is checked twice on
purpose: once over the transition table as a graph, which proves the machine has no
stranded state, and once by driving a real run into each one, which proves the store
agrees with the table.
"""

from __future__ import annotations

import pytest

from ops.models import (
    OUTCOMES_FOR,
    TERMINAL,
    TRANSITIONS,
    IllegalTransition,
    Outcome,
    RunState,
)
from ops.run_store import RunStoreError, SqlRunStore, UnknownRun
from tests.p04.conftest import started

# The list in the phase file, verbatim. If these ever disagree, one of them is wrong and
# it should be an argument rather than a silent divergence.
DECLARED = (
    "queued",
    "running",
    "waiting",
    "quarantined",
    "halted",
    "delivered",
    "superseded",
)


def test_there_are_exactly_seven_states_and_they_are_the_declared_ones() -> None:
    assert tuple(state.value for state in RunState) == DECLARED


def test_the_transition_table_covers_every_state() -> None:
    """A state missing from the table would raise KeyError at the worst moment."""
    assert set(TRANSITIONS) == set(RunState)
    for targets in TRANSITIONS.values():
        assert targets <= set(RunState)


def test_every_state_is_reachable_from_queued() -> None:
    """No stranded state. Walked as a graph rather than asserted one by one, so a state
    added later without a way in fails here instead of quietly never occurring."""
    seen = {RunState.QUEUED}
    frontier = [RunState.QUEUED]
    while frontier:
        current = frontier.pop()
        for target in TRANSITIONS[current]:
            if target not in seen:
                seen.add(target)
                frontier.append(target)
    assert seen == set(RunState), f"unreachable: {sorted(set(RunState) - seen)}"


def test_only_terminal_states_have_no_way_out() -> None:
    for state, targets in TRANSITIONS.items():
        if state is RunState.SUPERSEDED:
            assert not targets
        elif state in TERMINAL:
            assert targets == frozenset({RunState.SUPERSEDED})
        else:
            assert targets, f"{state} is not terminal but has no exit"


# --------------------------------------------------- driven against the store


def test_a_run_starts_queued(store: SqlRunStore) -> None:
    run_id = started(store)
    assert store.run(run_id).state is RunState.QUEUED
    assert store.run(run_id).ended_at is None


@pytest.mark.parametrize("state", [RunState.RUNNING, RunState.WAITING, RunState.QUARANTINED])
def test_each_working_state_is_reachable_on_a_real_run(store: SqlRunStore, state: RunState) -> None:
    run_id = started(store)
    store.transition(run_id, RunState.RUNNING)
    if state is not RunState.RUNNING:
        store.transition(run_id, state, reason="because the test said so")
    record = store.run(run_id)
    assert record.state is state
    assert record.ended_at is None, "a working state is not the end of a run"


@pytest.mark.parametrize(
    ("state", "outcome"),
    [
        (RunState.DELIVERED, Outcome.CLEAN),
        (RunState.DELIVERED, Outcome.RELEASED_WITH_REVIEW),
        (RunState.HALTED, Outcome.HALTED),
        (RunState.HALTED, Outcome.BLOCKED),
        (RunState.SUPERSEDED, Outcome.BLOCKED),
    ],
)
def test_each_terminal_state_is_reachable_on_a_real_run(
    store: SqlRunStore, state: RunState, outcome: Outcome
) -> None:
    run_id = started(store, run_id=f"run_{state}_{outcome}")
    store.transition(run_id, RunState.RUNNING)
    record = store.end_run(run_id, state, outcome)
    assert record.state is state
    assert record.outcome is outcome
    assert record.ended_at is not None, "a run that ended must say when"
    assert record.is_finished


def test_all_seven_states_are_asserted_by_this_module(store: SqlRunStore) -> None:
    """The phase's criterion, checked as one statement rather than inferred from the
    fact that several tests above happen to cover it between them."""
    reached: set[RunState] = set()

    run_id = started(store, run_id="run_sweep_working")
    reached.add(store.run(run_id).state)
    reached.add(store.transition(run_id, RunState.RUNNING).state)
    reached.add(store.transition(run_id, RunState.WAITING, reason="review item").state)
    store.transition(run_id, RunState.RUNNING)
    reached.add(store.transition(run_id, RunState.QUARANTINED, reason="step failed").state)
    store.transition(run_id, RunState.RUNNING)
    reached.add(store.end_run(run_id, RunState.DELIVERED, Outcome.CLEAN).state)
    reached.add(store.end_run(run_id, RunState.SUPERSEDED, Outcome.CLEAN).state)

    halted = started(store, run_id="run_sweep_halted")
    store.transition(halted, RunState.RUNNING)
    reached.add(store.end_run(halted, RunState.HALTED, Outcome.HALTED).state)

    assert reached == set(RunState)


# ------------------------------------------------------------- the refusals


def test_an_illegal_transition_is_refused_with_a_diagnostic(store: SqlRunStore) -> None:
    run_id = started(store)
    with pytest.raises(IllegalTransition) as raised:
        store.transition(run_id, RunState.WAITING)  # queued -> waiting: never
    assert raised.value.diagnostic.code == "PROCESS.ILLEGAL_TRANSITION"
    assert raised.value.diagnostic.what_now
    assert store.run(run_id).state is RunState.QUEUED, "the refusal left the run alone"


def test_a_terminal_state_cannot_be_reached_by_transition(store: SqlRunStore) -> None:
    """Because `end_run` is what the manifest writer wraps. If a run could slip into a
    terminal state through the side door, it could end without a record."""
    run_id = started(store)
    store.transition(run_id, RunState.RUNNING)
    for state in TERMINAL:
        with pytest.raises(RunStoreError) as raised:
            store.transition(run_id, state)
        assert "end_run" in str(raised.value)
    assert store.run(run_id).state is RunState.RUNNING


def test_a_finished_run_cannot_go_back_to_work(store: SqlRunStore) -> None:
    run_id = started(store)
    store.transition(run_id, RunState.RUNNING)
    store.end_run(run_id, RunState.HALTED, Outcome.HALTED)
    with pytest.raises(IllegalTransition):
        store.transition(run_id, RunState.RUNNING)


def test_a_delivered_run_cannot_report_that_it_halted(store: SqlRunStore) -> None:
    """The outcome and the state are two views of the same fact. A record where they
    disagree is a record a reviewer cannot use."""
    run_id = started(store)
    store.transition(run_id, RunState.RUNNING)
    with pytest.raises(RunStoreError) as raised:
        store.end_run(run_id, RunState.DELIVERED, Outcome.HALTED)
    assert "outcome" in str(raised.value)
    assert store.run(run_id).state is RunState.RUNNING


def test_a_halted_run_cannot_report_that_it_was_clean(store: SqlRunStore) -> None:
    run_id = started(store)
    store.transition(run_id, RunState.RUNNING)
    with pytest.raises(RunStoreError):
        store.end_run(run_id, RunState.HALTED, Outcome.CLEAN)


def test_a_working_state_is_not_an_ending(store: SqlRunStore) -> None:
    run_id = started(store)
    with pytest.raises(RunStoreError) as raised:
        store.end_run(run_id, RunState.RUNNING, Outcome.CLEAN)
    assert "terminal" in str(raised.value)


def test_every_terminal_state_declares_which_outcomes_it_may_carry() -> None:
    assert set(OUTCOMES_FOR) == TERMINAL
    for state, allowed in OUTCOMES_FOR.items():
        assert allowed, f"{state} allows no outcome at all"
        assert allowed <= set(Outcome)


def test_an_unknown_run_is_a_diagnostic_not_a_none(store: SqlRunStore) -> None:
    with pytest.raises(UnknownRun) as raised:
        store.run("run_that_never_was")
    assert raised.value.diagnostic.code == "PROCESS.UNKNOWN_RUN"
