"""The run trace: the architecture graph, coloured by what a run actually did.

One reducer over the event stream. Live and replay are the same fold - `apply` one
event at a time as the bus delivers them, or `fold` the stored stream of a run from six
months ago - so the view behaves identically on both, and nothing about the trace is
ever stored.

**Node state comes from the event's type, never from its level.** `guard.tieout.fail`
paints the tie-out gate red because the guard said it failed, not because somebody
logged it at `error`. The table below is the whole vocabulary; a type it has never seen
marks the node as touched and nothing more, which is what an unknown event honestly
tells you.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = ["NodeState", "Trace", "TraceReducer", "state_for"]


class NodeState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ACTIVE = "active"
    USED = "used"
    NOT_REACHED = "notreached"
    PENDING = "pending"


# Explicit, by full type. The event's level is not consulted anywhere in this module.
EXPLICIT: dict[str, NodeState] = {
    "step.started": NodeState.ACTIVE,
    "step.completed": NodeState.PASSED,
    "step.satisfied": NodeState.PASSED,
    "step.quarantined": NodeState.FAILED,
    "step.transport_failed": NodeState.FAILED,
    "step.result_discarded": NodeState.USED,
    "skill.dispatched": NodeState.ACTIVE,
    "skill.completed": NodeState.PASSED,
    "model.called": NodeState.ACTIVE,
    "model.answered": NodeState.PASSED,
    "context.assembled": NodeState.PASSED,
    "policy.allow": NodeState.PASSED,
    "tool.called": NodeState.USED,
    "tool.cap_exceeded": NodeState.FAILED,
    "intake.read": NodeState.PASSED,
    "hitl.item.queued": NodeState.ACTIVE,
    "hitl.item.routed": NodeState.USED,
    "hitl.item.auto_accepted": NodeState.PASSED,
    "hitl.proposal.revealed": NodeState.USED,
    "hitl.item.decided": NodeState.PASSED,
    "hitl.sla.breached": NodeState.FAILED,
    "run.launched": NodeState.PASSED,
    "run.resumed": NodeState.PASSED,
    "run.superseded": NodeState.USED,
    "run.scored": NodeState.PASSED,
    "run.manifest.written": NodeState.PASSED,
    "release.written": NodeState.PASSED,
    "release.replayed": NodeState.PASSED,
    "release.blocked": NodeState.FAILED,
    "lock.acquired": NodeState.PASSED,
    "lock.released": NodeState.PASSED,
    "lock.queued": NodeState.ACTIVE,
    "lock.timeout": NodeState.FAILED,
    "run.enqueued": NodeState.ACTIVE,
    "plan.requested": NodeState.ACTIVE,
    "plan.proposed": NodeState.PASSED,
    "plan.refused": NodeState.FAILED,
    "plan.compiled": NodeState.PASSED,
    "triage.escalated": NodeState.ACTIVE,
    "triage.suggestion_dropped": NodeState.USED,
    "worker.started": NodeState.ACTIVE,
    "worker.deferred": NodeState.USED,
    "worker.finished": NodeState.PASSED,
    "worker.lost": NodeState.FAILED,
    "budget.ceiling_crossed": NodeState.FAILED,
}

# Families whose members all say the same thing: every guard verdict ends in pass or
# fail, every loop event in iteration, exhausted, refused or unchanged, every alert is
# a failure somebody has to look at.
SUFFIX: dict[str, NodeState] = {
    "pass": NodeState.PASSED,
    "fail": NodeState.FAILED,
    "iteration": NodeState.ACTIVE,
    "exhausted": NodeState.FAILED,
    "refused": NodeState.FAILED,
    "unchanged": NodeState.FAILED,
    "started": NodeState.ACTIVE,
    "completed": NodeState.PASSED,
    "failed": NodeState.FAILED,
    "stalled": NodeState.FAILED,
}
PREFIX: dict[str, NodeState] = {"alert.": NodeState.FAILED}

# What an event does to the *step* it was executing, where that differs from the node.
STEP_ENDINGS = frozenset({"step.completed", "step.satisfied"})
STEP_FAILURES = frozenset({"step.quarantined"})
STEP_STARTS = frozenset({"step.started"})


def state_for(event_type: str) -> NodeState:
    """The state an event type puts its node in. Type only; never the level."""
    if event_type in EXPLICIT:
        return EXPLICIT[event_type]
    for prefix, state in PREFIX.items():
        if event_type.startswith(prefix):
            return state
    return SUFFIX.get(event_type.rsplit(".", 1)[-1], NodeState.USED)


@dataclass
class Trace:
    run_id: str
    nodes: dict[str, NodeState] = field(default_factory=dict)
    steps: dict[str, NodeState] = field(default_factory=dict)
    active_step: str | None = None
    diagnostics: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Per node, the last failure it reported: code, message, step. A diagnostic
    belongs to a failure, not to a node, so a later pass clears it."""
    touched: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    """Per node, the last few events that touched it."""
    events: int = 0
    last_seq: int = 0
    last_ts: str | None = None
    last_type: str | None = None

    def counts(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for state in self.nodes.values():
            found[str(state)] = found.get(str(state), 0) + 1
        return found

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "nodes": {k: str(v) for k, v in self.nodes.items()},
            "steps": {k: str(v) for k, v in self.steps.items()},
            "active_step": self.active_step,
            "diagnostics": dict(self.diagnostics),
            "touched": {k: list(v) for k, v in self.touched.items()},
            "events": self.events,
            "last_seq": self.last_seq,
            "last_ts": self.last_ts,
            "last_type": self.last_type,
            "counts": self.counts(),
        }


class TraceReducer:
    """Fold events into a Trace. The same object serves the live feed and a replay."""

    def __init__(self, run_id: str, planned_steps: Iterable[str] = (), keep: int = 8) -> None:
        self.trace = Trace(run_id=run_id)
        self._keep = keep
        for step_id in planned_steps:
            self.trace.steps[step_id] = NodeState.NOT_REACHED

    def fold(self, events: Iterable[Any]) -> Trace:
        for event in events:
            self.apply(event)
        return self.trace

    def apply(self, event: Any) -> Trace:
        run_id, node_id, event_type, step_id, seq, ts, message, code = _fields(event)
        if run_id != self.trace.run_id:
            return self.trace
        state = state_for(event_type)
        t = self.trace
        t.nodes[node_id] = state
        if state is NodeState.FAILED:
            t.diagnostics[node_id] = {
                "code": code,
                "message": message,
                "step_id": step_id,
                "type": event_type,
                "seq": seq,
            }
        elif state is NodeState.PASSED:
            t.diagnostics.pop(node_id, None)
        if step_id:
            if event_type in STEP_STARTS:
                t.steps[step_id] = NodeState.ACTIVE
                t.active_step = step_id
            elif event_type in STEP_ENDINGS:
                t.steps[step_id] = NodeState.PASSED
                if t.active_step == step_id:
                    t.active_step = None
            elif event_type in STEP_FAILURES:
                t.steps[step_id] = NodeState.FAILED
                if t.active_step == step_id:
                    t.active_step = None
            elif step_id not in t.steps:
                t.steps[step_id] = NodeState.USED
        touched = t.touched.setdefault(node_id, [])
        touched.append({"seq": seq, "ts": ts, "type": event_type, "step_id": step_id})
        del touched[: -self._keep]
        t.events += 1
        t.last_seq = max(t.last_seq, seq)
        t.last_ts = ts
        t.last_type = event_type
        return t


def _fields(event: Any) -> tuple[str, str, str, str | None, int, str, str, str | None]:
    """Read an EventRecord or the dict the bus delivers live; the same fields either way."""
    if isinstance(event, Mapping):
        get = event.get
    else:

        def get(name: str, default: Any = None) -> Any:
            return getattr(event, name, default)

    return (
        str(get("run_id")),
        str(get("node_id")),
        str(get("type")),
        get("step_id"),
        int(get("seq") or 0),
        str(get("ts")),
        str(get("message") or ""),
        get("diagnostic_code"),
    )
