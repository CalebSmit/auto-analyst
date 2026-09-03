"""The tables behind the record, and the one rule the database itself enforces.

Six models, as the phase says: run, step, event, artifact, review_item, decision. They
are deliberately boring - the interesting content of a run lives in the event stream and
in the manifest assembled from it, not in a widening schema here.

Three things in this module are not boring, and each is here rather than in a convention:

**The event table is append-only, in the database.** Not by API discipline, which is one
careless session away from being false. `event` carries BEFORE UPDATE and BEFORE DELETE
triggers on both SQLite and Postgres, and an ORM flush guard on top so the failure
arrives as a diagnostic rather than as a dialect-specific database error. A trace that
can be edited is not evidence of anything.

**Run state is a closed machine.** Seven states and an explicit transition table, so
"running -> delivered without ever completing a step" is a refusal rather than a row.

**Timestamps are stored as RFC 3339 text, in UTC, with a Z.** SQLite has no timezone-aware
type; Postgres does. Storing datetimes would mean the two backends round-trip differently
and the manifest would not be byte-identical across them - which is the exact class of
divergence the Postgres run exists to catch, so it is not worth introducing one on
purpose. Fixed-width UTC text also sorts correctly, and it is already the shape both
event@1.0.0 and run_manifest@1.0.0 ask for.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    DDL,
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import event as sa_event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from registries.errors import (
    APPEND_ONLY_VIOLATION,
    ILLEGAL_TRANSITION,
    DiagnosticError,
    diagnose,
)

__all__ = [
    "AppendOnlyViolation",
    "Artifact",
    "Base",
    "Decision",
    "Event",
    "IllegalTransition",
    "Ledger",
    "Outcome",
    "OUTCOMES_FOR",
    "Quarantine",
    "ReviewItem",
    "Run",
    "RunState",
    "Step",
    "StepStatus",
    "TERMINAL",
    "TRANSITIONS",
    "now_iso",
    "utc",
]


# --------------------------------------------------------------------- time


def utc() -> datetime:
    return datetime.now(tz=UTC)


def now_iso() -> str:
    """RFC 3339, UTC, with a Z. The one timestamp format this system writes."""
    return utc().isoformat(timespec="microseconds").replace("+00:00", "Z")


# -------------------------------------------------------------------- state


class RunState(StrEnum):
    """The seven states a run can be in.

    Four are worth saying out loud because they are the ones people conflate:

    * `waiting` - stopped on a person. The run holds no lock and burns no wall clock.
    * `quarantined` - stopped on itself: a step failed in a way retrying will not fix.
    * `halted` - ended without delivering. A guard refused, and nothing partial escapes.
    * `superseded` - a newer run replaced this one. Its record stays; it is not deleted.
    """

    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    QUARANTINED = "quarantined"
    HALTED = "halted"
    DELIVERED = "delivered"
    SUPERSEDED = "superseded"


TERMINAL: frozenset[RunState] = frozenset(
    {RunState.HALTED, RunState.DELIVERED, RunState.SUPERSEDED}
)

# Small and closed on purpose. A move that is not in here is a defect at the call site
# until somebody changes this table deliberately.
TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.QUEUED: frozenset({RunState.RUNNING, RunState.SUPERSEDED}),
    RunState.RUNNING: frozenset(
        {
            RunState.WAITING,
            RunState.QUARANTINED,
            RunState.HALTED,
            RunState.DELIVERED,
            RunState.SUPERSEDED,
        }
    ),
    RunState.WAITING: frozenset({RunState.RUNNING, RunState.HALTED, RunState.SUPERSEDED}),
    RunState.QUARANTINED: frozenset({RunState.RUNNING, RunState.HALTED, RunState.SUPERSEDED}),
    RunState.HALTED: frozenset({RunState.SUPERSEDED}),
    RunState.DELIVERED: frozenset({RunState.SUPERSEDED}),
    RunState.SUPERSEDED: frozenset(),
}


class Outcome(StrEnum):
    """What the run amounted to. Mirrors run_manifest@1.0.0 exactly.

    Four values rather than pass/fail because "halted before producing anything" and
    "delivered but three figures needed a person" are not the same event.
    """

    CLEAN = "clean"
    RELEASED_WITH_REVIEW = "released_with_review"
    HALTED = "halted"
    BLOCKED = "blocked"


# Which outcomes a terminal state may carry. A delivered run that reports `halted` is a
# contradiction in the permanent record, so it is refused where it is written, not
# discovered later by a reader.
OUTCOMES_FOR: dict[RunState, frozenset[Outcome]] = {
    RunState.DELIVERED: frozenset({Outcome.CLEAN, Outcome.RELEASED_WITH_REVIEW}),
    RunState.HALTED: frozenset({Outcome.HALTED, Outcome.BLOCKED}),
    # A superseded run keeps whatever it had reached. It may have delivered and been
    # replaced, or been stopped before it produced anything.
    RunState.SUPERSEDED: frozenset(Outcome),
}


class StepStatus(StrEnum):
    """Mirrors the manifest's step status enum. `not_reached` is the one that matters:
    a halted run's later steps are recorded as never having started, rather than absent,
    so the manifest can show where the run stopped instead of implying it finished."""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    QUARANTINED = "quarantined"
    NOT_REACHED = "not_reached"


class StepKind(StrEnum):
    SKILL = "skill"
    TOOL = "tool"
    GUARD = "guard"
    HUMAN = "human"
    IO = "io"


class DecisionKind(StrEnum):
    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    ESCALATED = "escalated"


# --------------------------------------------------------------- exceptions


class RunStoreError(DiagnosticError):
    """The run store refused something."""


class IllegalTransition(RunStoreError):
    """A run state change the machine does not allow."""


class AppendOnlyViolation(RunStoreError):
    """Something tried to change or remove a recorded event."""


def _enum_values(enum: type[StrEnum]) -> list[str]:
    return [member.value for member in enum]


def _one_of(column: str, enum: type[StrEnum]) -> str:
    listed = ", ".join(f"'{value}'" for value in _enum_values(enum))
    return f"{column} IN ({listed})"


# ------------------------------------------------------------------- tables


class Base(DeclarativeBase):
    pass


class Run(Base):
    """One run, and everything about it that is a single value rather than a stream.

    `sources` and `coverage_gaps` are JSON columns rather than tables of their own. The
    phase names six models and this keeps to six: both are per-run lists that are only
    ever read whole, by the manifest writer, and giving each a table would buy joins
    nobody performs. The intake register that owns source identity properly is P07's.
    """

    __tablename__ = "run"
    __table_args__ = (
        CheckConstraint(_one_of("state", RunState), name="run_state_is_known"),
        CheckConstraint(
            "outcome IS NULL OR " + _one_of("outcome", Outcome), name="run_outcome_is_known"
        ),
        Index("ix_run_engagement", "engagement_id"),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    engagement_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default=RunState.QUEUED)
    state_reason: Mapped[str | None] = mapped_column(Text, default=None)
    outcome: Mapped[str | None] = mapped_column(String(24), default=None)

    plan_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    started_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)
    ended_at: Mapped[str | None] = mapped_column(String(32), default=None)

    versions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    tieout_tolerance: Mapped[float | None] = mapped_column(Float, default=None)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    coverage_gaps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    # The cost meter's counters. Incremented as calls happen so the console can show a
    # running total; the manifest reads the same four numbers at the end.
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    model_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    superseded_by: Mapped[str | None] = mapped_column(String(64), default=None)

    # Wall clock the run is accountable for. A run waiting on a reviewer holds no
    # process, no lock and no context window, so it should burn no budget either -
    # otherwise the ceiling measures how fast people answer rather than how long the
    # work takes.
    active_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    resumed_at: Mapped[str | None] = mapped_column(String(32), default=None)
    """When the current active stretch began. None while the run is not running."""

    def __repr__(self) -> str:
        return f"<Run {self.run_id} {self.state} {self.outcome or '-'}>"


class Step(Base):
    """One compiled plan step and what became of it.

    `step_key` is the idempotency key, and it is also the checkpoint: on resume, a step
    whose key is already recorded as completed is satisfied from here rather than
    re-executed. That is why resume is replay rather than a second code path - the
    frontier is a query, not a reconstruction.
    """

    __tablename__ = "step"
    __table_args__ = (
        UniqueConstraint("run_id", "step_id", name="uq_step_run_step"),
        UniqueConstraint("run_id", "step_key", name="uq_step_run_key"),
        CheckConstraint(_one_of("kind", StepKind), name="step_kind_is_known"),
        CheckConstraint(_one_of("status", StepStatus), name="step_status_is_known"),
        CheckConstraint("attempts >= 1", name="step_attempts_at_least_one"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id"), nullable=False)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False)
    step_key: Mapped[str] = mapped_column(String(71), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    skill: Mapped[str | None] = mapped_column(String(64), default=None)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=StepStatus.NOT_REACHED)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    loop: Mapped[str | None] = mapped_column(String(64), default=None)
    result_ref: Mapped[str | None] = mapped_column(String(71), default=None)
    started_at: Mapped[str | None] = mapped_column(String(32), default=None)
    ended_at: Mapped[str | None] = mapped_column(String(32), default=None)

    def __repr__(self) -> str:
        return f"<Step {self.run_id}/{self.step_id} {self.status}>"


class Ledger(Base):
    """One row per completed step, keyed by its idempotency key.

    Written in the same transaction as the step result, which is the whole point: a
    ledger that could be one commit behind would let a resumed run re-execute a step
    whose result already exists, or - worse - believe a step finished that did not.

    The key is the primary key, so a repeat write is refused by the database rather than
    by a check somebody has to remember. That is what makes a retry, a crash resume and
    a manual re-run the same operation.
    """

    __tablename__ = "ledger"
    __table_args__ = (
        CheckConstraint("attempt >= 1", name="ledger_attempt_at_least_one"),
        Index("ix_ledger_run", "run_id"),
    )

    step_key: Mapped[str] = mapped_column(String(71), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id"), nullable=False)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False)
    result_ref: Mapped[str] = mapped_column(String(71), nullable=False)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False, default="application/json")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    recorded_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    def __repr__(self) -> str:
        return f"<Ledger {self.step_id} {self.step_key[:15]}... -> {self.result_ref[:15]}...>"


class SourceRow(Base):
    """One row a reader extracted, under its source and locator, immutable for the run.

    The Source Parse Store. Three guards resolve against it: Provenance asks whether a
    cited source and locator exist, Tie-Out asks for the rows behind a stated total, and
    the Numeric Lock compares a released figure to the value first read. Written once by
    the readers, never updated - a guard that could be pointed at rows that changed after
    the skill read them would be checking a different document.
    """

    __tablename__ = "source_row"
    __table_args__ = (
        UniqueConstraint("run_id", "source_id", "locator", "ordinal", name="uq_source_row"),
        Index("ix_source_row_locator", "run_id", "source_id", "locator"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id"), nullable=False)
    source_id: Mapped[str] = mapped_column(String(71), nullable=False)
    locator: Mapped[str] = mapped_column(String(256), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    value: Mapped[float | None] = mapped_column(Float, default=None)
    raw: Mapped[str] = mapped_column(Text, nullable=False, default="")
    """The cell as read, before any parsing. What the numeric lock compares against."""


class VaultEntry(Base):
    """One mask token and the value it stands for, encrypted, scoped to an engagement.

    The only table in the system that can re-identify anything. Two edges only: the
    Masking Engine writes it, the Unmasking Engine reads it, and neither runs a model.
    `value_hash` is a keyed HMAC of the plaintext so the masker can find an existing
    token for a value without decrypting anything - which is what makes the same account
    mask to the same token across runs weeks apart.

    `retention_until` is the retention field. Setting the policy is Risk / IT's decision
    in the blueprint; the column exists so that decision has somewhere to land.
    """

    __tablename__ = "vault"
    __table_args__ = (
        UniqueConstraint("engagement_id", "value_hash", name="uq_vault_value"),
        Index("ix_vault_engagement", "engagement_id"),
    )

    engagement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    value_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)
    retention_until: Mapped[str] = mapped_column(String(32), nullable=False)
    first_run_id: Mapped[str | None] = mapped_column(String(64), default=None)

    def __repr__(self) -> str:
        return f"<VaultEntry {self.engagement_id} {self.token}>"


class Event(Base):
    """One thing one node reported having just done.

    Append-only, enforced below by database triggers and an ORM flush guard. `seq` is a
    surrogate key so the stream has a total order even when two events share a
    timestamp; `event_id` is the identity the contract carries.
    """

    __tablename__ = "event"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_event_id"),
        CheckConstraint(
            "level IN ('info', 'warn', 'error', 'guard', 'loop')", name="event_level_is_known"
        ),
        Index("ix_event_run", "run_id", "seq"),
        Index("ix_event_engagement", "engagement_id"),
    )

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ts: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id"), nullable=False)
    engagement_id: Mapped[str] = mapped_column(String(64), nullable=False)
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    step_id: Mapped[str | None] = mapped_column(String(128), default=None)
    type: Mapped[str] = mapped_column(String(96), nullable=False)
    level: Mapped[str] = mapped_column(String(8), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    diagnostic_code: Mapped[str | None] = mapped_column(String(64), default=None)
    cost_usd: Mapped[float | None] = mapped_column(Float, default=None)

    def __repr__(self) -> str:
        return f"<Event {self.seq} {self.type} {self.node_id}>"


class Artifact(Base):
    """Something the run wrote, and the hash that proves which bytes."""

    __tablename__ = "artifact"
    __table_args__ = (UniqueConstraint("run_id", "name", "content_hash", name="uq_artifact"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    written_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)
    path: Mapped[str | None] = mapped_column(Text, default=None)


class ReviewItem(Base):
    """Something a person has to answer before the run can continue or release.

    An item is opened by the pipeline and closed only by a Decision. There is no
    `resolve()` on this model for the same reason there is no machine decision path:
    the only thing that closes a review item is a person deciding.
    """

    __tablename__ = "review_item"
    __table_args__ = (
        UniqueConstraint("run_id", "item_id", name="uq_review_item"),
        CheckConstraint("state IN ('open', 'decided')", name="review_state_is_known"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(8), nullable=False, default="open")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class Decision(Base):
    """A person's answer on a review item.

    `decided_by` cannot be empty, and nothing in the system writes a row here without
    one. This is the only kind of record that may later write to the Precedent Store,
    and that guarantee is worth exactly as much as this column.
    """

    __tablename__ = "decision"
    __table_args__ = (
        UniqueConstraint("run_id", "item_id", name="uq_decision_item"),
        CheckConstraint(_one_of("decision", DecisionKind), name="decision_is_known"),
        CheckConstraint("length(decided_by) > 0", name="decision_has_a_person"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_by: Mapped[str] = mapped_column(String(128), nullable=False)
    decided_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    writes_precedent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


# -------------------------------------------------- append-only, three ways

# 1. The API. Neither EventBus nor RunStore exposes a way to change an event.
# 2. The ORM, below: a flush carrying a modified or deleted Event is refused with a
#    diagnostic, in the same words on every backend.
# 3. The database, below that: triggers, so a raw UPDATE through a psql prompt or a
#    migration script fails too. Levels 1 and 2 are for us; level 3 is the one that is
#    still true when somebody bypasses this code entirely.

_APPEND_ONLY_MESSAGE = "PROCESS.APPEND_ONLY_VIOLATION - the event table is append-only"

_SQLITE_NO_UPDATE = DDL(  # type: ignore[no-untyped-call]
    'CREATE TRIGGER IF NOT EXISTS event_no_update BEFORE UPDATE ON "event" '
    f"BEGIN SELECT RAISE(ABORT, '{_APPEND_ONLY_MESSAGE}'); END"
)
_SQLITE_NO_DELETE = DDL(  # type: ignore[no-untyped-call]
    'CREATE TRIGGER IF NOT EXISTS event_no_delete BEFORE DELETE ON "event" '
    f"BEGIN SELECT RAISE(ABORT, '{_APPEND_ONLY_MESSAGE}'); END"
)
_PG_FUNCTION = DDL(  # type: ignore[no-untyped-call]
    "CREATE OR REPLACE FUNCTION event_append_only() RETURNS trigger AS $ev$ "
    f"BEGIN RAISE EXCEPTION '{_APPEND_ONLY_MESSAGE}'; END; $ev$ LANGUAGE plpgsql"
)
_PG_TRIGGER = DDL(  # type: ignore[no-untyped-call]
    'CREATE TRIGGER event_append_only BEFORE UPDATE OR DELETE ON "event" '
    "FOR EACH ROW EXECUTE FUNCTION event_append_only()"
)

sa_event.listen(Event.__table__, "after_create", _SQLITE_NO_UPDATE.execute_if(dialect="sqlite"))
sa_event.listen(Event.__table__, "after_create", _SQLITE_NO_DELETE.execute_if(dialect="sqlite"))
sa_event.listen(Event.__table__, "after_create", _PG_FUNCTION.execute_if(dialect="postgresql"))
sa_event.listen(Event.__table__, "after_create", _PG_TRIGGER.execute_if(dialect="postgresql"))


@sa_event.listens_for(Session, "before_flush")
def _refuse_to_change_an_event(session: Session, flush_context: Any, instances: Any) -> None:
    """Refuse a flush that would modify or remove a recorded event.

    Registered on Session rather than on one sessionmaker deliberately: the guarantee is
    about the event table, not about who opened the connection.
    """
    changed = [obj for obj in session.dirty if isinstance(obj, Event) and session.is_modified(obj)]
    removed = [obj for obj in session.deleted if isinstance(obj, Event)]
    if not changed and not removed:
        return
    what = []
    if changed:
        what.append(f"{len(changed)} modified")
    if removed:
        what.append(f"{len(removed)} deleted")
    raise AppendOnlyViolation(
        diagnose(
            APPEND_ONLY_VIOLATION,
            f"a flush carried {' and '.join(what)} event row(s)",
            locator="ops.models.Event",
        )
    )


def check_transition(current: RunState, target: RunState) -> None:
    """Raise unless the machine allows this move."""
    if target in TRANSITIONS[current]:
        return
    allowed = ", ".join(sorted(TRANSITIONS[current])) or "nothing - it is terminal"
    raise IllegalTransition(
        diagnose(
            ILLEGAL_TRANSITION,
            f"{current} -> {target} is not a legal move (from {current}: {allowed})",
            locator="ops.models.TRANSITIONS",
        )
    )


class Quarantine(Base):
    """Where a step goes when it has failed every way it is allowed to.

    Full context, nothing summarised: the inputs it was given, every iteration the loop
    admitted (with the key each one ran under and what triggered it), the guard output
    that rejected the last attempt, and the diagnostic that stopped it. Nothing is
    deleted. A quarantined step can be re-run by key once the cause is fixed, and the
    idempotency ledger makes that safe rather than duplicative.

    `review_item_id` is the item exhaustion opened. A quarantine that opened no item is
    a quarantine nobody will look at, which is why the Loop Controller opens one every
    time and records it here.
    """

    __tablename__ = "quarantine"
    __table_args__ = (
        UniqueConstraint("run_id", "step_key", name="uq_quarantine_run_key"),
        CheckConstraint("length(code) > 0", name="quarantine_has_a_code"),
        CheckConstraint("length(owner) > 0", name="quarantine_has_an_owner"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id"), nullable=False)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False)
    step_key: Mapped[str] = mapped_column(String(71), nullable=False)
    loop: Mapped[str | None] = mapped_column(String(64), default=None)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    owner: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    attempts: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    guard_output: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    diagnostic: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    review_item_id: Mapped[str | None] = mapped_column(String(64), default=None)
    held_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    def __repr__(self) -> str:
        return f"<Quarantine {self.run_id}/{self.step_id} {self.code}>"
