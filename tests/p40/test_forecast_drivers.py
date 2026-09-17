"""P40: forecast driver baselines - the arithmetic an analyst starts a forecast from.

The analyst's rule (knowledge, 2026-09-17-1): each driver starts from last year's percentage
or an average of the last few years, then steps. This module computes the candidates and
chooses none of them.
"""

from __future__ import annotations

import pytest

from registries.taxonomy import load_taxonomy
from tools.forecast_drivers import DRIVERS, OPEX_EXCLUDES, as_table, baselines
from tools.statement_checks import Line

TAXONOMY = load_taxonomy("coa-taxonomy@1.0.0")
# recompute rounds to six decimal places, and a growth rate is two recomputes deep.
TOL = 1e-5
Y = ["2021-12-31", "2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31"]


def company() -> list[Line]:
    """Revenue 1000, 1100, 1210, 1331, 1464.1 (10% a year), less returns of 0 then 10 in the
    last year; COGS 60% of gross revenue; wages 20%; depreciation 50 flat."""
    revenue = [1000.0, 1100.0, 1210.0, 1331.0, 1464.1]
    return [
        Line("revenue", dict(zip(Y, revenue, strict=True)), "IS!B2"),
        Line("contra_revenue", {Y[-1]: 10.0}, "IS!B3"),
        Line("cost_of_sales", {y: r * 0.6 for y, r in zip(Y, revenue, strict=True)}, "IS!B4"),
        Line("salaries_wages", {y: r * 0.2 for y, r in zip(Y, revenue, strict=True)}, "IS!B5"),
        Line("depreciation", dict.fromkeys(Y, 50.0), "IS!B6"),
        Line("cash", dict.fromkeys(Y, 999.0), "BS!B2"),  # a balance sheet line is ignored
    ]


def test_every_driver_is_computed_per_period_with_its_sources() -> None:
    drivers = baselines(company(), TAXONOMY)
    assert set(drivers) == set(DRIVERS)
    cogs = drivers["cogs_pct_of_revenue"]
    assert cogs.by_period[Y[0]] == pytest.approx(0.6, abs=TOL)
    assert set(cogs.sources[Y[0]]) == {"IS!B4", "IS!B2"}
    assert drivers["revenue_growth"].by_period[Y[1]] == pytest.approx(0.10, abs=TOL)


def test_contra_revenue_reduces_the_revenue_every_ratio_uses() -> None:
    drivers = baselines(company(), TAXONOMY)
    net = 1464.1 - 10.0
    assert drivers["cogs_pct_of_revenue"].by_period[Y[-1]] == pytest.approx(
        1464.1 * 0.6 / net, abs=TOL
    )
    assert "IS!B3" in drivers["cogs_pct_of_revenue"].sources[Y[-1]]


def test_opex_leaves_out_depreciation_and_amortization() -> None:
    assert {"depreciation", "amortization"} == OPEX_EXCLUDES
    opex = baselines(company(), TAXONOMY)["opex_pct_of_revenue"]
    assert opex.by_period[Y[0]] == pytest.approx(0.2, abs=TOL)
    assert "IS!B6" not in opex.sources[Y[0]]


def test_last_year_and_trailing_averages_are_the_candidates() -> None:
    wages = baselines(company(), TAXONOMY)["opex_pct_of_revenue"]
    assert wages.last_year == wages.by_period[Y[-1]]
    assert set(wages.trailing_averages) == {"2y", "3y", "5y"}
    growth = baselines(company(), TAXONOMY)["revenue_growth"]
    assert "5y" not in growth.trailing_averages, "growth has four periods, not five"
    assert growth.trailing_averages["3y"] == pytest.approx(
        (0.10 + 0.10 + (1454.1 / 1331.0 - 1)) / 3, abs=TOL
    )


def test_the_first_period_has_no_growth_and_says_why() -> None:
    growth = baselines(company(), TAXONOMY)["revenue_growth"]
    assert Y[0] not in growth.by_period
    assert "no prior year" in growth.not_evaluated[Y[0]]


def test_an_unmapped_line_blocks_its_period_and_the_averages_that_need_it() -> None:
    lines = [*company(), Line("unmapped", {Y[3]: 40.0}, "IS!B9")]
    drivers = baselines(lines, TAXONOMY)
    cogs = drivers["cogs_pct_of_revenue"]
    assert Y[3] not in cogs.by_period and "unmapped" in cogs.not_evaluated[Y[3]]
    assert "2y" not in cogs.trailing_averages and "3y" not in cogs.trailing_averages
    assert "no revenue" in drivers["revenue_growth"].not_evaluated[Y[-1]]


def test_zero_revenue_is_not_a_ratio() -> None:
    lines = [Line("revenue", {Y[0]: 0.0}, "IS!B2"), Line("cost_of_sales", {Y[0]: 5.0}, "IS!B4")]
    cogs = baselines(lines, TAXONOMY)["cogs_pct_of_revenue"]
    assert cogs.by_period == {} and "zero" in cogs.not_evaluated[Y[0]]


def test_it_chooses_nothing() -> None:
    """No field holds a chosen baseline or a projected year."""
    for row in as_table(baselines(company(), TAXONOMY)):
        assert set(row) == {
            "driver",
            "by_period",
            "not_evaluated",
            "last_year",
            "trailing_averages",
            "sources",
        }
        assert all(p in Y for p in row["by_period"])
