"""P123 - watching a run happen.

Everything a person wants during a first run is already recorded: `step.started` and
`step.completed` bracket each step, `model.answered` carries the price of each call, the
stall detector raises what has gone quiet, and the review queue holds what is waiting on
somebody. All of it was behind a browser page somebody has to keep refreshing, or behind
an API somebody has to know the shape of.

The question this answers is the one anybody asks during a first run — **is it working, or
is it stuck** — so what it puts in front of you is how long the current step has been
running against the bound its plan set, and what has been spent against the ceiling.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tools.watch_run import Step, report, steps_of

ROOT = Path(__file__).resolve().parents[2]
WATCHER = ROOT / "tools" / "watch_run.py"
T0 = datetime(2026, 9, 24, 21, 0, tzinfo=UTC)


def stamp(seconds: int) -> str:
    return (T0 + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def event(
    at: int, kind: str, step: str = "", *, cost: float = 0.0, code: str = "", said: str = ""
) -> Any:
    return type(
        "E",
        (),
        {
            "seq": at,
            "ts": stamp(at),
            "type": kind,
            "step_id": step,
            "cost_usd": cost,
            "diagnostic_code": code,
            "message": said,
            "payload": {},
        },
    )()


# ============================================================ the step, and how long


def test_a_running_step_is_timed_from_its_start_to_now() -> None:
    found = steps_of([event(0, "step.started", "timing")], T0 + timedelta(seconds=45))
    assert found == [Step("timing", stamp(0), False, 45.0, 0, 0.0)]


def test_a_finished_step_is_timed_to_when_it_finished() -> None:
    found = steps_of(
        [event(0, "step.started", "timing"), event(12, "step.completed", "timing")],
        T0 + timedelta(hours=3),
    )
    assert found[0].ended and found[0].seconds == 12.0


def test_a_resumed_run_does_not_restate_a_finished_step_s_time() -> None:
    """The bug the first real database found. A resumed run re-enters every finished step
    to satisfy it from the ledger, so the *last* event mentioning `intake` is minutes
    after intake ended - and taking that made a four-second step report three minutes."""
    found = steps_of(
        [
            event(0, "step.started", "intake"),
            event(4, "step.completed", "intake"),
            event(600, "step.satisfied", "intake"),
        ],
        T0 + timedelta(seconds=900),
    )
    assert found[0].seconds == 4.0


def test_steps_come_out_in_the_order_they_started() -> None:
    found = steps_of(
        [
            event(0, "step.started", "intake"),
            event(1, "step.started", "timing"),
            event(2, "step.started", "tagging"),
        ],
        T0,
    )
    assert [s.step_id for s in found] == ["intake", "timing", "tagging"]


def test_calls_and_spend_are_counted_per_step() -> None:
    found = steps_of(
        [
            event(0, "step.started", "timing"),
            event(1, "model.called", "timing"),
            event(2, "model.answered", "timing", cost=1.11),
            event(3, "step.completed", "timing"),
        ],
        T0,
    )
    assert found[0].calls == 1
    assert found[0].spent == pytest.approx(1.11)


def test_an_event_belonging_to_no_step_is_ignored() -> None:
    """`run.launched`, `lock.acquired` and the intake reads carry no step, and counting
    them would invent a step called nothing."""
    assert (
        steps_of(
            [
                event(0, "run.launched"),
                event(1, "lock.acquired"),
                event(2, "step.started"),  # a started event whose step is empty
                event(3, "model.called"),
            ],
            T0,
        )
        == []
    )


# ============================================================ slow, said out loud


def test_a_step_past_its_own_bound_is_marked() -> None:
    running = Step("timing", stamp(0), False, 400.0, 1, 0.0)
    assert "past the time its step allows" in running.line(300.0)


def test_a_step_inside_its_bound_is_not() -> None:
    assert "past the time" not in Step("timing", stamp(0), False, 100.0, 1, 0.0).line(300.0)


def test_a_finished_step_is_never_marked_slow() -> None:
    """It is over. Saying a completed step took too long is noise in the one place
    somebody is scanning for the step that has not finished."""
    done = Step("timing", stamp(0), True, 400.0, 1, 0.0)
    assert "past the time" not in done.line(300.0)


def test_a_step_with_no_known_bound_is_reported_without_one() -> None:
    """An unreadable recipe means no bound, not no report. A watcher that said nothing
    because it could not find a plan would be worse than one that does not mark a step."""
    assert "timing" in Step("timing", stamp(0), False, 9999.0, 0, 0.0).line(None)


# ============================================================ the whole report


class Store:
    """A run store with exactly what a watcher reads out of it."""

    def __init__(
        self, runs: list[Any], events: list[Any], waiting: list[Any] | None = None
    ) -> None:
        self._runs, self._events, self._waiting = runs, events, waiting or []
        self.wrote = False

    def runs(self) -> list[Any]:
        return self._runs

    def events(self, run_id: str) -> list[Any]:
        return self._events

    def open_review_items(self, run_id: str) -> list[Any]:
        return self._waiting


def a_run(**over: Any) -> Any:
    fields = {
        "run_id": "run_abc",
        "engagement_id": "KSPW-2026-01",
        "state": "running",
        "cost_usd": 1.44,
        "state_reason": "",
        "versions": {},
    }
    fields.update(over)
    return type("R", (), fields)()


def test_it_says_the_run_the_engagement_the_state_and_the_spend() -> None:
    said = report(
        Store([a_run()], [event(0, "step.started", "timing")]),
        now=T0 + timedelta(seconds=30),
        ceiling_usd=40.0,
    )
    assert "run_abc" in said and "KSPW-2026-01" in said
    assert "$1.44 of $40.00" in said


def test_it_says_how_long_the_run_has_been_quiet() -> None:
    """The other half of "is it stuck". A step that has been running twenty seconds with
    an event ten seconds ago is working; one with no event for six minutes is not."""
    said = report(
        Store([a_run()], [event(0, "step.started", "timing")]), now=T0 + timedelta(seconds=90)
    )
    assert "last event" in said and "1m30s" in said


def test_a_finished_run_is_not_asked_how_quiet_it_is() -> None:
    said = report(Store([a_run(state="delivered")], [event(0, "step.completed", "release")]))
    assert "last event" not in said


def test_it_says_what_is_waiting_on_a_person() -> None:
    waiting = [type("I", (), {"subject": "Freight: tag as other_operating_expense?"})()]
    said = report(Store([a_run()], [event(0, "step.started", "tagging")], waiting))
    assert "1 waiting on a person" in said
    assert "Freight" in said


def test_a_long_queue_is_summarised_rather_than_printed() -> None:
    waiting = [type("I", (), {"subject": f"item {n}"})() for n in range(40)]
    said = report(Store([a_run()], [event(0, "step.started", "tagging")], waiting))
    assert "40 waiting on a person" in said
    assert "and 37 more" in said
    shown = [line for line in said.splitlines() if line.strip().startswith("- item")]
    assert len(shown) == 3, "three, then a count - not forty lines of queue"


def test_diagnostics_are_shown_newest_last_and_capped() -> None:
    """A run that refused twenty precedent write-backs would otherwise bury the one line
    somebody is looking for."""
    events = [
        event(n, "precedent.writeback.refused", "model", code="PRIVACY.X", said=f"row {n}")
        for n in range(9)
    ]
    said = report(Store([a_run()], events))
    assert "9 diagnostics" in said
    assert "row 8" in said and "row 0" not in said


def test_no_runs_says_what_has_to_happen_first() -> None:
    """The most likely thing a person sees in their first minute, and "no runs" alone
    invites them to conclude it is broken."""
    said = report(Store([], []))
    assert "quiet" in said and "swept" in said


def test_it_can_be_asked_about_one_run() -> None:
    both = [a_run(run_id="run_one"), a_run(run_id="run_two")]
    said = report(Store(both, [event(0, "step.started", "timing")]), ["run_two"])
    assert "run_two" in said and "run_one" not in said


# ============================================================ it only reads


def test_it_writes_nothing() -> None:
    """A watcher that could alter a run would be a second thing deciding what happens to
    it. Walked rather than trusted: no call to anything that records, emits or transitions."""
    tree = ast.parse(WATCHER.read_text(encoding="utf-8"))
    forbidden = {
        "append_event",
        "emit",
        "record_decision",
        "transition",
        "start_run",
        "end_run",
        "open_review_item",
        "write",
        "commit_step",
        "finish_step",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden, node.func.attr


def test_the_store_it_opens_is_the_one_the_server_is_using() -> None:
    """`open_store()` resolves `AA_DB_URL` itself, so the watcher looks where the server
    looks without being told twice - and a second place that decided the database is a
    second place that could be pointed at the wrong one."""
    from tests.reading import python_code

    source = python_code(WATCHER.read_text(encoding="utf-8"))
    assert "open_store()" in source
    assert "AA_DB_URL" not in source, "not resolved a second time"
