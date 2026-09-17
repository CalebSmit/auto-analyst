"""P38: a forecast never enters the historical table, even when it is in a run's file set.

Classification labels a forecast; this is the half that acts on the label. It is done in
the procedure's code, not left to the model reading a `document_type` field in its payload.
"""

from __future__ import annotations

import json

from harness.procedures.timing_normalization import (
    NOT_HISTORICAL,
    SourceFile,
    TimingInputs,
    TimingNormalization,
    historical,
)


def source(name: str, document_type: str, label: str = "Revenue") -> SourceFile:
    return SourceFile(
        source_id=f"sha256:{name}",
        filename=name,
        document_type=document_type,
        blocks={"IS!B2:B3": [{"label": label, "value": 100.0, "raw": "100", "ordinal": 2}]},
        scale=1,
        currency="USD",
        period_type="annual",
        period_ends=("2025-12-31",),
    )


HISTORY = source("FY25 financial statements.xlsx", "financial_statements")
FORECAST = source("Forecast 2026-2030.xlsx", "forecast", label="Projected revenue")


def test_the_forecast_is_not_in_what_the_model_is_shown() -> None:
    payload = json.loads(TimingNormalization().payload(TimingInputs((HISTORY, FORECAST))))
    assert [f["filename"] for f in payload["files"]] == [HISTORY.filename]
    assert "Projected revenue" not in json.dumps(payload)


def test_the_forecast_is_not_in_what_the_tool_is_given() -> None:
    seen: dict = {}

    class Tools(dict):
        engagement_id = "E-1"

    def normalizer(**kwargs: object) -> object:
        seen.update(kwargs)

        class Result:
            value = {"output": {}}

        return Result()

    TimingNormalization().apply(
        {}, Tools(timing_normalizer=normalizer), TimingInputs((HISTORY, FORECAST)), "pin"
    )  # type: ignore[arg-type]
    assert list(seen["sources"]) == [HISTORY.source_id]
    assert list(seen["files"]) == [HISTORY.source_id]


def test_forecasts_alone_escalate_rather_than_becoming_a_history() -> None:
    reason = TimingNormalization().escalate(TimingInputs((FORECAST,)))
    assert reason is not None and "only forecasts" in reason
    assert TimingNormalization().escalate(TimingInputs((HISTORY, FORECAST))) is None


def test_a_forecast_with_an_unsettled_scale_does_not_stop_the_history() -> None:
    """A forecast is not read into the table, so its ambiguities are not the table's."""
    vague = SourceFile(**{**FORECAST.__dict__, "scale": None, "ambiguous": ("scale: unknown",)})
    assert TimingNormalization().escalate(TimingInputs((HISTORY, vague))) is None


def test_only_forecast_is_held_out_today() -> None:
    assert {"forecast"} == NOT_HISTORICAL
    assert historical(TimingInputs((HISTORY,))) == (HISTORY,)
