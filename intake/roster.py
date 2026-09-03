"""The Active Project Roster: which engagements are live this week.

Three states rather than two:

* **active** - swept, runs start.
* **paused** - the location is known, nothing starts, files accumulate.
* **archived** - not swept at all; the binding is kept for the record.

Paused and archived look identical on an on/off switch and mean completely different
things to whoever is deciding whether to chase a client. The Sweep Planner reads this
table and nothing else, which is why an engagement that is not on it has no path into
the pipeline at all - a property of the graph rather than a checkbox someone remembered
to tick.

Changing a state writes to the Config Change Log with who and when. Turning an
engagement off never deletes anything and never cancels a run already in flight: there
is no delete here, and nothing here touches a run.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from sqlalchemy import select

from intake.config import ConfigStore
from ops.models import RosterRow, now_iso
from ops.run_store import SqlRunStore

__all__ = ["ProjectRoster", "RosterEntry", "RosterState"]


class RosterState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class RosterEntry:
    engagement_id: str
    client: str
    scope_path: str
    watch_id: str
    destination_id: str
    state: RosterState = RosterState.ACTIVE
    folder: str = ""
    """Relative to the watch root, for a pattern watch: "Henderson Manufacturing/2026
    ESOP". Empty for a bound watch, which names the engagement itself."""
    template_pin: str = ""
    budget_usd: float | None = None
    review_level: str = "standard"
    note: str = ""
    updated_at: str = ""

    @property
    def is_active(self) -> bool:
        return self.state is RosterState.ACTIVE


class ProjectRoster:
    def __init__(self, store: SqlRunStore, config: ConfigStore) -> None:
        self._store = store
        self._config = config

    # -- reading

    def entries(self, state: RosterState | None = None) -> tuple[RosterEntry, ...]:
        with self._store._session() as session:  # noqa: SLF001 - the same database
            stmt = select(RosterRow).order_by(RosterRow.engagement_id)
            if state is not None:
                stmt = stmt.where(RosterRow.state == str(state))
            return tuple(_as_entry(r) for r in session.scalars(stmt))

    def active(self) -> tuple[RosterEntry, ...]:
        return self.entries(RosterState.ACTIVE)

    def get(self, engagement_id: str) -> RosterEntry | None:
        with self._store._session() as session:  # noqa: SLF001
            row = session.get(RosterRow, engagement_id)
            return _as_entry(row) if row else None

    def is_active(self, engagement_id: str) -> bool:
        entry = self.get(engagement_id)
        return entry is not None and entry.is_active

    # -- writing, every change logged

    def register(self, entry: RosterEntry, *, who: str, reason: str) -> RosterEntry:
        if self.get(entry.engagement_id) is not None:
            raise ValueError(f"{entry.engagement_id} is already on the roster; change its state")
        with self._store._session() as session:  # noqa: SLF001
            session.add(
                RosterRow(
                    engagement_id=entry.engagement_id,
                    client=entry.client,
                    scope_path=entry.scope_path,
                    state=str(entry.state),
                    watch_id=entry.watch_id,
                    folder=entry.folder,
                    destination_id=entry.destination_id,
                    template_pin=entry.template_pin,
                    budget_usd=entry.budget_usd,
                    review_level=entry.review_level,
                    note=entry.note,
                    updated_at=now_iso(),
                )
            )
        self._config.log_change(
            who=who,
            field=f"roster/{entry.engagement_id}",
            old={},
            new=_as_dict(entry),
            reason=reason,
        )
        found = self.get(entry.engagement_id)
        assert found is not None
        return found

    def set_state(
        self, engagement_id: str, state: RosterState, *, who: str, reason: str, note: str = ""
    ) -> RosterEntry:
        """Activate, pause or archive. Nothing is deleted and no run is touched."""
        before = self.get(engagement_id)
        if before is None:
            raise KeyError(f"{engagement_id} is not on the roster")
        with self._store._session() as session:  # noqa: SLF001
            row = session.get(RosterRow, engagement_id)
            assert row is not None
            row.state = str(state)
            row.updated_at = now_iso()
            if note:
                row.note = note
        self._config.log_change(
            who=who,
            field=f"roster/{engagement_id}/state",
            old={"state": str(before.state)},
            new={"state": str(state), **({"note": note} if note else {})},
            reason=reason,
        )
        return replace(before, state=state, note=note or before.note)


def _as_entry(row: RosterRow) -> RosterEntry:
    return RosterEntry(
        engagement_id=row.engagement_id,
        client=row.client,
        scope_path=row.scope_path,
        watch_id=row.watch_id,
        destination_id=row.destination_id,
        state=RosterState(row.state),
        folder=row.folder,
        template_pin=row.template_pin,
        budget_usd=row.budget_usd,
        review_level=row.review_level,
        note=row.note,
        updated_at=row.updated_at,
    )


def _as_dict(entry: RosterEntry) -> dict[str, Any]:
    return {
        "engagement_id": entry.engagement_id,
        "client": entry.client,
        "scope_path": entry.scope_path,
        "state": str(entry.state),
        "watch_id": entry.watch_id,
        "folder": entry.folder,
        "destination_id": entry.destination_id,
        "template_pin": entry.template_pin,
        "budget_usd": entry.budget_usd,
        "review_level": entry.review_level,
    }
