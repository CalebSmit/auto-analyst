"""The run store conformance suite.

Every test here takes the `store` fixture, which is parameterised over SQLite and
Postgres. That is the point of the phase's fourth criterion: "one URL apart" is a claim
about behaviour, and a claim about behaviour that is only ever exercised on one backend
is a claim nobody has checked.

SQLite always runs. Postgres runs under `--postgres`, and when it does not, the session
says so in words at the end - see `tests/conftest.py`.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from ops.models import DecisionKind, Outcome, RunState, StepStatus
from ops.run_store import (
    DEFAULT_URL,
    RunStore,
    SqlRunStore,
    UnknownRun,
    backend_of,
    open_store,
    store_url,
)
from tests.p04.conftest import ENGAGEMENT, PLAN_HASH, VERSIONS, started


def test_the_store_satisfies_its_own_protocol(store: SqlRunStore) -> None:
    assert isinstance(store, RunStore)


def test_the_store_says_which_backend_it_is(store: SqlRunStore) -> None:
    """What the console shows and what a support question starts with."""
    assert store.backend in {"sqlite", "postgresql"}
    assert store.backend in repr(store)


def test_a_run_round_trips(store: SqlRunStore) -> None:
    run_id = started(store)
    record = store.run(run_id)
    assert record.run_id == run_id
    assert record.engagement_id == ENGAGEMENT
    assert record.plan_hash == PLAN_HASH
    assert record.versions == VERSIONS
    assert record.tieout_tolerance == 1.0
    assert record.started_at.endswith("Z"), "one timestamp format, on both backends"


def test_a_record_cannot_be_written_to(store: SqlRunStore) -> None:
    """Reads hand back inert copies. A caller holding a live ORM row holds a session and
    a way to change the record by assignment, which is not what "source of truth" means.
    """
    record = store.run(started(store))
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.outcome = Outcome.CLEAN  # type: ignore[misc]


def test_runs_can_be_listed_by_engagement(store: SqlRunStore) -> None:
    started(store, run_id="run_a")
    started(store, run_id="run_b")
    started(store, run_id="run_other", engagement_id="OTHER-2026-01")
    assert [r.run_id for r in store.runs(ENGAGEMENT)] == ["run_a", "run_b"]
    assert len(store.runs()) == 3


def test_an_unknown_run_raises_rather_than_returning_nothing(store: SqlRunStore) -> None:
    with pytest.raises(UnknownRun):
        store.run("nope")


# ------------------------------------------------------------- accumulation


def test_sources_accumulate(store: SqlRunStore) -> None:
    """Guards the JSON-column trap: a list mutated in place is not seen as dirty, and
    the bug is invisible until a manifest is one source short of the truth."""
    run_id = started(store)
    for n in range(3):
        store.record_source(run_id, {"source_id": f"sha256:{n:064x}", "filename": f"{n}.pdf"})
    assert [s["filename"] for s in store.run(run_id).sources] == ["0.pdf", "1.pdf", "2.pdf"]


def test_coverage_gaps_accumulate(store: SqlRunStore) -> None:
    run_id = started(store)
    store.record_gap(run_id, "FY2023 depreciation", "not provided")
    store.record_gap(run_id, "Q3 bank statements", "client could not locate")
    assert [g["what"] for g in store.run(run_id).coverage_gaps] == [
        "FY2023 depreciation",
        "Q3 bank statements",
    ]


def test_cost_accumulates_per_call(store: SqlRunStore) -> None:
    run_id = started(store)
    store.record_model_call(run_id, 0.25, input_tokens=1000, output_tokens=100)
    store.record_model_call(run_id, 0.25, input_tokens=2000, output_tokens=200)
    record = store.run(run_id)
    assert (record.cost_usd, record.model_calls) == (0.5, 2)
    assert (record.input_tokens, record.output_tokens) == (3000, 300)


# -------------------------------------------------- steps and the frontier


def test_a_step_is_recorded_before_it_runs_and_finished_after(store: SqlRunStore) -> None:
    run_id = started(store)
    store.record_step(run_id, "s1", "sha256:" + "1" * 64, "skill", skill="ddr-tagging")
    assert store.steps(run_id)[0].status is StepStatus.NOT_REACHED
    store.finish_step(run_id, "s1", StepStatus.COMPLETED, result_ref="sha256:" + "2" * 64)
    step = store.steps(run_id)[0]
    assert step.status is StepStatus.COMPLETED
    assert step.result_ref == "sha256:" + "2" * 64
    assert step.attempts == 1
    assert step.ended_at is not None


def test_a_retried_step_counts_its_attempts(store: SqlRunStore) -> None:
    run_id = started(store)
    store.record_step(run_id, "s1", "sha256:" + "1" * 64, "skill", skill="ddr-tagging")
    store.finish_step(run_id, "s1", StepStatus.FAILED)
    store.finish_step(run_id, "s1", StepStatus.COMPLETED)
    assert store.steps(run_id)[0].attempts == 2


def test_the_frontier_is_the_set_of_completed_keys(store: SqlRunStore) -> None:
    """What resume is: a query, not a reconstruction. P08 executes from here, and a step
    whose key is in this set is never paid for twice."""
    run_id = started(store)
    keys = {name: f"sha256:{index:064x}" for index, name in enumerate(("s1", "s2", "s3"))}
    for name, key in keys.items():
        store.record_step(run_id, name, key, "skill", skill="ddr-tagging")
    store.finish_step(run_id, "s1", StepStatus.COMPLETED)
    store.finish_step(run_id, "s2", StepStatus.QUARANTINED)

    assert store.completed_step_keys(run_id) == frozenset({keys["s1"]})


def test_a_step_key_is_unique_within_a_run(store: SqlRunStore) -> None:
    """The idempotency key. Two steps sharing one would make a retry ambiguous, which is
    the same as having no key at all."""
    run_id = started(store)
    key = "sha256:" + "3" * 64
    store.record_step(run_id, "s1", key, "skill")
    with pytest.raises(IntegrityError):
        store.record_step(run_id, "s2", key, "skill")


def test_steps_keep_their_plan_order(store: SqlRunStore) -> None:
    run_id = started(store)
    for index, name in enumerate(("first", "second", "third")):
        store.record_step(run_id, name, f"sha256:{index:064x}", "io")
    assert [s.step_id for s in store.steps(run_id)] == ["first", "second", "third"]


# ------------------------------------------------------- referential rules


def test_an_event_for_a_run_that_does_not_exist_is_refused(store: SqlRunStore) -> None:
    """Nothing runs unscoped, so nothing is recorded unscoped either.

    On SQLite this only holds because the store turns foreign keys on - they ship off.
    Left off, the two backends would accept different data and this suite would prove
    nothing by passing on both.
    """
    with pytest.raises(IntegrityError):
        store.append_event(
            {
                "event_id": "evt_orphan",
                "ts": "2026-04-02T09:15:00Z",
                "run_id": "run_that_never_started",
                "engagement_id": ENGAGEMENT,
                "node_id": "dispatcher",
                "type": "skill.dispatched",
                "level": "info",
                "message": "orphan",
            }
        )


def test_an_event_id_is_unique(store: SqlRunStore) -> None:
    run_id = started(store)
    event = {
        "event_id": "evt_same",
        "ts": "2026-04-02T09:15:00Z",
        "run_id": run_id,
        "engagement_id": ENGAGEMENT,
        "node_id": "dispatcher",
        "type": "skill.dispatched",
        "level": "info",
        "message": "once",
    }
    store.append_event(event)
    with pytest.raises(IntegrityError):
        store.append_event(event)


# -------------------------------------------------- review and decisions


def test_only_a_decision_closes_a_review_item(store: SqlRunStore) -> None:
    """There is no `resolve()` on a review item for the same reason there is no machine
    decision path: the only thing that closes one is a person deciding."""
    run_id = started(store)
    store.open_review_item(run_id, "item_1", "tieout", "Total assets differ by 1,240")
    assert store.review_items(run_id)[0].state == "open"
    assert store.decisions(run_id) == ()

    store.record_decision(run_id, "item_1", "C. Smit", DecisionKind.ACCEPTED, rationale="checked")

    assert store.review_items(run_id)[0].state == "decided"
    decision = store.decisions(run_id)[0]
    assert decision.decided_by == "C. Smit"
    assert decision.decision is DecisionKind.ACCEPTED
    assert decision.writes_precedent is False


def test_a_decision_that_names_nobody_is_refused(store: SqlRunStore) -> None:
    """The Precedent Store guarantee is worth exactly as much as this column."""
    run_id = started(store)
    store.open_review_item(run_id, "item_1", "tieout", "subject")
    with pytest.raises(IntegrityError):
        store.record_decision(run_id, "item_1", "", DecisionKind.ACCEPTED)


def test_an_artifact_records_the_hash_that_proves_which_bytes(store: SqlRunStore) -> None:
    run_id = started(store)
    store.record_artifact(run_id, "model.xlsx", "sha256:" + "9" * 64, path="HEND/model.xlsx")
    artifact = store.artifacts(run_id)[0]
    assert artifact.name == "model.xlsx"
    assert artifact.content_hash.startswith("sha256:")
    assert artifact.written_at.endswith("Z")


# -------------------------------------------------------------- the URL


def test_the_backend_is_one_url_apart() -> None:
    """The claim the repository exists to make, checked on the string that makes it."""
    assert backend_of("sqlite:///runs/run_store.db") == "sqlite"
    assert backend_of("postgresql+psycopg://user:pw@localhost/analyst") == "postgresql"
    assert backend_of(DEFAULT_URL) == "sqlite"


def test_the_url_comes_from_config_and_is_read_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AA_DB_URL", raising=False)
    assert store_url() == DEFAULT_URL
    monkeypatch.setenv("AA_DB_URL", "postgresql+psycopg://localhost/x")
    assert store_url() == "postgresql+psycopg://localhost/x"
    assert store_url("sqlite:///explicit.db") == "sqlite:///explicit.db"


def test_a_store_survives_being_reopened(tmp_path: Path) -> None:
    """A crash is not a data loss event. The record is on disk, not in the process."""
    url = f"sqlite:///{(tmp_path / 'reopen.db').as_posix()}"
    first = open_store(url)
    run_id = started(first, run_id="run_survives")
    first.transition(run_id, RunState.RUNNING)
    first.close()

    second = open_store(url)
    assert second.run(run_id).state is RunState.RUNNING
    second.close()
