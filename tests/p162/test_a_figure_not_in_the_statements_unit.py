"""P162: a share count carried the statement's dollar scale, and three places multiply by it.

Found by `tools/check_against_filer.py` on EDGAR's own workbook, where a figure matched the
filer exactly and **only without the scale**:

    Common stock, shares, issued (in shares)        135,361,000   in the cell
    Common stock, par value (in dollars per share)        0.001    in the cell
    ... every dollar figure on the same sheet in thousands

The scale is per *file* - `SourceFile.scale`, applied to every row of it - and
`harness/procedures/ebitda_normalization.py`, `deliver/workpaper.py` and `harness/restate.py`
each multiply a figure by its scale. So the share count is reported as **135 billion** and
the par value as **$1.00**. Both are plausible numbers, which is exactly why nothing
downstream catches either: a total still foots, a balance sheet still balances, and the
figure cites a locator that resolves.

**The statement says so itself.** ResMed's balance sheet is headed *(In US$ and in thousands,
**except share and per share data**)*, and EDGAR writes the exception into each row's label.
Reading that is not guessing - it is what `two_sides` does with the two labels a balance
sheet writes and what `is_a_total` does with the word *total*.

**The contract was built for this and had never been exercised.** `figure.schema.json` has
carried `"unit": {"enum": [..., "shares"]}` since P02, allows a scale of 1, and *forbids* a
currency code on anything that is not currency. The producer only ever wrote `"currency"`.

**It does not bite on a PDF**, which is why one document could not have shown it: a typesetter
keeps the share count inside the label and the only figures in the column are dollars. It
bites on a workbook, and a client's workbook looks far more like a workbook than like
typesetting.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from intake.readers.units import DECLARES, declared_unit
from tools.normalize import _unit_of

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "fixtures" / "public"
sys.path.insert(0, str(ROOT))


def rows(*labels: str) -> list[tuple[object, dict[str, object], str]]:
    """The shape `_unit_of` is given: what the normalizer holds about each summed row."""
    return [
        (None, {"label": label, "value": 1.0}, f"p1/t1/r{n}")
        for n, label in enumerate(labels, 1)
    ]


# --------------------------------------------------------- what a label declares, and what not


@pytest.mark.parametrize(
    ("label", "unit"),
    [
        ("Common stock, shares, issued (in shares)", "shares"),
        ("Common stock, shares authorized (in shares)", "shares"),
        ("Basic (in shares)", "shares"),
        ("Beginning balance (in shares) at Dec. 31, 2023", "shares"),
        ("Common stock, par value (in dollars per share)", "currency"),
        ("Basic (in dollars per share)", "currency"),
        ("Conversion price (in dollars per share) | $ / shares", "currency"),
    ],
)
def test_a_row_that_declares_its_unit_is_not_at_the_statements_scale(
    label: str, unit: str
) -> None:
    """Every one of these is a real label off one of the three public filings."""
    said = declared_unit(label)
    assert said is not None, label
    assert said.unit == unit
    assert said.scale == 1, "the row's own scale, not the statement's"
    assert said.said, "and it carries the words that said so"


@pytest.mark.parametrize(
    "label",
    [
        # Ordinary dollar figures. The last three are the ones the rules I rejected broke.
        "Cash and cash equivalents",
        "Total assets",
        "Inventories",
        "Common stock, $0.001 par value, authorized 220,000 shares; shares issued 145,581 and",
        "Taxes paid related to net-share settlement of equity awards",
        "Treasury stock, at cost, 46,798,043 shares at June 30, 2026 and 2025",
    ],
)
def test_an_ordinary_figure_keeps_the_statements_scale(label: str) -> None:
    """**The direction that matters more.** A rule that stripped the scale from a real
    currency figure would be the same thousand-fold error the other way round, and the three
    labels at the end of this list are exactly where the looser rules did it.

    `Common stock, $0.001 par value, authorized 220,000 shares; shares issued 145,581 and`
    carries a figure of **146** on the filing's own balance sheet, which is $146 thousand.
    """
    assert declared_unit(label) is None, label


def test_the_rule_stops_at_a_parenthetical() -> None:
    """Said as a property rather than only by example: what makes a declaration is the
    parentheses, and prose about shares is prose."""
    assert DECLARES.search("(in shares)")
    assert DECLARES.search("Something (in dollars per share) qualified by a date")
    assert not DECLARES.search("in shares")
    assert not DECLARES.search("shares issued")
    assert not DECLARES.search("par value")
    assert not DECLARES.search("46,798,043 shares at June 30")


def test_the_row_this_does_not_catch_is_named() -> None:
    """The honest limit, from the same measurement. A row that is a share count and says so
    only in words is missed, and the one such row in three filings is a cover-page line
    rather than a statement's. Recorded here so it is a known limit rather than a surprise."""
    assert declared_unit("Entity Common Stock, Shares Outstanding") is None


# ----------------------------------------------- and the figure that is built from those rows


def test_a_figure_of_share_rows_is_in_shares_at_scale_one() -> None:
    """What the fix is for. 135,361,000 shares, not 135,361,000,000."""
    unit, scale, why = _unit_of(rows("Common stock, shares, issued (in shares)"), 1_000)
    assert unit == "shares"
    assert scale == 1
    assert "(in shares)" in why
    assert "1,000" in why, "and it says which scale it is declining to apply"


def test_a_figure_of_per_share_rows_is_currency_at_scale_one() -> None:
    """A per-share amount is money, so the unit stays currency - what differs is the scale.
    `figure.schema.json` requires a currency code on a currency figure, so calling this
    anything else would make the contract refuse it."""
    unit, scale, _ = _unit_of(rows("Basic (in dollars per share)"), 1_000)
    assert unit == "currency"
    assert scale == 1


def test_a_figure_of_ordinary_rows_keeps_the_files_scale() -> None:
    """Unchanged behaviour where a label says nothing, which is almost every row."""
    unit, scale, why = _unit_of(rows("Cash and cash equivalents", "Inventories"), 1_000)
    assert (unit, scale) == ("currency", 1_000)
    assert why == "", "and nothing is said about a figure nobody touched"


def test_rows_that_disagree_keep_the_files_scale_and_say_so() -> None:
    """Summing a share count with a dollar amount is meaningless at any scale, so there is
    no right answer to pick. What there is is a fact somebody needs.

    The figure stays as the file said - the behaviour that was there before - so a
    disagreement cannot quietly change a figure, and the sentence goes on the trail.
    """
    unit, scale, why = _unit_of(
        rows("Common stock, shares, issued (in shares)", "Cash and cash equivalents"),
        1_000,
    )
    assert (unit, scale) == ("currency", 1_000)
    assert "disagree" in why
    assert "(in shares)" in why


def test_no_currency_code_is_put_on_a_figure_that_is_not_currency() -> None:
    """`figure.schema.json` **forbids** it: *"Required when unit is currency, forbidden
    otherwise."* The conditional has been in the contract since P02 and the producer only
    ever wrote `currency`, so this is the first thing to exercise it."""
    import json

    schema = json.loads(
        (ROOT / "contracts" / "figure.schema.json").read_text(encoding="utf-8")
    )
    rule = next(
        r for r in schema["allOf"] if r.get("title") == "CURRENCY_REQUIRES_A_CURRENCY_CODE"
    )
    assert rule["then"] == {"required": ["currency"]}
    assert rule["else"] == {"not": {"required": ["currency"]}}
    assert "shares" in schema["properties"]["unit"]["enum"]
    assert 1 in schema["properties"]["scale"]["enum"]

    # And the producer honours it: a share figure gets no currency code.
    import inspect

    from tools import normalize

    source = inspect.getsource(normalize)
    assert 'if meta.get("currency") and unit == "currency":' in source


# ------------------------------------------- and through the figure, not past it


SOURCE = "sha256:" + "ab" * 32


def normalized(*rows_in: tuple[str, float]) -> dict[str, object]:
    """One file, one block, one period, through `timing_normalizer` itself.

    End to end on purpose. Every other test here calls `_unit_of` directly, and the revert
    harness showed what that misses: breaking the **call site** - the line in the figure
    assembly that asks the rows what they are in - left all of them green. A unit rule with
    tests on the rule and none on the wire is this repository's most repeated defect wearing
    a new hat.
    """
    from tools.normalize import timing_normalizer

    sources = {
        SOURCE: {
            "'Sheet1'!B2:B9": [
                # The ordinal *is* the row number inside the block: the block below is
                # B2:B9, so a row's ordinal and the locator that cites it have to agree,
                # and `_row_for` resolves a locator by matching them.
                {"label": label, "value": value, "raw": str(value), "ordinal": n}
                for n, (label, value) in enumerate(rows_in, start=2)
            ]
        }
    }
    files = {SOURCE: {"scale": 1_000, "currency": "USD", "source_version": 1}}
    mapping = {
        "periods": [
            {
                "source_id": SOURCE,
                "block": "'Sheet1'!B2:B9",
                "label": "FY2025",
                "type": "FY",
                "end": "2025-12-31",
            }
        ],
        "line_items": [
            {
                "canonical_label": "the line",
                "kind": "exact",
                "sources": [
                    {
                        "source_id": SOURCE,
                        "locator": f"'Sheet1'!B{n}",
                        "label": label,
                    }
                    for n, (label, _value) in enumerate(rows_in, start=2)
                ],
            }
        ],
    }
    out = timing_normalizer(
        mapping=mapping, sources=sources, files=files, model_pin="pin@1"
    )
    # The whole result, not only `output`: the derivation trail comes back beside it under
    # `rows`, and the trail is where a sentence about a figure has to land.
    return out


def test_a_share_row_reaches_the_figure_in_shares_at_scale_one() -> None:
    """**The wire, which nothing tested until the harness asked.**

    135,361,000 shares at scale 1. At the file's scale of a thousand this figure would say
    135,361,000,000, and `deliver/workpaper.py` would print it.
    """
    output = normalized(("Common stock, shares, issued (in shares)", 135_361_000.0))
    (item,) = output["output"]["normalized_historicals"]["line_items"]
    (figure,) = item["values"]
    assert figure["unit"] == "shares"
    assert figure["scale"] == 1
    assert figure["value"] == 135_361_000.0
    assert "currency" not in figure, (
        "figure.schema.json forbids a currency code on anything that is not currency"
    )
    assert float(figure["value"]) * int(figure["scale"]) == 135_361_000.0


def test_a_per_share_row_reaches_the_figure_as_currency_at_scale_one() -> None:
    """A par value of $0.001, not $1.00 - and it keeps its currency code, because it is
    money."""
    output = normalized(("Common stock, par value (in dollars per share)", 0.001))
    (figure,) = output["output"]["normalized_historicals"]["line_items"][0]["values"]
    assert figure["unit"] == "currency"
    assert figure["scale"] == 1
    assert figure["currency"] == "USD"
    assert float(figure["value"]) * int(figure["scale"]) == 0.001


def test_an_ordinary_row_reaches_the_figure_at_the_files_scale() -> None:
    """Unchanged, which is the half of this that must not move: 521,728 at a thousand is
    $521,728,000, and that is what the filer reported."""
    output = normalized(("Total assets", 521_728.0))
    (figure,) = output["output"]["normalized_historicals"]["line_items"][0]["values"]
    assert figure["unit"] == "currency"
    assert figure["scale"] == 1_000
    assert figure["currency"] == "USD"
    assert float(figure["value"]) * int(figure["scale"]) == 521_728_000.0


def test_a_figure_from_rows_that_disagree_keeps_the_files_scale_and_says_so() -> None:
    """Through the figure as well, because the sentence has to reach the trail a person
    reads rather than stopping at the function that composed it."""
    output = normalized(
        ("Common stock, shares, issued (in shares)", 135_361_000.0),
        ("Total assets", 521_728.0),
    )
    (figure,) = output["output"]["normalized_historicals"]["line_items"][0]["values"]
    assert figure["unit"] == "currency"
    assert figure["scale"] == 1_000
    said = str(output["rows"])
    assert "disagree" in said, said[:400]
    assert "unit_declared_by_the_row" in said


# ------------------------------------------------------- over the filings, nothing else moved


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
        for _locator, got in table.blocks.items():
            out += [(book, r.label, r.value) for r in got if r.value is not None]
    return out


def test_the_measurement_the_rule_was_settled_on(every_row) -> None:
    """2,373 rows, 53 of them declared, over 22 distinct labels.

    The numbers are asserted because they are the argument: a rule calibrated on a document
    and then not checked against it is a rule nobody can audit. **Both counts**, because the
    measurement that settled the anchor keyed on the locator too, so its 25 counts the
    same label in two blocks twice and is a third fact again.
    """
    assert len(every_row) == 2_373, f"the corpus moved to {len(every_row)} rows"
    declared = [
        (where, label, value)
        for where, label, value in every_row
        if declared_unit(label) is not None
    ]
    assert len(declared) == 53, [label for _, label, _ in declared]
    assert len({(w, label) for w, label, _ in declared}) == 22

    # Every one of them is on the workbook, which is the point about where this bites.
    assert {where for where, _, _ in declared} == {
        "sec-financial-report-3d-systems-2025q1.xlsx"
    }, {where for where, _, _ in declared}


def test_no_row_on_either_pdf_declares_a_unit(every_row) -> None:
    """Why one document could not have found this. A typesetter keeps the share count inside
    the label, so every figure in a PDF column is a dollar amount and the statement's scale
    is right for all of them."""
    for where, label, _value in every_row:
        if where.endswith(".pdf"):
            assert declared_unit(label) is None, f"{where}: {label}"


def test_nothing_that_was_currency_stopped_being_currency(every_row) -> None:
    """The exit criterion in the dangerous direction, over the whole corpus.

    A figure built from rows that declare nothing has to keep the file's scale, and that is
    2,320 of the 2,373 rows here. This is the assertion that would catch a rule widened later
    for a case somebody met.
    """
    kept = 0
    for _where, label, _value in every_row:
        if declared_unit(label) is not None:
            continue
        unit, scale, why = _unit_of(rows(label), 1_000)
        assert (unit, scale) == ("currency", 1_000), label
        assert why == ""
        kept += 1
    assert kept == 2_320, kept
