"""The Recompute / Tie-Out Engine: re-derive a stated figure from the rows behind it.

Takes a figure's derivation - an operation and the locators of its operands - together
with the rows the Source Parse Store holds under those locators, recomputes the figure
independently, and returns match or mismatch with the delta. It knows nothing about the
model that produced the claim; it only has the claim, the citation and the underlying
rows. The only arithmetic a skill can cause.

Tie-out proves arithmetic, not selection. Eight wrong rows added correctly still pass
here; selection is caught by materiality review, the self-verification pass and the
sampling audit.

Pure Python. Reached by a skill only through the Guarded Tool Runtime, under the name
`recompute`; reached by the Tie-Out guard directly, because a guard is code.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

__all__ = ["Recomputed", "recompute", "OPERATIONS"]

Rows = Sequence[float]


@dataclass(frozen=True)
class Recomputed:
    """What the rows say the figure is, and how far the stated figure is from it."""

    op: str
    stated: float
    recomputed: float
    tolerance: float
    rows_used: int

    @property
    def delta(self) -> float:
        return round(self.stated - self.recomputed, 6)

    @property
    def matches(self) -> bool:
        return abs(self.delta) <= self.tolerance


def _total(rows: Rows) -> float:
    return float(sum(rows))


def _sum(operands: Sequence[Rows]) -> float:
    return sum(_total(rows) for rows in operands)


def _difference(operands: Sequence[Rows]) -> float:
    first, *rest = (_total(rows) for rows in operands)
    return first - sum(rest)


def _product(operands: Sequence[Rows]) -> float:
    result = 1.0
    for rows in operands:
        result *= _total(rows)
    return result


def _quotient(operands: Sequence[Rows]) -> float:
    first, *rest = (_total(rows) for rows in operands)
    for divisor in rest:
        if divisor == 0:
            raise ZeroDivisionError("a quotient over a zero total")
        first /= divisor
    return first


def _average(operands: Sequence[Rows]) -> float:
    values = [v for rows in operands for v in rows]
    if not values:
        raise ValueError("an average over no rows")
    return sum(values) / len(values)


def _annualize(operands: Sequence[Rows]) -> float:
    """Rows are periods; the figure is the year. Twelve months from however many were
    read - a derivation that means something else declares a different op."""
    values = [v for rows in operands for v in rows]
    if not values:
        raise ValueError("annualize over no rows")
    return sum(values) * 12 / len(values)


def _restate_scale(operands: Sequence[Rows]) -> float:
    """The rows already carry the figure's scale - the figure envelope says which - so
    restating is the total as read. The op exists so the derivation is honest about
    what happened, not so arithmetic happens here."""
    return _sum(operands)


OPERATIONS: dict[str, Callable[[Sequence[Rows]], float]] = {
    "sum": _sum,
    "difference": _difference,
    "product": _product,
    "quotient": _quotient,
    "average": _average,
    "annualize": _annualize,
    "restate_scale": _restate_scale,
}


def recompute(
    op: str,
    operands: Sequence[Rows],
    stated: float,
    tolerance: float = 0.0,
    **caps: object,
) -> Recomputed:
    """Re-derive `stated` from `operands` with `op`. `caps` is what the runtime passes
    and this tool has no use for - the row cap was applied before the rows got here."""
    if op not in OPERATIONS:
        raise ValueError(f"{op!r} is not a derivation op (have: {', '.join(OPERATIONS)})")
    value = OPERATIONS[op](operands)
    return Recomputed(
        op=op,
        stated=float(stated),
        recomputed=round(value, 6),
        tolerance=float(tolerance),
        rows_used=sum(len(rows) for rows in operands),
    )
