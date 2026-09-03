"""The intake register: every file that arrived, and every folder nobody claimed.

Over the same database as the run store, through the same session, so an intake row and
the run that consumed it are one record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from ops.models import IntakeFile, UnclaimedFolder
from ops.run_store import SqlRunStore

__all__ = ["IntakeStore", "IntakeRow", "UnclaimedRow"]


@dataclass(frozen=True)
class IntakeRow:
    engagement_id: str
    source_id: str
    filename: str
    path: str
    watch_id: str
    document_type: str | None
    kind: str
    mime: str
    bytes: int
    source_version: int
    received_at: str
    state: str
    consumed_by: str | None = None

    def as_source(self) -> dict[str, Any]:
        """The run manifest's `sources` row."""
        return {
            "source_id": self.source_id,
            "filename": self.filename,
            "document_type": self.document_type or "unknown",
            "source_version": self.source_version,
            "received_at": self.received_at,
            "bytes": self.bytes,
        }


@dataclass(frozen=True)
class UnclaimedRow:
    watch_id: str
    location: str
    first_seen: str
    last_seen: str
    files: int


class IntakeStore:
    def __init__(self, store: SqlRunStore) -> None:
        self._store = store

    # -- files

    def record(self, row: IntakeRow) -> IntakeRow:
        with self._store._session() as session:  # noqa: SLF001 - the same database
            session.add(
                IntakeFile(
                    engagement_id=row.engagement_id,
                    source_id=row.source_id,
                    filename=row.filename,
                    path=row.path,
                    watch_id=row.watch_id,
                    document_type=row.document_type,
                    kind=row.kind,
                    mime=row.mime,
                    bytes=row.bytes,
                    source_version=row.source_version,
                    received_at=row.received_at,
                    state=row.state,
                    consumed_by=row.consumed_by,
                )
            )
        return row

    def known(self, engagement_id: str, source_id: str) -> IntakeRow | None:
        with self._store._session() as session:  # noqa: SLF001
            found = session.scalars(
                select(IntakeFile).where(
                    IntakeFile.engagement_id == engagement_id, IntakeFile.source_id == source_id
                )
            ).one_or_none()
            return _as_row(found) if found else None

    def versions_of(self, engagement_id: str, filename: str) -> tuple[IntakeRow, ...]:
        """Every version of a filename on this engagement, oldest first."""
        with self._store._session() as session:  # noqa: SLF001
            rows = session.scalars(
                select(IntakeFile)
                .where(IntakeFile.engagement_id == engagement_id, IntakeFile.filename == filename)
                .order_by(IntakeFile.source_version)
            )
            return tuple(_as_row(r) for r in rows)

    def files(self, engagement_id: str) -> tuple[IntakeRow, ...]:
        with self._store._session() as session:  # noqa: SLF001
            rows = session.scalars(
                select(IntakeFile)
                .where(IntakeFile.engagement_id == engagement_id)
                .order_by(IntakeFile.received_at, IntakeFile.id)
            )
            return tuple(_as_row(r) for r in rows)

    def pending(self, engagement_id: str) -> tuple[IntakeRow, ...]:
        return tuple(r for r in self.files(engagement_id) if r.state == "pending")

    def held(self, engagement_id: str) -> tuple[IntakeRow, ...]:
        return tuple(r for r in self.files(engagement_id) if r.state == "held")

    def current_set(self, engagement_id: str) -> tuple[IntakeRow, ...]:
        """The whole current intake set: the latest version of every bound filename,
        whether or not an earlier run already consumed it. A run consumes this, never a
        delta."""
        latest: dict[str, IntakeRow] = {}
        for row in self.files(engagement_id):
            if row.state == "held":
                continue
            have = latest.get(row.filename)
            if have is None or row.source_version > have.source_version:
                latest[row.filename] = row
        return tuple(sorted(latest.values(), key=lambda r: (r.filename, r.source_version)))

    def mark_consumed(self, engagement_id: str, source_ids: list[str], run_id: str) -> int:
        with self._store._session() as session:  # noqa: SLF001
            rows = session.scalars(
                select(IntakeFile).where(
                    IntakeFile.engagement_id == engagement_id,
                    IntakeFile.source_id.in_(source_ids),
                    IntakeFile.state == "pending",
                )
            ).all()
            for row in rows:
                row.state = "consumed"
                row.consumed_by = run_id
            return len(rows)

    def runs_that_consumed(self, engagement_id: str, filename: str) -> tuple[tuple[int, str], ...]:
        """(source_version, run_id) for every earlier version of a filename a run took."""
        return tuple(
            (r.source_version, r.consumed_by)
            for r in self.versions_of(engagement_id, filename)
            if r.consumed_by
        )

    # -- unclaimed folders

    def report_unclaimed(self, watch_id: str, location: str, files: int, now: str) -> UnclaimedRow:
        with self._store._session() as session:  # noqa: SLF001
            row = session.scalars(
                select(UnclaimedFolder).where(
                    UnclaimedFolder.watch_id == watch_id, UnclaimedFolder.location == location
                )
            ).one_or_none()
            if row is None:
                row = UnclaimedFolder(
                    watch_id=watch_id, location=location, first_seen=now, last_seen=now, files=files
                )
                session.add(row)
            else:
                row.last_seen = now
                row.files = files
            return UnclaimedRow(watch_id, location, row.first_seen, now, files)

    def unclaimed(self) -> tuple[UnclaimedRow, ...]:
        with self._store._session() as session:  # noqa: SLF001
            rows = session.scalars(select(UnclaimedFolder).order_by(UnclaimedFolder.id))
            return tuple(
                UnclaimedRow(r.watch_id, r.location, r.first_seen, r.last_seen, r.files)
                for r in rows
            )


def _as_row(row: IntakeFile) -> IntakeRow:
    return IntakeRow(
        engagement_id=row.engagement_id,
        source_id=row.source_id,
        filename=row.filename,
        path=row.path,
        watch_id=row.watch_id,
        document_type=row.document_type,
        kind=row.kind,
        mime=row.mime,
        bytes=row.bytes,
        source_version=row.source_version,
        received_at=row.received_at,
        state=row.state,
        consumed_by=row.consumed_by,
    )
