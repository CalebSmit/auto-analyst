"""The Token & Cost Meter: what every model call cost, from the usage the API reported.

Derived, never estimated. The API returns token counts with each response; the meter
prices them against the pinned rate table and writes the charge to the run. Tier choices
on the map are cost decisions, and this is where they get checked against reality.

The exit criterion is that the meter agrees with the usage the API reports. It does
because it has no other input: there is no estimate here to disagree with.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ops.run_store import RunRecord, RunStore
from ports.llm import (
    CACHE_READ_MULTIPLIER,
    CACHE_WRITE_MULTIPLIER,
    RATES_USD_PER_MTOK,
    TIER_MODELS,
    ModelPin,
    Usage,
)
from registries.errors import MODEL_PIN_UNAVAILABLE, RegistryError, diagnose

__all__ = ["Breakdown", "Charge", "CostMeter", "EngagementSpend", "Line", "Spend", "price"]

TIER_OF: dict[str, str] = {model: tier for tier, model in TIER_MODELS.items()}


@dataclass(frozen=True)
class Line:
    """Spend along one axis: a skill, a model, a tier, a run."""

    key: str
    usd: float
    calls: int
    input_tokens: int
    output_tokens: int

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "usd": round(self.usd, 6),
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


@dataclass(frozen=True)
class Breakdown:
    """One run's spend by skill, by model and by tier, from `model.answered` events.

    Tier choices on the map are cost decisions, and this is where they get checked
    against reality: "does the classifier need to be mid tier" is a question with a
    number attached once a run has been metered.
    """

    run_id: str
    by_skill: tuple[Line, ...]
    by_model: tuple[Line, ...]
    by_tier: tuple[Line, ...]
    total_usd: float
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def cache_hit_rate(self) -> float | None:
        """Of the tokens that could have been cached, the share that was read rather than
        written. `None` when nothing was cacheable at all, which is a different answer from
        zero and reads differently to whoever is asking whether this is working."""
        offered = self.cache_read_tokens + self.cache_write_tokens
        return round(self.cache_read_tokens / offered, 4) if offered else None

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "total_usd": round(self.total_usd, 6),
            "by_skill": [line.as_dict() for line in self.by_skill],
            "by_model": [line.as_dict() for line in self.by_model],
            "by_tier": [line.as_dict() for line in self.by_tier],
        }


@dataclass(frozen=True)
class EngagementSpend:
    engagement_id: str
    runs: tuple[Line, ...]
    by_skill: tuple[Line, ...]
    by_tier: tuple[Line, ...]
    total_usd: float

    def as_dict(self) -> dict[str, object]:
        return {
            "engagement_id": self.engagement_id,
            "total_usd": round(self.total_usd, 6),
            "runs": [line.as_dict() for line in self.runs],
            "by_skill": [line.as_dict() for line in self.by_skill],
            "by_tier": [line.as_dict() for line in self.by_tier],
        }


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

    def breakdown(self, run_id: str) -> Breakdown:
        """By skill, by model, by tier - from every `model.answered` event on the run.
        The step's skill comes from the step table; the model from the event; the tier
        from the pin table, so a model no tier resolves to is reported as `unpinned`."""
        skill_of = {s.step_id: s.skill or "(no skill)" for s in self.store.steps(run_id)}
        by_skill: dict[str, list[float | int]] = {}
        by_model: dict[str, list[float | int]] = {}
        by_tier: dict[str, list[float | int]] = {}

        def add(bucket: dict[str, list[float | int]], key: str, e: Any) -> None:
            row = bucket.setdefault(key, [0.0, 0, 0, 0])
            row[0] += float(e.cost_usd or 0.0)
            row[1] += 1
            row[2] += int(e.payload.get("input_tokens", 0))
            row[3] += int(e.payload.get("output_tokens", 0))

        total = 0.0
        read = written = 0
        for e in self.store.events(run_id):
            if e.type != "model.answered":
                continue
            model = str(e.payload.get("model", "unknown"))
            add(by_skill, skill_of.get(e.step_id or "", "(no step)"), e)
            add(by_model, model, e)
            add(by_tier, TIER_OF.get(model, "unpinned"), e)
            total += float(e.cost_usd or 0.0)
            read += int(e.payload.get("cache_read_tokens", 0))
            written += int(e.payload.get("cache_write_tokens", 0))
        return Breakdown(
            run_id=run_id,
            by_skill=_lines(by_skill),
            by_model=_lines(by_model),
            by_tier=_lines(by_tier),
            total_usd=round(total, 6),
            cache_read_tokens=read,
            cache_write_tokens=written,
        )

    def rollup(self, engagement_id: str) -> EngagementSpend:
        """Every run on the engagement, and the same axes summed across them."""
        runs: list[Line] = []
        by_skill: dict[str, list[float | int]] = {}
        by_tier: dict[str, list[float | int]] = {}
        total = 0.0
        for run in self.store.runs(engagement_id):
            b = self.breakdown(run.run_id)
            runs.append(
                Line(run.run_id, b.total_usd, run.model_calls, run.input_tokens, run.output_tokens)
            )
            for bucket, lines in ((by_skill, b.by_skill), (by_tier, b.by_tier)):
                for line in lines:
                    row = bucket.setdefault(line.key, [0.0, 0, 0, 0])
                    row[0] += line.usd
                    row[1] += line.calls
                    row[2] += line.input_tokens
                    row[3] += line.output_tokens
            total += b.total_usd
        return EngagementSpend(
            engagement_id=engagement_id,
            runs=tuple(runs),
            by_skill=_lines(by_skill),
            by_tier=_lines(by_tier),
            total_usd=round(total, 6),
        )

    def _loop_iterations(self, run_id: str) -> int:
        """Every iteration of every loop, as the event stream recorded them. The Loop
        Controller (P14) emits them; counting from the record rather than a counter means
        the governor and the manifest cannot disagree."""
        return sum(1 for e in self.store.events(run_id) if e.level == "loop")


def _lines(bucket: dict[str, list[float | int]]) -> tuple[Line, ...]:
    return tuple(
        Line(key, round(float(row[0]), 6), int(row[1]), int(row[2]), int(row[3]))
        for key, row in sorted(bucket.items(), key=lambda kv: (-kv[1][0], kv[0]))
    )


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
