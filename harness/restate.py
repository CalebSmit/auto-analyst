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
- **The unit is asked before the scale is touched.** A scale is a currency convention -
  *in thousands* - and a count of shares is not in it, at any scale. P162 taught the reader
  that, and gave such a figure `unit: shares, scale: 1`; this module then divided it by a
  thousand anyway, read `scale` alone, and rewrote the scale to the template's so that the
  writer's own refusal for a figure at the wrong scale could never fire. Six lines across
  three modules multiplied a figure by its scale and two lines in the repository read its
  unit, both asking only whether it was currency. So `amount_of` and `expect_unit` below
  are the one way a figure becomes a number, every site reaches them, and a test makes
  `_moved` raise and watches each site fail - which is the only proof of "one place" that
  is not a search for a word.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from registries.errors import WRITE_FAILED, RegistryError, diagnose

__all__ = [
    "BARE_NUMBERS_ARE_AT",
    "Amount",
    "Left",
    "Restatement",
    "amount_of",
    "expect_unit",
    "restated",
]

BARE_NUMBERS_ARE_AT = 1
"""The scale of a figure that arrives as a plain number rather than an envelope."""

_DESCRIBED = {
    "currency": "money",
    "shares": "a count of shares",
    "count": "a count",
    "percent": "a percentage",
    "ratio": "a ratio",
    "multiple": "a multiple",
    "years": "a number of years",
}
"""What a figure of each unit is, for the sentence a person reads. The units are
`figure.schema.json`'s; one it does not name is described by its own word."""


def _describe(unit: str) -> str:
    return _DESCRIBED.get(unit, f"a figure in {unit}")


def _unit_of(figure: Mapping[str, Any] | float | int) -> tuple[str, str | None]:
    """The unit a figure is in and, for money, its currency code. A bare number is money
    with no code, which is what the profile's benchmark is."""
    if not isinstance(figure, Mapping):
        return "currency", None
    unit = str(figure.get("unit") or "currency")
    code = figure.get("currency")
    return unit, (str(code) if code else None)


@dataclass(frozen=True)
class Amount:
    """A figure as a number a person can read: in units, with what it is a number of."""

    number: float
    """The value at scale 1 - the one multiplication, made by `_moved`."""
    unit: str
    currency: str | None
    """The ISO code when the unit is currency and the figure carries one; else None."""
    ref: str

    def __str__(self) -> str:
        word = self.currency if self.unit == "currency" and self.currency else self.unit
        return f"{self.number:,.0f} {word}"


def expect_unit(
    figure: Mapping[str, Any] | float | int,
    ref: str,
    *,
    unit: str,
    currency: str | None = None,
    destination: str,
) -> None:
    """Refuse a figure that is not what the caller's destination is a number of.

    No arithmetic, so the writer may ask it: `deliver/builder.py` is bracketed by the
    Numeric Integrity Lock and has to stay arithmetic-free. `destination` is what the
    caller wanted, as a clause - *every input of this template is USD at scale 1000* -
    because the sentence has to say both what the figure is and what it was going into.
    """
    have, code = _unit_of(figure)
    if have != unit:
        value = float(figure["value"] if isinstance(figure, Mapping) else figure)
        scale = figure.get("scale", BARE_NUMBERS_ARE_AT) if isinstance(figure, Mapping) else 1
        shown = f"{value:,.0f}" if value == int(value) else f"{value:,}"
        raise RegistryError(
            diagnose(
                WRITE_FAILED,
                f"{ref}: the figure is {_describe(have)} ({shown} at scale {scale}) "
                f"and {destination}; what a figure is a number of is not restated away",
                locator=ref,
            )
        )
    if unit == "currency" and currency is not None and code is not None and code != currency:
        raise RegistryError(
            diagnose(
                WRITE_FAILED,
                f"{ref}: the figure is in {code} and {destination}",
                locator=ref,
            )
        )


def amount_of(
    figure: Mapping[str, Any] | float | int,
    ref: str,
    *,
    unit: str | None = None,
    currency: str | None = None,
    destination: str = "",
) -> Amount:
    """The figure in units, with what it is a number of.

    With `unit` given it is also a refusal: the materiality test and the officer total
    want money in the benchmark's currency and nothing else. With `unit` left out it takes
    anything, which is what a narrative that prints a count as a count wants.
    """
    if unit is not None:
        expect_unit(
            figure,
            ref,
            unit=unit,
            currency=currency,
            destination=destination or f"this is a number of {_describe(unit)}",
        )
    have, code = _unit_of(figure)
    if isinstance(figure, Mapping):
        value = float(figure["value"])
        scale = int(figure.get("scale", BARE_NUMBERS_ARE_AT))
    else:
        value, scale = float(figure), BARE_NUMBERS_ARE_AT
    return Amount(number=_moved(value, scale, 1, ref), unit=have, currency=code, ref=ref)


@dataclass(frozen=True)
class Left:
    """A figure the restatement left as it came, because a template's scale is a currency
    scale and the figure is not money."""

    figure_ref: str
    unit: str
    why: str

    def as_row(self) -> dict[str, Any]:
        return {"figure_ref": self.figure_ref, "unit": self.unit, "why": self.why}


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
) -> tuple[
    dict[str, Mapping[str, Any] | float | int],
    tuple[Restatement, ...],
    tuple[Left, ...],
]:
    """Every currency figure at the scale the template declares, what had to move to get
    there, and every other figure as it came.

    A figure already at that scale is returned as it came and is not in the second part of
    the tuple - there is nothing to record about a number nobody touched. A figure that is
    not money is returned as it came too, and **is** recorded, in the third part: a count
    of shares at scale 1 is a count of shares, and dividing it by a thousand to fit a
    template in thousands made it 135,361 and listed the division as a restatement. The
    catalogue holds every row of the table and most rows are bound to nothing, so this is
    not where to refuse - the writer refuses a cell bound to one, with the unit in the
    sentence, and that refusal is reachable now because nothing rewrites the scale first.
    """
    out: dict[str, Mapping[str, Any] | float | int] = {}
    moves: list[Restatement] = []
    left: list[Left] = []
    for ref, figure in figures.items():
        unit, _ = _unit_of(figure)
        if unit != "currency":
            out[ref] = figure
            left.append(
                Left(
                    ref,
                    unit,
                    f"{_describe(unit)} is not restated to a currency scale; a cell bound "
                    f"to it is refused by the writer",
                )
            )
            continue
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
    return out, tuple(moves), tuple(left)
