"""The Token & Cost Meter: what every model call cost, from the usage the API reported.

Derived, never estimated. The API returns token counts with each response; the meter
prices them against the pinned rate table and writes the charge to the run. Tier choices
on the map are cost decisions, and this is where they get checked against reality.

The exit criterion is that the meter agrees with the usage the API reports. It does
because it has no other input: there is no estimate here to disagree with.
"""

from __future__ import annotations

from dataclasses import dataclass

from ops.run_store import RunRecord, RunStore
from ports.llm import (
    CACHE_READ_MULTIPLIER,
    CACHE_WRITE_MULTIPLIER,
    RATES_USD_PER_MTOK,
    ModelPin,
    Usage,
)
from registries.errors import MODEL_PIN_UNAVAILABLE, RegistryError, diagnose

__all__ = ["Charge", "CostMeter", "Spend", "price"]


@dataclass(frozen=True)
class Charge:
    """One call's cost."""

    model: str
    usd: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class Spend:
    """A run's position against its ceilings, in the ceilings' own units."""

    run_id: str
    usd: float
    model_calls: int
    input_tokens: int
    output_tokens: int
    active_seconds: float
    loop_iterations: int

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def price(model: str, usage: Usage) -> Charge:
    """USD for one call, from the rate table. Unknown model, no price - and no guess."""
    if model not in RATES_USD_PER_MTOK:
        raise RegistryError(
            diagnose(
                MODEL_PIN_UNAVAILABLE,
                f"{model!r} has no entry in the rate table, so its cost cannot be metered. "
                f"A run that cannot say what it spent cannot be budgeted.",
                locator=model,
            )
        )
    per_input, per_output = RATES_USD_PER_MTOK[model]
    usd = (
        usage.input_tokens * per_input
        + usage.output_tokens * per_output
        + usage.cache_read_input_tokens * per_input * CACHE_READ_MULTIPLIER
        + usage.cache_creation_input_tokens * per_input * CACHE_WRITE_MULTIPLIER
    ) / 1_000_000
    return Charge(
        model=model,
        usd=round(usd, 6),
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_input_tokens,
        cache_write_tokens=usage.cache_creation_input_tokens,
    )


class CostMeter:
    """Writes each charge to the run and reads the total back."""

    def __init__(self, store: RunStore) -> None:
        self.store = store

    def record(self, run_id: str, pin: ModelPin, usage: Usage) -> Charge:
        charge = price(pin.model, usage)
        self.store.record_model_call(
            run_id,
            charge.usd,
            input_tokens=charge.input_tokens + charge.cache_read_tokens + charge.cache_write_tokens,
            output_tokens=charge.output_tokens,
        )
        return charge

    def spend(self, run_id: str) -> Spend:
        run = self.store.run(run_id)
        return _spend_of(run, self._loop_iterations(run_id))

    def _loop_iterations(self, run_id: str) -> int:
        """Every iteration of every loop, as the event stream recorded them. The Loop
        Controller (P14) emits them; counting from the record rather than a counter means
        the governor and the manifest cannot disagree."""
        return sum(1 for e in self.store.events(run_id) if e.level == "loop")


def _spend_of(run: RunRecord, loop_iterations: int) -> Spend:
    return Spend(
        run_id=run.run_id,
        usd=run.cost_usd,
        model_calls=run.model_calls,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        active_seconds=run.active_seconds,
        loop_iterations=loop_iterations,
    )
