"""Checkpoint C17 - what the second interview changed.

Proves: the analyst's one-time rule and the forecast baselines work on a real skill's output,
not only on hand-built lines - the EBITDA step's schedule carries the analyst's test on every
one-time item, and the same normalized historicals it read produce forecast driver baselines
with their sources.

P40 changed a procedure that P20 built (the one-time test) and added a tool that reads the
table P18 builds and P19 tags. Each was tested alone; this is where they read the same data.
"""

from __future__ import annotations

from typing import Any

from graph.compile import Step
from graph.resolve import ResolvedScope
from harness.procedures.ebitda_normalization import CONFIRM_WITH_MANAGEMENT, one_time_doubts
from registries.taxonomy import load_taxonomy
from tests.p20.conftest import first_pass
from tools.forecast_drivers import baselines
from tools.statement_checks import Line


def test_every_one_time_item_in_a_real_schedule_carries_the_analysts_test(
    world: dict[str, Any], ebitda_step: Step, scope: ResolvedScope, case: dict[str, Any]
) -> None:
    done = first_pass(world, ebitda_step, scope, case)
    inputs = world["inputs"]
    one_time = [i for i in done.output["addback_schedule"] if i["category"] == "non_recurring"]
    assert one_time, "the fixture proposes non-recurring items"
    for item in one_time:
        line = inputs.line(item["line_item_ref"])
        assert line is not None
        doubts = one_time_doubts(inputs.periods, line.periods)
        assert CONFIRM_WITH_MANAGEMENT in item["rationale"]
        if len(doubts) > 1:
            assert item["review_required"], f"{item['candidate_id']} failed the test: {doubts[0]}"
            assert doubts[0] in item["rationale"]


def test_the_table_the_ebitda_step_read_gives_forecast_baselines_with_sources(
    world: dict[str, Any],
) -> None:
    inputs = world["inputs"]
    taxonomy = load_taxonomy("coa-taxonomy@1.0.0")
    lines = [
        Line(
            category=ln.category,
            amounts={p: float(f["value"]) for p, f in ln.figures.items()},
            locator=str(next(iter(ln.figures.values()))["locator"]),
            label=ln.description,
        )
        for ln in inputs.lines
        if ln.figures
    ]
    drivers = baselines(lines, taxonomy)
    cogs = drivers["cogs_pct_of_revenue"]
    evaluated = set(cogs.by_period) | set(cogs.not_evaluated)
    assert evaluated == set(inputs.periods), "every period is either computed or explained"
    for period, value in cogs.by_period.items():
        assert 0 < value < 1, f"cost of sales as a share of revenue in {period}: {value}"
        assert cogs.sources[period], "no value without the lines it came from"
