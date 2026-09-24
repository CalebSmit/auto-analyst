"""The one multiplication in the run, and the only place it is allowed to happen.

The analyst's rule, 2026-09-22: *"the client could give us their financials in any form,
we always put it in thousands no matter what they give us."* So a figure arrives at
whatever scale the client stated and a template declares the scale it wants, and between
them somebody has to multiply.

**Not the writer.** `deliver/builder.py` refuses a scale mismatch rather than restating,
and that refusal is load-bearing: the Numeric Integrity Lock brackets the write - values
tokenised before, read back after, multiset difference empty - and it is only evidence
because the code it brackets is arithmetic-free. Arithmetic inside the bracket would be
arithmetic the lock cannot see. So the restatement happens *before* the mapping resolves,
the locked values are the restated ones, and the lock still proves what it claims.

Three rules, all of them about not being clever:

- **A ratio that is not an exact power of ten is refused.** The figure contract allows
  1, 1000 and 1000000, so in practice every ratio is; the guard is for the template that
  one day declares something else, because a fractional factor here would be a silently
  wrong number everywhere downstream.
- **One operation per figure, chosen so it is correctly rounded.** `value * (from // to)`
  going up, `value / (to // from)` going down - never `value * from / to`, which rounds
  twice for no reason. The analyst asked for every decimal kept; a restatement that
  introduces its own error is not keeping them.
- **A bare number is at scale 1.** The only figure in the catalogue that is not an
  envelope is the profile's owner-compensation benchmark, and the profile states amounts
  in units: its schema gives `amount` a currency and no scale. That assumption is held by
  a test, because the day the profile gains a scale field is the day this is wrong.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from registries.errors import WRITE_FAILED, RegistryError, diagnose

__all__ = ["BARE_NUMBERS_ARE_AT", "Restatement", "restated"]

BARE_NUMBERS_ARE_AT = 1
"""The scale of a figure that arrives as a plain number rather than an envelope."""


@dataclass(frozen=True)
class Restatement:
    """One figure moved, in enough detail to check by hand."""

    figure_ref: str
    from_scale: int
    to_scale: int
    before: float
    after: float

    @property
    def factor(self) -> float:
        return self.from_scale / self.to_scale

    def as_row(self) -> dict[str, Any]:
        return {
            "figure_ref": self.figure_ref,
            "from_scale": self.from_scale,
            "to_scale": self.to_scale,
            "before": self.before,
            "after": self.after,
        }


def _power_of_ten(value: int) -> bool:
    if value < 1:
        return False
    while value % 10 == 0:
        value //= 10
    return value == 1


def _moved(value: float, from_scale: int, to_scale: int, ref: str) -> float:
    """One correctly-rounded operation, or a refusal."""
    if not (_power_of_ten(from_scale) and _power_of_ten(to_scale)):
        raise RegistryError(
            diagnose(
                WRITE_FAILED,
                f"{ref}: restating from scale {from_scale} to {to_scale} is not a power "
                f"of ten, and a figure is not approximated to fit a template",
                locator=ref,
            )
        )
    if from_scale > to_scale:
        return value * (from_scale // to_scale)
    return value / (to_scale // from_scale)


def restated(
    figures: Mapping[str, Mapping[str, Any] | float | int], to_scale: int
) -> tuple[dict[str, Mapping[str, Any] | float | int], tuple[Restatement, ...]]:
    """Every figure at the scale the template declares, and what had to move to get there.

    A figure already at that scale is returned as it came and is not in the second half of
    the tuple - there is nothing to record about a number nobody touched.
    """
    out: dict[str, Mapping[str, Any] | float | int] = {}
    moves: list[Restatement] = []
    for ref, figure in figures.items():
        if isinstance(figure, Mapping):
            from_scale = int(figure.get("scale", BARE_NUMBERS_ARE_AT))
            before = float(figure["value"])
        else:
            from_scale = BARE_NUMBERS_ARE_AT
            before = float(figure)
        if from_scale == to_scale:
            out[ref] = figure
            continue
        after = _moved(before, from_scale, to_scale, ref)
        out[ref] = (
            {**figure, "value": after, "scale": to_scale} if isinstance(figure, Mapping) else after
        )
        moves.append(Restatement(ref, from_scale, to_scale, before, after))
    return out, tuple(moves)
