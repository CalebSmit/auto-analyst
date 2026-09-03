"""The event bus: what it accepts, what it refuses, and what it swallows.

The distinction worth testing carefully is the last one. "Emission is fire-and-forget"
is a real constraint - observability must not become a new way for work to break - but
applied to everything it would also swallow the bugs that make a stream useless. So a
store that cannot take the event is survived and counted; an event that does not satisfy
`event@1.0.0` is not.
"""

from __future__ import annotations

from typing import Any

import pytest

from ops.events import EventBus, guard_name_and_result
from ops.run_store import SqlRunStore
from registries.contracts import ContractRegistry
from registries.errors import ContractViolation
from tests.p04.conftest import ENGAGEMENT, started


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


def emit(bus: EventBus, run_id: str, **overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "run_id": run_id,
        "engagement_id": ENGAGEMENT,
        "node_id": "dispatcher",
        "type": "skill.dispatched",
        "message": "ddr-tagging dispatched",
    }
    fields.update(overrides)
    return bus.emit(**fields)


# ------------------------------------------------------------ what it records


def test_an_emitted_event_is_stored_and_readable(bus: EventBus, store: SqlRunStore) -> None:
    run_id = started(store)
    emitted = emit(bus, run_id)
    recorded = store.events(run_id)
    assert len(recorded) == 1
    assert recorded[0].event_id == emitted["event_id"]
    assert recorded[0].type == "skill.dispatched"
    assert recorded[0].node_id == "dispatcher"


def test_every_event_satisfies_the_contract_as_it_is_emitted(
    bus: EventBus, store: SqlRunStore, contracts: ContractRegistry
) -> None:
    """Validated on the way in rather than on the way out, so a malformed event never
    reaches the record at all."""
    run_id = started(store)
    emitted = emit(bus, run_id, payload={"skill": "ddr-tagging@1.0.0"})
    contracts.validate("event@1.0.0", emitted)


def test_node_id_is_required_because_the_trace_is_derived_from_it(
    bus: EventBus, store: SqlRunStore
) -> None:
    run_id = started(store)
    with pytest.raises(ContractViolation):
        emit(bus, run_id, node_id="Dispatcher")  # capitalised: not a graph node id
    assert store.events(run_id) == ()


def test_the_stream_has_a_total_order_and_a_since_cursor(
    bus: EventBus, store: SqlRunStore
) -> None:
    """Two events in the same microsecond still have an order, which is what makes a
    live console feed resumable rather than approximately correct."""
    run_id = started(store)
    for n in range(5):
        emit(bus, run_id, message=f"step {n}")
    recorded = store.events(run_id)
    assert [record.seq for record in recorded] == sorted(record.seq for record in recorded)
    assert len(recorded) == 5

    after_two = store.events(run_id, since_seq=recorded[1].seq)
    assert [record.message for record in after_two] == ["step 2", "step 3", "step 4"]


def test_the_level_is_inferred_from_the_type_when_it_is_obvious(
    bus: EventBus, store: SqlRunStore
) -> None:
    run_id = started(store)
    assert emit(bus, run_id, type="loop.repair.result", message="attempt 1 of 2")["level"] == "loop"
    assert emit(bus, run_id, type="skill.dispatched", message="go")["level"] == "info"
    assert emit(bus, run_id, type="release.written", message="x", level="warn")["level"] == "warn"


def test_events_are_scoped_to_a_run(bus: EventBus, store: SqlRunStore) -> None:
    first = started(store, run_id="run_one")
    second = started(store, run_id="run_two")
    emit(bus, first, message="first")
    emit(bus, second, message="second")
    assert [record.message for record in store.events(first)] == ["first"]
    assert [record.message for record in store.events(second)] == ["second"]


# --------------------------------------------------------------- guard events


def test_a_guard_pass_is_recorded_as_readily_as_a_failure(
    bus: EventBus, store: SqlRunStore
) -> None:
    """The whole reason guard events exist. A guard that only speaks when it fires is
    indistinguishable, on a quiet day, from a guard that never ran."""
    run_id = started(store)
    bus.emit_guard(
        run_id=run_id, engagement_id=ENGAGEMENT, node_id="tieout_gate",
        guard="tieout", passed=True, checked=412,
    )
    bus.emit_guard(
        run_id=run_id, engagement_id=ENGAGEMENT, node_id="schema_gate",
        guard="schema", passed=False, checked=13, failed=1,
        diagnostic_code="SKILL.SCHEMA_INVALID",
    )
    results = bus.guard_results(run_id)
    assert [(r.guard, r.result, r.checked, r.failed) for r in results] == [
        ("tieout", "pass", 412, 0),
        ("schema", "fail", 13, 1),
    ]
    assert results[1].diagnostic_code == "SKILL.SCHEMA_INVALID"
    assert all(r.at for r in results)


def test_a_guard_must_say_how_many_things_it_checked(bus: EventBus, store: SqlRunStore) -> None:
    """'Passed' over nothing is not a pass anyone should trust, and the manifest has
    nowhere to put the difference if it is not recorded."""
    run_id = started(store)
    with pytest.raises(ValueError, match="checked"):
        emit(bus, run_id, type="guard.tieout.pass", level="guard", message="fine")


def test_a_guard_event_whose_type_the_manifest_cannot_read_is_refused(
    bus: EventBus, store: SqlRunStore
) -> None:
    run_id = started(store)
    with pytest.raises(ValueError, match="guard"):
        emit(
            bus, run_id, type="guard.tieout", level="guard",
            message="no result in the type", payload={"checked": 1},
        )
    assert store.events(run_id) == ()


def test_a_nested_guard_name_survives_the_round_trip() -> None:
    assert guard_name_and_result("guard.tieout.repair.pass") == ("tieout_repair", "pass")
    assert guard_name_and_result("guard.schema.fail") == ("schema", "fail")
    with pytest.raises(ValueError, match="not a guard event type"):
        guard_name_and_result("skill.dispatched")


# ------------------------------------------------------- fire and forget


class BrokenStore:
    """A store that has stopped answering, which is the situation the rule is for."""

    backend = "broken"

    def append_event(self, event: dict[str, Any]) -> int:
        raise OSError("the disk is full")

    def events(self, run_id: str, since_seq: int = 0) -> tuple[()]:
        return ()


def test_a_store_that_cannot_record_does_not_fail_the_run(contracts: ContractRegistry) -> None:
    seen: list[tuple[dict[str, Any], Exception]] = []
    bus = EventBus(BrokenStore(), contracts=contracts, on_drop=lambda e, x: seen.append((e, x)))

    emitted = emit(bus, "run_x")

    assert emitted["type"] == "skill.dispatched", "the caller still gets its event back"
    assert bus.dropped == 1, "and the loss is counted rather than invisible"
    assert seen[0][0]["event_id"] == emitted["event_id"]
    assert isinstance(seen[0][1], OSError)


def test_a_reader_cannot_fail_a_run(bus: EventBus, store: SqlRunStore) -> None:
    """Console down, runs continue. A subscriber that raises is dropped from delivery,
    which is the dependency direction that makes an always-on dashboard safe."""
    run_id = started(store)
    delivered: list[str] = []
    bus.subscribe(lambda event: delivered.append(event["type"]))
    bus.subscribe(lambda event: (_ for _ in ()).throw(RuntimeError("console is down")))

    emit(bus, run_id)
    emit(bus, run_id)

    assert delivered == ["skill.dispatched", "skill.dispatched"]
    assert len(tuple(bus.subscribers())) == 1, "the broken reader was dropped, not retried"
    assert len(store.events(run_id)) == 2
