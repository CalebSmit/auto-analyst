"""Beta for the cost of equity: the comps' median unlevered beta, relevered to the subject.

From the analyst (knowledge, 2026-09-17-2): "beta is found by median unlevered beta of comps
pulled from cap iq. Then we relever it to our subject company." And the WACC is not final until
the comp set is - which is why the pilot recipe's WACC step waits for the comps.

This is the arithmetic of that sentence and nothing more:

- `unlever` and `relever` under a formula the caller names. There is no default formula: which
  one the firm uses has not been confirmed (knowledge/followups.md), and a silent default is how
  a firm's method gets decided by a library. `FORMULAS` lists the two in common use.
- `median_unlevered` over the comp set, naming every company used and every company left out and
  why. A company is left out only for having no beta - never for having an inconvenient one;
  dropping comps is the analyst's decision, made on the set, not here.
- Every multiplication and average goes through `tools.recompute`.

Which capital structure to relever at, and the tax rate, are the caller's inputs. Whether that is
the subject's actual debt to equity, the comps' median, or a target is also unconfirmed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from tools.recompute import recompute

__all__ = ["FORMULAS", "Comparable", "MedianBeta", "median_unlevered", "relever", "unlever"]

FORMULAS = ("hamada", "harris_pringle")


@dataclass(frozen=True)
class Comparable:
    """One guideline company's beta as exported, and the capital structure to unlever it at."""

    name: str
    levered_beta: float | None = None
    unlevered_beta: float | None = None
    """Taken as given when the export already carries it; otherwise unlevered here."""
    debt_to_equity: float | None = None
    tax_rate: float | None = None
    source: str = ""


@dataclass
class MedianBeta:
    value: float | None
    used: list[tuple[str, float]] = field(default_factory=list)
    """(company, its unlevered beta) for every company in the median."""
    left_out: list[tuple[str, str]] = field(default_factory=list)
    """(company, why) for every company with no usable beta."""
    formula: str = ""


def _factor(debt_to_equity: float, tax_rate: float, formula: str) -> float:
    """The (1 + ...) multiplier between unlevered and levered beta."""
    if formula not in FORMULAS:
        raise ValueError(f"{formula!r} is not a relevering formula (have: {', '.join(FORMULAS)})")
    if debt_to_equity < 0:
        raise ValueError("debt to equity is zero or positive")
    if not 0 <= tax_rate < 1:
        raise ValueError("a tax rate is a fraction from 0 up to 1")
    if formula == "hamada":
        after_tax = recompute("difference", [[1.0], [tax_rate]], 0.0).recomputed
        leverage = recompute("product", [[after_tax], [debt_to_equity]], 0.0).recomputed
    else:  # harris_pringle: no tax shield in the multiplier
        leverage = debt_to_equity
    return recompute("sum", [[1.0], [leverage]], 0.0).recomputed


def unlever(levered_beta: float, debt_to_equity: float, tax_rate: float, *, formula: str) -> float:
    factor = _factor(debt_to_equity, tax_rate, formula)
    return recompute("quotient", [[levered_beta], [factor]], 0.0).recomputed


def relever(
    unlevered_beta: float, debt_to_equity: float, tax_rate: float, *, formula: str
) -> float:
    factor = _factor(debt_to_equity, tax_rate, formula)
    return recompute("product", [[unlevered_beta], [factor]], 0.0).recomputed


def median_unlevered(comps: Sequence[Comparable], *, formula: str) -> MedianBeta:
    """The median unlevered beta of the set, with every company accounted for."""
    if formula not in FORMULAS:
        raise ValueError(f"{formula!r} is not a relevering formula (have: {', '.join(FORMULAS)})")
    result = MedianBeta(value=None, formula=formula)
    for comp in comps:
        if comp.unlevered_beta is not None:
            result.used.append((comp.name, float(comp.unlevered_beta)))
            continue
        if comp.levered_beta is None:
            result.left_out.append((comp.name, "no beta in the export"))
            continue
        if comp.debt_to_equity is None or comp.tax_rate is None:
            result.left_out.append(
                (comp.name, "a levered beta with no debt to equity or tax rate to unlever it at")
            )
            continue
        result.used.append(
            (
                comp.name,
                unlever(comp.levered_beta, comp.debt_to_equity, comp.tax_rate, formula=formula),
            )
        )
    if not result.used:
        return result
    ordered = sorted(beta for _, beta in result.used)
    middle = len(ordered) // 2
    centre = ordered[middle - 1 : middle + 1] if len(ordered) % 2 == 0 else [ordered[middle]]
    result.value = recompute("average", [centre], 0.0).recomputed
    return result
