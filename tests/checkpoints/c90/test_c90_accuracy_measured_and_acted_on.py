"""C90 - accuracy, measured and acted on.

Two phases that are one claim from both ends.

* **P161** built the only thing in this build that can answer whether a figure is *right*
  rather than whether it adds up. The SEC publishes the filer's own numbers as XBRL, so
  `Assets` at 2025-12-31 is 521,728,000 and the 521,728 on page 56 can be checked against it
  - at the date that column is as of, which is what sees a figure read out of the wrong
  column.
* **P162** is the first defect it found. A share count carried the statement's dollar scale,
  and three places multiply a figure by its scale, so 135,361,000 shares became 135 billion
  and a par value of $0.001 became $1.00.

**A measurement is only worth having if it catches a real error, and a fix is only
trustworthy if the measurement that found it still passes afterwards.** Each phase proves
half of that and neither can prove both, which is what this is for.

And the question neither asks: do the three filings still read the same way now that a row's
own label can override the file's scale? 2,373 rows, of which 53 changed what scale applies
to them, and the other 2,320 must not have moved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intake.readers.units import declared_unit
from tools.check_against_filer import FIXTURES, check, load_facts

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "fixtures" / "public"


@pytest.fixture(scope="module")
def checked() -> dict[str, list]:
    out: dict[str, list] = {}
    for name, fixture in FIXTURES.items():
        facts = load_facts(fixture.facts)
        out[name] = [
            said
            for statement in fixture.statements
            for said in check(fixture, statement, facts)
        ]
    return out


@pytest.fixture(scope="module")
def every_row() -> list[tuple[str, str, float]]:
    """Every row carrying a figure, over all three public filings."""
    from intake.readers.documents import read_document
    from intake.readers.workbook import normalize_workbook, survey_workbook

    out: list[tuple[str, str, float]] = []
    for name in ("sec-ars-3d-systems-2025.pdf", "sec-ars-resmed-2026.pdf"):
        doc = read_document((PUBLIC / name).read_bytes(), name)
        out += [
            (name, row.label, row.value)
            for page in doc.pages
            for table in page.tables
            for column in table.columns
            for row in column.rows
            if row.value is not None
        ]
    book = "sec-financial-report-3d-systems-2025q1.xlsx"
    data = (PUBLIC / book).read_bytes()
    survey = survey_workbook(data)
    for table in normalize_workbook(data, [s.name for s in survey.sheets if s.readable]):
        for _locator, rows in table.blocks.items():
            out += [(book, r.label, r.value) for r in rows if r.value is not None]
    return out


# ----------------------------------------------- the measurement still says what it said


def test_no_figure_came_out_of_the_wrong_column_after_the_fix(checked) -> None:
    """The half P162 could break and did not. A unit rule that touched which column a
    figure came from would be a far worse defect than the one it fixed."""
    wrong = [
        (name, said.where, label, value)
        for name, all_said in checked.items()
        for said in all_said
        for label, value, _ in said.elsewhere
    ]
    assert wrong == [], wrong


def test_the_counts_are_still_the_counts(checked) -> None:
    """194 right, 2 at another scale, 0 wrong-column, 3 not in the feed. Asserted here as
    well as in `tests/p161` because this is the only place that runs after P162."""
    totals = {"here": 0, "unscaled": 0, "elsewhere": 0, "nowhere": 0}
    for all_said in checked.values():
        for said in all_said:
            totals["here"] += len(said.here)
            totals["unscaled"] += len(said.unscaled)
            totals["elsewhere"] += len(said.elsewhere)
            totals["nowhere"] += len(said.nowhere)
    assert totals == {"here": 194, "unscaled": 2, "elsewhere": 0, "nowhere": 3}, totals


def test_the_two_at_another_scale_are_still_reported(checked) -> None:
    """**And they should be**, which is the exit criterion I wrote wrongly.

    The check reads the readers' *rows*, and a row holds the cell value as the file wrote
    it: a share count in a cell is 135,361,000 whatever the statement is in. The fix is at
    the **figure** built from those rows, which now carries scale 1. So the two reports are
    true statements about the rows and are the thing that found the defect - expecting them
    to disappear confused the row with the figure, and `gate amend` carries the correction.
    """
    said = checked["sec-financial-report-3d-systems-2025q1"]
    flagged = [
        (label, value) for column in said for label, value, _ in column.unscaled
    ]
    assert [label for label, _ in flagged] == [
        "Common stock, shares, issued (in shares)",
        "Common stock, shares, issued (in shares)",
    ], flagged

    # And each one's label is exactly what P162 reads, so the two halves agree about which
    # rows they are talking about.
    for label, _value in flagged:
        got = declared_unit(label)
        assert got is not None and got.unit == "shares" and got.scale == 1


# ------------------------------------------------- and the filings still read as they did


def test_nothing_that_was_currency_stopped_being_currency(every_row) -> None:
    """The dangerous direction, over the whole corpus. A rule that stripped the scale from a
    real dollar figure would be the same thousand-fold error the other way round, and
    2,320 of these 2,373 rows depend on it not having."""
    from tools.normalize import _unit_of

    kept = 0
    for _where, label, _value in every_row:
        if declared_unit(label) is not None:
            continue
        unit, scale, why = _unit_of(
            [(None, {"label": label, "value": 1.0}, "x")], 1_000
        )
        assert (unit, scale, why) == ("currency", 1_000, ""), label
        kept += 1
    assert kept == 2_320, kept


def test_the_rows_that_changed_are_all_on_the_workbook(every_row) -> None:
    """Why one document could not have found this, said over the corpus rather than by
    example. A typesetter keeps a share count inside the label, so every figure in a PDF
    column is a dollar amount; a workbook gives each one its own row."""
    changed = {
        where for where, label, _ in every_row if declared_unit(label) is not None
    }
    assert changed == {"sec-financial-report-3d-systems-2025q1.xlsx"}, changed
    assert len([1 for w, label, _ in every_row if declared_unit(label) is not None]) == 53


def test_the_three_tie_outs_still_hold_on_both_pdfs(every_row) -> None:
    """P154's, P160's and P99's, on the two filings that carry statements a person reads.
    A unit rule has no business changing whether a balance sheet balances, and this is the
    assertion that would notice if it had."""
    from intake.readers.documents import read_document
    from intake.readers.footing import cash_roll_forward, footings_in, two_sides

    _ = every_row
    expected = {
        ("sec-ars-3d-systems-2025.pdf", 56): 521_728.0,
        ("sec-ars-resmed-2026.pdf", 79): 8_965_950.0,
    }
    for (name, page_number), assets in expected.items():
        doc = read_document((PUBLIC / name).read_bytes(), name)
        page = next(p for p in doc.pages if p.number == page_number)
        widest = max((len(t.columns) for t in page.tables), default=0)
        first = [
            row
            for table in page.tables
            if len(table.columns) >= 1
            for row in table.columns[0].rows
        ]
        sides = two_sides(first)
        assert sides.stated, name
        assert sides.balances is True, name
        assert sides.assets == assets, (name, sides.assets)
        assert widest >= 2, name

        # And every footing that claims cover re-adds, asked of the blocks footing is given.
        for table in page.tables:
            for column in table.columns:
                by_ordinal = {r.ordinal: r for r in column.rows}
                for found in footings_in(column.rows).footings:
                    if not found.covered:
                        continue
                    parts = [by_ordinal[o].value or 0.0 for o in found.ordinals]
                    assert sum(parts) == pytest.approx(found.value), (name, found.label)

        assert cash_roll_forward(first).stated is False, (
            f"{name} p{page_number} is a balance sheet, and should roll no cash forward"
        )


# --------------------------------------------------------- the measurement's own provenance


def test_the_ground_truth_is_the_regulators_and_says_so() -> None:
    """What makes this a measurement rather than an opinion: the figures came from the SEC,
    for the same accession, on a recorded date - and each file says what it cannot speak
    about."""
    for name, fixture in FIXTURES.items():
        body = load_facts(fixture.facts)
        assert body["source"].startswith("https://data.sec.gov/api/xbrl/companyfacts/")
        assert body["cik"] and body["accession"] and body["retrieved"]
        assert "dimensionless" in body["caveat"], name
        assert (PUBLIC / fixture.document).exists(), name

    # And the README carries the same provenance for a person rather than for a test.
    said = (PUBLIC / "README.md").read_text(encoding="utf-8")
    assert "filer-facts/" in said
    assert "data.sec.gov" in said


def test_the_facts_hold_the_dates_the_statements_declare() -> None:
    """A facts file trimmed to the wrong dates would report every figure as wrong-column,
    which would look exactly like B-030 and be the measurement's fault."""
    for name, fixture in FIXTURES.items():
        body = load_facts(fixture.facts)
        for statement in fixture.statements:
            for date in statement.columns:
                assert date in body["at_date"], f"{name}: no facts at {date}"
                assert body["at_date"][date], f"{name}: {date} is empty"
                # Every value parses as a number, because they are keyed as strings.
                for value in list(body["at_date"][date])[:20]:
                    float(value)
    # And the files are small enough to live in a git history.
    for fixture in FIXTURES.values():
        path = PUBLIC / "filer-facts" / fixture.facts
        assert path.stat().st_size < 150_000, path.name
        json.loads(path.read_text(encoding="utf-8"))
