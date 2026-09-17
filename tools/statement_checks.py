"""Statement checks: the analyst's model checks, as deterministic code.

The first /improve-agent session named three checks a model must pass before review, and
named getting them to pass as one of the slow parts of the job:

1. net income in the model ties to the client's stated net income;
2. the balance sheet balances;
3. ending cash on the cash flow statement equals cash on the balance sheet.

The research on AI in valuation practice that followed (docs/research/ai-in-valuation.md)
said the same thing from outside: the defensible pattern is extraction with provenance
first, then **code** for the numbers, and a check that fails is **preserved as a finding
with both numbers**, never smoothed into one. That is what this module does.

Every total is taken through `tools.recompute`, so the arithmetic here is the same
arithmetic a skill can cause and a guard re-derives - there is no second adder. Output is
the `qc_findings` item shape of `skills/qc-tieout@1.0.0`, so the qc-tieout procedure (backlog
B-004) wires this in rather than rewriting it.

What it will not do is guess:

- A category this module has no direction for - a new taxonomy version, say - makes the
  check `could_not_evaluate` and names the category. Deciding whether a line adds or
  subtracts is a decision, and it gets made here once, in `DIRECTION`, by a person.
- An `unmapped` line with an amount in the period makes that period `could_not_evaluate`:
  a total over lines nobody has categorised is not a total.
- No stated figure to compare against is `could_not_evaluate`, never a pass. Absence of
  evidence is the commonest way a checklist lies.
- Tolerance and the movement threshold have no defaults. Materiality belongs to the
  practice (BUILD/OPEN.md section 2); the caller passes the run's.

Amounts are as presented on the statement: expenses positive, contra lines either sign
(they always reduce their section, so their absolute value is taken). Lines whose normal
direction is fixed but which carry a negative amount are counted in the evidence, because a
signed ledger export read as presented is the likeliest cause of a false failure.

Pure Python. Not yet reachable by a skill: that needs it named in constraints.yaml and in
qc-tieout's tool list, which is a governance change, not an import.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from registries.taxonomy import UNMAPPED, Taxonomy
from tools.recompute import recompute

__all__ = [
    "DIRECTION",
    "Line",
    "Stated",
    "balance_sheet_balances",
    "cash_agrees",
    "movements",
    "net_income_ties",
    "readiness",
    "run_checks",
]

PLUS, MINUS, CONTRA, SIGNED = "plus", "minus", "contra", "signed"

# How each category of coa-taxonomy@1.0.0 enters its statement's total. Keyed by category,
# not by section, because the exceptions (contra lines, interest income, gains that may be
# losses) are exactly where a section rule would be silently wrong.
#
# Income statement: + adds to net income, - reduces it. Balance sheet: + is an asset (or a
# liability or equity, on its own side), contra reduces its side.
DIRECTION: dict[str, str] = {
    # income statement
    "revenue": PLUS,
    "contra_revenue": CONTRA,
    "cost_of_sales": MINUS,
    "officer_compensation": MINUS,
    "salaries_wages": MINUS,
    "payroll_taxes": MINUS,
    "employee_benefits": MINUS,
    "rent": MINUS,
    "utilities": MINUS,
    "repairs_maintenance": MINUS,
    "insurance": MINUS,
    "professional_fees": MINUS,
    "advertising_marketing": MINUS,
    "travel_entertainment": MINUS,
    "office_supplies": MINUS,
    "vehicle_expense": MINUS,
    "bad_debt": MINUS,
    "depreciation": MINUS,
    "amortization": MINUS,
    "other_operating_expense": MINUS,
    "interest_expense": MINUS,
    "interest_income": PLUS,
    "gain_loss_on_disposal": SIGNED,  # a gain positive, a loss negative, as presented
    "other_income_expense": SIGNED,
    "income_tax": MINUS,
    # balance sheet - assets
    "cash": PLUS,
    "accounts_receivable": PLUS,
    "allowance_doubtful": CONTRA,
    "inventory": PLUS,
    "prepaid_expenses": PLUS,
    "other_current_assets": PLUS,
    "related_party_receivable": PLUS,
    "investments": PLUS,
    "ppe": PLUS,
    "accumulated_depreciation": CONTRA,
    "intangibles": PLUS,
    "right_of_use_asset": PLUS,
    "other_noncurrent_assets": PLUS,
    # balance sheet - liabilities and equity
    "accounts_payable": PLUS,
    "accrued_liabilities": PLUS,
    "deferred_revenue": PLUS,
    "other_current_liabilities": PLUS,
    "line_of_credit": PLUS,
    "current_debt": PLUS,
    "lease_liability": PLUS,
    "long_term_debt": PLUS,
    "related_party_payable": PLUS,
    "other_noncurrent_liabilities": PLUS,
    "equity": SIGNED,  # an accumulated deficit is negative equity, as presented
}

ASSET_SECTIONS = frozenset({"current_assets", "noncurrent_assets"})
CLAIM_SECTIONS = frozenset(
    {"current_liabilities", "noncurrent_liabilities", "liabilities", "equity"}
)


@dataclass(frozen=True)
class Line:
    """One tagged line of the normalized historicals: its category, an amount per period
    end (as presented), and where it was read from."""

    category: str
    amounts: Mapping[str, float]
    locator: str
    label: str = ""


@dataclass(frozen=True)
class Stated:
    """A total the client stated, and where: net income on the income statement, ending
    cash on the cash flow statement."""

    value: float
    locator: str


@dataclass
class _Totals:
    plus: list[float] = field(default_factory=list)
    minus: list[float] = field(default_factory=list)
    negative_fixed: int = 0
    lines: int = 0

    def add(self, direction: str, amount: float) -> None:
        self.lines += 1
        if direction == CONTRA:
            self.minus.append(abs(amount))
        elif direction == MINUS:
            self.minus.append(amount)
            self.negative_fixed += amount < 0
        else:
            self.plus.append(amount)
            self.negative_fixed += direction == PLUS and amount < 0


def _finding(
    check: str,
    result: str,
    evidence: str,
    *,
    threshold: float | None = None,
    locator: str | None = None,
) -> dict[str, Any]:
    return {
        "check": check,
        "result": result,
        "evidence": evidence,
        "magnitude": None,
        "threshold": threshold,
        "locator": locator,
    }


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _statement(taxonomy: Taxonomy, category: str) -> str | None:
    """IS, BS or NA for a known category; None for one the taxonomy does not have."""
    found = taxonomy.get(category)
    return None if found is None else found.statement


def _on(lines: Sequence[Line], taxonomy: Taxonomy, statement: str) -> list[Line]:
    """The lines a statement's check must consider: its own, plus every line that cannot be
    placed (unmapped, or unknown to the taxonomy) - those block rather than vanish."""
    return [
        ln
        for ln in lines
        if ln.category == UNMAPPED or _statement(taxonomy, ln.category) in (statement, None)
    ]


def _periods(lines: Iterable[Line]) -> list[str]:
    return sorted({period for line in lines for period in line.amounts})


def _blockers(lines: Sequence[Line], taxonomy: Taxonomy, period: str) -> list[str]:
    """Why a period cannot be totalled: unmapped lines, or categories with no direction."""
    reasons = []
    unmapped = [ln for ln in lines if ln.category == UNMAPPED and period in ln.amounts]
    if unmapped:
        reasons.append(
            f"{len(unmapped)} unmapped line(s) carry an amount in {period} "
            f"(first at {unmapped[0].locator}); a person categorises them first"
        )
    unknown = sorted(
        {
            ln.category
            for ln in lines
            if ln.category != UNMAPPED
            and period in ln.amounts
            and (ln.category not in DIRECTION or taxonomy.get(ln.category) is None)
        }
    )
    if unknown:
        reasons.append(
            "no direction is declared for "
            + ", ".join(unknown)
            + " - add it to DIRECTION in tools/statement_checks.py deliberately"
        )
    return reasons


def _sign_note(totals: _Totals) -> str:
    if not totals.negative_fixed:
        return ""
    return (
        f" {totals.negative_fixed} line(s) whose normal direction is fixed carry a "
        "negative amount; if the source is a signed ledger export, conventions are mixed."
    )


# ---------------------------------------------------------------------- the checks


def net_income_ties(
    lines: Sequence[Line],
    taxonomy: Taxonomy,
    stated: Mapping[str, Stated],
    tolerance: float,
) -> list[dict[str, Any]]:
    """Net income computed from the tagged income statement, against the client's own."""
    check = "net income ties to the client's net income"
    income = _on(lines, taxonomy, "IS")
    findings = []
    for period in sorted(set(_periods(income)) | set(stated)):
        blockers = _blockers(income, taxonomy, period)
        if not any(period in ln.amounts and ln.category != UNMAPPED for ln in income):
            blockers.append(f"no tagged income statement lines for {period}")
        if blockers:
            findings.append(
                _finding(f"{check} ({period})", "could_not_evaluate", "; ".join(blockers))
            )
            continue
        if period not in stated:
            findings.append(
                _finding(
                    f"{check} ({period})",
                    "could_not_evaluate",
                    f"no client-stated net income for {period}; locate the net income line "
                    "on the client's statement",
                )
            )
            continue
        totals = _Totals()
        for ln in income:
            if period in ln.amounts:
                totals.add(DIRECTION[ln.category], ln.amounts[period])
        claim = stated[period]
        result = recompute("difference", [totals.plus, totals.minus], claim.value, tolerance)
        evidence = (
            f"computed {_money(result.recomputed)} from {totals.lines} tagged line(s); "
            f"client states {_money(claim.value)} at {claim.locator}; "
            f"difference {_money(result.delta)}."
        )
        if not result.matches:
            evidence += _sign_note(totals) + (
                " Common causes: a line tagged to the wrong statement, a total row tagged as a "
                "line, or a discontinued-operations line with no category."
            )
        findings.append(
            _finding(
                f"{check} ({period})",
                "pass" if result.matches else "fail",
                evidence,
                threshold=tolerance,
                locator=claim.locator,
            )
        )
    return findings


def balance_sheet_balances(
    lines: Sequence[Line], taxonomy: Taxonomy, tolerance: float
) -> list[dict[str, Any]]:
    """Assets against liabilities plus equity, per period."""
    check = "balance sheet balances"
    balance = _on(lines, taxonomy, "BS")
    findings = []
    for period in _periods(balance):
        blockers = _blockers(balance, taxonomy, period)
        if blockers:
            findings.append(
                _finding(f"{check} ({period})", "could_not_evaluate", "; ".join(blockers))
            )
            continue
        assets, claims = _Totals(), _Totals()
        unplaced = []
        for ln in balance:
            if period not in ln.amounts:
                continue
            found = taxonomy.get(ln.category)
            section = found.section if found else ""
            if section in ASSET_SECTIONS:
                assets.add(DIRECTION[ln.category], ln.amounts[period])
            elif section in CLAIM_SECTIONS:
                claims.add(DIRECTION[ln.category], ln.amounts[period])
            else:
                unplaced.append(section)
        if unplaced:
            findings.append(
                _finding(
                    f"{check} ({period})",
                    "could_not_evaluate",
                    "no side of the balance sheet is declared for section(s) "
                    + ", ".join(sorted(set(unplaced)))
                    + " - add them to ASSET_SECTIONS or CLAIM_SECTIONS deliberately",
                )
            )
            continue
        if not assets.lines or not claims.lines:
            findings.append(
                _finding(
                    f"{check} ({period})",
                    "could_not_evaluate",
                    f"{period} has {assets.lines} asset line(s) and {claims.lines} liability or "
                    "equity line(s); one side is missing, so this is not a whole balance sheet",
                )
            )
            continue
        total_assets = recompute("difference", [assets.plus, assets.minus], 0.0).recomputed
        result = recompute("difference", [claims.plus, claims.minus], total_assets, tolerance)
        evidence = (
            f"assets {_money(total_assets)} ({assets.lines} lines); liabilities and equity "
            f"{_money(result.recomputed)} ({claims.lines} lines); "
            f"difference {_money(result.delta)}."
        )
        if not result.matches:
            evidence += (
                _sign_note(assets)
                + _sign_note(claims)
                + (
                    " If this is a pre-close trial balance, current-period earnings may not be in "
                    "equity yet."
                )
            )
        findings.append(
            _finding(
                f"{check} ({period})",
                "pass" if result.matches else "fail",
                evidence,
                threshold=tolerance,
                locator=f"balance_sheet:{period}",
            )
        )
    return findings


def cash_agrees(
    lines: Sequence[Line],
    stated_ending_cash: Mapping[str, Stated],
    tolerance: float,
) -> list[dict[str, Any]]:
    """Balance sheet cash against ending cash on the client's cash flow statement."""
    check = "cash flow ending cash equals balance sheet cash"
    cash = [ln for ln in lines if ln.category == "cash"]
    findings = []
    for period in sorted(set(_periods(cash)) | set(stated_ending_cash)):
        in_period = [ln.amounts[period] for ln in cash if period in ln.amounts]
        if not in_period:
            findings.append(
                _finding(
                    f"{check} ({period})",
                    "could_not_evaluate",
                    f"no balance sheet cash line for {period}",
                )
            )
            continue
        if period not in stated_ending_cash:
            findings.append(
                _finding(
                    f"{check} ({period})",
                    "could_not_evaluate",
                    f"no cash flow statement ending cash for {period}; if the client sent no "
                    "cash flow statement, this check is not applicable to them",
                )
            )
            continue
        claim = stated_ending_cash[period]
        result = recompute("sum", [in_period], claim.value, tolerance)
        evidence = (
            f"balance sheet cash {_money(result.recomputed)} ({len(in_period)} line(s)); "
            f"cash flow ending cash {_money(claim.value)} at {claim.locator}; "
            f"difference {_money(result.delta)}."
        )
        if not result.matches:
            evidence += (
                " Common causes: restricted cash or cash equivalents shown separately, or an "
                "overdraft netted on one statement and not the other."
            )
        findings.append(
            _finding(
                f"{check} ({period})",
                "pass" if result.matches else "fail",
                evidence,
                threshold=tolerance,
                locator=claim.locator,
            )
        )
    return findings


def movements(
    lines: Sequence[Line],
    threshold: float,
    explained: Mapping[tuple[str, str], str] | None = None,
) -> list[dict[str, Any]]:
    """Period-over-period movements at or above `threshold` (0.25 is 25%) with no recorded
    explanation. The raw material for the "changes in financial condition" narrative a
    reviewer asks about - flagged by code, explained by a person."""
    if threshold <= 0:
        raise ValueError("a movement threshold is a positive fraction; there is no default")
    explained = explained or {}
    flagged = []
    for ln in lines:
        periods = sorted(ln.amounts)
        for before, after in zip(periods, periods[1:], strict=False):
            a, b = ln.amounts[before], ln.amounts[after]
            if a == 0 and b == 0:
                continue
            change = float("inf") if a == 0 else (b - a) / abs(a)
            if abs(change) < threshold:
                continue
            name = ln.label or ln.category
            if (ln.locator, after) in explained:
                continue
            size = "from zero" if a == 0 else f"{change:+.1%}"
            flagged.append(
                _finding(
                    f"movement: {name} {before} to {after}",
                    "fail",
                    f"{_money(a)} to {_money(b)} ({size}), at or above the {threshold:.0%} "
                    "threshold with no explanation recorded",
                    threshold=threshold,
                    locator=ln.locator,
                )
            )
    if not flagged:
        return [
            _finding(
                "movements above threshold",
                "pass",
                f"no line moved {threshold:.0%} or more between periods without an explanation",
                threshold=threshold,
            )
        ]
    return flagged


def run_checks(
    lines: Sequence[Line],
    taxonomy: Taxonomy,
    *,
    tolerance: float,
    stated_net_income: Mapping[str, Stated] | None = None,
    stated_ending_cash: Mapping[str, Stated] | None = None,
    movement_threshold: float | None = None,
    explained: Mapping[tuple[str, str], str] | None = None,
) -> list[dict[str, Any]]:
    """All of them, in the order the analyst named them. Movements only when a threshold is
    given, because the threshold is the practice's decision and has no default."""
    if tolerance < 0:
        raise ValueError("a tolerance is zero or positive")
    findings = net_income_ties(lines, taxonomy, stated_net_income or {}, tolerance)
    findings += balance_sheet_balances(lines, taxonomy, tolerance)
    findings += cash_agrees(lines, stated_ending_cash or {}, tolerance)
    if movement_threshold is not None:
        findings += movements(lines, movement_threshold, explained)
    return findings


def readiness(findings: Iterable[Mapping[str, Any]]) -> str:
    """The contract's two values. Anything failed or not evaluated is outstanding; nothing
    here can say approved, because the contract has no such value."""
    outstanding = any(f["result"] in ("fail", "could_not_evaluate") for f in findings)
    return "items_outstanding" if outstanding else "no_automated_issues_found"
