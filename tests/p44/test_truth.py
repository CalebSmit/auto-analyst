"""P44: what the dashboards say is what the record says.

Five reviews of the consoles - an MD, a frontend engineer, an AI architect, an analyst and a
security engineer - agreed on where the gap was: the record holds far more than the screens
show, and three things on screen were not true. What is tested here is each of those: the
colour a verdict is painted, the sentence an empty page says, the decisions that were made,
the questions asked about work that has been replaced, and who raises an alert when no
browser is open.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ops.console.app import PAGE as ACTIVITY
from ops.console.app import Console, create_app
from ops.events import EventBus
from ops.models import DecisionKind
from ops.run_store import SqlRunStore
from ops.scorecard import Verdict
from tests.p23.conftest import ENGAGEMENT, Clock, clean_run, reviewed_run


@pytest.fixture
def console(store: SqlRunStore, bus: EventBus) -> Console:
    return Console(store, bus, clock=Clock())


@pytest.fixture
def client(console: Console) -> TestClient:
    return TestClient(create_app(console))


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))


# ------------------------------------------------------------------ the verdict's colour


def test_every_verdict_the_scorecard_can_emit_has_a_tone() -> None:
    """The page used to colour the verdict by comparing it to `clean` - which is an
    *outcome*, never a verdict. The one branch that could go green was unreachable, so a
    passing run was painted in the colour this product uses for "needs attention"."""
    body = script()
    table = re.search(r"const VERDICT_TONE = \{(.*?)\};", body, re.S)
    assert table, "the page names no verdict tones"
    named = set(re.findall(r"(\w+):", table.group(1)))
    assert {str(v) for v in Verdict} <= named, "a verdict the scorecard emits has no tone"
    assert "clean" not in named, "clean is an outcome, not a verdict"


def test_a_passing_verdict_is_not_painted_as_a_problem() -> None:
    body = script()
    tone = re.search(r"const VERDICT_TONE = \{(.*?)\};", body, re.S).group(1)
    assert re.search(r"pass:\s*'good'", tone)
    assert re.search(r"halted:\s*'bad'", tone)


def test_the_scorecard_summary_separates_failed_from_never_measured() -> None:
    """ "4 of 10 criteria met" reads the same whether six failed or six were never reached.
    The scorecard's own rule is that silence is never a pass."""
    body = script()
    assert "never measured" in body
    assert "criteria met" not in body


# ------------------------------------------------------------------ empty states


def test_an_empty_page_does_not_claim_what_it_cannot_know() -> None:
    """With nothing run, "everything the system proposed was inside its confidence bar" is a
    claim about proposals that do not exist."""
    body = script()
    assert "No run has reached a proposal yet" in body
    assert "Everything the system proposed was inside its confidence bar" not in body


# ------------------------------------------------------------------ the decision trail


def test_the_decisions_on_a_run_are_readable(
    client: TestClient, store: SqlRunStore, bus: EventBus
) -> None:
    reviewed_run(store, bus, run_id="run_decided")
    rows = client.get("/api/runs/run_decided/decisions").json()
    assert rows, "a run where a person decided something has a decision trail"
    assert {"item_id", "decision", "decided_by", "rationale", "revealed_at"} <= set(rows[0])
    assert any(r["decision"] == str(DecisionKind.CORRECTED) for r in rows)
    assert all(r["decided_by"] for r in rows), "a decision carries whoever made it"


def test_a_decision_says_whether_the_proposal_was_revealed_first(
    client: TestClient, store: SqlRunStore, bus: EventBus
) -> None:
    """The surface records the reveal so that "approved without ever looking" is answerable.
    It is answered here, on the page, rather than only in the database."""
    reviewed_run(store, bus, run_id="run_seen")
    store.open_review_item("run_seen", "li_seen", kind="tagging", subject="Which category?")
    store.record_decision(
        "run_seen",
        item_id="li_seen",
        decided_by="C. Smit",
        decision=DecisionKind.ACCEPTED,
        rationale="",
        skill="line-item-tagging@0.1.0",
        proposal={"category": "other_operating_expense"},
        answer={},
    )
    bus.emit(
        run_id="run_seen",
        engagement_id=ENGAGEMENT,
        node_id="review_surface",
        type="hitl.proposal.revealed",
        message="li_seen: proposal revealed to C. Smit",
        payload={"item_id": "li_seen", "viewer": "C. Smit", "version": 1},
    )
    (row,) = [
        r for r in client.get("/api/runs/run_seen/decisions").json() if r["item_id"] == "li_seen"
    ]
    assert row["revealed_to"] == "C. Smit"
    assert row["seconds_looking"] is not None


def test_an_unknown_run_has_no_decision_trail(client: TestClient) -> None:
    assert client.get("/api/runs/run_nope/decisions").status_code == 404


def test_the_page_asks_for_the_decisions_and_shows_the_model(client: TestClient) -> None:
    body = script()
    assert "async function decisions(id)" in body
    assert "decided without the proposal being revealed" in body
    assert "versions.model_pin" in body, "which model produced this is a question with an answer"
    assert "Run manifest" in body, "the audit record is on the run it belongs to"


# ------------------------------------------------------------------ superseded work


def test_an_item_on_a_replaced_run_is_not_asked_of_anybody(
    client: TestClient, store: SqlRunStore, bus: EventBus
) -> None:
    """A client sending a corrected statement supersedes the run that read the old one.
    Answering its questions is work thrown away."""
    clean_run(store, bus, run_id="run_old")
    store.open_review_item("run_old", "li_old", kind="tagging", subject="Which category?")
    assert [i["item_id"] for i in client.get("/api/review").json()] == ["li_old"]

    clean_run(store, bus, run_id="run_new")
    store.mark_superseded_by("run_old", "run_new")
    assert client.get("/api/review").json() == [], "the newer run asks its own questions"
    assert store.review_items("run_old"), "the item stays on the record, on its run"


def test_a_replaced_run_says_what_replaced_it(
    client: TestClient, store: SqlRunStore, bus: EventBus
) -> None:
    clean_run(store, bus, run_id="run_a")
    clean_run(store, bus, run_id="run_b")
    store.mark_superseded_by("run_a", "run_b")
    assert client.get("/api/runs/run_a").json()["superseded_by"] == "run_b"
    assert "Replaced by" in script()


# ------------------------------------------------------------------ spend, and its ceiling


def test_spend_is_shown_against_a_ceiling(
    client: TestClient, store: SqlRunStore, bus: EventBus
) -> None:
    clean_run(store, bus, run_id="run_cost")
    run = client.get("/api/runs/run_cost").json()
    assert run["budget_usd"] and run["budget_usd"] > 0, "a spend with no ceiling cannot be judged"
    assert "run.budget_usd" in script()


# ------------------------------------------------------------------ who raises an alert


def test_the_console_reads_alerts_rather_than_raising_them(
    client: TestClient, store: SqlRunStore, bus: EventBus
) -> None:
    """The page says it drives nothing. Before this it was the only thing raising alerts, so
    a run that stalled on Friday raised nothing until somebody opened a browser on Monday."""
    clean_run(store, bus, run_id="run_quiet")
    before = len(store.events("run_quiet"))
    for _ in range(3):
        client.get("/api/alerts")
    assert len(store.events("run_quiet")) == before, "reading the console wrote to the record"


def test_the_sweep_loop_raises_alerts_and_escalates_overdue_items() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "tools" / "serve.py").read_text(
        encoding="utf-8"
    )
    assert "_raise_alerts(served)" in source, "the loop that runs without a browser raises them"
    assert "escalate_overdue" in source, "and says so to whoever owns an overdue item"


# ------------------------------------------------------------------ resuming


def test_resuming_a_stopped_run_needs_a_reason(
    client: TestClient, store: SqlRunStore, bus: EventBus
) -> None:
    """Halting one always did. Restarting a run a guard refused is the same kind of
    judgement, and the reason belongs beside the refusal."""
    body = script()
    field = re.search(r"\{name: 'reason', label: 'What changed'.*?\}", body)
    assert field and "required: true" in field.group(0)

    from admin.app import install_identity
    from ops.console.app import create_app as build

    class Pool:
        def resume(self, run_id: str) -> Any:
            raise AssertionError("a resume with no reason reached the pool")

    clean_run(store, bus, run_id="run_stop")
    app = build(Console(store, bus, clock=Clock()), pool=Pool())
    install_identity(app)
    refused = TestClient(app).post("/api/runs/run_stop/resume", json={"who": None, "reason": "  "})
    assert refused.status_code == 422, refused.text
    assert "RATIONALE_REQUIRED" in refused.text


def test_every_step_status_the_record_uses_has_a_tone() -> None:
    """The same mistake as the verdict pill, one panel over: the page was written against a
    status word (`committed`) the record does not use, so every completed step was neutral.
    `not_reached` stays neutral on purpose - it neither passed nor failed."""
    from ops.models import StepStatus

    table = re.search(r"const STEP_TONE = \{(.*?)\};", script(), re.S)
    assert table, "the page names no step tones"
    named = set(re.findall(r"(\w+):", table.group(1)))
    assert {str(s) for s in StepStatus} == named
    assert re.search(r"completed:\s*'good'", table.group(1))
