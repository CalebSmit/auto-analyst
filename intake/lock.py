"""The Engagement Lock: one run at a time per deal, so two runs cannot fight.

An advisory lock keyed on engagement_id, with a visible queue and a timeout that alerts
rather than force-releasing. A second run queues rather than starting alongside the
first, because both would write to the same mask vault and the same output folder - two
runs masking the same account concurrently and issuing different tokens for it raises
no error; it breaks period alignment downstream and produces a plausible wrong answer,
the worst failure shape this system has.

The lock is a primary key. The second insert fails, and that failure is the queue's
front door: nothing here checks-then-inserts, so two launches in the same second
serialise on the database rather than on luck.

A lock held past its timeout is an incident, not something to clear automatically.
There is no method here that releases a lock without the holder's run_id.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ops.events import EventBus
from ops.models import EngagementLockRow, LockQueueRow, RunState
from ops.run_store import SqlRunStore
from registries.errors import ENGAGEMENT_LOCKED, RUN_STALLED, Diagnostic, diagnose

__all__ = ["EngagementLock", "Holder", "LockResult"]

NODE = "engagement_lock"


@dataclass(frozen=True)
class Holder:
    engagement_id: str
    run_id: str
    acquired_at: str
    expires_at: str


@dataclass(frozen=True)
class LockResult:
    engagement_id: str
    run_id: str
    acquired: bool
    position: int = 0
    """0 when acquired; otherwise this run's place in the queue, 1 being next."""
    diagnostic: Diagnostic | None = None

    @property
    def code(self) -> str | None:
        return None if self.diagnostic is None else self.diagnostic.code


class EngagementLock:
    def __init__(
        self,
        store: SqlRunStore,
        bus: EventBus,
        timeout: timedelta = timedelta(hours=6),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.bus = bus
        self.timeout = timeout
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    # -- acquire

    def acquire(self, engagement_id: str, run_id: str) -> LockResult:
        """Take the lock or join the queue. Never both, never neither."""
        now = self._clock()
        try:
            with self.store._session() as session:  # noqa: SLF001 - the same database
                session.add(
                    EngagementLockRow(
                        engagement_id=engagement_id,
                        run_id=run_id,
                        acquired_at=_stamp(now),
                        expires_at=_stamp(now + self.timeout),
                    )
                )
        except IntegrityError:
            return self._queue(engagement_id, run_id, now)
        run = self.store.run(run_id)
        if run.state is RunState.QUEUED:
            self.store.transition(run_id, RunState.RUNNING, reason="engagement lock acquired")
        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type="lock.acquired",
            message=f"{engagement_id}: lock acquired by {run_id}",
            payload={"expires_at": _stamp(now + self.timeout)},
        )
        return LockResult(engagement_id, run_id, acquired=True)

    def _queue(self, engagement_id: str, run_id: str, now: datetime) -> LockResult:
        holder = self.holder(engagement_id)
        with self.store._session() as session:  # noqa: SLF001
            session.add(
                LockQueueRow(engagement_id=engagement_id, run_id=run_id, queued_at=_stamp(now))
            )
        position = [q.run_id for q in self.queue(engagement_id)].index(run_id) + 1
        d = diagnose(
            ENGAGEMENT_LOCKED,
            f"{engagement_id} is locked by {holder.run_id if holder else '?'}; {run_id} is "
            f"queued at position {position}",
            locator=engagement_id,
        )
        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type="lock.queued",
            message=d.detail,
            level="warn",
            diagnostic_code=d.code,
            payload={"position": position, "holder": holder.run_id if holder else None},
        )
        return LockResult(engagement_id, run_id, acquired=False, position=position, diagnostic=d)

    # -- release

    def release(self, engagement_id: str, run_id: str) -> LockResult | None:
        """The holder gives the lock up, and the next queued run takes it. Only the
        holder can: a release naming any other run is refused."""
        with self.store._session() as session:  # noqa: SLF001
            row = session.get(EngagementLockRow, engagement_id)
            if row is None or row.run_id != run_id:
                raise PermissionError(
                    f"{run_id} does not hold the lock on {engagement_id}"
                    + (f" ({row.run_id} does)" if row else "")
                )
            session.delete(row)
        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type="lock.released",
            message=f"{engagement_id}: lock released by {run_id}",
        )
        waiting = self.queue(engagement_id)
        if not waiting:
            return None
        next_run = waiting[0].run_id
        with self.store._session() as session:  # noqa: SLF001
            queued = session.scalars(
                select(LockQueueRow).where(
                    LockQueueRow.engagement_id == engagement_id, LockQueueRow.run_id == next_run
                )
            ).one()
            session.delete(queued)
        return self.acquire(engagement_id, next_run)

    # -- reading

    def holder(self, engagement_id: str) -> Holder | None:
        with self.store._session() as session:  # noqa: SLF001
            row = session.get(EngagementLockRow, engagement_id)
            return (
                Holder(row.engagement_id, row.run_id, row.acquired_at, row.expires_at)
                if row
                else None
            )

    def queue(self, engagement_id: str) -> tuple[LockQueueRow, ...]:
        with self.store._session() as session:  # noqa: SLF001
            rows = session.scalars(
                select(LockQueueRow)
                .where(LockQueueRow.engagement_id == engagement_id)
                .order_by(LockQueueRow.queued_at, LockQueueRow.id)
            ).all()
            session.expunge_all()
            return tuple(rows)

    def overdue(self) -> tuple[Holder, ...]:
        """Locks held past their timeout. Reported as incidents; never cleared here."""
        now = self._clock()
        with self.store._session() as session:  # noqa: SLF001
            rows = session.scalars(select(EngagementLockRow)).all()
            late = tuple(
                Holder(r.engagement_id, r.run_id, r.acquired_at, r.expires_at)
                for r in rows
                if _parse(r.expires_at) < now
            )
        for holder in late:
            d = diagnose(
                RUN_STALLED,
                f"{holder.run_id} has held the lock on {holder.engagement_id} since "
                f"{holder.acquired_at}, past its timeout at {holder.expires_at}. Not cleared: "
                f"a lock held past its timeout is an incident.",
                locator=holder.engagement_id,
            )
            self.bus.emit(
                run_id=holder.run_id,
                engagement_id=holder.engagement_id,
                node_id=NODE,
                type="lock.timeout",
                message=d.detail,
                level="error",
                diagnostic_code=d.code,
                payload={"expires_at": holder.expires_at, "what_now": d.what_now},
            )
        return late


def _stamp(at: datetime) -> str:
    return at.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
