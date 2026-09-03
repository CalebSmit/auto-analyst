"""The Configuration Store: where every setup answer lives - and the Change Log behind it.

A versioned config document per environment, validated on write against
`config_document@1.0.0`, with every change appended to the Config Change Log: the field,
the old and new values, the person, the timestamp and a reason.

One boundary this module exists to make visible: **configuration writes the engagement
record, and guards read the run.** There is no field in the document a guard reads, and
nothing here reaches into a run. Lowering a budget for one engagement is an admin
action; raising one above the firm ceiling is a governance change, and the document
schema has no field for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from ops.models import ConfigChange, ConfigDocument, now_iso
from ops.run_store import SqlRunStore
from registries.contracts import ContractRegistry
from registries.errors import UNKNOWN_TYPE, WATCH_OVERLAP, RegistryError, diagnose

__all__ = ["ChangeRecord", "ConfigStore", "IntakeTiming", "Watch"]

CONTRACT = "config_document@1.0.0"


@dataclass(frozen=True)
class Watch:
    id: str
    kind: str
    name: str
    root: str
    recipe: str
    engagement_id: str | None = None
    depth: int = 2

    @property
    def is_bound(self) -> bool:
        return self.kind == "bound"


@dataclass(frozen=True)
class IntakeTiming:
    quiet_period_minutes: float
    max_wait_hours: float
    lock_timeout_hours: float


@dataclass(frozen=True)
class ChangeRecord:
    at: str
    who: str
    field: str
    old: dict[str, Any]
    new: dict[str, Any]
    reason: str


class ConfigStore:
    def __init__(
        self, store: SqlRunStore, contracts: ContractRegistry, environment: str = "local"
    ) -> None:
        self._store = store
        self._contracts = contracts
        self.environment = environment

    # -- the document

    def document(self) -> dict[str, Any]:
        with self._store._session() as session:  # noqa: SLF001 - the same database
            row = session.get(ConfigDocument, self.environment)
            if row is None:
                raise KeyError(f"no configuration written for environment {self.environment!r}")
            return dict(row.body)

    def version(self) -> int:
        with self._store._session() as session:  # noqa: SLF001
            row = session.get(ConfigDocument, self.environment)
            return 0 if row is None else row.version

    def write(self, body: dict[str, Any], *, who: str, reason: str) -> int:
        """Validate, then replace the whole document and log what changed, field by
        field. Returns the new version. An invalid document is refused before anything
        is written; a document with two watches on one path is refused the same way."""
        self._contracts.validate(CONTRACT, body)
        self._check_conventions(body)
        _check_no_overlap(tuple(_watch(w) for w in body["watches"]))

        with self._store._session() as session:  # noqa: SLF001
            row = session.get(ConfigDocument, self.environment)
            before = dict(row.body) if row else {}
            if row is None:
                row = ConfigDocument(
                    environment=self.environment,
                    version=1,
                    body=dict(body),
                    updated_at=now_iso(),
                    updated_by=who,
                )
                session.add(row)
            else:
                row.version = row.version + 1
                row.body = dict(body)
                row.updated_at = now_iso()
                row.updated_by = who
            version = row.version
        for field in sorted(set(before) | set(body)):
            if before.get(field) != body.get(field):
                self.log_change(
                    who=who,
                    field=field,
                    old=_as_value(before.get(field)),
                    new=_as_value(body.get(field)),
                    reason=reason,
                )
        return version

    # -- typed views

    def watches(self) -> tuple[Watch, ...]:
        return tuple(_watch(w) for w in self.document()["watches"])

    def watch(self, watch_id: str) -> Watch:
        found = next((w for w in self.watches() if w.id == watch_id), None)
        if found is None:
            raise KeyError(f"no watch {watch_id!r} in the {self.environment} configuration")
        return found

    def timing(self, engagement_id: str | None = None) -> IntakeTiming:
        """The environment's intake timing, tightened by the engagement's override. An
        override may shorten the quiet period or the wait; it may not lengthen the lock
        timeout, which is not per engagement at all."""
        doc = self.document()
        base = doc["intake"]
        over = (doc.get("engagements") or {}).get(engagement_id or "", {})
        return IntakeTiming(
            quiet_period_minutes=float(
                over.get("quiet_period_minutes", base["quiet_period_minutes"])
            ),
            max_wait_hours=float(over.get("max_wait_hours", base["max_wait_hours"])),
            lock_timeout_hours=float(base["lock_timeout_hours"]),
        )

    def conventions(self) -> dict[str, tuple[str, ...]]:
        return {
            doc_type: tuple(str(t).lower() for t in tokens)
            for doc_type, tokens in self.document()["document_type_conventions"].items()
        }

    # -- the change log

    def log_change(
        self, *, who: str, field: str, old: dict[str, Any], new: dict[str, Any], reason: str
    ) -> ChangeRecord:
        if not who.strip() or not reason.strip():
            raise ValueError("a configuration change names a person and gives a reason")
        with self._store._session() as session:  # noqa: SLF001
            row = ConfigChange(at=now_iso(), who=who, field=field, old=old, new=new, reason=reason)
            session.add(row)
            session.flush()
            return ChangeRecord(
                row.at, row.who, row.field, dict(row.old), dict(row.new), row.reason
            )

    def changes(self) -> tuple[ChangeRecord, ...]:
        with self._store._session() as session:  # noqa: SLF001
            rows = session.scalars(select(ConfigChange).order_by(ConfigChange.id))
            return tuple(
                ChangeRecord(r.at, r.who, r.field, dict(r.old), dict(r.new), r.reason) for r in rows
            )

    # -- plumbing

    def _check_conventions(self, body: dict[str, Any]) -> None:
        known = {t.id for t in self._contracts.intake_document_types()}
        for doc_type in body["document_type_conventions"]:
            if doc_type not in known:
                raise RegistryError(
                    diagnose(
                        UNKNOWN_TYPE,
                        f"the configuration binds filenames to {doc_type!r}, which is not an "
                        f"intake document type the Contract Registry declares "
                        f"(have: {', '.join(sorted(known))})",
                        locator=f"config/{self.environment}/document_type_conventions",
                    )
                )


def _watch(raw: dict[str, Any]) -> Watch:
    return Watch(
        id=str(raw["id"]),
        kind=str(raw["kind"]),
        name=str(raw["name"]),
        root=str(raw["root"]).strip("/"),
        recipe=str(raw["recipe"]),
        engagement_id=raw.get("engagement_id"),
        depth=int(raw.get("depth", 2)),
    )


def _check_no_overlap(watches: tuple[Watch, ...]) -> None:
    """No two watches claim the same path. An overlap would start two runs on one file."""
    for i, a in enumerate(watches):
        if a.is_bound and not a.engagement_id:
            raise RegistryError(
                diagnose(WATCH_OVERLAP, f"bound watch {a.id} names no engagement", locator=a.id)
            )
        for b in watches[i + 1 :]:
            if _same_or_nested(a.root, b.root):
                raise RegistryError(
                    diagnose(
                        WATCH_OVERLAP,
                        f"watches {a.id} ({a.root or '/'}) and {b.id} ({b.root or '/'}) claim "
                        f"the same path",
                        locator=f"{a.id},{b.id}",
                    )
                )


def _same_or_nested(a: str, b: str) -> bool:
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    return shorter == "" or longer.startswith(shorter + "/")


def _as_value(value: Any) -> dict[str, Any]:
    return {"value": value}
