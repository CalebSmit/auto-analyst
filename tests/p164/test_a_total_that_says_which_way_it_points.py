"""P164: a total that says which way it points.

Every tie-out in `intake/readers/footing.py` passes a statement whose every sign is
inverted. Rows of -12,000 and -3,000 under a total of -15,000 re-add, and so do the same
three flipped positive; two sides that agree at 521,728 agree at -521,728; cash rolls
forward to a negative balance as readily as to a positive one. A cash flow investing or
financing section is **all negative**, so a column read with every sign flipped foots
exactly - and arithmetic cover is the evidence that will decide whether a person looks at
a figure at all. The analyst's rule is *a figure is proved by arithmetic, or it is seen*,
and this was a proof that proved nothing, under which the figure was neither.

What catches it is not arithmetic but a statement about the table: `Total assets` is not
negative, `Net cash used in financing activities` is not positive. The whole of the rule is
the line between a label that cannot honestly go either way and one that can - and the
second kind says nothing. **Calibrated over every row of the three public filings**, 2,373
of them: the phrases kept read **69** rows and contradict **none**; every phrase rejected
was rejected on a row that fired, and the reasons are written beside the rule.

A contradiction withdraws the arithmetic cover of its whole block, not its row, because on
a flipped column the rows carrying no direction word look right and the one row that does
is the only thing that saw it. The footings are kept - the arithmetic did re-add - and what
they stop being is cover. Reported, never repaired.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from intake.readers.documents import read_document
from intake.readers.footing import (
    Contradiction,
    footings_in,
    is_a_change_column,
    sign_contradictions,
    states_a_direction,
)
from intake.readers.workbook import normalize_workbook, survey_workbook

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "fixtures" / "public"


@dataclass(frozen=True)
class R:
    label: str
    value: float | None
    ordinal: int = 0
    raw: str = ""


def rows(*pairs: tuple[str, float | None]) -> list[R]:
    return [R(label, value, n) for n, (label, value) in enumerate(pairs, start=1)]


@pytest.fixture(scope="module")
def corpus() -> list[tuple[str, str, str, list]]:
    """Every block of the three filings: (file, locator, heading, rows)."""
    out: list[tuple[str, str, str, list]] = []
    for name in ("sec-ars-3d-systems-2025.pdf", "sec-ars-resmed-2026.pdf"):
        doc = read_document((PUBLIC / name).read_bytes(), name)
        for page in doc.pages:
            for table in page.tables:
                for column in table.columns:
                    out.append((name, table.locator_for(column), column.heading, list(column.rows)))
    book = "sec-financial-report-3d-systems-2025q1.xlsx"
    data = (PUBLIC / book).read_bytes()
    survey = survey_workbook(data)
    for table in normalize_workbook(data, [s.name for s in survey.sheets if s.readable]):
        for locator, block in table.blocks.items():
            out.append((book, locator, table.block_headers.get(locator, ""), list(block)))
    return out


# ------------------------------------------------------------- the proof that proved nothing


def test_every_tie_out_passes_a_wholly_negated_column() -> None:
    """The defect, stated as the three tie-outs state it. Kept green on purpose: this is
    what arithmetic can and cannot see, and the sign check is built beside it rather than
    into it."""
    from intake.readers.footing import cash_roll_forward, two_sides

    right = rows(("Cash", 12_000.0), ("Receivables", 3_000.0), ("Total current assets", 15_000.0))
    wrong = rows(
        ("Cash", -12_000.0), ("Receivables", -3_000.0), ("Total current assets", -15_000.0)
    )
    assert footings_in(right).foots is True
    assert footings_in(wrong).foots is True, "arithmetic cannot see a flipped column"

    assert two_sides(
        rows(
            ("Total assets", -521_728.0),
            ("Total liabilities and stockholders' equity", -521_728.0),
        )
    ).balances is True
    assert cash_roll_forward(
        rows(
            ("Cash at beginning of year", -100_000.0),
            ("Net decrease in cash", 4_365.0),
            ("Cash at end of year", -95_635.0),
        )
    ).rolls_forward is True


def test_a_contradiction_withdraws_the_cover_of_the_whole_block() -> None:
    """The footing still re-adds and is still reported - it is a fact about the arithmetic.
    What it no longer is is cover: no ordinal in the block counts as proved."""
    wrong = rows(
        ("Cash", -12_000.0), ("Receivables", -3_000.0), ("Total current assets", -15_000.0)
    )
    report = footings_in(wrong)
    assert report.foots is True
    assert report.totals == 1
    assert report.covered_ordinals == frozenset()
    assert [c.label for c in report.contradictions] == ["Total current assets"]
    assert report.contradictions[0].states == "not negative"
    assert report.contradictions[0].value == -15_000.0
    assert "contradict the direction the label states" in report.as_line()
    assert "no row is covered by a total" in report.as_line()

    right = rows(("Cash", 12_000.0), ("Receivables", 3_000.0), ("Total current assets", 15_000.0))
    assert footings_in(right).covered_ordinals == frozenset({1, 2})
    assert footings_in(right).contradictions == ()


def test_a_negated_balance_sheet_is_reported_with_its_rows_named(corpus) -> None:
    """On the two real balance sheets, with column one negated: seven rows each, and the
    cover goes from twenty-odd rows to none. On 3D's cash flow statement, three."""
    expected = {
        ("sec-ars-3d-systems-2025.pdf", 56): (7, 26),
        ("sec-ars-resmed-2026.pdf", 79): (7, 28),
        ("sec-ars-3d-systems-2025.pdf", 59): (3, 0),
    }
    for (name, page), (hits, cover) in expected.items():
        found: list[str] = []
        before = after = 0
        for file, locator, heading, block in corpus:
            if file != name or not locator.startswith(f"p{page}/") or not locator.endswith("/c1"):
                continue
            flipped = [
                R(r.label, -r.value if r.value is not None else None, r.ordinal) for r in block
            ]
            was, now = footings_in(block, heading), footings_in(flipped, heading)
            before += len(was.covered_ordinals)
            after += len(now.covered_ordinals)
            found += [c.label for c in now.contradictions]
        assert len(found) == hits, (name, page, found)
        assert (before, after) == (cover, 0), (name, page, before, after)
        if page != 59:
            assert "Total assets" in found and "Total liabilities" in found


# ----------------------------------------------------------- the rule, and what it refuses


def test_the_phrases_that_cannot_go_either_way() -> None:
    assert states_a_direction("Total assets") == "not negative"
    assert states_a_direction("TOTAL CURRENT ASSETS") == "not negative"
    assert states_a_direction("Total liabilities and stockholders' equity") == "not negative"
    assert states_a_direction("Net cash used in operating activities") == "not positive"
    assert states_a_direction("Net cash used for investing activities") == "not positive"
    assert states_a_direction("Net decrease in cash and cash equivalents") == "not positive"
    assert states_a_direction("Accumulated deficit") == "not positive"
    assert states_a_direction("Treasury stock, at cost, 46,798,043 shares") == "not positive"
    assert states_a_direction("Accumulated other comprehensive loss") == "not positive"


def test_a_label_that_carries_both_directions_says_nothing() -> None:
    """Most of the section lines on an audited cash flow statement. ResMed's reads
    `Net cash provided by (used in) investing activities` on every section, so a negated
    ResMed cash flow statement is **not** caught - which is the honest shape of this."""
    assert states_a_direction("Net cash provided by (used in) investing activities") is None
    assert states_a_direction("Net increase (decrease) in cash") is None
    assert states_a_direction("Retained earnings (accumulated deficit)") is None
    assert states_a_direction("Accumulated other comprehensive income (loss)") is None


def test_the_phrases_rejected_on_the_filings() -> None:
    """Each of these fired on a known-good row, or is of the same class as one that did,
    and the reason is recorded beside the rule. An expense is printed positive on one
    statement and negative on the next page; a proceed inside a roll-forward is a deduction;
    equity goes negative in a deficit and cash in an overdraft; accounting software prints
    `Net Income -96,083` under a fixed label."""
    for label in (
        "Interest expense",
        "Depreciation and amortization",
        "Cost of sales",
        "Gross profit",
        "Proceeds from sale of assets",
        "Repayments of borrowings",
        "Payments for legal settlements",
        "Purchases of property and equipment",
        "Dividends paid",
        "Total stockholders' equity",
        "Cash and cash equivalents at end of period",
        "Net cash provided by operating activities",
        "Net increase in cash",
        "Net income",
        "Net loss",
        "Treasury stock purchases",
        "Weighted average shares outstanding",
        "Revenue",
    ):
        assert states_a_direction(label) is None, label


def test_a_column_of_changes_is_left_alone() -> None:
    """A negative revenue under `Change` is a fall, and contradicts nothing. Page 30 of the
    3D filing is headed `2025 2024 Change` and its third column is where a wide rule read
    `Revenue -53,219` as a wrong sign."""
    assert is_a_change_column("Change") is True
    assert is_a_change_column("% Change") is True
    assert is_a_change_column("Increase (decrease)") is True
    assert is_a_change_column("2025") is False
    assert is_a_change_column("") is False
    block = rows(("Total assets", -53_219.0))
    assert sign_contradictions(block, "Change") == ()
    assert len(sign_contradictions(block, "2025")) == 1
    assert len(sign_contradictions(block, "")) == 1


def test_zero_and_nil_contradict_nothing() -> None:
    assert sign_contradictions(rows(("Total assets", 0.0), ("Accumulated deficit", None))) == ()


def test_a_contradiction_reads_as_a_sentence() -> None:
    said = Contradiction(ordinal=3, label="Total assets", value=-521_728.0, states="not negative")
    assert said.as_line() == "Total assets is -521,728.00, and the label says it is not negative"


# ------------------------------------------------------- calibrated, and the counts asserted


def test_the_rule_reads_sixty_nine_rows_and_contradicts_none(corpus) -> None:
    """2,373 rows carrying a value over three audited filings the reader gets right. Every
    firing here would be a false positive, and there are none - and the number of rows the
    rule reads at all is asserted so its coverage cannot be overstated: 69, which is 2.9%,
    and they are the grand and section totals, which is one row of every block that is
    wrong on every row of a flipped column."""
    total = sum(1 for *_, block in corpus for r in block if r.value is not None)
    read = [
        (file, r.label)
        for file, _, _, block in corpus
        for r in block
        if r.value is not None and states_a_direction(r.label)
    ]
    fired = [
        (file, locator, c.as_line())
        for file, locator, heading, block in corpus
        for c in sign_contradictions(block, heading)
    ]
    assert total == 2_373, total
    assert len(read) == 69, len(read)
    assert fired == [], fired


def test_the_three_tie_outs_still_say_what_they_said(corpus) -> None:
    """Cover over the unchanged corpus is exactly what it was before this phase, because
    no block of it holds a contradiction: 262 of 815 rows covered on the 3D filing, 230 of
    960 on ResMed's, 116 of 598 on the workbook. Measured with the sign check in place and
    with it taken out, identically - which is the assertion that would notice a phrase
    widened later for a case somebody met."""
    covered: dict[str, list[int]] = {}
    for file, _, heading, block in corpus:
        report = footings_in(block, heading)
        covered.setdefault(file, [0, 0])
        covered[file][0] += len(report.covered_ordinals)
        covered[file][1] += report.rows
    assert covered["sec-ars-3d-systems-2025.pdf"] == [262, 815], covered
    assert covered["sec-ars-resmed-2026.pdf"] == [230, 960], covered
    assert covered["sec-financial-report-3d-systems-2025q1.xlsx"] == [116, 598], covered


def test_a_document_column_headed_change_is_left_alone_on_the_wire(
    store, parse_store, boundary, started, bus
) -> None:
    """The document reader hands each block's heading to the footing check. Asserted
    through `read_source` rather than by calling `footings_in` with a heading, because the
    revert harness found that cutting the hand-over in the reader left every test green:
    the corpus holds no change column with a direction row in it, so nothing on it could
    tell. A `.txt` statement headed `2025 Change` with `Total assets` falling by 53,219 is
    the case the hand-over exists for - a wrong sign under 2025, a movement under Change."""
    from intake.readers import read_source
    from tests.p17.conftest import ENGAGEMENT, intake_row

    statement = "\n".join(
        [
            "CONSOLIDATED BALANCE SHEETS",
            "(in thousands of US dollars)",
            "                          2025        Change",
            "Cash                   100,000       (40,000)",
            "Receivables             50,000       (13,219)",
            "Total assets           150,000       (53,219)",
        ]
    ).encode("utf-8")
    report = read_source(
        started,
        ENGAGEMENT,
        intake_row("bs.txt", statement, "document"),
        statement,
        store=store,
        parse_store=parse_store,
        boundary=boundary,
        bus=bus,
    )
    assert "p1/t1/c2" in report.footing, sorted(report.footing)
    assert report.footing["p1/t1/c2"].contradictions == (), report.signs_contradicted
    assert report.signs_contradicted == ()
    # And the same rows under a year heading are the wrong sign they look like - so it is
    # the heading, handed over by the reader, that kept the check quiet.
    rows_under_change = read_document(statement, "bs.txt").blocks()["p1/t1/c2"]
    assert [c.label for c in sign_contradictions(rows_under_change, "2025")] == ["Total assets"]
    assert sign_contradictions(rows_under_change, "Change") == ()


# ------------------------------------------------------------ and where a person reads it


def test_the_read_report_names_the_rows_and_the_event_carries_them(
    store, parse_store, boundary, started, bus
) -> None:
    """Through `read_source` itself, with a workbook whose balance sheet column is wholly
    negated - so the sentence reaches the parse-summary event a person reads, beside the
    totals that did and did not re-add."""
    import io

    from openpyxl import Workbook

    from intake.readers import read_source
    from tests.p17.conftest import ENGAGEMENT, intake_row

    book = Workbook()
    sheet = book.active
    sheet.title = "BS"
    for row in (
        ["Balance Sheet", None],
        ["($000s)", None],
        [None, "FY2025"],
        ["Cash", -12_000],
        ["Receivables", -3_000],
        ["Total current assets", -15_000],
        ["Total assets", -15_000],
    ):
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    data = buffer.getvalue()

    report = read_source(
        started,
        ENGAGEMENT,
        intake_row("bs.xlsx", data, "spreadsheet"),
        data,
        store=store,
        parse_store=parse_store,
        boundary=boundary,
        bus=bus,
    )
    (read,) = [e for e in store.events(started) if e.type == "intake.read"]
    payload = read.payload
    assert report.signs_contradicted, "the report should name the contradicted rows"
    assert any("Total assets is -15,000.00" in line for line in report.signs_contradicted)
    assert report.covered_rows == 0
    assert payload["signs_contradicted"] == list(report.signs_contradicted)
    assert payload["rows_covered_by_a_total"] == 0
