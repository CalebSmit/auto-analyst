"""Watch a run happen, from one command.

    python -m uv run python tools/watch_run.py            # every run, refreshing
    python -m uv run python tools/watch_run.py --once     # one look, for a log or a paste
    python -m uv run python tools/watch_run.py --run run_abc123

Everything here is already recorded. `step.started` and `step.completed` bracket every
step, `model.answered` carries the price of each call, the stall detector raises what has
gone quiet, and the review queue holds what is waiting on a person. What was missing was
somewhere to *see* it while it is happening: the alternative is a browser page somebody
keeps refreshing, or an API somebody has to know the shape of.

The question this is written to answer is the one anybody asks during a first run - **is
it working, or is it stuck** - so the two things it puts in front of you are how long the
current step has been running against the bound its plan set, and what has been spent
against the ceiling that binds first.

**It reads and changes nothing.** No event, no decision, no transition. A watcher that
could alter a run would be a second thing deciding what happens to it, and the one thing
worse than not knowing is a bystander with a hand on the wheel.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.models import RunState  # noqa: E402
from ops.run_store import EventRecord, RunRecord, RunStore  # noqa: E402

ENDED = frozenset(
    {RunState.DELIVERED, RunState.HALTED, RunState.QUARANTINED, RunState.SUPERSEDED}
)

SLOW = 1.0
"""The fraction of a step's own bound at which it is called out.

Not a number of seconds. A step that declares five minutes and has used four is worth
saying out loud; one that declares two and has used four is a different sentence. The
bound is the plan's, so this stays right when the plan changes."""


def _when(stamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _ago(stamp: str, now: datetime) -> float:
    at = _when(stamp)
    return (now - at).total_seconds() if at else 0.0


def _clock(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"


@dataclass(frozen=True)
class Step:
    """A step that has started, and what has happened to it since."""

    step_id: str
    started_at: str
    ended: bool
    seconds: float
    calls: int
    spent: float

    def line(self, bound: float | None) -> str:
        over = bound is not None and bound > 0 and self.seconds > bound * SLOW
        mark = "  <-- past the time its step allows" if over and not self.ended else ""
        state = "done" if self.ended else "running"
        cost = f", ${self.spent:.2f}" if self.spent else ""
        calls = f", {self.calls} call{'s' if self.calls != 1 else ''}" if self.calls else ""
        return f"    {self.step_id:22s} {state:8s} {_clock(self.seconds):>7s}{calls}{cost}{mark}"


def steps_of(events: Sequence[EventRecord], now: datetime) -> list[Step]:
    """Every step this run has started, in the order it started them.

    Built from the event stream rather than from the step table because the stream is what
    the run wrote as it went: a step whose row has not been updated yet is still visible
    here, and during a first run that is exactly the step somebody is asking about.
    """
    ENDS = {"step.completed", "step.quarantined", "step.satisfied"}
    started: dict[str, str] = {}
    ended: dict[str, str] = {}
    calls: dict[str, int] = {}
    spent: dict[str, float] = {}
    order: list[str] = []
    for event in events:
        step_id = event.step_id or ""
        if not step_id:
            continue
        if event.type == "step.started" and step_id not in started:
            started[step_id] = event.ts
            order.append(step_id)
        # The *first* ending after the start, not the last event mentioning the step. A
        # resumed run re-enters every finished step to satisfy it from the ledger, so the
        # last mention of `intake` is minutes after `intake` ended - and taking that made
        # a step that took four seconds report three minutes.
        if event.type in ENDS and step_id in started and step_id not in ended:
            ended[step_id] = event.ts
        if event.type == "model.called":
            calls[step_id] = calls.get(step_id, 0) + 1
        if event.cost_usd:
            spent[step_id] = spent.get(step_id, 0.0) + float(event.cost_usd)
    out: list[Step] = []
    for step_id in order:
        finished = step_id in ended
        until = _when(ended[step_id]) if finished else now
        seconds = _ago(started[step_id], until or now)
        out.append(
            Step(
                step_id=step_id,
                started_at=started[step_id],
                ended=finished,
                seconds=max(seconds, 0.0),
                calls=calls.get(step_id, 0),
                spent=spent.get(step_id, 0.0),
            )
        )
    return out


def bounds_for(run: RunRecord) -> dict[str, float]:
    """Each step's declared timeout, from the plan this run was compiled under.

    Empty when the plan cannot be read - a watcher that refused to say anything because it
    could not find a recipe would be worse than one that simply does not mark a step slow.
    """
    from graph.recipes import load_recipe  # noqa: PLC0415

    name = str((run.versions or {}).get("recipe") or "")
    if not name:
        return {}
    try:
        recipe = load_recipe(name)
    except Exception:  # noqa: BLE001 - an unreadable recipe is somebody else's refusal
        return {}
    found: dict[str, float] = {}
    for step in getattr(recipe, "steps", ()) or ():
        step_id = str(getattr(step, "id", "") or "")
        timeout = getattr(step, "timeout_s", None)
        if step_id and timeout:
            found[step_id] = float(timeout)
    return found


def report(
    store: RunStore,
    run_ids: Iterable[str] | None = None,
    *,
    now: datetime | None = None,
    ceiling_usd: float | None = None,
) -> str:
    """What is happening, as text. One run per block, newest first."""
    at = now or datetime.now(tz=UTC)
    runs = list(store.runs())
    if run_ids is not None:
        wanted = set(run_ids)
        runs = [r for r in runs if r.run_id in wanted]
    if not runs:
        return "  no runs yet. Files have to land, go quiet, and be swept."

    lines: list[str] = []
    for run in runs:
        events = list(store.events(run.run_id))
        steps = steps_of(events, at)
        bounds = bounds_for(run)
        quiet = _ago(events[-1].ts, at) if events else 0.0
        head = f"  {run.run_id}  {run.engagement_id}  {str(run.state):<22s}"
        if run.cost_usd:
            head += f"${run.cost_usd:.2f}"
            if ceiling_usd:
                head += f" of ${ceiling_usd:.2f}"
        lines.append(head)
        for step in steps:
            lines.append(step.line(bounds.get(step.step_id)))
        if run.state not in ENDED:
            lines.append(f"    last event {_clock(quiet)} ago")
        waiting = list(store.open_review_items(run.run_id))
        if waiting:
            lines.append(f"    {len(waiting)} waiting on a person:")
            for item in waiting[:3]:
                lines.append(f"      - {str(getattr(item, 'subject', item))[:96]}")
            if len(waiting) > 3:
                lines.append(f"      ... and {len(waiting) - 3} more")
        # The last few, newest last. A run that refused twenty precedent write-backs
        # would otherwise bury the one line somebody is looking for.
        coded = [e for e in events if e.diagnostic_code]
        if len(coded) > 4:
            lines.append(f"    ! {len(coded)} diagnostics; the last four:")
        for event in coded[-4:]:
            lines.append(f"    ! {event.diagnostic_code}: {event.message[:88]}")
        if run.state_reason:
            lines.append(f"    ended: {run.state_reason}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", action="append", help="one run id; may be repeated")
    parser.add_argument("--once", action="store_true", help="print once and stop")
    parser.add_argument("--every", type=float, default=5.0, help="seconds between looks")
    args = parser.parse_args(argv)

    from ops.run_store import open_store  # noqa: PLC0415

    # `open_store()` already resolves AA_DB_URL and falls back to the default, so the
    # watcher looks at whatever the server is looking at without being told twice.
    store = open_store()
    ceiling: float | None = None
    try:
        from registries.constraints import ConstraintRegistry  # noqa: PLC0415

        ceiling = float(ConstraintRegistry.load().ceilings["per_run"]["usd_max"])
    except Exception:  # noqa: BLE001 - a missing ceiling is not a reason to say nothing
        ceiling = None

    try:
        while True:
            said = report(store, args.run, ceiling_usd=ceiling)
            stamp = datetime.now(tz=UTC).strftime("%H:%M:%S")
            print(f"\n=== {stamp}\n{said}", flush=True)
            if args.once:
                return 0
            time.sleep(max(args.every, 1.0))
    except KeyboardInterrupt:
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
