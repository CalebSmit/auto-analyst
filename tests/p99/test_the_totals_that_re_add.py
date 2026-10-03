"""P99 - the totals that re-add, and the rows they cover.

`review/router.py` has routed an extracted figure to a person since P37 unless something
re-added a total it feeds, and nothing has ever produced that evidence. So `extracted`
figures have been uncovered by construction, the rule has only ever been able to say "show
him all of it", and `BUILD/OPEN.md` has carried the producer as owed since.

The first real client folder showed the producer was a walk over rows this build already
parses. Across the fourteen sheets of their statements every one of 280 subtotals re-adds
exactly, and four fifths of the parsed rows sit under one.

**The figures in that folder are a client's and do not enter this repo.** The statements
below are synthetic and carry the *shape* that mattered - totals of lines, totals of
subtotals, a run that starts after a heading rather than after the previous total. The one
test that reads the real folder skips when it is not there, which is every machine but the
one it was found on.

What this proves is addition. Eight wrong rows added correctly still foot; a statement that
foots perfectly can be the wrong period or the wrong company. That is worth saying out loud
because "arithmetic cover" sounds like more than it is - it is evidence a figure was not
*misread*, which is exactly the failure a confidence score cannot see.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from intake.readers.footing import (
    CENT,
    LINES,
    SUBTOTALS,
    footings_in,
    is_a_total,
)

ROOT = Path(__file__).resolve().parents[2]
THE_REAL_FOLDER = ROOT / "inbox" / "test-client"


@dataclass(frozen=True)
class Row:
    label: str
    value: float | None
    ordinal: int = 0


def statement(*pairs: tuple[str, float | None]) -> list[Row]:
    return [Row(label, value, n) for n, (label, value) in enumerate(pairs)]


#: The shape of a real balance sheet: leaves, a subtotal, more leaves, another subtotal,
#: then a total of the subtotals, then the same again for liabilities, then a grand total
#: of two subtotals that are themselves totals of subtotals.
A_BALANCE_SHEET = statement(
    ("ASSETS", None),
    ("Cash - operating", 390_196.88),
    ("Cash - petty", 5_300.00),
    ("Cash - money market", 1_514_741.10),
    ("Total Cash", 1_910_237.98),
    ("Accounts receivable", 8_000_000.00),
    ("Allowance for doubtful accounts", -335_991.98),
    ("Total Receivables", 7_664_008.02),
    ("Total Current Assets", 9_574_246.00),
    ("Equipment", 1_600_000.00),
    ("Accumulated depreciation", -154_539.52),
    ("Total Fixed Assets", 1_445_460.48),
    ("TOTAL ASSETS", 11_019_706.48),
)


# ============================================================ what re-adds


def test_a_total_of_the_lines_above_it_is_found() -> None:
    report = footings_in(A_BALANCE_SHEET)
    cash = next(f for f in report.footings if f.label == "Total Cash")
    assert cash.covered
    assert cash.how == LINES
    assert len(cash.ordinals) == 3, "the three cash accounts, and not the heading above them"


def test_a_total_of_the_subtotals_above_it_is_found() -> None:
    """The shape that made the first attempt fail. `Total Current Assets` sums the two
    totals before it, not the lines - by then the lines have already been consumed."""
    report = footings_in(A_BALANCE_SHEET)
    current = next(f for f in report.footings if f.label == "Total Current Assets")
    assert current.how == SUBTOTALS
    assert len(current.ordinals) == 2


def test_a_grand_total_sums_the_subtotals_that_are_themselves_totals_of_subtotals() -> None:
    """Three levels. `TOTAL ASSETS` takes `Total Current Assets` and `Total Fixed Assets`,
    and the first of those has already eaten the two below it - so the run it needs is the
    *tail* of what is left rather than everything since the last total."""
    report = footings_in(A_BALANCE_SHEET)
    grand = next(f for f in report.footings if f.label == "TOTAL ASSETS")
    assert grand.covered, grand
    assert grand.how == SUBTOTALS
    assert len(grand.ordinals) == 2


def test_a_subtotal_a_later_total_did_not_consume_is_still_available_to_the_next() -> None:
    """The case the balance sheet above is too tidy to reach, and the real statement is not.

    `Total Liabilities` takes the last two subtotals and leaves `TOTAL ASSETS` sitting
    before them, still unconsumed. If a subtotals-total cleared the whole list instead of
    removing only the run it used, the earlier subtotal would vanish and anything that
    needed it later would be reported uncovered - a statement that foots, read as one that
    does not.
    """
    rows = statement(
        ("Cash", 10.0),
        ("Total Cash", 10.0),
        ("Stock", 20.0),
        ("Total Stock", 20.0),
        ("Plant", 30.0),
        ("Total Plant", 30.0),
        ("Total Stock and Plant", 50.0),
        ("TOTAL ASSETS", 60.0),
    )
    report = footings_in(rows)
    assert report.foots, [f"{f.label} out by {f.delta}" for f in report.uncovered]
    grand = next(f for f in report.footings if f.label == "TOTAL ASSETS")
    assert grand.how == SUBTOTALS
    assert len(grand.ordinals) == 2, "Total Cash and Total Stock and Plant"


def test_every_total_in_a_well_formed_statement_re_adds() -> None:
    report = footings_in(A_BALANCE_SHEET)
    assert report.foots
    assert report.totals == 5
    assert report.uncovered == ()


def test_the_rows_a_total_covers_are_reported_so_the_rest_can_be_counted() -> None:
    """The number the acceptance rule turns into work: what is covered is proved, and what
    is left is what a person reads.

    Eleven of twelve, not nine. A subtotal is covered twice over - once as the total of the
    lines beneath it, and again as a *line* of the total above it - and both are real
    arithmetic about the same figure. Only the grand total is left uncovered, which is
    correct: nothing on the statement re-adds it, and on a balance sheet the thing that
    would is the other side.
    """
    report = footings_in(A_BALANCE_SHEET)
    assert len(report.covered_ordinals) == 11
    assert report.rows == 12, "the heading carries no value and is not a row here"
    uncovered_rows = {r.ordinal for r in A_BALANCE_SHEET if r.value is not None} - (
        report.covered_ordinals
    )
    assert uncovered_rows == {12}, "only the grand total itself"


# ============================================================ what does not


def test_a_total_that_re_adds_from_nothing_is_reported_uncovered() -> None:
    """A missing row is the commonest reason, and the point of the whole module: a figure
    misread off a scanned page shows up here and nowhere else."""
    broken = statement(
        ("Cash - operating", 100.00),
        ("Cash - petty", 50.00),
        ("Total Cash", 200.00),
    )
    report = footings_in(broken)
    assert not report.foots
    assert report.uncovered[0].label == "Total Cash"
    assert not report.uncovered[0].covered


def test_it_says_by_how_much_rather_than_only_that_it_failed() -> None:
    """Fifty out of two hundred is a missing row; a cent is a rounding difference. The
    person reading it needs to know which, and "did not re-add" does not say."""
    report = footings_in(
        statement(("A", 100.00), ("B", 50.00), ("Total Cash", 200.00))
    )
    assert report.uncovered[0].delta == pytest.approx(-50.00)


def test_it_is_never_attached_to_the_nearest_thing_that_nearly_fits() -> None:
    """The temptation, and the thing that would make the cover worthless. A total out by
    fifty is uncovered; it does not quietly take the run that is closest."""
    report = footings_in(
        statement(("A", 100.00), ("B", 50.00), ("Total", 151.00))
    )
    assert report.uncovered and report.uncovered[0].ordinals == ()


def test_the_tolerance_is_half_a_cent_and_not_a_materiality_threshold() -> None:
    """A loose tolerance buys a few more covered rows and sells the only thing the cover is
    worth. These values come from a workbook at full stored precision, so a real sum matches
    to floating point."""
    assert CENT == 0.005
    near = footings_in(statement(("A", 100.001), ("B", 50.0), ("Total", 150.0)))
    assert near.foots, "a tenth of a cent is float noise"
    far = footings_in(statement(("A", 100.02), ("B", 50.0), ("Total", 150.0)))
    assert not far.foots, "two cents is a difference somebody should see"


# ============================================================ what counts as a total


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Total Cash", True),
        ("TOTAL ASSETS", True),
        ("Subtotal - operating", True),
        # Both are derived by subtraction, and this reader adds. Claiming them reported
        # `Gross Profit` uncovered - true and useless - and, worse, made `Net Income (Loss)
        # Y-T-D` inside equity consume the rows above it, breaking the real
        # `Total Stockholder's Equity` underneath.
        ("Gross Profit", False),
        ("Net Income (Loss) Y-T-D", False),
        ("Cash - operating", False),
        ("", False),
    ],
)
def test_a_row_is_a_total_because_the_statement_says_so(label: str, expected: bool) -> None:
    assert is_a_total(label) is expected


def test_a_line_that_happens_to_equal_the_sum_above_it_is_not_a_total() -> None:
    """On a short statement a coincidence is common. The document's own word for it is the
    only evidence used."""
    coincidence = statement(("A", 50.0), ("B", 50.0), ("Insurance", 100.0))
    assert footings_in(coincidence).totals == 0


# ============================================================ what it may not do


def test_a_total_is_matched_to_a_contiguous_run_and_never_to_a_combination() -> None:
    """Subsets would find a combination for almost any target on a long statement, which is
    how an algorithm produces a number that is right about nothing. A statement is laid out
    as runs; this reads runs."""
    rows = statement(
        ("A", 7.0), ("B", 13.0), ("C", 5.0), ("Total", 12.0)  # 7 + 5, not contiguous
    )
    assert not footings_in(rows).foots


def test_nothing_here_reaches_a_model_an_engine_or_the_network() -> None:
    """The figures on this path are the ones a person would otherwise re-key, and the whole
    argument for trusting the cover is that it is arithmetic rather than judgement."""
    source = (ROOT / "intake" / "readers" / "footing.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    named: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            named.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            named.add(node.module)
    for forbidden in ("ports", "harness", "skills", "graph", "anthropic", "httpx2"):
        assert not any(n == forbidden or n.startswith(forbidden + ".") for n in named), forbidden
    for reaching in ("requests", "socket", "urllib"):
        assert reaching not in source, reaching


def test_it_says_that_it_proves_addition_and_not_selection() -> None:
    """Written down beside the code, because "arithmetic cover" reads like more than it is
    and the person relying on it is relying on the distinction."""
    said = (ROOT / "intake" / "readers" / "footing.py").read_text(encoding="utf-8")
    assert "proves addition" in said
    assert "not selection" in said


# ============================================================ it reaches a person


def test_the_read_report_carries_it_and_names_what_did_not_foot() -> None:
    """P99's own risk. A footing report on a dataclass nobody reads is this build's most
    repeated defect, and the whole point is that a statement which does not add up is
    visible the day it arrives."""
    from intake.readers import ReadReport

    report = ReadReport(source_id="s", filename="f.xlsx", kind="spreadsheet")
    report.footing["'FY23'!B1:B9"] = footings_in(
        statement(("A", 100.00), ("B", 50.00), ("Total Cash", 200.00))
    )
    assert report.covered_rows == 0
    named = report.totals_that_did_not_foot
    assert named and "Total Cash" in named[0]
    assert "-50.00" in named[0], "the amount, not just the fact"


def test_the_source_says_it_out_loud_in_the_event_a_person_reads() -> None:
    source = (ROOT / "intake" / "readers" / "__init__.py").read_text(encoding="utf-8")
    # Both call sites pass the column's heading since P164, so the sign check can stay
    # quiet on a column of changes.
    assert 'footings_in(rows, heading=headings.get(locator, ""))' in source
    assert (
        'footings_in(\n                    rows, heading=table.block_headers.get(locator, "")'
        in source
    )
    assert "did not re-add" in source
    assert '"rows_covered_by_a_total"' in source
    assert '"signs_contradicted"' in source


# ============================================================ the real folder, if it is here


@pytest.mark.skipif(
    not THE_REAL_FOLDER.is_dir(),
    reason="the client folder is gitignored and lives only on the machine it was tested on",
)
def test_the_real_statements_still_foot_to_the_penny() -> None:
    """The measurement that justified the phase, re-run rather than quoted. Skips
    everywhere the folder is absent, which is every clone - so it is evidence on the
    machine that has the files and silence elsewhere, and it says which."""
    from intake.readers.workbook import StructuralSelector, normalize_workbook, survey_workbook

    statements = sorted(
        (THE_REAL_FOLDER / "Historical and Forecasted Financial Statements").glob(
            "Consolidated*.xlsx"
        )
    )
    assert statements, "the folder is here but the statements are not"

    totals = re_added = covered = 0
    for path in statements:
        data = path.read_bytes()
        survey = survey_workbook(data)
        chosen = StructuralSelector().select(survey).accounting_for(survey)
        for table in normalize_workbook(data, [s.sheet for s in chosen.selected]):
            for rows in table.blocks.values():
                report = footings_in(rows)
                totals += report.totals
                re_added += report.totals - len(report.uncovered)
                covered += len(report.covered_ordinals)

    assert totals > 200, totals
    assert re_added == totals, f"{totals - re_added} of {totals} totals stopped adding up"
    assert covered > 1500, covered
