"""The Precedent Store: every tagging decision an analyst approved, reused as an example.

Masked, and scoped. A query is built from the engagement's resolved scope - the
`PrecedentQuery` the Context Builder derives, with no free-text alternative - and the
WHERE clause is built from that query's practice. A Corporate Finance decision is not
filtered out of a Valuation retrieval; it is never in the result set to filter, which is
the difference between a rule and a construction. For a returning client, that client's
own prior decisions come first.

Ranking within the scope is lexical: token overlap between the step's masked
descriptions and the stored ones. The blueprint calls this an embedding index; through
P24 the pipeline is local and keyless, so the index is deterministic Python. Swapping
the ranker for an embedding port later changes nothing about where the store looks,
because the ranker only orders rows the scope already admitted.

Exactly one writer. `admit` is the entry, it is called by the Precedent Write-back and
nothing else (a test walks the tree), it re-reads the decision it is handed before it
writes, and the table's own foreign key and BEFORE INSERT trigger refuse a row with no
qualifying decision behind it even when this module is bypassed entirely.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from harness.context import Precedent, PrecedentQuery
from ops.models import Decision, PrecedentRow
from ops.run_store import SqlRunStore
from registries.errors import PRECEDENT_NO_DECISION, DiagnosticError, diagnose

__all__ = ["PrecedentRecord", "PrecedentStore", "PrecedentRefused", "similarity"]

TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset({"and", "the", "of", "for", "to", "in", "on", "a", "an", "other"})


class PrecedentRefused(DiagnosticError):
    """The store would not record that."""


@dataclass(frozen=True)
class PrecedentRecord:
    """One row, as the store holds it. `example` is what a model is shown."""

    precedent_id: str
    decision_run_id: str
    decision_item_id: str
    engagement_id: str
    client_id: str
    practice: str
    segment: str
    disposition: str
    skill: str
    taxonomy_version: str
    decided_by: str
    decided_at: str
    decision: str
    description: str
    example: dict[str, Any]
    written_at: str = ""

    @property
    def scope_path(self) -> str:
        return f"{self.practice}/{self.segment}/{self.disposition}"

    def as_precedent(self) -> Precedent:
        return Precedent(
            precedent_id=self.precedent_id,
            engagement_id=self.engagement_id,
            client_id=self.client_id,
            scope=self.scope_path,
            masked=True,
            example=dict(self.example),
        )

    def as_row(self) -> dict[str, Any]:
        """What the `precedent_lookup` tool returns per row: the example and its
        provenance, nothing that names a client."""
        return {
            "precedent_id": self.precedent_id,
            "scope": self.scope_path,
            "skill": self.skill,
            "taxonomy_version": self.taxonomy_version,
            "decision": self.decision,
            "decided_at": self.decided_at,
            **{k: v for k, v in self.example.items() if k != "precedent_id"},
        }


def _tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS)


def similarity(a: str, b: str) -> float:
    """Jaccard over word tokens, 1.0 for the same words in any order. Deterministic,
    and honest about what it is: a ranker for rows the scope already admitted."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class PrecedentStore:
    """Scope-built retrieval; one writer."""

    def __init__(self, store: SqlRunStore) -> None:
        self._store = store

    def _session(self) -> AbstractContextManager[Session]:
        return self._store._session()  # noqa: SLF001 - the same database, the same rules

    # -- retrieval

    def retrieve(self, query: PrecedentQuery) -> tuple[Precedent, ...]:
        """The `PrecedentSource` the Context Builder calls. Only a `PrecedentQuery` is
        accepted, and the only place one is built is the builder."""
        return tuple(r.as_precedent() for r in self.records(query))

    def records(self, query: PrecedentQuery) -> tuple[PrecedentRecord, ...]:
        skill = query.skill.split("@", 1)[0]
        with self._session() as session:
            stmt = select(PrecedentRow).where(PrecedentRow.practice == query.practice)
            if skill:
                stmt = stmt.where(PrecedentRow.skill == skill)
            rows = [_as_record(r) for r in session.scalars(stmt)]
        return tuple(_rank(rows, query))

    def get(self, ids: Iterable[str], *, practice: str) -> tuple[PrecedentRecord, ...]:
        """Rows by id, within one practice. An id from another practice is not found -
        it is not hidden, it is outside the query."""
        wanted = [i for i in ids if i]
        if not wanted:
            return ()
        with self._session() as session:
            stmt = select(PrecedentRow).where(
                PrecedentRow.practice == practice, PrecedentRow.precedent_id.in_(wanted)
            )
            found = {r.precedent_id: _as_record(r) for r in session.scalars(stmt)}
        return tuple(found[i] for i in wanted if i in found)

    def count(self, practice: str | None = None) -> int:
        with self._session() as session:
            stmt = select(func.count()).select_from(PrecedentRow)
            if practice is not None:
                stmt = stmt.where(PrecedentRow.practice == practice)
            return int(session.scalar(stmt) or 0)

    def snapshot_id(self) -> str:
        """What the plan hash folds in. Two runs that see different examples get
        different hashes, which is the correction the compiler's docstring records."""
        with self._session() as session:
            ids = list(
                session.scalars(
                    select(PrecedentRow.precedent_id).order_by(PrecedentRow.precedent_id)
                )
            )
        if not ids:
            return "precedent_snapshot_empty"
        digest = hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()
        return f"precedent_snapshot_{digest[:16]}"

    # -- the one entry

    def admit(self, record: PrecedentRecord) -> PrecedentRecord:
        """Record an example. Called by the Precedent Write-back and nothing else.

        The decision is re-read here, not trusted from the record: it has to exist, to
        write precedent, and to name a person. A second admit for the same decision
        returns the row already written - a decision writes one precedent, once.
        """
        with self._session() as session:
            decision = session.scalars(
                select(Decision).where(
                    Decision.run_id == record.decision_run_id,
                    Decision.item_id == record.decision_item_id,
                )
            ).one_or_none()
            if decision is None or not decision.writes_precedent or not decision.decided_by.strip():
                found = (
                    "no decision"
                    if decision is None
                    else f"{decision.decision} by {decision.decided_by!r}"
                )
                raise PrecedentRefused(
                    diagnose(
                        PRECEDENT_NO_DECISION,
                        f"{record.decision_run_id}/{record.decision_item_id}: {found}",
                        locator=record.precedent_id,
                        expected="an accepted or corrected decision naming a person",
                        found=found,
                    )
                )
            existing = session.scalars(
                select(PrecedentRow).where(
                    PrecedentRow.decision_run_id == record.decision_run_id,
                    PrecedentRow.decision_item_id == record.decision_item_id,
                )
            ).one_or_none()
            if existing is not None:
                return _as_record(existing)
            row = PrecedentRow(
                precedent_id=record.precedent_id,
                decision_run_id=record.decision_run_id,
                decision_item_id=record.decision_item_id,
                engagement_id=record.engagement_id,
                client_id=record.client_id,
                practice=record.practice,
                segment=record.segment,
                disposition=record.disposition,
                skill=record.skill,
                taxonomy_version=record.taxonomy_version,
                decided_by=decision.decided_by,
                decided_at=decision.decided_at,
                decision=decision.decision,
                masked=True,
                description=record.description,
                example=dict(record.example),
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError as exc:
                raise PrecedentRefused(
                    diagnose(
                        PRECEDENT_NO_DECISION,
                        f"the database refused the row: {exc.orig}",
                        locator=record.precedent_id,
                    )
                ) from exc
            return _as_record(row)

    def all(self) -> Iterator[PrecedentRecord]:
        with self._session() as session:
            for row in session.scalars(select(PrecedentRow).order_by(PrecedentRow.written_at)):
                yield _as_record(row)


# ------------------------------------------------------------------ ranking


def _rank(rows: list[PrecedentRecord], query: PrecedentQuery) -> list[PrecedentRecord]:
    """Own client first when the scope says so - every one of the client's own rows
    before any other client's - then the best lexical match to any term, then the same
    segment, then recency. Everything ranked was already in scope."""
    own_first = query.precedent_scope == "client_first"

    def key(r: PrecedentRecord) -> tuple[int, float, int, str]:
        own = 0 if (own_first and r.client_id == query.client_id) else 1
        seg = 0 if r.segment == query.segment else 1
        score = max((similarity(term, r.description) for term in query.terms), default=0.0)
        return own, -score, seg, _newest(r)

    return sorted(rows, key=key)[: query.limit]


def _newest(r: PrecedentRecord) -> str:
    # Sort key: later decisions first. ISO timestamps sort as text.
    return "".join(chr(0x10FFFF - ord(c)) for c in r.decided_at)


def _as_record(row: PrecedentRow) -> PrecedentRecord:
    return PrecedentRecord(
        precedent_id=row.precedent_id,
        decision_run_id=row.decision_run_id,
        decision_item_id=row.decision_item_id,
        engagement_id=row.engagement_id,
        client_id=row.client_id,
        practice=row.practice,
        segment=row.segment,
        disposition=row.disposition,
        skill=row.skill,
        taxonomy_version=row.taxonomy_version,
        decided_by=row.decided_by,
        decided_at=row.decided_at,
        decision=row.decision,
        description=row.description,
        example=dict(row.example),
        written_at=row.written_at,
    )
