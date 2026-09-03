"""Each of the four ceilings halts and escalates.

The exit criterion, one test per ceiling, plus the shape of a halt: an event with the
code and the owner, a review item naming the ceiling and the number, and a raise. Halt,
not throttle - a run that quietly degrades to a cheaper model is much harder to reason
about afterwards than one that stops and says why.
"""

from __future__ import annotations

import pytest

from harness.budget import CEILINGS, BudgetExceeded, BudgetGovernor
from harness.door import ModelDoor
from ops.cost import CostMeter
from ops.run_store import SqlRunStore
from ports.llm import ModelPin, Usage
from privacy.payload_scan import IdentifierList
from registries.constraints import ConstraintRegistry
from tests.p11.conftest import ENGAGEMENT, masked_request


def test_there_are_four_and_they_are_the_blueprints() -> None:
    """Token spend, currency spend, wall clock, total loop iterations."""
    assert [c.key for c in CEILINGS] == [
        "usd_max", "tokens_max", "wall_clock_s", "loop_iterations_max"
    ]


def test_every_ceiling_is_in_the_constraints(constraints: ConstraintRegistry) -> None:
    for ceiling in CEILINGS:
        assert ceiling.key in constraints.ceilings["per_run"]


def test_a_run_under_every_ceiling_is_allowed(governor: BudgetGovernor, started: str) -> None:
    spend = governor.check(started, ENGAGEMENT, about_to_spend_usd=0.5, about_to_call=True)
    assert spend.usd == 0.0
    assert governor.remaining_usd(started) == governor.limit(CEILINGS[0])


def halted(store: SqlRunStore, run_id: str, key: str) -> None:
    """What every halt has to leave behind."""
    events = [e for e in store.events(run_id) if e.type == "budget.ceiling_crossed"]
    assert len(events) == 1
    assert events[0].diagnostic_code == "POLICY.BUDGET_EXCEEDED"
    assert events[0].level == "error"
    assert events[0].payload["ceiling"] == key
    items = store.review_items(run_id)
    assert [i.item_id for i in items] == [f"budget_{key}"]
    assert items[0].kind == "budget"
    assert key in items[0].subject


def test_the_currency_ceiling_halts_and_escalates(
    governor: BudgetGovernor, meter: CostMeter, started: str, store: SqlRunStore
) -> None:
    limit = governor.limit(CEILINGS[0])
    # Spend up to just under the ceiling on Opus, then propose a call that crosses it.
    nearly_all = int(limit * 0.98 / 5 * 1e6)  # Opus input at $5/MTok
    meter.record(started, ModelPin.for_tier("high"), Usage(input_tokens=nearly_all))
    with pytest.raises(BudgetExceeded) as raised:
        governor.check(started, ENGAGEMENT, about_to_spend_usd=limit * 0.05, about_to_call=True)
    assert raised.value.ceiling.key == "usd_max"
    assert raised.value.diagnostic.code == "POLICY.BUDGET_EXCEEDED"
    halted(store, started, "usd_max")


def test_the_token_ceiling_halts_and_escalates(
    governor: BudgetGovernor, meter: CostMeter, started: str, store: SqlRunStore
) -> None:
    limit = int(governor.limit(CEILINGS[1]))
    meter.record(started, ModelPin.for_tier("low"), Usage(input_tokens=limit))
    with pytest.raises(BudgetExceeded) as raised:
        governor.check(started, ENGAGEMENT, about_to_spend_tokens=1, about_to_call=True)
    assert raised.value.ceiling.key == "tokens_max"
    halted(store, started, "tokens_max")


def test_the_wall_clock_ceiling_halts_and_escalates(
    governor: BudgetGovernor, started: str, store: SqlRunStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Active wall clock, which is the clock that stops while a person is thinking. Moved
    by hand rather than waited for - the ceiling is ninety minutes."""
    limit = governor.limit(CEILINGS[2])
    from ops import run_store

    monkeypatch.setattr(run_store, "_elapsed", lambda since: limit + 1)
    store.stop_clock(started)
    with pytest.raises(BudgetExceeded) as raised:
        governor.check(started, ENGAGEMENT)
    assert raised.value.ceiling.key == "wall_clock_s"
    halted(store, started, "wall_clock_s")


def test_the_loop_ceiling_halts_and_escalates(
    governor: BudgetGovernor, bus, started: str, store: SqlRunStore
) -> None:
    """Total across every loop. Several loops cannot conspire to run long by each
    staying under its own maximum."""
    limit = int(governor.limit(CEILINGS[3]))
    for n in range(limit + 1):
        bus.emit(
            run_id=started, engagement_id=ENGAGEMENT, node_id="loop_controller",
            type="loop.guard_repair.iteration", message=f"iteration {n}",
            payload={"loop": "guard_repair:ebitda", "iteration": n},
        )
    with pytest.raises(BudgetExceeded) as raised:
        governor.check(started, ENGAGEMENT)
    assert raised.value.ceiling.key == "loop_iterations_max"
    halted(store, started, "loop_iterations_max")


def test_a_halt_is_a_halt_not_a_throttle(
    governor: BudgetGovernor, meter: CostMeter, started: str
) -> None:
    """After a ceiling is crossed there is no cheaper path offered, no reduced effort,
    no retry. The governor has no method that would do any of those."""
    for name in ("throttle", "degrade", "downgrade", "reduce", "retry", "extend", "raise_ceiling"):
        assert not hasattr(governor, name)


def test_the_door_checks_before_and_after(
    door: ModelDoor, identifiers: IdentifierList, started: str, meter: CostMeter,
    governor: BudgetGovernor, store: SqlRunStore,
) -> None:
    """Before: is there room for this call. After: was this the one that crossed."""
    limit = governor.limit(CEILINGS[0])
    # Spent as Opus output at $25/MTok, so the dollars are nearly at the ceiling while the
    # tokens stay well under theirs - it has to be the currency ceiling that fires.
    nearly_all = int((limit - 0.001) / 25 * 1e6)
    meter.record(started, ModelPin.for_tier("high"), Usage(output_tokens=nearly_all))
    with pytest.raises(BudgetExceeded):
        door.send(masked_request(), identifiers, started, estimated_cost_usd=0.0)
    # The call went (the estimate was zero) and the answer's real cost crossed the line.
    # Two calls on the record: the spend this test seeded, and the one the door made.
    assert store.run(started).model_calls == 2
    halted(store, started, "usd_max")


def test_remaining_budget_is_what_the_gate_reads(
    governor: BudgetGovernor, meter: CostMeter, started: str
) -> None:
    before = governor.remaining_usd(started)
    charge = meter.record(started, ModelPin.for_tier("mid"), Usage(input_tokens=1_000_000))
    assert governor.remaining_usd(started) == pytest.approx(before - charge.usd)
