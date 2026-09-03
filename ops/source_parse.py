"""The Source Parse Store: every row a reader extracted, addressable by locator.

Written once by the readers (P17), never updated, immutable for the life of the run.
Three guards resolve against it: Provenance asks whether a cited source and locator
exist, Tie-Out asks for the rows behind a stated total, and the Numeric Lock compares a
released figure to the value first read.

A locator is a sheet range for a workbook and a page/table/row triple for a document.
Both resolve through this one interface, so a guard never needs to know which kind of
file a figure came from.
"""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ops.models import SourceRow
from ops.run_store import LateResult, SqlRunStore
from registries.errors import LATE_RESULT, diagnose

__all__ = ["Row", "SourceParseStore"]


@dataclass(frozen=True)
class Row:
    label: str
    value: float | None
    raw: str = ""
    ordinal: int = 0


class SourceParseStore:
    """Rows in, rows out, by (run, source, locator). No update."""

    def __init__(self, store: SqlRunStore) -> None:
        self._store = store

    def write(
        self, run_id: str, source_id: str, locator: str, rows: Iterable[Row | dict[str, Any]]
    ) -> int:
        """Record the rows behind a locator. Once.

        A second write to the same locator is refused rather than merged or replaced: a
        guard that could be pointed at rows that changed after the skill read them would
        be checking a different document from the one the figure cites.
        """
        with self._session() as session:
            existing = session.scalars(
                select(SourceRow.id)
                .where(
                    SourceRow.run_id == run_id,
                    SourceRow.source_id == source_id,
                    SourceRow.locator == locator,
                )
                .limit(1)
            ).first()
            if existing is not None:
                raise LateResult(
                    diagnose(
                        LATE_RESULT,
                        f"{locator} under {source_id[:19]}... is already in the parse "
                        f"store for this run. Rows are written once; a re-read is a new "
                        f"run, not an update.",
                        locator=f"{run_id}/{locator}",
                    )
                )
            count = 0
            for ordinal, row in enumerate(rows):
                r = row if isinstance(row, Row) else Row(**row)
                session.add(
                    SourceRow(
                        run_id=run_id,
                        source_id=source_id,
                        locator=locator,
                        ordinal=r.ordinal or ordinal,
                        label=r.label,
                        value=r.value,
                        raw=r.raw,
                    )
                )
                count += 1
            return count

    def rows(self, run_id: str, source_id: str, locator: str) -> tuple[Row, ...]:
        with self._session() as session:
            found = session.scalars(
                select(SourceRow)
                .where(
                    SourceRow.run_id == run_id,
                    SourceRow.source_id == source_id,
                    SourceRow.locator == locator,
                )
                .order_by(SourceRow.ordinal)
            )
            return tuple(
                Row(label=r.label, value=r.value, raw=r.raw, ordinal=r.ordinal) for r in found
            )

    def exists(self, run_id: str, source_id: str, locator: str) -> bool:
        return bool(self.rows(run_id, source_id, locator))

    def locators(self, run_id: str, source_id: str) -> tuple[str, ...]:
        with self._session() as session:
            found = session.scalars(
                select(SourceRow.locator)
                .where(SourceRow.run_id == run_id, SourceRow.source_id == source_id)
                .distinct()
            )
            return tuple(sorted(found))

    def _session(self) -> AbstractContextManager[Session]:
        return self._store._session()  # noqa: SLF001 - the same database, the same rules
