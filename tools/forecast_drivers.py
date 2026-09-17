"""Forecast driver baselines: the arithmetic half of a firm-built forecast.

When a client sends no forecast, the analyst builds one from drivers beneath the income
statement - a revenue growth rate per year, cost of goods sold as a percentage of revenue,
operating expenses as a percentage of revenue - and starts each from "an average from the
last year, or few years, depending what we believe a normal % is going forward, then step up
or down that % in the future years" (knowledge, 2026-09-17-1).

The first half of that is arithmetic, and it is here: every driver's value in every
historical period, its last-year value, and its trailing averages, each with the lines it came
from. The second half - which baseline is normal, and how it steps over the forecast - is
judgment. A forecast skill proposes it with a reason and a person reviews it. Nothing in this
module picks a baseline, rounds one, or projects a year.

Every quotient and average goes through `tools.recompute`, as in `statement_checks`. What it
will not do is guess:

- A period with an `unmapped` line or a category the taxonomy does not know cannot produce
  drivers: the missing line might be revenue.
- Revenue of zero, or no revenue line, is `could_not_evaluate` for every ratio in the period.
- Growth needs the period before it; the first period has none, and says so.
- An average is only reported over periods that all produced the driver - a trailing average
  with a hole in it is a different number wearing the same name.

Operating expenses here exclude depreciation and amortization, which a model usually carries
on their own lines. Whether the firm's template does is a question for the analyst
(knowledge/followups.md); `OPEX_EXCLUDES` is the one place to change it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from registries.taxonomy import UNMAPPED, Taxonomy
from tools.recompute import recompute
from tools.statement_checks import Line

__all__ = ["DRIVERS", "OPEX_EXCLUDES", "Driver", "baselines"]

DRIVERS = ("revenue_growth", "cogs_pct_of_revenue", "opex_pct_of_revenue")
OPEX_EXCLUDES = frozenset({"depreciation", "amortization"})
WINDOWS = (2, 3, 5)


@dataclass
class Driver:
    """One driver across the historical periods, and the baselines an analyst starts from."""

    driver: str
    by_period: dict[str, float] = field(default_factory=dict)
    not_evaluated: dict[str, str] = field(default_factory=dict)
    """period -> why no value."""
    last_year: float | None = None
    trailing_averages: dict[str, float] = field(default_factory=dict)
    """"2y", "3y", "5y" -> the average over that many most recent periods, when all have one."""
    sources: dict[str, list[str]] = field(default_factory=dict)
    """period -> the locators of the lines the value came from."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "driver": self.driver,
            "by_period": dict(self.by_period),
            "not_evaluated": dict(self.not_evaluated),
            "last_year": self.last_year,
            "trailing_averages": dict(self.trailing_averages),
            "sources": {p: list(v) for p, v in self.sources.items()},
        }


def _blocker(lines: Sequence[Line], taxonomy: Taxonomy, period: str) -> str | None:
    unplaced = sorted(
        {
            ln.category
            for ln in lines
            if period in ln.amounts
            and (ln.category == UNMAPPED or taxonomy.get(ln.category) is None)
        }
    )
    if unplaced:
        return (
            "a line in this period is " + ", ".join(unplaced) + "; it could be revenue or a "
            "cost, so no ratio is taken until a person places it"
        )
    return None


def _income_lines(lines: Sequence[Line], taxonomy: Taxonomy) -> list[Line]:
    out = []
    for ln in lines:
        found = taxonomy.get(ln.category)
        if ln.category == UNMAPPED or found is None or found.statement == "IS":
            out.append(ln)
    return out


def _total(
    lines: Sequence[Line], period: str, categories: frozenset[str]
) -> tuple[float, list[str]]:
    rows = [ln for ln in lines if ln.category in categories and period in ln.amounts]
    value = recompute("sum", [[ln.amounts[period] for ln in rows]], 0.0).recomputed
    return value, [ln.locator for ln in rows]


def baselines(lines: Sequence[Line], taxonomy: Taxonomy) -> dict[str, Driver]:
    """Each driver in `DRIVERS`, over every period the income statement lines cover.

    Amounts are as presented, as in `statement_checks`: revenue and costs positive, contra
    revenue reducing revenue whatever its sign.
    """
    income = _income_lines(lines, taxonomy)
    periods = sorted({p for ln in income for p in ln.amounts})
    opex_categories = frozenset(
        cid
        for cid, cat in taxonomy.categories.items()
        if cat.section == "operating_expenses" and cid not in OPEX_EXCLUDES
    )
    drivers = {name: Driver(name) for name in DRIVERS}

    revenue: dict[str, float] = {}
    revenue_sources: dict[str, list[str]] = {}
    for period in periods:
        blocked = _blocker(income, taxonomy, period)
        if blocked:
            for d in drivers.values():
                d.not_evaluated[period] = blocked
            continue
        gross, gross_src = _total(income, period, frozenset({"revenue"}))
        contra_rows = [
            ln for ln in income if ln.category == "contra_revenue" and period in ln.amounts
        ]
        contra = [abs(ln.amounts[period]) for ln in contra_rows]
        if not gross_src:
            for d in drivers.values():
                d.not_evaluated[period] = "no revenue line in this period"
            continue
        net = recompute("difference", [[gross], contra], 0.0).recomputed
        if net == 0:
            for d in drivers.values():
                d.not_evaluated[period] = "revenue is zero; no ratio or growth rate exists"
            continue
        revenue[period] = net
        revenue_sources[period] = gross_src + [ln.locator for ln in contra_rows]

        for name, categories in (
            ("cogs_pct_of_revenue", frozenset({"cost_of_sales"})),
            ("opex_pct_of_revenue", opex_categories),
        ):
            cost, cost_src = _total(income, period, categories)
            driver = drivers[name]
            driver.by_period[period] = recompute("quotient", [[cost], [net]], 0.0).recomputed
            driver.sources[period] = cost_src + revenue_sources[period]

    growth = drivers["revenue_growth"]
    for before, after in zip(periods, periods[1:], strict=False):
        if after in growth.not_evaluated:
            continue
        if before not in revenue:
            growth.not_evaluated[after] = f"no revenue for {before} to grow from"
            continue
        ratio = recompute("quotient", [[revenue[after]], [revenue[before]]], 0.0).recomputed
        growth.by_period[after] = recompute("difference", [[ratio], [1.0]], 0.0).recomputed
        growth.sources[after] = revenue_sources[before] + revenue_sources[after]
    if periods and periods[0] not in growth.not_evaluated:
        growth.not_evaluated[periods[0]] = "the first period has no prior year to grow from"

    for driver in drivers.values():
        _summarise(driver, periods)
    return drivers


def _summarise(driver: Driver, periods: Sequence[str]) -> None:
    if not periods:
        return
    latest = periods[-1]
    driver.last_year = driver.by_period.get(latest)
    for window in WINDOWS:
        recent = list(periods[-window:])
        if len(recent) < window or any(p not in driver.by_period for p in recent):
            continue
        driver.trailing_averages[f"{window}y"] = recompute(
            "average", [[driver.by_period[p] for p in recent]], 0.0
        ).recomputed


def as_table(drivers: Mapping[str, Driver]) -> list[dict[str, Any]]:
    """The drivers as plain rows, in `DRIVERS` order - what a skill payload or a page reads."""
    return [drivers[name].as_dict() for name in DRIVERS if name in drivers]
