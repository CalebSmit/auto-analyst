"""C91 - what the page says about its columns and what a person declared about them agree.

Two reads of the same fact, made by different phases from different evidence.

* **P161** declares, by hand, the date each statement column is as of -
  `Statement.columns` in `tools/check_against_filer.py` - because a column headed `2025`
  names a year and not a year end, and which day a fiscal year ends on is a property of
  the company. Those declarations are what the accuracy harness checks 199 figures against.
* **P163** reads the year printed above each column off the page itself, from the nearest
  band above the table that dates every column.

Neither phase can check the other on its own. A wrong declaration would report every figure
in a column as landing at another date and read as B-030; a wrong year read would settle
the period detector on a date the column is not. If the two agree, column by column, each
is evidence for the other - and if they ever disagree, one of them is wrong and this is the
test that says which statement to look at.

And the question the accuracy harness cannot ask of itself: the table P163 reports as having
lost a column is on a page the harness does not cover, which is the honest reason the
harness never saw it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intake.readers.documents import read_document
from intake.readers.periods import detect_periods
from tools.check_against_filer import FIXTURES, check, load_facts

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "fixtures" / "public"


@pytest.fixture(scope="module")
def pdfs():
    return {
        name: read_document((PUBLIC / fixture.document).read_bytes(), fixture.document)
        for name, fixture in FIXTURES.items()
        if fixture.document.endswith(".pdf")
    }


def test_the_year_the_page_prints_is_the_year_a_person_declared(pdfs) -> None:
    """Column by column, on every statement the harness checks. The declaration is an ISO
    date and the page prints a bare year, so the comparison is on the year - a year end is
    the engagement's to know, not the page's to say."""
    for name, fixture in FIXTURES.items():
        if name not in pdfs:
            continue
        for statement in fixture.statements:
            page = next(p for p in pdfs[name].pages if p.number == statement.page)
            declared = tuple(date[:4] for date in statement.columns)
            for table in page.tables:
                assert table.headings == declared, (
                    f"{name} p{statement.page} {table.locator}: the page says "
                    f"{table.headings} and the declaration says {declared}"
                )


def test_a_statement_the_harness_checks_settles_on_its_own_evidence(pdfs) -> None:
    """The harness needed a person to say which column is which. The page now says it, and
    the detector agrees with the person: the period ends it finds are the declared dates."""
    for name, fixture in FIXTURES.items():
        if name not in pdfs:
            continue
        for statement in fixture.statements:
            page = next(p for p in pdfs[name].pages if p.number == statement.page)
            found = detect_periods(page.text, tables=list(page.tables))
            assert found.settled is True, (name, statement.page, found.ambiguous)
            assert found.period_ends == tuple(sorted(statement.columns)), (
                name,
                found.period_ends,
            )


def test_the_figures_the_harness_measured_did_not_move(pdfs) -> None:
    """P163 writes column headings and touches neither the columns nor the rows. The
    harness's own count is the sharpest way to say so, and it is the same 194."""
    _ = pdfs
    totals = {"here": 0, "unscaled": 0, "elsewhere": 0, "nowhere": 0}
    for fixture in FIXTURES.values():
        facts = load_facts(fixture.facts)
        for statement in fixture.statements:
            for said in check(fixture, statement, facts):
                totals["here"] += len(said.here)
                totals["unscaled"] += len(said.unscaled)
                totals["elsewhere"] += len(said.elsewhere)
                totals["nowhere"] += len(said.nowhere)
    assert totals == {"here": 194, "unscaled": 2, "elsewhere": 0, "nowhere": 3}, totals


def test_the_lost_column_is_on_a_page_the_harness_does_not_check(pdfs) -> None:
    """Why 194 right and 0 out of the wrong column was true and incomplete at once. The
    harness checks balance sheets, every table of which carries the statement's full column
    count; the table that dropped a column is on the cash flow statement. The two findings
    are consistent, and this is the assertion that keeps them so: the harness's pages report
    no gap, and the gap is where the harness is not."""
    covered = {
        (name, statement.page)
        for name, fixture in FIXTURES.items()
        for statement in fixture.statements
        if statement.page is not None
    }
    gapped: set[tuple[str, int]] = set()
    for name, doc in pdfs.items():
        for page in doc.pages:
            found = detect_periods(page.text, tables=list(page.tables))
            if any(s.startswith("columns:") and "gap" in s for s in found.ambiguous):
                gapped.add((name, page.number))
    assert gapped == {("sec-ars-3d-systems-2025", 59), ("sec-ars-3d-systems-2025", 104)}
    assert not gapped & covered, "a page the harness checks has lost a column"
