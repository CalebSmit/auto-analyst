# ruff: noqa: E501 - the patterns read better on one line each
"""The Source Parse Store: every row a reader extracted, addressable by locator.

Written once by the readers (P17), never updated, immutable for the life of the run.
Three guards resolve against it: Provenance asks whether a cited source and locator
exist, Tie-Out asks for the rows behind a stated total, and the Numeric Lock compares a
released figure to the value first read.

A locator is a sheet range for a workbook and a page/table/row triple for a document.
Both resolve through this one interface, so a guard never needs to know which kind of
file a figure came from:

    TB_FY25!B44:B47      rows 44-47 of column B on that sheet
    'Income Stmt'!C12    one cell, by row, on a sheet with a space in its name
    p14/t2/r7            page 14, table 2, row 7
    p14/t2               every row of that table
    p3/text              the text lines on page 3

Readers write *blocks* - one column of a sheet, one table of a document - and the
resolver answers any locator that sits inside a block, so a figure may cite a sub-range
the reader never wrote as its own key.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ops.models import SourceRow
from ops.run_store import LateResult, SqlRunStore
from registries.errors import LATE_RESULT, diagnose

__all__ = ["DocLocator", "Row", "SheetRange", "SourceParseStore", "parse_locator"]


@dataclass(frozen=True)
class Row:
    label: str
    value: float | None
    raw: str = ""
    ordinal: int = 0


# ---------------------------------------------------------------- locators


@dataclass(frozen=True)
class SheetRange:
    sheet: str
    column: str
    row_start: int
    column_end: str
    row_end: int

    @property
    def single_column(self) -> bool:
        return self.column == self.column_end

    def block(self, row_start: int, row_end: int) -> str:
        """The locator a reader writes for this column over those rows."""
        return f"{_quote(self.sheet)}!{self.column}{row_start}:{self.column}{row_end}"


@dataclass(frozen=True)
class DocLocator:
    page: int
    table: int | None = None
    row: int | None = None
    text: bool = False
    column: int | None = None
    """Which column of figures, on a table that has more than one.

    Every audited statement is comparative, and the column is what says which period a
    figure belongs to. It lives in the locator rather than in the row because a row with
    several values would have to be understood by all three guards that resolve here -
    provenance, tie-out and the numeric lock - and each would have to be told which value
    it meant. One column per block leaves them as they were, and makes footing *more*
    exact: a stated total is re-added against its own column rather than a mixture of
    years that happens to sum.

    `None` is a table with a single column of figures, which is what every locator written
    before this meant and still means.
    """

    @property
    def block(self) -> str:
        if self.text:
            return f"p{self.page}/text"
        if self.table is None:
            return f"p{self.page}"
        if self.column is None:
            return f"p{self.page}/t{self.table}"
        return f"p{self.page}/t{self.table}/c{self.column}"


_SHEET = re.compile(
    r"^(?:'(?P<quoted>[^']+)'|(?P<bare>[^!']+))!(?P<c1>[A-Z]{1,3})(?P<r1>\d+)(?::(?P<c2>[A-Z]{1,3})(?P<r2>\d+))?$"
)
_DOC = re.compile(
    r"^p(?P<page>\d+)"
    r"(?:/t(?P<table>\d+)(?:/c(?P<column>\d+))?(?:/r(?P<row>\d+))?|/text(?:/r(?P<line>\d+))?)?$"
)


def parse_locator(text: str) -> SheetRange | DocLocator:
    """A locator's meaning, or ValueError. The two shapes and nothing else."""
    sheet = _SHEET.match(text)
    if sheet:
        name = sheet.group("quoted") or sheet.group("bare")
        c1, r1 = sheet.group("c1"), int(sheet.group("r1"))
        c2 = sheet.group("c2") or c1
        r2 = int(sheet.group("r2")) if sheet.group("r2") else r1
        if r2 < r1:
            raise ValueError(f"{text!r}: the range ends before it starts")
        return SheetRange(name, c1, r1, c2, r2)
    doc = _DOC.match(text)
    if doc:
        line = doc.group("line")
        return DocLocator(
            page=int(doc.group("page")),
            table=int(doc.group("table")) if doc.group("table") else None,
            row=int(doc.group("row") or line) if (doc.group("row") or line) else None,
            text=text.count("/text") == 1,
            column=int(doc.group("column")) if doc.group("column") else None,
        )
    raise ValueError(f"{text!r} is not a sheet range or a page/table/row locator")


def _quote(sheet: str) -> str:
    return f"'{sheet}'" if re.search(r"[^A-Za-z0-9_]", sheet) else sheet


# ------------------------------------------------------------------ store


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
        parse_locator(locator)  # a block is written under a locator the resolver can read
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

    def block(self, run_id: str, source_id: str, locator: str) -> tuple[Row, ...]:
        """Exactly the rows written under this locator, in order. Empty if none."""
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

    def resolve(self, run_id: str, source_id: str, locator: str) -> tuple[Row, ...]:
        """The rows a locator names, through one interface whatever kind of file.

        A locator that was written as a block resolves to that block. A sub-range of a
        sheet column resolves to the rows of the block containing it; a multi-column
        range resolves column by column. A document row resolves to that row of its
        table. Anything that resolves to nothing is nothing - never a guess.
        """
        exact = self.block(run_id, source_id, locator)
        if exact:
            return exact
        try:
            where = parse_locator(locator)
        except ValueError:
            return ()
        if isinstance(where, SheetRange):
            return self._resolve_sheet(run_id, source_id, where)
        return self._resolve_doc(run_id, source_id, where)

    def rows(self, run_id: str, source_id: str, locator: str) -> tuple[Row, ...]:
        return self.resolve(run_id, source_id, locator)

    def exists(self, run_id: str, source_id: str, locator: str) -> bool:
        return bool(self.resolve(run_id, source_id, locator))

    def locators(self, run_id: str, source_id: str) -> tuple[str, ...]:
        with self._session() as session:
            found = session.scalars(
                select(SourceRow.locator)
                .where(SourceRow.run_id == run_id, SourceRow.source_id == source_id)
                .distinct()
            )
            return tuple(sorted(found))

    # -- resolution

    def _resolve_sheet(self, run_id: str, source_id: str, want: SheetRange) -> tuple[Row, ...]:
        rows: list[Row] = []
        for column in _columns(want.column, want.column_end):
            for locator in self.locators(run_id, source_id):
                try:
                    have = parse_locator(locator)
                except ValueError:
                    continue
                if (
                    not isinstance(have, SheetRange)
                    or have.sheet != want.sheet
                    or have.column != column
                    or not have.single_column
                    or have.row_start > want.row_start
                    or have.row_end < want.row_end
                ):
                    continue
                rows.extend(
                    r
                    for r in self.block(run_id, source_id, locator)
                    if want.row_start <= r.ordinal <= want.row_end
                )
                break
        return tuple(rows)

    def _resolve_doc(self, run_id: str, source_id: str, want: DocLocator) -> tuple[Row, ...]:
        block = self.block(run_id, source_id, want.block)
        if want.row is None:
            return block
        return tuple(r for r in block if r.ordinal == want.row)

    def _session(self) -> AbstractContextManager[Session]:
        return self._store._session()  # noqa: SLF001 - the same database, the same rules


def _columns(first: str, last: str) -> list[str]:
    start, end = _col_index(first), _col_index(last)
    return [_col_name(i) for i in range(start, end + 1)]


def _col_index(name: str) -> int:
    n = 0
    for ch in name:
        n = n * 26 + (ord(ch) - 64)
    return n


def _col_name(index: int) -> str:
    out = ""
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out
