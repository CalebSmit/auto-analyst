"""FastAPI plus SSE over the event bus: the console is a reader, and it replays a
completed run from the event stream alone."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ops.console import Console, create_app
from ops.events import EventBus
from ops.manifest import close_out
from ops.models import Outcome, RunState
from ops.run_store import SqlRunStore
from tests.p23.conftest import ENGAGEMENT, Clock, Script, clean_run, halted_run, reviewed_run


@pytest.fixture
def console(store: SqlRunStore, bus: EventBus, clock: Clock) -> Console:
    return Console(store, bus, clock=clock)


@pytest.fixture
def client(console: Console) -> TestClient:
    return TestClient(create_app(console))


def frames(text: str) -> list[dict[str, Any]]:
    """Parse SSE frames: event, id, data.

    Every frame carries the one name the page listens for; what the frame *is* - the event
    type, or the end of the replay - is in the body, so a type nobody anticipated still
    reaches a listener.
    """
    found = []
    for block in text.split("\n\n"):
        if not block.strip() or block.startswith(":"):
            continue
        frame: dict[str, Any] = {}
        for line in block.splitlines():
            key, _, value = line.partition(": ")
            frame[key] = json.loads(value) if key == "data" else value
        found.append(frame)
    return found


def test_the_console_replays_a_completed_run_from_the_event_stream_alone(
    store: SqlRunStore, bus: EventBus, delivery: Any, console: Console, client: TestClient
) -> None:
    halted_run(store, bus)
    close_out(store, "run_halted", RunState.HALTED, Outcome.HALTED, delivery, bus=bus)

    with client.stream("GET", "/api/runs/run_halted/stream") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    got = frames(body)
    assert {f["event"] for f in got} == {"aa"}, "one frame name, so nothing is dropped unseen"
    assert got[-1]["data"]["type"] == "replayed"
    assert got[-1]["data"]["event"]["through"] == len(store.events("run_halted"))
    types = [f["data"]["type"] for f in got[:-1]]
    assert types == [e.type for e in store.events("run_halted")]
    final = got[-2]["data"]["trace"]
    assert final["nodes"] == console.replay("run_halted").as_dict()["nodes"]
    assert final["nodes"]["tieout_gate"] == "failed"
    assert final["diagnostics"]["tieout_gate"]["code"] == "GUARD.TIEOUT_MISMATCH"
    assert final["steps"]["release"] == "notreached"

    again = client.get("/api/runs/run_halted/trace").json()
    assert again["nodes"] == final["nodes"] and again["counts"]["failed"] == 3


def test_the_stream_follows_a_live_run_and_closes_when_the_manifest_is_written(
    store: SqlRunStore, bus: EventBus, delivery: Any, client: TestClient
) -> None:
    s = Script(store, bus, "run_live", ENGAGEMENT)
    s.start()

    def later() -> None:
        # The run carries on in its own thread once the console has subscribed.
        deadline = time.monotonic() + 10
        while not bus.subscribers() and time.monotonic() < deadline:
            time.sleep(0.02)
        s.intake()
        s.skill(
            "timing",
            "timing-normalization@0.1.0",
            summary={"periods": ["FY2025"], "period_gaps": []},
        )
        s.guard("provenance_gate", "provenance", True, 3, step_id="timing")
        s.guard("tieout_gate", "tieout", True, 1, step_id="timing")
        s.guard("reconcile", "reconcile", True, 3, step_id="timing")
        s.release()
        close_out(store, "run_live", RunState.DELIVERED, Outcome.CLEAN, delivery, bus=bus)

    worker = threading.Thread(target=later)
    worker.start()
    with client.stream("GET", "/api/runs/run_live/stream") as response:
        body = "".join(response.iter_text())
    worker.join(timeout=10)
    assert not worker.is_alive()
    got = [f for f in frames(body) if "event" in f]
    events = [f["data"]["type"] for f in got]
    assert events[0] == "run.launched"
    assert "replayed" in events and events[-1] == "run.manifest.written"
    assert events.index("replayed") < events.index("guard.tieout.pass"), (
        "live half came after replay"
    )
    assert got[-1]["data"]["trace"]["nodes"]["run_manifest"] == "passed"
    assert got[-1]["data"]["event"]["payload"]["verdict"] == "pass"
    assert bus.subscribers() == (), "the client is gone; nothing is left on the bus"


def test_the_run_page_carries_the_scorecard_the_spend_and_the_trace(
    store: SqlRunStore, bus: EventBus, delivery: Any, client: TestClient, clock: Clock
) -> None:
    reviewed_run(store, bus, at=clock())
    close_out(
        store, "run_reviewed", RunState.DELIVERED, Outcome.RELEASED_WITH_REVIEW, delivery, bus=bus
    )
    page = client.get("/api/runs/run_reviewed").json()
    assert page["state"] == "delivered" and page["outcome"] == "released_with_review"
    assert page["scorecard"]["verdict"] == "pass_with_exceptions"
    assert page["spend"]["model_calls"] == 3 and page["cost"]["by_tier"][0]["key"] == "mid"
    assert page["trace"]["nodes"]["decision_log"] == "passed"
    assert {s["step_id"] for s in page["steps"]} == {
        "intake",
        "timing",
        "tagging",
        "ebitda",
        "release",
    }
    card = client.get("/api/runs/run_reviewed/scorecard").json()
    assert "PASS_WITH_EXCEPTIONS" in card["report"] and not card["in_progress"]
    assert client.get("/api/runs/nope").status_code == 404


def test_the_inbox_the_guard_strip_the_alerts_and_the_aggregates(
    store: SqlRunStore, bus: EventBus, delivery: Any, client: TestClient, clock: Clock
) -> None:
    clean_run(store, bus)
    close_out(store, "run_clean", RunState.DELIVERED, Outcome.CLEAN, delivery, bus=bus)
    s = Script(store, bus, "run_open", ENGAGEMENT)
    s.start()
    s.intake()
    s.review("li_7", "line-item-tagging@0.1.0", confidence=0.55, due_hours=2, at=clock())
    store.transition("run_open", RunState.WAITING, reason="blocked on tagging")

    runs = client.get("/api/runs").json()
    assert {r["run_id"]: r["state"] for r in runs} == {
        "run_clean": "delivered",
        "run_open": "waiting",
    }
    assert next(r for r in runs if r["run_id"] == "run_open")["open_review_items"] == 1

    (item,) = client.get("/api/review").json()
    assert item["item_id"] == "li_7" and item["owner"] == "Dana Whitfield"

    strip = client.get("/api/guards").json()
    assert {(g["run_id"], g["guard"], g["result"]) for g in strip} == {
        ("run_open", "payload_scan", "pass")
    }

    assert client.get("/api/alerts").json() == []
    clock.advance(hours=3)
    (alert,) = client.get("/api/alerts").json()
    assert alert["kind"] == "review_overdue" and alert["code"] == "PROCESS.REVIEW_SLA_BREACH"

    analytics = client.get("/api/analytics").json()
    assert analytics["head"]["runs"] == 2 and analytics["stuck"]["review_items_past_sla"] == 1
    cost = client.get(f"/api/cost/{ENGAGEMENT}").json()
    assert cost["total_usd"] > 0 and {r["key"] for r in cost["runs"]} == {"run_clean", "run_open"}
    assert client.get("/api/drift").json()["flags"] == []
    assert client.get("/api/runs/run_clean/artifacts").json()[0]["name"] == "run_manifest.json"


def test_the_browser_page_subscribes_to_the_stream_and_the_console_holds_no_state(
    store: SqlRunStore, bus: EventBus, client: TestClient
) -> None:
    page = client.get("/")
    assert page.status_code == 200 and "EventSource('/api/runs/'" in page.text
    assert "console down, runs continue" in page.text

    # A reader that breaks is dropped by the bus; the run goes on.
    def broken(event: dict[str, Any]) -> None:
        raise RuntimeError("console crashed")

    bus.subscribe(broken)
    s = Script(store, bus, "run_on", ENGAGEMENT)
    s.start()
    assert broken not in bus.subscribers()
    assert store.run("run_on").state is RunState.RUNNING
    assert client.get("/api/runs/run_on").json()["state"] == "running"
