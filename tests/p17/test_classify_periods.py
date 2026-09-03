"""The classifier's closed set with "other", and the period detector's honest ambiguity."""

from __future__ import annotations

import pytest

from intake.readers.classify import CLASSES, Evidence, classify
from intake.readers.periods import detect_periods
from registries.contracts import ContractRegistry


def test_the_classes_are_the_registrys_intake_types_plus_the_blueprints_extras(
    contracts: ContractRegistry,
) -> None:
    registry = {t.id for t in contracts.intake_document_types()}
    assert registry <= set(CLASSES)
    assert set(CLASSES) - registry == {"gl_detail", "cap_table", "other"}


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        (
            Evidence("TB_FY25.xlsx", ["Account", "Debit", "Credit"], [], ["TB_FY25"]),
            "trial_balance",
        ),
        (
            Evidence(
                "FY25 financials.pdf", ["Henderson - Income Statement", "Revenue", "Net income"]
            ),
            "financial_statements",
        ),
        (
            Evidence(
                "Balance sheet 12-31-25.pdf", ["Statement of financial position", "Total assets"]
            ),
            "financial_statements",
        ),
        (Evidence("Response.docx", ["Due diligence response - round 2"]), "ddr_response"),
        (
            Evidence("census.xlsx", ["Participant", "Date of birth", "Hours"], [], ["Census 2025"]),
            "participant_census",
        ),
        (Evidence("return.pdf", ["Form 1120", "U.S. Corporation Income Tax Return"]), "tax_return"),
        (Evidence("GL.xlsx", ["General ledger detail", "Posting date", "Journal"]), "gl_detail"),
        (
            Evidence("owners.xlsx", ["Capitalization table", "Shares outstanding", "Shareholder"]),
            "cap_table",
        ),
    ],
)
def test_recognisable_documents_classify(evidence: Evidence, expected: str) -> None:
    result = classify(evidence)
    assert result.document_type == expected, result
    assert result.confidence >= 0.8 and result.reasons


def test_other_is_a_first_class_answer_that_routes_to_a_person() -> None:
    result = classify(Evidence("Schedule_C_final(2).pdf", ["Schedule C", "Attachment"]))
    assert result.document_type == "other" and result.review_required
    assert result.confidence == 0.0


def test_a_tie_is_other_rather_than_a_coin_toss() -> None:
    both = Evidence("mixed.pdf", ["Trial balance", "Income statement"])
    result = classify(both)
    assert result.document_type == "other"
    assert "scores" in result.reasons[0] or "but" in result.reasons[0]


# ----------------------------------------------------------------- periods


def test_thousands_stated_is_read_once_and_settled() -> None:
    found = detect_periods("Trial Balance ($ in thousands) FY2025 year ended December 31, 2025 USD")
    assert found.scale == 1000 and found.currency == "USD"
    assert found.period_type == "annual" and found.period_ends == ("2025-12-31",)
    assert found.fiscal_year_end_month == 12
    assert found.settled


def test_scale_ambiguity_is_reported_and_never_assumed() -> None:
    """The exit criterion. No cue: scale is None and says so. Conflicting cues: the
    same. Nothing here ever fills in 1 or 1000."""
    nothing = detect_periods("Trial Balance FY2025 Account Debit Credit")
    assert nothing.scale is None
    assert any(a.startswith("scale: no cue") for a in nothing.ambiguous)

    conflicting = detect_periods("Revenue (in thousands) ... Total assets (in millions)")
    assert conflicting.scale is None
    assert any(a.startswith("scale: conflicting") for a in conflicting.ambiguous)

    units = detect_periods("Amounts in whole dollars FY2025")
    assert units.scale == 1 and not any(a.startswith("scale") for a in units.ambiguous)


def test_monthly_columns_give_twelve_period_ends() -> None:
    header = "Account " + " ".join(
        f"{m}-25"
        for m in [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
    )
    found = detect_periods(header + " ($000s)")
    assert found.period_type == "monthly"
    assert len(found.period_ends) == 12 and found.period_ends[1] == "2025-02-28"
    assert found.scale == 1000


def test_quarters_and_years_together_are_ambiguous() -> None:
    found = detect_periods("Q1 2025 Q2 2025 FY2024 ($ in thousands) USD")
    assert found.period_type is None
    assert any(a.startswith("period_type") for a in found.ambiguous)


def test_currency_is_never_guessed_between_two() -> None:
    found = detect_periods("Revenue USD 1,200 CAD 1,600 (in thousands)")
    assert found.currency is None
    assert any(a.startswith("currency") for a in found.ambiguous)
    assert detect_periods("no money words here").currency is None


def test_a_bare_dollar_sign_is_usd_but_the_cue_says_so() -> None:
    found = detect_periods("Balance sheet $ in thousands 12/31/2025")
    assert found.currency == "USD" and "no code stated" in found.cues["currency"][0]
    assert found.period_ends == ("2025-12-31",)
