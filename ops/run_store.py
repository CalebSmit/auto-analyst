"""The Run Store: one interface over the record, and one SQL implementation of it.

The blueprint says Postgres. Phases 1-24 run on SQLite. Both statements are true at once
only if nothing above this module can tell which is underneath - so the store is a
repository behind a Protocol, chosen by a single URL:

    AA_DB_URL=sqlite:///runs/run_store.db          # the default
    AA_DB_URL=postgresql+psycopg://.../analyst     # the same code, later

Two design choices carry most of the weight.

**Reads return frozen records, never ORM rows.** A caller holding a live `Run` object
holds a session, a lazy loader and a way to write to the record by assignment. Records
are inert copies, so "the run store is the source of truth" stays a fact about the store
rather than a request to callers.

**There is no update path for events, and no way to add one here.** `append_event` and
`events` are the whole surface. That is the first of the three levels described in
`ops.models`; the ORM guard and the database triggers are the two beneath it, and they
are what make the claim true rather than merely intended.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import Engine, create_engine, select
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session, sessionmaker

from ops.models import (
    OUTCOMES_FOR,
    Artifact,
    Base,
    Decision,
    DecisionKind,
    Event,
    Ledger,
    Outcome,
    Quarantine,
    ReleaseLedgerRow,
    ReviewItem,
    Run,
    RunState,
    RunStoreError,
    Step,
    StepKind,
    StepStatus,
    check_transition,
    now_iso,
    utc,
)
from registries.errors import (
    ILLEGAL_TRANSITION,
    LATE_RESULT,
    STALE_DECISION,
    UNKNOWN_RUN,
    diagnose,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = f"sqlite:///{(REPO_ROOT / 'runs' / 'run_store.db').as_posix()}"
URL_VAR = "AA_DB_URL"

__all__ = [
    "ArtifactRecord",
    "DecisionRecord",
    "EventRecord",
    "LateResult",
    "LedgerEntry",
    "QuarantineRecord",
    "ReleaseRecord",
    "LateResult",
    "LedgerEntry",
    "ReviewItemRecord",
    "RunRecord",
    "RunStore",
    "SqlRunStore",
    "StepRecord",
    "UnknownRun",
    "backend_of",
    "open_store",
    "store_url",
]


class UnknownRun(RunStoreError):
    """No run is recorded under that id."""


class LateResult(RunStoreError):
    """A result arrived for an attempt that something newer has already replaced.

    The case that actually happens: a step times out, the executor starts attempt two,
    and attempt one finishes anyway. Its answer is not wrong - it is simply no longer the
    one that counts, and letting it land would mean the ledger recorded a result nothing
    downstream was built on.
    """


# ------------------------------------------------------------------ records


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    engagement_id: str
    state: RunState
    outcome: Outcome | None
    plan_hash: str
    started_at: str
    ended_at: str | None
    versions: dict[str, Any]
    tieout_tolerance: float | None
    sources: tuple[dict[str, Any], ...]
    coverage_gaps: tuple[dict[str, Any], ...]
    cost_usd: float
    model_calls: int
    input_tokens: int
    output_tokens: int
    state_reason: str | None = None
    superseded_by: str | None = None
    active_seconds: float = 0.0
    resumed_at: str | None = None

    @property
    def is_finished(self) -> bool:
        return self.ended_at is not None


@dataclass(frozen=True)
class StepRecord:
    step_id: str
    step_key: str
    kind: str
    status: StepStatus
    skill: str | None = None
    attempts: int = 1
    loop: str | None = None
    result_ref: str | None = None
    started_at: str | None = None
    ended_at: str | None = None


@dataclass(frozen=True)
class LedgerEntry:
    """A completed step, as the ledger remembers it."""

    step_key: str
    step_id: str
    result_ref: str
    media_type: str
    size_bytes: int
    attempt: int
    recorded_at: str


@dataclass(frozen=True)
class EventRecord:
    seq: int
    event_id: str
    ts: str
    run_id: str
    engagement_id: str
    node_id: str
    type: str
    level: str
    message: str
    step_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    diagnostic_code: str | None = None
    cost_usd: float | None = None


@dataclass(frozen=True)
class ArtifactRecord:
    name: str
    content_hash: str
    written_at: str
    path: str | None = None


@dataclass(frozen=True)
class ReleaseRecord:
    """One row of the idempotency ledger: what was released, where, under which event."""

    run_id: str
    content_hash: str
    name: str
    path: str
    version: int
    event_id: str
    released_at: str


@dataclass(frozen=True)
class ReviewItemRecord:
    item_id: str
    kind: str
    subject: str
    state: str
    created_at: str
    detail: dict[str, Any] = field(default_factory=dict)
    run_id: str = ""
    version: int = 1
    owner: str | None = None
    due_at: str | None = None


@dataclass(frozen=True)
class QuarantineRecord:
    step_id: str
    step_key: str
    code: str
    owner: str
    reason: str
    loop: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    attempts: list[Any] = field(default_factory=list)
    guard_output: dict[str, Any] = field(default_factory=dict)
    diagnostic: dict[str, Any] = field(default_factory=dict)
    review_item_id: str | None = None
    held_at: str = ""


@dataclass(frozen=True)
class DecisionRecord:
    item_id: str
    decided_by: str
    decided_at: str
    decision: DecisionKind
    rationale: str = ""
    writes_precedent: bool = False
    skill: str = ""
    proposal: dict[str, Any] = field(default_factory=dict)
    answer: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------- the Protocol


@runtime_checkable
class RunStore(Protocol):
    """What the rest of the system may ask of the record.

    Deliberately absent: anything that changes an event, anything that deletes a run,
    and anything that closes a review item without a person's decision.
    """

    backend: str

    # lifecycle
    def start_run(
        self,
        run_id: str,
        engagement_id: str,
        plan_hash: str,
        versions: dict[str, Any],
        tieout_tolerance: float | None = None,
    ) -> RunRecord: ...
    def run(self, run_id: str) -> RunRecord: ...
    def runs(self, engagement_id: str | None = None) -> tuple[RunRecord, ...]: ...
    def transition(self, run_id: str, target: RunState, reason: str | None = None) -> RunRecord: ...
    def end_run(
        self, run_id: str, state: RunState, outcome: Outcome, reason: str | None = None
    ) -> RunRecord: ...

    # what the run accumulated
    def record_source(self, run_id: str, source: dict[str, Any]) -> None: ...
    def record_gap(self, run_id: str, what: str, why: str) -> None: ...
    def record_model_call(
        self, run_id: str, usd: float, input_tokens: int = 0, output_tokens: int = 0
    ) -> None: ...

    # steps, which double as the checkpoint
    def record_step(
        self,
        run_id: str,
        step_id: str,
        step_key: str,
        kind: str,
        skill: str | None = None,
        loop: str | None = None,
    ) -> None: ...
    def finish_step(
        self, run_id: str, step_id: str, status: StepStatus, reason: str = ...
    ) -> None: ...
    def steps(self, run_id: str) -> tuple[StepRecord, ...]: ...
    def completed_step_keys(self, run_id: str) -> frozenset[str]: ...
    def ensure_step(
        self,
        run_id: str,
        step_id: str,
        step_key: str,
        kind: str,
        skill: str | None = None,
        loop: str | None = None,
    ) -> None: ...
    def begin_attempt(self, run_id: str, step_id: str) -> int: ...
    def commit_step(
        self,
        run_id: str,
        step_id: str,
        step_key: str,
        result_ref: str,
        attempt: int,
        media_type: str = ...,
        size_bytes: int = ...,
    ) -> LedgerEntry: ...
    def ledger_entry(self, step_key: str) -> LedgerEntry | None: ...
    def ledger(self, run_id: str) -> tuple[LedgerEntry, ...]: ...

    # the wall clock that stops while a person is thinking
    def start_clock(self, run_id: str) -> None: ...
    def stop_clock(self, run_id: str) -> float: ...

    # the event stream: append and read, and nothing else
    def append_event(self, event: dict[str, Any]) -> int: ...
    def events(self, run_id: str, since_seq: int = 0) -> tuple[EventRecord, ...]: ...

    # the idempotency ledger: one row per released artifact, with its event
    def record_release(
        self,
        run_id: str,
        content_hash: str,
        path: str,
        version: int,
        name: str,
        event: dict[str, Any],
    ) -> ReleaseRecord: ...
    def release_for(self, run_id: str, content_hash: str) -> ReleaseRecord | None: ...
    def releases(self, run_id: str) -> tuple[ReleaseRecord, ...]: ...

    # artifacts, review, decisions
    def record_artifact(
        self, run_id: str, name: str, content_hash: str, path: str | None = None
    ) -> None: ...
    def artifacts(self, run_id: str) -> tuple[ArtifactRecord, ...]: ...
    def open_review_item(
        self,
        run_id: str,
        item_id: str,
        kind: str,
        subject: str,
        detail: dict[str, Any] | None = None,
        owner: str | None = None,
        due_at: str | None = None,
    ) -> None: ...
    def review_items(self, run_id: str) -> tuple[ReviewItemRecord, ...]: ...
    def open_review_items(
        self, engagement_id: str | None = None
    ) -> tuple[ReviewItemRecord, ...]: ...
    def record_decision(
        self,
        run_id: str,
        item_id: str,
        decided_by: str,
        decision: DecisionKind,
        rationale: str = "",
        writes_precedent: bool = False,
        expected_version: int | None = None,
        proposal: dict[str, Any] | None = None,
        answer: dict[str, Any] | None = None,
        skill: str = "",
    ) -> None: ...
    def decisions(self, run_id: str) -> tuple[DecisionRecord, ...]: ...

    # -- supersession: a newer run covers this one; its record stays
    def mark_superseded_by(self, run_id: str, by: str) -> RunRecord: ...

    # -- quarantine: full context, nothing deleted
    def hold(self, run_id: str, record: QuarantineRecord) -> None: ...
    def quarantines(self, run_id: str) -> tuple[QuarantineRecord, ...]: ...

    def close(self) -> None: ...


# ------------------------------------------------------- the implementation


class SqlRunStore:
    """The SQLAlchemy implementation. One per URL."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._sessions = sessionmaker(bind=engine, expire_on_commit=False)
        self.backend = backend_of(str(engine.url))
        Base.metadata.create_all(engine)

    # -- plumbing

    @contextmanager
    def _session(self) -> Iterator[Session]:
        session = self._sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _row(self, session: Session, run_id: str) -> Run:
        row = session.get(Run, run_id)
        if row is None:
            raise UnknownRun(diagnose(UNKNOWN_RUN, f"no run {run_id!r}", locator=self.backend))
        return row

    # -- lifecycle

    def start_run(
        self,
        run_id: str,
        engagement_id: str,
        plan_hash: str,
        versions: dict[str, Any],
        tieout_tolerance: float | None = None,
    ) -> RunRecord:
        with self._session() as session:
            session.add(
                Run(
                    run_id=run_id,
                    engagement_id=engagement_id,
                    plan_hash=plan_hash,
                    versions=dict(versions),
                    tieout_tolerance=tieout_tolerance,
                    state=RunState.QUEUED,
                    started_at=now_iso(),
                    sources=[],
                    coverage_gaps=[],
                )
            )
        return self.run(run_id)

    def run(self, run_id: str) -> RunRecord:
        with self._session() as session:
            return _as_run(self._row(session, run_id))

    def runs(self, engagement_id: str | None = None) -> tuple[RunRecord, ...]:
        stmt = select(Run).order_by(Run.started_at, Run.run_id)
        if engagement_id is not None:
            stmt = stmt.where(Run.engagement_id == engagement_id)
        with self._session() as session:
            return tuple(_as_run(row) for row in session.scalars(stmt))

    def transition(self, run_id: str, target: RunState, reason: str | None = None) -> RunRecord:
        """Move a run between working states.

        Terminal states are refused here on purpose. Every way a run can end goes
        through `end_run`, and `end_run` is what `ops.manifest.close_out` wraps - so
        there is exactly one door out of a run, and a manifest is behind it.
        """
        if target in OUTCOMES_FOR:
            raise RunStoreError(
                diagnose(
                    ILLEGAL_TRANSITION,
                    f"{target} ends a run; use end_run so the manifest is written",
                    locator="ops.run_store.SqlRunStore.end_run",
                )
            )
        with self._session() as session:
            row = self._row(session, run_id)
            check_transition(RunState(row.state), target)
            row.state = target
            if reason is not None:
                row.state_reason = reason
            return _as_run(row)

    def end_run(
        self, run_id: str, state: RunState, outcome: Outcome, reason: str | None = None
    ) -> RunRecord:
        """Move a run into a terminal state and stamp when it ended.

        This does not write the manifest. `ops.manifest.close_out` does, and it is the
        function the pipeline calls - the split is here so the store stays a store, and
        the "a manifest is written whatever the outcome" guarantee lives in one place
        where it can be read at a glance.
        """
        if state not in OUTCOMES_FOR:
            raise RunStoreError(
                diagnose(
                    ILLEGAL_TRANSITION,
                    f"{state} is not a terminal state; a run does not end in it",
                    locator="ops.models.TERMINAL",
                )
            )
        if outcome not in OUTCOMES_FOR[state]:
            allowed = ", ".join(sorted(OUTCOMES_FOR[state]))
            raise RunStoreError(
                diagnose(
                    ILLEGAL_TRANSITION,
                    f"a {state} run cannot report outcome {outcome!r} (allowed: {allowed})",
                    locator="ops.models.OUTCOMES_FOR",
                )
            )
        with self._session() as session:
            row = self._row(session, run_id)
            check_transition(RunState(row.state), state)
            row.state = state
            row.outcome = outcome
            row.ended_at = now_iso()
            if reason is not None:
                row.state_reason = reason
            return _as_run(row)

    # -- what the run accumulated

    def record_source(self, run_id: str, source: dict[str, Any]) -> None:
        with self._session() as session:
            row = self._row(session, run_id)
            # Reassigned rather than appended: a JSON column mutated in place is not
            # seen as dirty, and the bug is invisible until a manifest is short a source.
            row.sources = [*row.sources, dict(source)]

    def record_gap(self, run_id: str, what: str, why: str) -> None:
        with self._session() as session:
            row = self._row(session, run_id)
            row.coverage_gaps = [*row.coverage_gaps, {"what": what, "why": why}]

    def record_model_call(
        self, run_id: str, usd: float, input_tokens: int = 0, output_tokens: int = 0
    ) -> None:
        with self._session() as session:
            row = self._row(session, run_id)
            row.cost_usd = round(row.cost_usd + usd, 6)
            row.model_calls += 1
            row.input_tokens += input_tokens
            row.output_tokens += output_tokens

    # -- steps, which double as the checkpoint

    def record_step(
        self,
        run_id: str,
        step_id: str,
        step_key: str,
        kind: str,
        skill: str | None = None,
        loop: str | None = None,
    ) -> None:
        with self._session() as session:
            self._row(session, run_id)
            session.add(
                Step(
                    run_id=run_id,
                    step_id=step_id,
                    step_key=step_key,
                    kind=StepKind(kind),
                    skill=skill,
                    loop=loop,
                    status=StepStatus.NOT_REACHED,
                )
            )

    def finish_step(self, run_id: str, step_id: str, status: StepStatus, reason: str = "") -> None:
        """End a step that produced nothing: failed, quarantined, skipped, not reached.

        COMPLETED is refused here and belongs to `commit_step`, which writes the result
        into the ledger in the same transaction. A step that could be marked completed
        without a result would be one the resume frontier re-executes anyway, and the run
        would look finished while quietly paying twice.
        """
        if status == StepStatus.COMPLETED:
            raise RunStoreError(
                diagnose(
                    LATE_RESULT,
                    "a step is completed by commit_step, which writes its result into "
                    "the ledger in the same transaction. finish_step is for the endings "
                    "that produce nothing.",
                    locator=f"{run_id}/{step_id}",
                )
            )
        with self._session() as session:
            row = session.scalars(
                select(Step).where(Step.run_id == run_id, Step.step_id == step_id)
            ).one()
            row.status = status
            row.ended_at = now_iso()
            if reason:
                row.result_ref = None

    def steps(self, run_id: str) -> tuple[StepRecord, ...]:
        with self._session() as session:
            rows = session.scalars(select(Step).where(Step.run_id == run_id).order_by(Step.id))
            return tuple(_as_step(row) for row in rows)

    def completed_step_keys(self, run_id: str) -> frozenset[str]:
        """The resume frontier. A step whose key is in here is satisfied from the record
        rather than executed again, which is why a resumed run costs nothing for the work
        it already paid for.

        Read from the ledger rather than from the step rows. The two are written in one
        transaction so they cannot disagree, but the ledger is the one holding the
        result - and a frontier naming a step with no result to hand back would skip work
        without having done it.
        """
        with self._session() as session:
            rows = session.scalars(select(Ledger.step_key).where(Ledger.run_id == run_id))
            return frozenset(rows)

    def ensure_step(
        self,
        run_id: str,
        step_id: str,
        step_key: str,
        kind: str,
        skill: str | None = None,
        loop: str | None = None,
    ) -> None:
        """Register a step, or update the key of one already registered.

        The executor calls this, because the executor is what computes the key: it needs
        the content hashes of the actual inputs, which do not exist until the producers
        have run. A caller registering steps up front would have to invent a key, and an
        invented key is one the ledger will never match.

        A key that changed since last time means the inputs changed, so it is a different
        unit of work. The old ledger row stays - it is still the answer to the old
        question - and this step is looked up under its new key and runs again. That is
        the whole of "only the steps whose inputs actually changed are paid for twice".
        """
        with self._session() as session:
            self._row(session, run_id)
            row = session.scalars(
                select(Step).where(Step.run_id == run_id, Step.step_id == step_id)
            ).one_or_none()
            if row is None:
                session.add(
                    Step(
                        run_id=run_id,
                        step_id=step_id,
                        step_key=step_key,
                        kind=StepKind(kind),
                        skill=skill,
                        loop=loop,
                        status=StepStatus.NOT_REACHED,
                    )
                )
                return
            if row.step_key != step_key and row.status != StepStatus.COMPLETED:
                row.step_key = step_key
                row.status = StepStatus.NOT_REACHED
                row.attempts = 1
                row.started_at = None
                row.ended_at = None

    def begin_attempt(self, run_id: str, step_id: str) -> int:
        """Claim the next attempt number for a step, and return it.

        The token a result must carry to be accepted. Incremented here rather than at
        commit time, which is what makes a late result identifiable: attempt one comes
        back holding a 1 when the step has already moved on to 2.
        """
        with self._session() as session:
            row = session.scalars(
                select(Step).where(Step.run_id == run_id, Step.step_id == step_id)
            ).one()
            if row.started_at is None:
                row.started_at = now_iso()
            else:
                row.attempts += 1
            return int(row.attempts)

    def commit_step(
        self,
        run_id: str,
        step_id: str,
        step_key: str,
        result_ref: str,
        attempt: int,
        media_type: str = "application/json",
        size_bytes: int = 0,
    ) -> LedgerEntry:
        """Write the ledger row and the step result in one transaction.

        One transaction, because the alternative has a window in it. Ledger first, and a
        resumed run believes a step finished that has no result. Step first, and it
        re-executes work already paid for. Both are silent.

        Refuses a result from a superseded attempt, and refuses a second result for a key
        the ledger already holds - the second by primary key, which is to say by the
        database rather than by a check somebody has to remember to write.
        """
        with self._session() as session:
            row = session.scalars(
                select(Step).where(Step.run_id == run_id, Step.step_id == step_id)
            ).one()
            if attempt != row.attempts:
                raise LateResult(
                    diagnose(
                        LATE_RESULT,
                        f"{step_id} attempt {attempt} finished, but the step is on "
                        f"attempt {row.attempts}",
                        locator=f"{run_id}/{step_id}",
                    )
                )
            existing = session.get(Ledger, step_key)
            if existing is not None:
                raise LateResult(
                    diagnose(
                        LATE_RESULT,
                        f"the ledger already holds this key from attempt "
                        f"{existing.attempt}; a key is written once",
                        locator=f"{run_id}/{step_id}",
                    )
                )
            entry = Ledger(
                step_key=step_key,
                run_id=run_id,
                step_id=step_id,
                result_ref=result_ref,
                media_type=media_type,
                size_bytes=size_bytes,
                attempt=attempt,
                recorded_at=now_iso(),
            )
            session.add(entry)
            row.status = StepStatus.COMPLETED
            row.result_ref = result_ref
            row.ended_at = now_iso()
            return _as_ledger(entry)

    def ledger_entry(self, step_key: str) -> LedgerEntry | None:
        with self._session() as session:
            row = session.get(Ledger, step_key)
            return _as_ledger(row) if row is not None else None

    def ledger(self, run_id: str) -> tuple[LedgerEntry, ...]:
        with self._session() as session:
            rows = session.scalars(
                select(Ledger).where(Ledger.run_id == run_id).order_by(Ledger.recorded_at)
            )
            return tuple(_as_ledger(row) for row in rows)

    # -- the clock that stops while a person is thinking

    def start_clock(self, run_id: str) -> None:
        """Begin an active stretch. Idempotent: starting a running clock changes nothing."""
        with self._session() as session:
            row = self._row(session, run_id)
            if row.resumed_at is None:
                row.resumed_at = now_iso()

    def stop_clock(self, run_id: str) -> float:
        """End the active stretch and bank it. Returns the run's accountable seconds.

        Called when a run blocks on a person, and when it ends. A run waiting on a
        reviewer holds no process, no lock and no context window, so it burns no budget
        either - otherwise the ceiling measures how quickly people answer rather than how
        long the work takes.
        """
        with self._session() as session:
            row = self._row(session, run_id)
            if row.resumed_at is not None:
                row.active_seconds = round(row.active_seconds + _elapsed(row.resumed_at), 3)
                row.resumed_at = None
            return float(row.active_seconds)

    # -- the event stream

    def append_event(self, event: dict[str, Any]) -> int:
        """Append one event and return its sequence number. There is no counterpart."""
        with self._session() as session:
            row = Event(
                event_id=event["event_id"],
                ts=event["ts"],
                run_id=event["run_id"],
                engagement_id=event["engagement_id"],
                node_id=event["node_id"],
                step_id=event.get("step_id"),
                type=event["type"],
                level=event["level"],
                message=event["message"],
                payload=dict(event.get("payload") or {}),
                diagnostic_code=event.get("diagnostic_code"),
                cost_usd=event.get("cost_usd"),
            )
            session.add(row)
            session.flush()
            return int(row.seq)

    def events(self, run_id: str, since_seq: int = 0) -> tuple[EventRecord, ...]:
        with self._session() as session:
            rows = session.scalars(
                select(Event)
                .where(Event.run_id == run_id, Event.seq > since_seq)
                .order_by(Event.seq)
            )
            return tuple(_as_event(row) for row in rows)

    # -- the idempotency ledger: written with the release event, in one transaction

    def record_release(
        self,
        run_id: str,
        content_hash: str,
        path: str,
        version: int,
        name: str,
        event: dict[str, Any],
    ) -> ReleaseRecord:
        """The ledger row and the release event, together or not at all. A second row
        for the same (run, hash) is refused by the unique key, which is the guarantee
        the release gate relies on rather than a check it remembers to make."""
        with self._session() as session:
            session.add(
                Event(
                    event_id=event["event_id"],
                    ts=event["ts"],
                    run_id=event["run_id"],
                    engagement_id=event["engagement_id"],
                    node_id=event["node_id"],
                    step_id=event.get("step_id"),
                    type=event["type"],
                    level=event["level"],
                    message=event["message"],
                    payload=dict(event.get("payload") or {}),
                    diagnostic_code=event.get("diagnostic_code"),
                    cost_usd=event.get("cost_usd"),
                )
            )
            row = ReleaseLedgerRow(
                run_id=run_id,
                content_hash=content_hash,
                name=name,
                path=path,
                version=version,
                event_id=event["event_id"],
            )
            session.add(row)
            session.flush()
            return _as_release(row)

    def release_for(self, run_id: str, content_hash: str) -> ReleaseRecord | None:
        with self._session() as session:
            row = session.scalars(
                select(ReleaseLedgerRow).where(
                    ReleaseLedgerRow.run_id == run_id,
                    ReleaseLedgerRow.content_hash == content_hash,
                )
            ).one_or_none()
            return None if row is None else _as_release(row)

    def releases(self, run_id: str) -> tuple[ReleaseRecord, ...]:
        with self._session() as session:
            rows = session.scalars(
                select(ReleaseLedgerRow)
                .where(ReleaseLedgerRow.run_id == run_id)
                .order_by(ReleaseLedgerRow.id)
            )
            return tuple(_as_release(row) for row in rows)

    # -- artifacts, review, decisions

    def record_artifact(
        self, run_id: str, name: str, content_hash: str, path: str | None = None
    ) -> None:
        with self._session() as session:
            self._row(session, run_id)
            # The same bytes at the same name is the same artifact. A resumed run
            # rebuilds contexts it built before, and recording them twice would make an
            # idempotent pass look like it did something.
            existing = session.scalars(
                select(Artifact).where(
                    Artifact.run_id == run_id,
                    Artifact.name == name,
                    Artifact.content_hash == content_hash,
                )
            ).one_or_none()
            if existing is not None:
                return
            session.add(
                Artifact(
                    run_id=run_id,
                    name=name,
                    content_hash=content_hash,
                    path=path,
                    written_at=now_iso(),
                )
            )

    def artifacts(self, run_id: str) -> tuple[ArtifactRecord, ...]:
        with self._session() as session:
            rows = session.scalars(
                select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.id)
            )
            return tuple(
                ArtifactRecord(
                    name=row.name,
                    content_hash=row.content_hash,
                    written_at=row.written_at,
                    path=row.path,
                )
                for row in rows
            )

    def open_review_item(
        self,
        run_id: str,
        item_id: str,
        kind: str,
        subject: str,
        detail: dict[str, Any] | None = None,
        owner: str | None = None,
        due_at: str | None = None,
    ) -> None:
        with self._session() as session:
            self._row(session, run_id)
            existing = session.scalars(
                select(ReviewItem).where(
                    ReviewItem.run_id == run_id, ReviewItem.item_id == item_id
                )
            ).first()
            if existing is not None:
                # The same question, asked again. A resume re-reaches the step that
                # escalated - nothing about the file changed - and an item id names the
                # question rather than the asking, so this is the row that already exists.
                # Left exactly as it is: somebody may have picked it up, and a resume must
                # not quietly reopen what they are part-way through answering.
                return
            session.add(
                ReviewItem(
                    run_id=run_id,
                    item_id=item_id,
                    kind=kind,
                    subject=subject,
                    detail=dict(detail or {}),
                    state="open",
                    created_at=now_iso(),
                    version=1,
                    owner=owner,
                    due_at=due_at,
                )
            )

    def review_items(self, run_id: str) -> tuple[ReviewItemRecord, ...]:
        with self._session() as session:
            rows = session.scalars(
                select(ReviewItem).where(ReviewItem.run_id == run_id).order_by(ReviewItem.id)
            )
            return tuple(_as_review_item(row) for row in rows)

    def open_review_items(self, engagement_id: str | None = None) -> tuple[ReviewItemRecord, ...]:
        """The queue: everything open, oldest first, across runs - the inbox is of items,
        not of runs.

        Items on a superseded run are not in it. A client sending a corrected statement
        supersedes the run that read the old one, and answering its questions is work
        thrown away - the newer run asks its own. The items stay on the record and on
        their run; they are not asked of anybody.
        """
        with self._session() as session:
            query = (
                select(ReviewItem)
                .join(Run, Run.run_id == ReviewItem.run_id)
                .where(ReviewItem.state == "open", Run.superseded_by.is_(None))
                .order_by(ReviewItem.created_at, ReviewItem.id)
            )
            if engagement_id is not None:
                query = query.where(Run.engagement_id == engagement_id)
            return tuple(_as_review_item(row) for row in session.scalars(query))

    def record_decision(
        self,
        run_id: str,
        item_id: str,
        decided_by: str,
        decision: DecisionKind,
        rationale: str = "",
        writes_precedent: bool = False,
        expected_version: int | None = None,
        proposal: dict[str, Any] | None = None,
        answer: dict[str, Any] | None = None,
        skill: str = "",
    ) -> None:
        """The only thing that closes a review item.

        `decided_by` is required by the column and by the caller. There is no overload
        of this that a machine can reach without naming a person, which is the whole of
        the guarantee that only a human decision may write precedent.

        `expected_version` is the optimistic lock: the version of the item the reviewer
        looked at. A mismatch, or an item already decided, is refused - the second
        reviewer sees the first's decision rather than overwriting it.
        """
        with self._session() as session:
            item = session.scalars(
                select(ReviewItem).where(ReviewItem.run_id == run_id, ReviewItem.item_id == item_id)
            ).one()
            if item.state != "open" or (
                expected_version is not None and item.version != expected_version
            ):
                raise RunStoreError(
                    diagnose(
                        STALE_DECISION,
                        f"{item_id} is {item.state} at version {item.version}; the decision "
                        f"was made against version {expected_version}",
                        locator=f"{run_id}/{item_id}",
                        expected=f"open at version {expected_version}",
                        found=f"{item.state} at version {item.version}",
                    )
                )
            item.state = "decided"
            item.version = item.version + 1
            session.add(
                Decision(
                    run_id=run_id,
                    item_id=item_id,
                    decided_by=decided_by,
                    decided_at=now_iso(),
                    decision=DecisionKind(decision),
                    rationale=rationale,
                    writes_precedent=writes_precedent,
                    skill=skill,
                    proposal=dict(proposal or {}),
                    answer=dict(answer or {}),
                )
            )

    def decisions(self, run_id: str) -> tuple[DecisionRecord, ...]:
        with self._session() as session:
            rows = session.scalars(
                select(Decision).where(Decision.run_id == run_id).order_by(Decision.id)
            )
            return tuple(
                DecisionRecord(
                    item_id=row.item_id,
                    decided_by=row.decided_by,
                    decided_at=row.decided_at,
                    decision=DecisionKind(row.decision),
                    rationale=row.rationale,
                    writes_precedent=row.writes_precedent,
                    skill=row.skill,
                    proposal=dict(row.proposal),
                    answer=dict(row.answer),
                )
                for row in rows
            )

    # -- supersession

    def mark_superseded_by(self, run_id: str, by: str) -> RunRecord:
        """A newer run over a newer source version covers this one.

        A run that has ended moves to `superseded`; its outcome, its end time and its
        manifest stay exactly as they were - the manifest is retained, never overwritten.
        A run still in flight is only marked: it finishes on its own, and nothing here
        cancels it.
        """
        with self._session() as session:
            row = self._row(session, run_id)
            self._row(session, by)
            row.superseded_by = by
            if row.ended_at is not None and row.state != RunState.SUPERSEDED:
                check_transition(RunState(row.state), RunState.SUPERSEDED)
                row.state = RunState.SUPERSEDED
                row.state_reason = f"superseded by {by}"
            return _as_run(row)

    # -- quarantine

    def hold(self, run_id: str, record: QuarantineRecord) -> None:
        """Record that a step was quarantined. Idempotent on `(run_id, step_key)`.

        A quarantined step is not in the ledger, so a resumed pass re-reaches it, re-runs it
        and quarantines it again. Before P60 nothing called this in production and the
        question never arose; the moment it did, the second pass hit the table's own unique
        constraint and raised inside the executor. Holding the same step twice is not new
        information - the first record already says what happened, and the run's events carry
        each attempt - so the second is dropped rather than raising or piling up.
        """
        with self._session() as session:
            self._row(session, run_id)
            existing = session.scalars(
                select(Quarantine).where(
                    Quarantine.run_id == run_id, Quarantine.step_key == record.step_key
                )
            ).first()
            if existing is not None:
                return
            session.add(
                Quarantine(
                    run_id=run_id,
                    step_id=record.step_id,
                    step_key=record.step_key,
                    loop=record.loop,
                    code=record.code,
                    owner=record.owner,
                    reason=record.reason,
                    inputs=dict(record.inputs),
                    attempts=list(record.attempts),
                    guard_output=dict(record.guard_output),
                    diagnostic=dict(record.diagnostic),
                    review_item_id=record.review_item_id,
                    held_at=record.held_at or now_iso(),
                )
            )

    def quarantines(self, run_id: str) -> tuple[QuarantineRecord, ...]:
        with self._session() as session:
            rows = session.scalars(
                select(Quarantine).where(Quarantine.run_id == run_id).order_by(Quarantine.id)
            )
            return tuple(
                QuarantineRecord(
                    step_id=row.step_id,
                    step_key=row.step_key,
                    code=row.code,
                    owner=row.owner,
                    reason=row.reason,
                    loop=row.loop,
                    inputs=dict(row.inputs),
                    attempts=list(row.attempts),
                    guard_output=dict(row.guard_output),
                    diagnostic=dict(row.diagnostic),
                    review_item_id=row.review_item_id,
                    held_at=row.held_at,
                )
                for row in rows
            )

    def close(self) -> None:
        self._engine.dispose()

    def __repr__(self) -> str:
        return f"<SqlRunStore {self.backend}>"


# ------------------------------------------------------------- construction


def store_url(url: str | None = None) -> str:
    """The URL this process should use. Read fresh, like every other config here."""
    return url or os.environ.get(URL_VAR) or DEFAULT_URL


def backend_of(url: str) -> str:
    """`sqlite` or `postgresql`. What the manifest and the console report."""
    return url.split(":", 1)[0].split("+", 1)[0]


def open_store(url: str | None = None) -> SqlRunStore:
    """Open the run store. SQLite and Postgres differ by this string and nothing else."""
    resolved = store_url(url)
    if resolved.startswith("sqlite") and ":memory:" not in resolved:
        _ensure_parent(resolved)
    engine = create_engine(resolved, future=True)
    if backend_of(resolved) == "sqlite":
        _enforce_sqlite_foreign_keys(engine)
    return SqlRunStore(engine)


def _ensure_parent(url: str) -> None:
    path = Path(url.split("///", 1)[1])
    path.parent.mkdir(parents=True, exist_ok=True)


def _enforce_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite ships with foreign keys off. Leaving them off would mean the two backends
    accept different data, which is precisely the divergence the Postgres run exists to
    find - so it would find nothing."""

    @sa_event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# --------------------------------------------------------------- converters


def _as_run(row: Run) -> RunRecord:
    return RunRecord(
        run_id=row.run_id,
        engagement_id=row.engagement_id,
        state=RunState(row.state),
        outcome=Outcome(row.outcome) if row.outcome else None,
        plan_hash=row.plan_hash,
        started_at=row.started_at,
        ended_at=row.ended_at,
        versions=dict(row.versions),
        tieout_tolerance=row.tieout_tolerance,
        sources=tuple(dict(s) for s in row.sources),
        coverage_gaps=tuple(dict(g) for g in row.coverage_gaps),
        cost_usd=row.cost_usd,
        model_calls=row.model_calls,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        state_reason=row.state_reason,
        superseded_by=row.superseded_by,
        active_seconds=row.active_seconds,
        resumed_at=row.resumed_at,
    )


def _elapsed(since_iso: str) -> float:
    """Seconds from an RFC 3339 stamp until now."""
    started = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    return max(0.0, (utc() - started).total_seconds())


def _as_ledger(row: Ledger) -> LedgerEntry:
    return LedgerEntry(
        step_key=row.step_key,
        step_id=row.step_id,
        result_ref=row.result_ref,
        media_type=row.media_type,
        size_bytes=row.size_bytes,
        attempt=row.attempt,
        recorded_at=row.recorded_at,
    )


def _as_step(row: Step) -> StepRecord:
    return StepRecord(
        step_id=row.step_id,
        step_key=row.step_key,
        kind=row.kind,
        status=StepStatus(row.status),
        skill=row.skill,
        attempts=row.attempts,
        loop=row.loop,
        result_ref=row.result_ref,
        started_at=row.started_at,
        ended_at=row.ended_at,
    )


def _as_event(row: Event) -> EventRecord:
    return EventRecord(
        seq=row.seq,
        event_id=row.event_id,
        ts=row.ts,
        run_id=row.run_id,
        engagement_id=row.engagement_id,
        node_id=row.node_id,
        type=row.type,
        level=row.level,
        message=row.message,
        step_id=row.step_id,
        payload=dict(row.payload),
        diagnostic_code=row.diagnostic_code,
        cost_usd=row.cost_usd,
    )


def _as_review_item(row: ReviewItem) -> ReviewItemRecord:
    return ReviewItemRecord(
        item_id=row.item_id,
        kind=row.kind,
        subject=row.subject,
        state=row.state,
        created_at=row.created_at,
        detail=dict(row.detail),
        run_id=row.run_id,
        version=row.version,
        owner=row.owner,
        due_at=row.due_at,
    )


def _as_release(row: ReleaseLedgerRow) -> ReleaseRecord:
    return ReleaseRecord(
        run_id=row.run_id,
        content_hash=row.content_hash,
        name=row.name,
        path=row.path,
        version=row.version,
        event_id=row.event_id,
        released_at=row.released_at,
    )
