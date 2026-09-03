"""The event table has no update path reachable from application code.

The phase's criterion, taken literally and checked at all three levels, because each one
alone is a promise rather than a guarantee:

1. **the API** - nothing on the bus or the store can change an event, checked by
   inspecting the surface rather than by reading it;
2. **the ORM** - a flush carrying a modified or deleted Event is refused with a
   diagnostic, in the same words on both backends;
3. **the database** - triggers, checked by reaching *past* the API with raw SQL, which
   is the only version of this test that would still mean something if somebody opened
   a psql prompt.
"""

from __future__ import annotations

import inspect

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from ops.events import EventBus
from ops.models import AppendOnlyViolation, Event, RunState
from ops.run_store import RunStore, SqlRunStore
from registries.contracts import ContractRegistry
from tests.p04.conftest import ENGAGEMENT, started

# Names that would mean an event can be changed. Matched as substrings so `update_event`,
# `set_event_level` and `purge_events` are all caught.
MUTATION_WORDS = ("update", "delete", "remove", "purge", "edit", "amend", "set_", "redact")


def raw(store: SqlRunStore, statement: str) -> None:
    """Execute SQL straight at the database, past every layer this package owns."""
    with store._engine.begin() as connection:  # noqa: SLF001 - deliberately past the API
        connection.execute(text(statement))


def emit_one(store: SqlRunStore, contracts: ContractRegistry, run_id: str) -> int:
    bus = EventBus(store, contracts=contracts)
    bus.emit(
        run_id=run_id,
        engagement_id=ENGAGEMENT,
        node_id="dispatcher",
        type="skill.dispatched",
        message="ddr-tagging dispatched",
    )
    return store.events(run_id)[0].seq


# ------------------------------------------------------------- 1. the API


def test_the_run_store_protocol_offers_no_way_to_change_an_event() -> None:
    """Read off the Protocol, so adding one to the implementation later is not enough
    to make it reachable through the interface everything else holds."""
    offenders = [
        name
        for name in dir(RunStore)
        if not name.startswith("__")
        and "event" in name.lower()
        and any(word in name.lower() for word in MUTATION_WORDS)
    ]
    assert not offenders, f"the store exposes {offenders}"


def test_the_event_surface_is_append_and_read_and_nothing_else() -> None:
    event_methods = {
        name
        for name in dir(RunStore)
        if not name.startswith("_") and "event" in name.lower()
    }
    assert event_methods == {"append_event", "events"}


def test_the_bus_offers_no_way_to_change_an_event() -> None:
    offenders = [
        name
        for name, _ in inspect.getmembers(EventBus, callable)
        if not name.startswith("__") and any(word in name.lower() for word in MUTATION_WORDS)
    ]
    assert not offenders, f"the bus exposes {offenders}"


# ------------------------------------------------------------- 2. the ORM


def test_modifying_a_recorded_event_is_refused_by_the_orm(
    store: SqlRunStore, contracts: ContractRegistry
) -> None:
    run_id = started(store)
    emit_one(store, contracts, run_id)

    with Session(store._engine) as session:  # noqa: SLF001 - past the API on purpose
        row = session.scalars(select(Event)).one()
        row.message = "something that never happened"
        with pytest.raises(AppendOnlyViolation) as raised:
            session.commit()
    assert raised.value.diagnostic.code == "PROCESS.APPEND_ONLY_VIOLATION"
    assert store.events(run_id)[0].message == "ddr-tagging dispatched"


def test_deleting_a_recorded_event_is_refused_by_the_orm(
    store: SqlRunStore, contracts: ContractRegistry
) -> None:
    run_id = started(store)
    emit_one(store, contracts, run_id)

    with Session(store._engine) as session:  # noqa: SLF001
        row = session.scalars(select(Event)).one()
        session.delete(row)
        with pytest.raises(AppendOnlyViolation):
            session.commit()
    assert len(store.events(run_id)) == 1


# -------------------------------------------------------- 3. the database


def test_raw_sql_cannot_update_an_event(store: SqlRunStore, contracts: ContractRegistry) -> None:
    """The one that still means something when this code is not in the picture.

    Both dialects get a BEFORE UPDATE trigger, so the guarantee survives a migration
    script, a psql session and anything else that talks to the database directly.
    """
    run_id = started(store)
    emit_one(store, contracts, run_id)

    with pytest.raises(DatabaseError) as raised:
        raw(store, "UPDATE event SET message = 'rewritten'")
    assert "append-only" in str(raised.value).lower()
    assert store.events(run_id)[0].message == "ddr-tagging dispatched"


def test_raw_sql_cannot_delete_an_event(store: SqlRunStore, contracts: ContractRegistry) -> None:
    run_id = started(store)
    emit_one(store, contracts, run_id)

    with pytest.raises(DatabaseError) as raised:
        raw(store, "DELETE FROM event")
    assert "append-only" in str(raised.value).lower()
    assert len(store.events(run_id)) == 1


def test_the_stream_still_grows_after_a_refusal(
    store: SqlRunStore, contracts: ContractRegistry
) -> None:
    """Append-only means append is still open. A guard that also stopped new events
    would be a very quiet way to lose a run's record."""
    run_id = started(store)
    emit_one(store, contracts, run_id)
    with Session(store._engine) as session:  # noqa: SLF001
        row = session.scalars(select(Event)).one()
        row.level = "error"
        with pytest.raises(AppendOnlyViolation):
            session.commit()

    store.transition(run_id, RunState.RUNNING)
    emit_one(store, contracts, run_id)
    assert len(store.events(run_id)) == 2
