"""P76: a real filing, kept as the document that finds things.

Every other fixture here is synthetic, and a synthetic document is written by whoever wrote
the code that reads it - so it agrees with that code. The first time the Document Reader
met a real financial statement it took the wrong column of a comparative balance sheet.

`Cash and cash equivalents $ 95,635 $ 171,324` is one line of a real annual report. The
reader matches one figure per row anchored to the end of the line, so it takes **171,324**
- the prior year - and swallows the current year into the label. Every figure in the run
becomes last year's, and both guards pass: provenance passes because the number really is
at that locator, and footing passes because the rows are consistently prior-year so the
totals still re-add.

That is B-030, written down as a prediction in the backlog and never demonstrated until a
real document was put in front of it.

The pair that matters is `test_the_reader_still_takes_the_wrong_column` and
`test_the_escalation_fires_on_every_comparative_page`. The first pins a defect that has not
been fixed, so that fixing it is a decision somebody makes rather than a surprise. The
second pins the only thing standing between this document and a silently wrong model - if
it ever stops firing while the first still fails, the run proceeds on last year's balance
sheet.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from intake.readers.documents import read_document
from intake.readers.periods import detect_periods

ROOT = Path(__file__).resolve().parents[2]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"

BALANCE_SHEET = 56
COMPARATIVE = (56, 57, 58)
IMAGE_ONLY = (107, 108)


@pytest.fixture(scope="module")
def filing():
    return read_document(FILING.read_bytes(), FILING.name)


# ------------------------------------------------------------------ it is what it says


def test_the_filing_is_here_with_its_provenance() -> None:
    """A public document is only public if somebody can check where it came from."""
    assert FILING.is_file()
    readme = (FILING.parent / "README.md").read_text(encoding="utf-8")
    assert "https://www.sec.gov/Archives/edgar/data/910638/" in readme
    assert "Retrieved" in readme and "2026-09-19" in readme


def test_the_fixtures_rule_permits_it_everywhere_the_rule_is_written() -> None:
    """Three places say what a fixture may be. A rule widened in one of them is a rule that
    disagrees with itself the next time somebody reads a different copy."""
    for where in ("CLAUDE.md", "fixtures/README.md", "tools/bootstrap_scaffold.py"):
        text = (ROOT / where).read_text(encoding="utf-8")
        assert "public" in text and "synthetic" in text, where
        assert "masked or synthetic, always" not in text, f"{where} still says the old rule"


# ------------------------------------------------------------------ what the reader does


def test_it_reads_a_hundred_page_filing(filing) -> None:
    assert len(filing.pages) == 108
    assert sum(len(p.tables) for p in filing.pages) > 40
    assert sum(len(t.rows) for p in filing.pages for t in p.tables) > 150


def test_the_image_only_pages_are_reported_as_scanned(filing) -> None:
    """Real scanned pages, in a real filing - not one manufactured for a test."""
    scanned = {p.number for p in filing.pages if p.scanned}
    assert scanned == set(IMAGE_ONLY), scanned


def test_a_page_of_prose_is_not_mistaken_for_a_scan(filing) -> None:
    blank = next(p for p in filing.pages if p.number == 106)
    assert not blank.scanned
    assert "INTENTIONALLY LEFT BLANK" in blank.text


def test_the_balance_sheet_rows_are_recovered(filing) -> None:
    page = next(p for p in filing.pages if p.number == BALANCE_SHEET)
    labels = [row.label for table in page.tables for row in table.rows]
    assert any("Cash and cash equivalents" in label for label in labels)
    assert any("Total current assets" in label for label in labels)


# ------------------------------------------------------------------ the defect, pinned


def test_the_reader_still_takes_the_wrong_column(filing) -> None:
    """B-030, demonstrated rather than predicted.

    Pinned as it is, not as it should be. When somebody builds B-030 this test fails, and
    that failure is the reminder to come back here and say what the new answer is - which
    is better than a defect that quietly stops being true.
    """
    page = next(p for p in filing.pages if p.number == BALANCE_SHEET)
    line = next(line for line in page.lines if line.text.startswith("Cash and cash equivalents"))
    assert line.text == "Cash and cash equivalents $ 95,635 $ 171,324", line.text

    row = next(
        row
        for table in page.tables
        for row in table.rows
        if row.label.startswith("Cash and cash equivalents")
    )
    assert row.value == 171324.0, "the prior year, which is the defect"
    assert "95,635" in row.label, "the current year, swallowed into the label"


def test_both_guards_would_pass_on_that_row(filing) -> None:
    """Why the escalation is the only defence. The figure is really at that locator, so
    provenance is satisfied; and the whole column is consistently prior-year, so anything
    that re-adds the rows still balances."""
    page = next(p for p in filing.pages if p.number == BALANCE_SHEET)
    rows = [row for table in page.tables for row in table.rows]
    assert all(str(int(row.value)) in row.raw.replace(",", "") for row in rows[:6]), (
        "each value really is on the line it cites"
    )


def test_the_escalation_fires_on_every_comparative_page(filing) -> None:
    """The only thing between this document and a run built on last year's figures."""
    for number in COMPARATIVE:
        page = next(p for p in filing.pages if p.number == number)
        found = detect_periods(page.text)
        columns = [a for a in found.ambiguous if a.startswith("columns:")]
        assert columns, f"page {number} carries multiple columns and did not escalate"
        assert "more than one period" in columns[0]


def test_a_single_column_page_does_not_escalate(filing) -> None:
    """A rule that escalated everything would be no rule. Somewhere in a hundred pages
    there is ordinary text, and it must pass."""
    quiet = [
        p.number
        for p in filing.pages
        if p.text.strip()
        and not [a for a in detect_periods(p.text).ambiguous if a.startswith("columns:")]
    ]
    assert quiet, "every page in the filing escalated, so the check says nothing"


# ------------------------------------------------------------------ the OCR benchmark


def test_the_ocr_benchmark_runs_or_says_why(ocr_engine) -> None:
    """Accuracy on a real statement, measured against the document's own text layer.

    Behind `--ocr` because it needs an engine most machines do not have - the same
    arrangement as postgres, redis and the container, and for the same reason: a check that
    quietly skips is a check nobody knows did not run.

    What it establishes is an upper bound, not a forecast. These pages were born digital and
    rendered to images, so they have no skew, no scanner noise and no photocopy generation
    loss. A client's scan has all three.
    """
    engine, render = ocr_engine
    data = FILING.read_bytes()
    truth = {p.number: p for p in read_document(data, FILING.name).pages}
    figure = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")

    document = render.PdfDocument(data)
    try:
        for number in COMPARATIVE:
            page = engine.read_one(document, number)
            want = figure.findall(truth[number].text)
            got = set(figure.findall("\n".join(line.text for line in page.lines)))
            missed = [f for f in want if f not in got]
            share = 1 - len(missed) / len(want)
            assert share >= 0.95, (
                f"page {number}: {share:.1%} of figures read, missed {missed[:8]}"
            )
    finally:
        document.close()
