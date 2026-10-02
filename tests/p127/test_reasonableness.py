"""The questions a reviewer asks, and the ones this module refuses to answer.

Three things are being held here, and the third is the one that matters most.

**It finds the gaps.** Depreciation with no fixed assets, interest with no debt, tax in a
loss year, a margin that gives up two points a year for three years. One test each.

**It asks once.** The first version asked every question of every period, so a three-year
table with depreciation and no fixed assets produced three identical findings and a
six-question report ran to eighteen lines. A reviewer answers that question for the
history, not for each year of it.

**It concludes nothing, and it has no defaults.** Every tolerance is the caller's, in the
ratio's own unit, and a unit with no tolerance is reported as a question nobody asked
rather than left out of the report. That is not a style choice: materiality belongs to the
practice (`BUILD/OPEN.md` section 2), "nothing concludes, signs or certifies" is a
blueprint invariant, and a module that shipped a default margin tolerance would have set
one of the nine decisions that belong to people.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from registries.taxonomy import load_taxonomy
from tools.reasonableness import (
    DAYS,
    IMPLICATIONS,
    implications,
    lines_from,
    main,
    ratios,
    ratios_for,
    run_questions,
    shape_of_the_history,
    tax_in_a_loss_year,
)
from tools.statement_checks import Line

ROOT = Path(__file__).resolve().parents[2]
TAXONOMY = load_taxonomy("coa-taxonomy@1.0.0")
Y = ("2023-12-31", "2024-12-31", "2025-12-31")


def line(category: str, *amounts: float, locator: str = "", label: str = "") -> Line:
    """One tagged line over as many of the three periods as amounts are given for."""
    return Line(
        category=category,
        amounts=dict(zip(Y, amounts, strict=False)),
        locator=locator or f"IS!{category}",
        label=label,
    )


def a_table(**overrides: list[Line]) -> list[Line]:
    """A three-year table with nothing worth asking about.

    Flat margins, flat working capital, fixed assets behind the depreciation, debt behind
    the interest, tax against a profit. Every question this module asks has an answer on
    this table, which is what makes it the right thing to measure silence against.
    """
    base = [
        line("revenue", 1_000_000, 1_050_000, 1_100_000),
        line("cost_of_sales", 400_000, 420_000, 440_000),
        line("salaries_wages", 300_000, 315_000, 330_000),
        line("depreciation", 30_000, 31_000, 32_000),
        line("interest_expense", 25_000, 24_000, 23_000),
        line("income_tax", 50_000, 52_000, 55_000),
        line("cash", 80_000, 84_000, 88_000),
        line("accounts_receivable", 110_000, 115_000, 120_000),
        line("inventory", 90_000, 94_000, 99_000),
        line("ppe", 400_000, 420_000, 440_000),
        line("accounts_payable", 70_000, 73_000, 77_000),
        line("long_term_debt", 300_000, 290_000, 280_000),
        line("equity", 400_000, 450_000, 500_000),
    ]
    by_category = {ln.category: ln for ln in base}
    for category, replacement in overrides.items():
        by_category.pop(category, None)
        for ln in replacement:
            by_category[ln.category] = ln
    return list(by_category.values())


def without(*categories: str) -> list[Line]:
    return [ln for ln in a_table() if ln.category not in categories]


def failed(findings: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {f["check"]: f for f in findings if f["result"] == "fail"}


TOLERANT = {"points": 5.0, "days": 10.0, "x": 0.5}


# --------------------------------------------------------- a line that implies another


def test_depreciation_with_no_fixed_assets() -> None:
    (check, found), *rest = failed(implications(without("ppe"))).items()
    assert rest == []
    assert check == "depreciation and fixed assets (every period)"
    assert "no fixed assets" in found["evidence"]
    assert found["locator"] == "IS!depreciation"


def test_interest_expense_with_no_debt() -> None:
    """The first question an MD asks, and the one that feeds the debt tab."""
    found = failed(implications(without("long_term_debt")))
    assert "interest expense and debt (every period)" in found
    assert "long-term debt note" in found["interest expense and debt (every period)"]["evidence"]


def test_debt_with_no_interest_expense_is_asked_from_the_other_side() -> None:
    found = failed(implications(without("interest_expense")))
    (check,) = [c for c in found if c.startswith("interest expense and debt, the other way")]
    assert "is on the table and" in found[check]["evidence"]
    assert found[check]["locator"] == "IS!long_term_debt"


def test_a_question_is_asked_once_and_names_its_periods() -> None:
    """Three periods, one finding. The whole point of grouping: a reviewer answers the
    question for the history, and three copies of it is three times the reading for the
    same amount of information."""
    found = [
        f
        for f in implications(without("ppe"))
        if f["result"] == "fail" and f["check"].startswith("depreciation")
    ]
    assert len(found) == 1
    assert "every period" in found[0]["check"]
    assert "In every period on the table" in found[0]["evidence"]


def test_a_gap_in_one_period_names_that_period() -> None:
    """A client who bought the fixed assets in the second year. The period is the useful
    half of the finding, so it is named exactly rather than counted."""
    lines = [ln for ln in a_table() if ln.category != "ppe"]
    lines.append(Line(category="ppe", amounts={Y[1]: 400_000, Y[2]: 420_000}, locator="BS!ppe"))
    found = failed(implications(lines))
    assert "depreciation and fixed assets (2023-12-31)" in found
    assert "In 2023-12-31, " in found["depreciation and fixed assets (2023-12-31)"]["evidence"]


def test_rent_beside_a_related_party_balance_is_a_question_about_a_pair() -> None:
    """Not a missing line - both are present, and the pair is the finding. It is the
    market-rent fact the EBITDA skill holds an add-back for."""
    lines = [*a_table(), line("rent", 60_000, 60_000, 60_000),
             line("related_party_payable", 40_000, 45_000, 50_000)]
    found = failed(implications(lines))
    assert any(c.startswith("related-party rent") for c in found)


def test_a_question_that_does_not_arise_says_so_rather_than_passing() -> None:
    """`not_applicable` and `pass` are different answers. Nothing on this table is
    amortisation, so the amortisation question was not answered - it was not asked."""
    found = {f["check"]: f for f in implications(a_table())}
    assert found["amortisation and intangibles"]["result"] == "not_applicable"
    assert "does not arise" in found["amortisation and intangibles"]["evidence"]
    assert found["depreciation and fixed assets"]["result"] == "pass"


def test_a_table_with_no_amounts_is_reported_rather_than_passed() -> None:
    (only,) = implications([Line(category="revenue", amounts={}, locator="IS!5")])
    assert only["result"] == "could_not_evaluate"
    assert "no amounts in any period" in only["evidence"]


def test_a_zero_balance_counts_as_absence() -> None:
    """A balance sheet listing `Long-term debt` with nothing against it is saying there
    is no debt. A check that read the label rather than the amount would stay silent on
    exactly the engagement that needed the question."""
    lines = [ln for ln in a_table() if ln.category != "long_term_debt"]
    lines.append(line("long_term_debt", 0, 0, 0, locator="BS!debt"))
    assert "interest expense and debt (every period)" in failed(implications(lines))


def test_every_implication_carries_a_question_rather_than_a_verdict() -> None:
    for rule in IMPLICATIONS:
        assert rule.asks.strip()
        assert not rule.asks.endswith("."), "the module adds the full stop"
        assert rule.present, f"{rule.name} is triggered by nothing"


# ------------------------------------------------------------------ a ratio over time


def test_a_ratio_that_moves_between_two_periods() -> None:
    lines = without("accounts_receivable")
    lines.append(line("accounts_receivable", 110_000, 115_000, 260_000, locator="BS!ar"))
    found = failed(ratios(lines, TOLERANT, TAXONOMY))
    (check,) = [c for c in found if c.startswith("days receivable 2024")]
    assert "a move of +" in found[check]["evidence"]
    assert found[check]["threshold"] == 10.0


def test_a_ratio_that_never_trips_a_step_and_moves_across_the_history() -> None:
    """The comparison an MD actually makes. A margin giving up two and a half points a
    year for three years trips no step tolerance of five and has moved seven and a half,
    which is the whole story of the business."""
    lines = without("cost_of_sales")
    lines.append(line("cost_of_sales", 400_000, 446_250, 495_000))  # 60.0, 57.5, 55.0
    found = failed(ratios(lines, {"points": 5.0}, TAXONOMY))
    assert [c for c in found if c.startswith("gross margin")] == [
        "gross margin across the whole history"
    ], "no single step moved five points"
    said = found["gross margin across the whole history"]["evidence"]
    assert "-5.0 points over 3 periods" in said
    assert "A trend rather than an event" in said


def test_a_unit_with_no_tolerance_is_a_question_nobody_asked() -> None:
    """Not left out. A report with no margin questions in it reads as a document with no
    margin questions, which is the one outcome worse than being told nothing was asked."""
    found = {f["check"]: f for f in ratios(a_table(), {"days": 10.0}, TAXONOMY)}
    assert found["gross margin"]["result"] == "could_not_evaluate"
    assert "nobody has said how far this may move" in found["gross margin"]["evidence"]
    assert "measured in points" in found["gross margin"]["evidence"]
    assert found["days receivable"]["result"] == "pass"


def test_a_tolerance_of_zero_is_refused() -> None:
    with pytest.raises(ValueError, match="no default and no zero"):
        ratios(a_table(), {"points": 0.0}, TAXONOMY)


def test_one_tolerance_cannot_serve_three_units() -> None:
    """Why `move` is keyed by unit. Five is a sensible question of a margin in points and
    no question at all of a current ratio that cannot move five turns, so a single number
    silently stops asking about the thing it does not fit."""
    one_number = {"points": 5.0, "days": 5.0, "x": 5.0}
    lines = without("accounts_payable")
    # The current ratio goes 4.0, 3.9, 4.7: a move of 0.7 turns, which is a question at
    # a tolerance of half a turn and invisible at a tolerance of five.
    lines.append(line("accounts_payable", 70_000, 73_000, 65_000, locator="BS!ap"))
    assert not [
        f for f in ratios(lines, one_number, TAXONOMY) if f["check"].startswith("the current")
        and f["result"] == "fail"
    ]
    found = failed(ratios(lines, {**one_number, "x": 0.5}, TAXONOMY))
    assert [c for c in found if c.startswith("the current ratio")]


def test_a_ratio_with_one_period_cannot_move() -> None:
    lines = [
        Line(category="revenue", amounts={Y[0]: 1_000_000}, locator="IS!5"),
        Line(category="cost_of_sales", amounts={Y[0]: 400_000}, locator="IS!6"),
    ]
    found = {f["check"]: f for f in ratios(lines, TOLERANT, TAXONOMY)}
    assert found["gross margin"]["result"] == "could_not_evaluate"
    assert "needs two periods" in found["gross margin"]["evidence"]


def test_a_period_the_ratio_could_not_be_computed_for_is_named() -> None:
    lines = without("accounts_receivable")
    lines.append(Line(category="accounts_receivable", amounts={Y[0]: 110_000, Y[1]: 115_000},
                      locator="BS!ar"))
    found = {f["check"]: f for f in ratios(lines, TOLERANT, TAXONOMY)}
    missing = found["days receivable, where it could not be computed"]
    assert missing["result"] == "could_not_evaluate"
    assert Y[2] in missing["evidence"]


def test_days_are_computed_on_three_hundred_and_sixty_five() -> None:
    """The analyst's own spreadsheets use 365. One convention here and another there is
    two numbers for one thing, which is what the shared `Line` exists to avoid."""
    assert DAYS == 365
    found = {f["check"]: f for f in ratios(a_table(), {"days": 10.0}, TAXONOMY)}
    # 110,000 / 1,000,000 * 365 = 40.15
    assert "40.1" in found["days receivable"]["evidence"]


# ------------------------------------------- the ratios are built from the taxonomy


def test_the_operating_margin_covers_every_operating_expense_the_taxonomy_declares() -> None:
    """The reason the ratios are a function of the taxonomy rather than a constant. A
    hand-written list goes quietly out of date, and the operating margin would one day be
    computed over fifteen of the seventeen operating expense lines and look entirely
    plausible while doing it."""
    declared = {c.id for c in TAXONOMY.categories.values() if c.section == "operating_expenses"}
    assert len(declared) > 10, "the taxonomy has a real operating expense section"
    (margin,) = [r for r in ratios_for(TAXONOMY) if r.name == "operating margin"]
    subtracted = {term.lstrip("-") for term in margin.numerator if term.startswith("-")}
    assert declared <= subtracted
    assert "interest_expense" not in subtracted, "interest is not an operating expense"
    assert "income_tax" not in subtracted


def test_the_current_ratio_uses_the_sections_rather_than_a_list() -> None:
    (current,) = [r for r in ratios_for(TAXONOMY) if r.name == "the current ratio"]
    assets = {c.id for c in TAXONOMY.categories.values() if c.section == "current_assets"}
    claims = {c.id for c in TAXONOMY.categories.values() if c.section == "current_liabilities"}
    assert set(current.numerator) == assets
    assert set(current.denominator) == claims
    assert "lease_liability" not in current.denominator, (
        "the taxonomy puts it in `liabilities`, because the current/non-current split is "
        "not on the face of the statements - putting the whole of it on one side would "
        "make the ratio wrong in a way nobody could see"
    )


# ------------------------------------------------------------------ tax in a loss year


def test_tax_expense_in_a_year_the_business_lost_money() -> None:
    lines = without("salaries_wages")
    lines.append(line("salaries_wages", 700_000, 750_000, 800_000))
    found = failed(tax_in_a_loss_year(lines, TAXONOMY))
    (check,) = list(found)
    assert check.startswith("tax in a loss year")
    assert "before tax" in found[check]["evidence"]
    assert "S corporation" in found[check]["evidence"], "the ordinary answers are offered"


def test_tax_against_a_profit_is_not_a_question() -> None:
    (only,) = tax_in_a_loss_year(a_table(), TAXONOMY)
    assert only["result"] == "pass"


def test_no_tax_on_the_table_means_the_question_does_not_arise() -> None:
    (only,) = tax_in_a_loss_year(without("income_tax"), TAXONOMY)
    assert only["result"] == "not_applicable"


def test_tax_with_too_little_tagged_to_tell_says_so() -> None:
    lines = [
        Line(category="income_tax", amounts={Y[0]: 5_000}, locator="IS!26"),
    ]
    (only,) = tax_in_a_loss_year(lines, TAXONOMY)
    assert only["result"] == "could_not_evaluate"
    assert "not enough of the income statement is tagged" in only["evidence"]


# --------------------------------------------------------------- the shape of history


def test_a_year_missing_from_the_middle_of_the_range() -> None:
    lines = [
        Line(
            category="revenue",
            amounts={"2021-12-31": 1.0, "2023-12-31": 2.0, "2025-12-31": 3.0},
            locator="IS!5",
        )
    ]
    found = {f["check"]: f for f in shape_of_the_history(lines)}
    gap = found["a year missing from the middle of the range"]
    assert gap["result"] == "fail"
    assert "2022, 2024" in gap["evidence"]


def test_a_continuous_range_passes() -> None:
    found = {f["check"]: f for f in shape_of_the_history(a_table())}
    assert found["a year missing from the middle of the range"]["result"] == "pass"


def test_how_many_years_the_engagement_needs_has_no_default() -> None:
    found = {f["check"]: f for f in shape_of_the_history(a_table())}
    assert found["enough years of history"]["result"] == "could_not_evaluate"
    assert "nobody has said how many years" in found["enough years of history"]["evidence"]

    asked = {f["check"]: f for f in shape_of_the_history(a_table(), years=5)}
    assert asked["enough years of history"]["result"] == "fail"
    assert asked["enough years of history"]["threshold"] == 5.0
    enough = {f["check"]: f for f in shape_of_the_history(a_table(), years=3)}
    assert enough["enough years of history"]["result"] == "pass"


# ------------------------------------------------------- and silence, where it is due


def test_a_table_with_nothing_worth_asking_about_asks_nothing() -> None:
    """Flat margins, flat working capital, fixed assets behind the depreciation, debt
    behind the interest, tax against a profit. The half of a check that is easy to lose."""
    findings = run_questions(a_table(), TAXONOMY, move=TOLERANT, years=3)
    asked = [f for f in findings if f["result"] == "fail"]
    assert asked == [], [f["check"] + ": " + f["evidence"] for f in asked]
    assert findings, "and it still reported on everything it looked at"


def test_nothing_in_the_output_concludes_anything() -> None:
    """The blueprint invariant, held over the text this module produces. No finding may
    say a valuation, or anything else, is reasonable, approved, fine or acceptable."""
    findings = run_questions(a_table(), TAXONOMY, move=TOLERANT, years=3)
    said = " ".join(f"{f['check']} {f['evidence']}" for f in findings).lower()
    for word in ("reasonable", "approved", "we conclude", "is correct", "acceptable",
                 "valuation is", "fair market value"):
        assert word not in said, f"the output says {word!r}"


def test_every_result_is_one_the_contract_allows() -> None:
    """The output is the `qc_findings` item shape of `skills/qc-tieout@1.0.0`, so the two
    engines compose into one list. Read out of the schema rather than repeated here: a
    copy of an enum is a copy that stops matching."""
    schema = json.loads((ROOT / "contracts" / "skills" / "qc-tieout.schema.json").read_text())
    allowed = set(schema["properties"]["qc_findings"]["items"]["properties"]["result"]["enum"])
    required = schema["properties"]["qc_findings"]["items"]["required"]
    for findings in (
        run_questions(a_table(), TAXONOMY, move=TOLERANT, years=3),
        run_questions(without("ppe", "long_term_debt"), TAXONOMY, move=TOLERANT),
    ):
        for finding in findings:
            assert finding["result"] in allowed, finding
            assert set(required) <= set(finding), finding
            assert finding["evidence"].strip()


# ------------------------------------------------------------------- the command line


@pytest.fixture
def table(tmp_path: Path) -> Path:
    path = tmp_path / "table.json"
    path.write_text(
        json.dumps(
            {
                "lines": [
                    {
                        "category": ln.category,
                        "amounts": dict(ln.amounts),
                        "locator": ln.locator,
                        "label": ln.label,
                    }
                    for ln in without("ppe")
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_the_command_line_asks_and_exits_nonzero(table: Path) -> None:
    assert main([str(table), "--move", "points=5", "--move", "days=10"]) == 1


def test_the_command_line_refuses_a_unit_no_ratio_is_measured_in(
    table: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A misspelled unit doing nothing silently would read as a table with no margin
    questions in it."""
    assert main([str(table), "--move", "pts=5"]) == 2
    said = capsys.readouterr().err
    assert "not a unit any ratio is measured in" in said
    assert "points" in said, "and it says what the units are"


def test_the_command_line_refuses_a_malformed_tolerance(
    table: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(table), "--move", "points"]) == 2
    assert "UNIT=N" in capsys.readouterr().err
    assert main([str(table), "--move", "points=soon"]) == 2
    assert "is not a number" in capsys.readouterr().err


def test_a_table_that_is_not_a_table_is_refused_rather_than_read_as_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A row this cannot read is not dropped. A question not asked because a row was
    silently skipped is the worst outcome this module has."""
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"lines": [{"category": "revenue"}]}), encoding="utf-8")
    assert main([str(path)]) == 2
    assert "lines[0] is not a line" in capsys.readouterr().err

    with pytest.raises(ValueError, match="needs a 'lines' array"):
        lines_from({"rows": []})


def test_a_taxonomy_this_build_does_not_have_is_refused(
    table: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(table), "--taxonomy", "coa-taxonomy@9.9.9"]) == 2
    assert "not a taxonomy this build has" in capsys.readouterr().err


def test_the_command_line_can_hand_its_answer_to_something_else(
    table: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([str(table), "--move", "points=5", "--json"])
    body = json.loads(capsys.readouterr().out)
    assert body["qc_findings"]
    assert any(f["result"] == "fail" for f in body["qc_findings"])


def test_the_report_says_out_loud_that_nothing_in_it_concludes(
    table: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([str(table), "--move", "points=5"])
    assert "a question, not a verdict" in capsys.readouterr().out
