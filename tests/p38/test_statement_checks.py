"""P38: the analyst's model checks, as deterministic code.

Checked against a small, hand-built company whose statements tie, and then against the ways
they fail in practice. Every failure must carry both numbers; every absence must be
`could_not_evaluate`, never a pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from registries.contracts import ContractRegistry
from registries.taxonomy import load_taxonomy
from tools.statement_checks import (
    DIRECTION,
    Line,
    Stated,
    balance_sheet_balances,
    cash_agrees,
    movements,
    net_income_ties,
    readiness,
    run_checks,
)

ROOT = Path(__file__).resolve().parents[2]
TAXONOMY = load_taxonomy("coa-taxonomy@1.0.0")
FY24, FY25 = "2024-12-31", "2025-12-31"


def company() -> list[Line]:
    """Two years that tie. FY25: revenue 1,000 less returns 20, COGS 600, wages 200,
    interest 30, a loss on disposal of 10, tax 40 -> net income 100. Balance sheet: cash 150,
    receivables 250 less allowance 10, PP&E 500 less accumulated depreciation (presented
    negative) 200 -> assets 690; payables 90, long-term debt 300, equity 300 -> 690."""
    return [
        Line("revenue", {FY24: 900.0, FY25: 1000.0}, "IS!B2", "Revenue"),
        Line("contra_revenue", {FY24: 15.0, FY25: 20.0}, "IS!B3", "Returns"),
        Line("cost_of_sales", {FY24: 540.0, FY25: 600.0}, "IS!B4", "COGS"),
        Line("salaries_wages", {FY24: 190.0, FY25: 200.0}, "IS!B5", "Wages"),
        Line("interest_expense", {FY24: 35.0, FY25: 30.0}, "IS!B6", "Interest"),
        Line("gain_loss_on_disposal", {FY24: 5.0, FY25: -10.0}, "IS!B7", "Gain (loss)"),
        Line("income_tax", {FY24: 25.0, FY25: 40.0}, "IS!B8", "Tax"),
        Line("cash", {FY24: 120.0, FY25: 150.0}, "BS!B2", "Cash"),
        Line("accounts_receivable", {FY24: 240.0, FY25: 250.0}, "BS!B3", "AR"),
        Line("allowance_doubtful", {FY24: 10.0, FY25: 10.0}, "BS!B4", "Allowance"),
        Line("ppe", {FY24: 480.0, FY25: 500.0}, "BS!B5", "PP&E"),
        Line("accumulated_depreciation", {FY24: -160.0, FY25: -200.0}, "BS!B6", "Acc dep"),
        Line("accounts_payable", {FY24: 85.0, FY25: 90.0}, "BS!B7", "AP"),
        Line("long_term_debt", {FY24: 325.0, FY25: 300.0}, "BS!B8", "Term loan"),
        Line("equity", {FY24: 260.0, FY25: 300.0}, "BS!B9", "Equity"),
    ]


NET_INCOME = {FY24: Stated(100.0, "IS!B10"), FY25: Stated(100.0, "IS!B10")}
ENDING_CASH = {FY24: Stated(120.0, "CF!B20"), FY25: Stated(150.0, "CF!B20")}


def by_result(findings: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in findings:
        out.setdefault(f["result"], []).append(f["check"])
    return out


# ------------------------------------------------------------------ it ties


def test_a_company_that_ties_passes_every_check() -> None:
    findings = run_checks(
        company(),
        TAXONOMY,
        tolerance=0.5,
        stated_net_income=NET_INCOME,
        stated_ending_cash=ENDING_CASH,
    )
    assert [f["result"] for f in findings] == ["pass"] * 6
    assert readiness(findings) == "no_automated_issues_found"


def test_the_findings_make_a_valid_qc_tieout_output() -> None:
    """Checked through the repo's own contract registry, as the whole output the qc-tieout
    procedure would return - not one item against a copied schema."""
    findings = run_checks(
        company(),
        TAXONOMY,
        tolerance=0.5,
        stated_net_income={FY25: Stated(90.0, "IS!B10")},
        movement_threshold=0.25,
    )
    output = {
        "schema_version": "skills/qc-tieout@1.0.0",
        "produced_by": "qc-tieout@0.1.0",
        "qc_findings": findings,
        "readiness": readiness(findings),
    }
    assert ContractRegistry.load().check("skills/qc-tieout@1.0.0", output) == ()
    assert {f["result"] for f in findings} >= {"fail", "could_not_evaluate"}


def test_every_category_in_the_taxonomy_has_a_declared_direction() -> None:
    """A new category with no direction would make every check could_not_evaluate - loud,
    but better caught here, when the taxonomy changes, than on a client's run."""
    missing = [
        c for c, cat in TAXONOMY.categories.items() if cat.statement != "NA" and c not in DIRECTION
    ]
    assert missing == []


# ------------------------------------------------------------ it does not tie


def test_a_failure_carries_both_numbers_and_the_difference() -> None:
    findings = net_income_ties(company(), TAXONOMY, {FY25: Stated(112.0, "IS!B10")}, 0.5)
    fy25 = next(f for f in findings if FY25 in f["check"])
    assert fy25["result"] == "fail"
    assert "computed 100.00" in fy25["evidence"]
    assert "client states 112.00 at IS!B10" in fy25["evidence"]
    assert "difference 12.00" in fy25["evidence"]
    assert fy25["locator"] == "IS!B10"


def test_an_unbalanced_balance_sheet_fails_and_mentions_a_pre_close_trial_balance() -> None:
    lines = [
        ln if ln.category != "equity" else Line("equity", {FY25: 200.0}, "BS!B9")
        for ln in company()
    ]
    findings = balance_sheet_balances(lines, TAXONOMY, 0.5)
    fy25 = next(f for f in findings if FY25 in f["check"])
    assert fy25["result"] == "fail"
    assert "difference 100.00" in fy25["evidence"]
    assert "pre-close trial balance" in fy25["evidence"]


def test_a_signed_ledger_export_is_named_as_the_likely_cause() -> None:
    lines = [
        Line(ln.category, {k: -v for k, v in ln.amounts.items()}, ln.locator)
        if ln.category in ("cost_of_sales", "salaries_wages")
        else ln
        for ln in company()
    ]
    findings = net_income_ties(lines, TAXONOMY, NET_INCOME, 0.5)
    assert all(f["result"] == "fail" for f in findings)
    assert all("signed ledger export" in f["evidence"] for f in findings)


def test_cash_that_disagrees_fails() -> None:
    findings = cash_agrees(company(), {FY25: Stated(170.0, "CF!B20")}, 0.5)
    fy25 = next(f for f in findings if FY25 in f["check"])
    assert fy25["result"] == "fail" and "restricted cash" in fy25["evidence"]


# ------------------------------------------------------------- it cannot tell


def test_no_stated_figure_is_never_a_pass() -> None:
    findings = run_checks(company(), TAXONOMY, tolerance=0.5)
    results = by_result(findings)
    assert len(results["could_not_evaluate"]) == 4  # net income and cash, both years
    assert readiness(findings) == "items_outstanding"


def test_an_unmapped_line_blocks_its_period_rather_than_vanishing() -> None:
    lines = [*company(), Line("unmapped", {FY25: 45.0}, "IS!B9", "Misc")]
    findings = net_income_ties(lines, TAXONOMY, NET_INCOME, 0.5)
    fy25 = next(f for f in findings if FY25 in f["check"])
    fy24 = next(f for f in findings if FY24 in f["check"])
    assert fy25["result"] == "could_not_evaluate" and "unmapped" in fy25["evidence"]
    assert fy24["result"] == "pass", "a blocker in one period does not spoil the others"


def test_a_category_the_taxonomy_does_not_have_is_named() -> None:
    lines = [*company(), Line("crypto_holdings", {FY25: 5.0}, "BS!B10")]
    findings = balance_sheet_balances(lines, TAXONOMY, 0.5)
    fy25 = next(f for f in findings if FY25 in f["check"])
    assert fy25["result"] == "could_not_evaluate"
    assert "crypto_holdings" in fy25["evidence"]


def test_half_a_balance_sheet_is_not_a_balance_sheet() -> None:
    assets_only = [ln for ln in company() if ln.category in ("cash", "ppe")]
    findings = balance_sheet_balances(assets_only, TAXONOMY, 0.5)
    assert {f["result"] for f in findings} == {"could_not_evaluate"}


def test_a_stated_figure_with_no_lines_is_not_a_comparison() -> None:
    findings = net_income_ties([], TAXONOMY, {FY25: Stated(100.0, "IS!B10")}, 0.5)
    assert findings[0]["result"] == "could_not_evaluate"


# ------------------------------------------------------------------ movements


def test_movements_flag_large_changes_and_honour_explanations() -> None:
    lines = company()
    flagged = movements(lines, 0.25)
    names = {f["check"] for f in flagged}
    assert "movement: Gain (loss) 2024-12-31 to 2025-12-31" in names  # 5 -> -10
    assert "movement: Tax 2024-12-31 to 2025-12-31" in names  # 25 -> 40, +60%
    assert "movement: Revenue 2024-12-31 to 2025-12-31" not in names  # +11%

    quiet = movements(
        lines, 0.25, explained={("IS!B7", FY25): "sold a truck", ("IS!B8", FY25): "rate"}
    )
    assert all(f["check"] != "movement: Tax 2024-12-31 to 2025-12-31" for f in quiet)


def test_a_line_appearing_from_zero_is_flagged() -> None:
    flagged = movements([Line("rent", {FY24: 0.0, FY25: 50.0}, "IS!B11", "Rent")], 0.25)
    assert flagged[0]["result"] == "fail" and "from zero" in flagged[0]["evidence"]


def test_nothing_moving_is_a_recorded_pass() -> None:
    findings = movements([Line("rent", {FY24: 50.0, FY25: 51.0}, "IS!B11")], 0.25)
    assert [f["result"] for f in findings] == ["pass"]


@pytest.mark.parametrize("threshold", [0.0, -0.1])
def test_there_is_no_default_threshold(threshold: float) -> None:
    with pytest.raises(ValueError, match="no default"):
        movements(company(), threshold)


def test_a_negative_tolerance_is_refused() -> None:
    with pytest.raises(ValueError, match="tolerance"):
        run_checks(company(), TAXONOMY, tolerance=-1)


def test_readiness_can_never_say_approved() -> None:
    assert readiness([]) == "no_automated_issues_found"
    assert readiness([{"result": "not_applicable"}]) == "no_automated_issues_found"
    assert readiness([{"result": "fail"}]) == "items_outstanding"
