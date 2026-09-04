"""The analytics view answers four questions from the run store, and the cost meter
says what each run and each skill cost."""

from __future__ import annotations

from typing import Any

from ops.analytics import Analytics
from ops.cost import CostMeter
from ops.events import EventBus
from ops.manifest import close_out
from ops.models import Outcome, RunState
from ops.run_store import SqlRunStore
from ops.stall import StallDetector
from tests.p23.conftest import ENGAGEMENT, Clock, clean_run, halted_run, reviewed_run


def three_runs(store: SqlRunStore, bus: EventBus, delivery: Any, clock: Clock) -> None:
    clean_run(store, bus)
    close_out(store, "run_clean", RunState.DELIVERED, Outcome.CLEAN, delivery, bus=bus)
    reviewed_run(store, bus, at=clock())
    close_out(
        store, "run_reviewed", RunState.DELIVERED, Outcome.RELEASED_WITH_REVIEW, delivery, bus=bus
    )
    halted_run(store, bus)
    close_out(store, "run_halted", RunState.HALTED, Outcome.HALTED, delivery, bus=bus)


def test_is_it_healthy_what_should_we_fix_is_it_improving_is_anything_stuck(
    store: SqlRunStore, bus: EventBus, delivery: Any, clock: Clock
) -> None:
    three_runs(store, bus, delivery, clock)
    clock.advance(minutes=5)
    view = Analytics(store, stall=StallDetector(store, bus, clock=clock), clock=clock).overview()

    # Healthy?
    assert view.head["runs"] == 3 and view.head["finished"] == 3
    assert view.head["first_pass_yield"] == round(2 / 3, 4)
    assert view.head["released_then_corrected"] == 0
    (week,) = view.outcomes
    assert {k: week[k] for k in ("clean", "released_with_review", "halted", "blocked")} == {
        "clean": 1,
        "released_with_review": 1,
        "halted": 1,
        "blocked": 0,
    }
    assert [f["reached"] for f in view.funnel] == [3, 3, 3, 2, 2, 2]
    assert view.funnel[-1] == {"stage": "Released", "reached": 2, "dropped": 0}

    # Fix what?
    top = view.failures[0]
    assert top["code"] == "GUARD.TIEOUT_MISMATCH" and top["owner"] == "client-data"
    assert top["count"] == 3 and top["what_now"]
    assert {f["code"] for f in view.failures} >= {"LOOP.EXHAUSTED"}

    # Improving?
    assert view.trends["auto_accept_rate"] == round(10 / 12, 4)
    assert view.trends["override_rate"] == 0.5
    assert view.trends["override_rate_human_baseline"] == "unmeasured"
    assert view.trends["tieout_failure_rate"] == round(1 / 3, 4)
    assert view.trends["cost_per_engagement_usd"] > 0

    # Stuck?
    assert view.stuck["quarantined_steps"] == 1
    assert view.stuck["review_items_past_sla"] == 0
    assert view.stuck["stalled_runs"] == 0
    assert view.stuck["skills_flagged_by_drift"] == []

    (row,) = [r for r in view.skills if r["skill"] == "line-item-tagging"]
    assert row["scope"] == "_firm" and row["items"] == 12 and row["override_rate"] == 0.5
    assert "failures, ranked" in view.report()


def test_the_human_baseline_sits_beside_the_override_rate_once_it_is_measured(
    store: SqlRunStore, bus: EventBus, delivery: Any, clock: Clock
) -> None:
    three_runs(store, bus, delivery, clock)
    view = Analytics(store, human_baseline_override_rate=0.07, clock=clock).overview()
    assert view.trends["override_rate_human_baseline"] == 0.07
    assert view.as_dict()["human_baseline_override_rate"] == 0.07


def test_the_cost_meter_breaks_a_run_down_by_skill_model_and_tier(
    store: SqlRunStore, bus: EventBus, delivery: Any, clock: Clock
) -> None:
    three_runs(store, bus, delivery, clock)
    meter = CostMeter(store)
    b = meter.breakdown("run_clean")
    assert b.total_usd == round(3 * 0.42, 6)
    assert {line.key for line in b.by_skill} == {
        "timing-normalization@0.1.0",
        "line-item-tagging@0.1.0",
        "ebitda-normalization@0.1.0",
    }
    assert b.by_skill[0].usd == 0.42 and b.by_skill[0].calls == 1
    (model,) = b.by_model
    assert model.key == "claude-sonnet-5" and model.input_tokens == 3 * 18_400
    (tier,) = b.by_tier
    assert tier.key == "mid" and tier.calls == 3

    rollup = meter.rollup(ENGAGEMENT)
    assert {line.key for line in rollup.runs} == {"run_clean", "run_reviewed", "run_halted"}
    assert rollup.total_usd == round(sum(line.usd for line in rollup.runs), 6)
    assert rollup.by_tier[0].key == "mid"
    assert rollup.as_dict()["engagement_id"] == ENGAGEMENT
    # Derived from the record, so the meter and the run's own counter agree.
    assert abs(rollup.total_usd - sum(r.cost_usd for r in store.runs(ENGAGEMENT))) < 1e-6
