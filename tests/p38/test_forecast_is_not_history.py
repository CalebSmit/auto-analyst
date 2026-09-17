"""P38: a client forecast is its own document type, never historical financial statements.

The finding: a forecast workbook ("Income Statement Forecast", "Projected P&L") scored on
every statement cue and was bound as `financial_statements` with confidence 1.0 and no
review. The pilot recipe waits for historicals and nothing else, so a forecast arriving
first could release a run on projected years. The analyst's own rule (session
2026-09-16-1) is that historicals gate everything; the research's is that provenance comes
first. Both say this must not happen.
"""

from __future__ import annotations

import pytest

from intake.readers.classify import CLASSES, Evidence, classify
from registries.contracts import ContractRegistry


@pytest.mark.parametrize(
    ("filename", "sheets", "headers"),
    [
        (
            "Client Forecast 2026-2030.xlsx",
            ["Income Statement Forecast"],
            ["FY2026E", "FY2027E", "Revenue", "Net income"],
        ),
        ("Projections.xlsx", ["Projected P&L", "Balance Sheet"], ["2026", "Revenue", "EBITDA"]),
        ("Mgmt model.xlsx", ["Pro forma"], ["Income statement", "Total assets", "2027E"]),
    ],
)
def test_a_forecast_shaped_like_statements_is_a_forecast(
    filename: str, sheets: list[str], headers: list[str]
) -> None:
    found = classify(Evidence(filename, headers=headers, sheet_names=sheets))
    assert found.document_type == "forecast"
    assert any("outranks the statement cues" in r for r in found.reasons)


@pytest.mark.parametrize(
    ("filename", "headers"),
    [
        ("FY2024 Financial Statements.pdf", ["Income Statement", "Balance Sheet", "Net income"]),
        ("2025 P&L and balance sheet.xlsx", ["Statement of operations", "Total assets"]),
    ],
)
def test_historical_statements_are_still_historical(filename: str, headers: list[str]) -> None:
    assert classify(Evidence(filename, headers=headers)).document_type == "financial_statements"


def test_a_budget_alone_is_tentative_and_goes_to_a_person() -> None:
    found = classify(Evidence("Budget FY26.xlsx", headers=["Revenue", "Net income"]))
    assert found.document_type == "forecast"
    assert found.review_required


def test_forecast_is_in_the_closed_vocabulary_and_required_by_nothing_yet() -> None:
    assert "forecast" in CLASSES
    declared = ContractRegistry.load().intake_document_type("forecast")
    assert declared.supplied_by == "client"
    assert declared.required_by == ()


def test_a_forecast_cannot_satisfy_the_pilot_waiting_for_historicals() -> None:
    import yaml

    from tests.p37.test_interview import ROOT

    recipe = yaml.safe_load(
        (ROOT / "recipes" / "mature-company-valuation.yaml").read_text(encoding="utf-8")
    )
    forecast = classify(
        Evidence("Forecast.xlsx", headers=["Income statement", "2026E"], sheet_names=["IS"])
    )
    assert forecast.document_type not in recipe["intake"]["required_types"]
