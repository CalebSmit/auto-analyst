"""Stall & Alert Detection: a run that goes quiet is a visible fact, not a mystery.

The failure mode for an unattended pipeline is not a crash - a crash is loud. It is a
run that silently stops and is noticed three days later when someone asks for the model.
So this is a timer over the record, run by the console or a scheduler, that looks for
four kinds of quiet:

* a running run that has recorded no event for longer than the silence threshold;
* a started step past the per-step timeout with no ending;
* the same guard failing again and again on one run;
* a review item past the SLA its engagement's checkpoint policy set when it was queued.

Every alert is a recorded event with a diagnostic code and an owner, raised once per
episode, so it reaches the console and the manifest without anyone watching a screen.
The detector decides nothing about the run: a stalled run is resumed by a person, an
overdue item is decided by one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ops.events import EventBus, guard_name_and_result
from ops.models import RunState
from ops.run_store import EventRecord, RunStore
from registries.constraints import ConstraintRegistry
from registries.errors import REVIEW_SLA_BREACH, RUN_STALLED, WHAT_NOW, diagnose

__all__ = ["Alert", "StallDetector"]

NODE = "stall_alert"
DEFAULT_SILENCE_S = 1800.0
DEFAULT_REPEATED_FAILURES = 3


@dataclass(frozen=True)
class Alert:
    kind: str
    """`run_silent`, `step_overdue`, `guard_repeating` or `review_overdue`."""
    run_id: str
    engagement_id: str
    subject: str
    code: str
    owner: str
    what_now: str
    since: str
    detail: dict[str, Any] = field(default_factory=dict)
    emitted: bool = False

    @property
    def event_type(self) -> str:
        return f"alert.{self.kind}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "run_id": self.run_id,
            "engagement_id": self.engagement_id,
            "subject": self.subject,
            "code": self.code,
            "owner": self.owner,
            "what_now": self.what_now,
            "since": self.since,
            "detail": dict(self.detail),
        }

    def line(self) -> str:
        return f"{self.kind:<16} {self.run_id}/{self.subject}  {self.code} [{self.owner}]"


class StallDetector:
    def __init__(
        self,
        store: RunStore,
        bus: EventBus | None = None,
        *,
        constraints: ConstraintRegistry | None = None,
        clock: Callable[[], datetime] | None = None,
        silence_s: float = DEFAULT_SILENCE_S,
        repeated_failures: int = DEFAULT_REPEATED_FAILURES,
    ) -> None:
        self.store = store
        self.bus = bus
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        ceilings = (constraints or ConstraintRegistry.load()).ceilings
        self.step_timeout_s = float(ceilings["per_step"]["timeout_s"])
        self.silence_s = silence_s
        self.repeated_failures = repeated_failures

    # -- the scan

    def scan(self, engagement_id: str | None = None, *, emit: bool = True) -> tuple[Alert, ...]:
        """Every condition that holds right now. With `emit`, each one not already on
        the record for this episode is raised as an event."""
        now = self._clock()
        found: list[Alert] = []
        for run in self.store.runs(engagement_id):
            if run.is_finished:
                continue
            events = self.store.events(run.run_id)
            if run.state is RunState.RUNNING:
                found += self._silent(run.run_id, run.engagement_id, run.started_at, events, now)
                found += self._overdue_steps(run.run_id, run.engagement_id, now)
            found += self._repeating_guards(run.run_id, run.engagement_id, events)
        found += self._overdue_reviews(engagement_id, now)
        if not emit or self.bus is None:
            return tuple(found)
        return tuple(self._raise(alert) for alert in found)

    def open_alerts(self, engagement_id: str | None = None) -> tuple[Alert, ...]:
        return self.scan(engagement_id, emit=False)

    # -- the four conditions

    def _silent(
        self,
        run_id: str,
        engagement_id: str,
        started_at: str,
        events: tuple[EventRecord, ...],
        now: datetime,
    ) -> list[Alert]:
        activity = [e for e in events if e.node_id != NODE]
        last = activity[-1].ts if activity else started_at
        quiet = (now - _parse(last)).total_seconds()
        if quiet <= self.silence_s:
            return []
        d = diagnose(
            RUN_STALLED,
            f"no event for {quiet / 60:.0f} min (threshold {self.silence_s / 60:.0f} min); "
            f"last {activity[-1].type if activity else 'launch'} at {last}",
            locator=run_id,
        )
        return [
            Alert(
                "run_silent",
                run_id,
                engagement_id,
                run_id,
                d.code,
                d.owner,
                d.what_now,
                last,
                {"quiet_s": round(quiet), "last_seq": activity[-1].seq if activity else 0},
            )
        ]

    def _overdue_steps(self, run_id: str, engagement_id: str, now: datetime) -> list[Alert]:
        found = []
        for step in self.store.steps(run_id):
            if not step.started_at or step.ended_at:
                continue
            elapsed = (now - _parse(step.started_at)).total_seconds()
            if elapsed <= self.step_timeout_s:
                continue
            d = diagnose(
                RUN_STALLED,
                f"{step.step_id} started {elapsed / 60:.0f} min ago against a step timeout "
                f"of {self.step_timeout_s / 60:.0f} min and has not ended",
                locator=f"{run_id}/{step.step_id}",
                step_id=step.step_id,
                skill=step.skill or "",
            )
            found.append(
                Alert(
                    "step_overdue",
                    run_id,
                    engagement_id,
                    step.step_id,
                    d.code,
                    d.owner,
                    d.what_now,
                    step.started_at,
                    {"elapsed_s": round(elapsed), "attempt": step.attempts},
                )
            )
        return found

    def _repeating_guards(
        self, run_id: str, engagement_id: str, events: tuple[EventRecord, ...]
    ) -> list[Alert]:
        failures: dict[str, list[EventRecord]] = {}
        for e in events:
            if e.level != "guard":
                continue
            name, result = guard_name_and_result(e.type)
            if result == "fail":
                failures.setdefault(name, []).append(e)
        found = []
        for name, hits in failures.items():
            if len(hits) < self.repeated_failures:
                continue
            code = hits[-1].diagnostic_code or RUN_STALLED
            owner, what_now = WHAT_NOW.get(code, WHAT_NOW[RUN_STALLED])
            found.append(
                Alert(
                    "guard_repeating",
                    run_id,
                    engagement_id,
                    name,
                    code,
                    owner,
                    what_now,
                    hits[0].ts,
                    {"failures": len(hits), "last_seq": hits[-1].seq},
                )
            )
        return found

    def _overdue_reviews(self, engagement_id: str | None, now: datetime) -> list[Alert]:
        found = []
        for item in self.store.open_review_items(engagement_id):
            if not item.due_at or _parse(item.due_at) >= now:
                continue
            run = self.store.run(item.run_id)
            late = (now - _parse(item.due_at)).total_seconds()
            d = diagnose(
                REVIEW_SLA_BREACH,
                f"{item.item_id} open since {item.created_at}, due {item.due_at}, "
                f"{late / 3600:.1f} h past its SLA; owner {item.owner or 'unassigned'}",
                locator=f"{item.run_id}/{item.item_id}",
            )
            found.append(
                Alert(
                    "review_overdue",
                    item.run_id,
                    run.engagement_id,
                    item.item_id,
                    d.code,
                    d.owner,
                    d.what_now,
                    item.due_at,
                    {
                        "assigned_to": item.owner,
                        "due_at": item.due_at,
                        "late_s": round(late),
                        "kind": item.kind,
                    },
                )
            )
        return found

    # -- raising, once per episode

    def _raise(self, alert: Alert) -> Alert:
        assert self.bus is not None
        events = self.store.events(alert.run_id)
        if self._already_raised(alert, events):
            return alert
        self.bus.emit(
            run_id=alert.run_id,
            engagement_id=alert.engagement_id,
            node_id=NODE,
            type=alert.event_type,
            message=f"{alert.subject}: {alert.kind.replace('_', ' ')} - {alert.what_now}",
            level="error",
            step_id=alert.subject if alert.kind == "step_overdue" else None,
            diagnostic_code=alert.code,
            payload={"subject": alert.subject, "owner": alert.owner, **alert.detail},
        )
        return Alert(
            alert.kind,
            alert.run_id,
            alert.engagement_id,
            alert.subject,
            alert.code,
            alert.owner,
            alert.what_now,
            alert.since,
            alert.detail,
            emitted=True,
        )

    def _already_raised(self, alert: Alert, events: tuple[EventRecord, ...]) -> bool:
        """An episode ends when the run speaks again: a silence alert is raised once
        per silence, and the others once per subject on the run."""
        since = int(alert.detail.get("last_seq", 0)) if alert.kind == "run_silent" else 0
        return any(
            e.type == alert.event_type
            and e.payload.get("subject") == alert.subject
            and e.seq > since
            for e in events
        )


def _parse(stamp: str) -> datetime:
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
