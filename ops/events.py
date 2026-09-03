"""The Event Bus: every node says what it just did, once, and it is never edited.

Two things about this module are deliberate and easy to get wrong later.

**Guard passes are events.** A guard that only speaks when it fires is, on a quiet day,
indistinguishable from a guard that never ran at all. `emit_guard` therefore takes a
result rather than only being called on failure, and the run manifest's `guard_events`
is assembled from exactly these - so a pass that was never emitted cannot appear in the
record, and a guard that stopped running shows up as silence somebody can see.

**Recording is fire-and-forget; malformed is not.** The blueprint's rule is that a
failure to record must never fail a run, because observability must not become a new way
for work to break. That applies to the *store*: a lost connection or a full disk is
counted and reported through `on_drop`, and the run continues. It does not apply to an
event that does not satisfy `event@1.0.0`, which is a defect in the emitting node -
deterministic, caught by the suite, and worth failing loudly, because swallowing it
would silently drop a whole class of event from every run forever.

The bus is append-only by construction: `emit` and `emit_guard` write, `stream` reads,
and there is nothing else. See `ops.models` for the two levels underneath.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from ops.models import now_iso
from ops.run_store import EventRecord, RunStore
from registries.contracts import ContractRegistry

EVENT_CONTRACT = "event@1.0.0"

LEVELS = ("info", "warn", "error", "guard", "loop")

# A guard event's type carries the guard's name and its result, because the manifest is
# assembled from the stream and has to be able to say which guard produced which result
# without a second table to keep in step.
GUARD_TYPE = re.compile(r"^guard[.]([a-z][a-z0-9_]*(?:[.][a-z][a-z0-9_]*)*)[.](pass|fail)$")

__all__ = [
    "EVENT_CONTRACT",
    "EventBus",
    "GuardResult",
    "guard_name_and_result",
]


@dataclass(frozen=True)
class GuardResult:
    """One guard's verdict, in the shape the manifest wants."""

    guard: str
    result: str
    checked: int
    failed: int
    at: str
    diagnostic_code: str | None = None


class EventBus:
    """The in-process publisher, writing through to the append-only event table.

    Subscribers exist for the Ops Console, which is a reader of this stream and nothing
    more: console down, runs continue. A subscriber that raises is dropped from the
    delivery, never propagated - the same reason emission is fire-and-forget.
    """

    def __init__(
        self,
        store: RunStore,
        contracts: ContractRegistry | None = None,
        on_drop: Callable[[dict[str, Any], Exception], None] | None = None,
    ) -> None:
        self._store = store
        self._contracts = contracts or ContractRegistry.load()
        self._on_drop = on_drop
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []
        self.dropped = 0
        """How many events the store refused to take. Not zero is a thing to look at:
        a run whose record is missing events is still a run, but nobody should have to
        guess whether the gap was silence or loss."""

    # -- writing

    def emit(
        self,
        *,
        run_id: str,
        engagement_id: str,
        node_id: str,
        type: str,
        message: str,
        level: str | None = None,
        step_id: str | None = None,
        payload: dict[str, Any] | None = None,
        diagnostic_code: str | None = None,
        cost_usd: float | None = None,
    ) -> dict[str, Any]:
        """Record one event. Returns what was emitted, whether or not it was stored."""
        event: dict[str, Any] = {
            "event_id": f"evt_{uuid4().hex[:20]}",
            "ts": now_iso(),
            "run_id": run_id,
            "engagement_id": engagement_id,
            "node_id": node_id,
            "step_id": step_id,
            "type": type,
            "level": level or _level_for(type),
            "message": message,
            "payload": dict(payload or {}),
            "diagnostic_code": diagnostic_code,
            "schema_version": EVENT_CONTRACT,
        }
        if cost_usd is not None:
            event["cost_usd"] = cost_usd

        self._validate(event)

        try:
            self._store.append_event(event)
        except Exception as failure:  # noqa: BLE001 - the whole point is to not re-raise
            self.dropped += 1
            if self._on_drop is not None:
                self._on_drop(event, failure)

        for subscriber in tuple(self._subscribers):
            try:
                subscriber(event)
            except Exception:  # noqa: BLE001 - a reader must not be able to fail a run
                self._subscribers.remove(subscriber)
        return event

    def emit_guard(
        self,
        *,
        run_id: str,
        engagement_id: str,
        node_id: str,
        guard: str,
        passed: bool,
        checked: int,
        failed: int = 0,
        message: str | None = None,
        step_id: str | None = None,
        diagnostic_code: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a guard result - a pass as readily as a failure.

        `checked` is required rather than optional because "the tie-out guard passed" and
        "the tie-out guard passed over nothing" are different facts, and only one of them
        is reassuring.
        """
        result = "pass" if passed else "fail"
        body = dict(payload or {})
        body["checked"] = checked
        body["failed"] = failed
        return self.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=node_id,
            type=f"guard.{guard}.{result}",
            level="guard",
            message=message or f"{guard} {result}: {checked} checked, {failed} failed",
            step_id=step_id,
            payload=body,
            diagnostic_code=diagnostic_code,
        )

    # -- reading

    def stream(self, run_id: str, since_seq: int = 0) -> tuple[EventRecord, ...]:
        return self._store.events(run_id, since_seq)

    def guard_results(self, run_id: str) -> tuple[GuardResult, ...]:
        """Every guard verdict on a run, in order. What the manifest records verbatim."""
        found: list[GuardResult] = []
        for record in self._store.events(run_id):
            if record.level != "guard":
                continue
            guard, result = guard_name_and_result(record.type)
            found.append(
                GuardResult(
                    guard=guard,
                    result=result,
                    checked=int(record.payload.get("checked", 0)),
                    failed=int(record.payload.get("failed", 0)),
                    at=record.ts,
                    diagnostic_code=record.diagnostic_code,
                )
            )
        return tuple(found)

    def subscribe(self, subscriber: Callable[[dict[str, Any]], None]) -> None:
        """Add a reader. Readers never affect the run - see the class docstring."""
        self._subscribers.append(subscriber)

    def subscribers(self) -> Iterable[Callable[[dict[str, Any]], None]]:
        return tuple(self._subscribers)

    # -- internals

    def _validate(self, event: dict[str, Any]) -> None:
        self._contracts.validate(EVENT_CONTRACT, event)
        if event["level"] == "guard" and not GUARD_TYPE.match(event["type"]):
            raise ValueError(
                f"a guard event's type must read guard.<name>.<pass|fail>, not "
                f"{event['type']!r}. The manifest's guard_events is assembled from the "
                f"type, so a shape it cannot read is a guard result nobody can audit."
            )
        if event["level"] == "guard" and not isinstance(event["payload"].get("checked"), int):
            raise ValueError(
                "a guard event must report how many things it checked; "
                "'passed' over nothing is not a pass anyone should trust."
            )

    def __repr__(self) -> str:
        return f"<EventBus dropped={self.dropped} subscribers={len(self._subscribers)}>"


def guard_name_and_result(event_type: str) -> tuple[str, str]:
    """`guard.tieout.repair.pass` -> `('tieout_repair', 'pass')`.

    Dots become underscores so the name satisfies the manifest's guard pattern while the
    event type keeps its dotted, routable shape.
    """
    match = GUARD_TYPE.match(event_type)
    if match is None:
        raise ValueError(f"{event_type!r} is not a guard event type")
    return match.group(1).replace(".", "_"), match.group(2)


def _level_for(event_type: str) -> str:
    """A sensible level from the type, so callers only say it when it is not obvious."""
    head = event_type.split(".", 1)[0]
    if head == "guard":
        return "guard"
    if head == "loop":
        return "loop"
    return "info"
