"""C92 - a number that passes every arithmetic check and is wrong.

Two phases about the same thing from two ends. **P164**: a statement whose every sign is
inverted re-adds, balances and rolls forward, so arithmetic cover - the evidence that will
decide whether a person looks - was granted to a column nobody should trust. **P165**: a
share count that P162 correctly left at scale 1 was divided by a thousand on its way into
the workbook, because the restater read its scale and never its unit, and the refusal that
would have caught it was made unreachable by the division itself.

Neither phase's own tests can ask the question this one asks: does one workbook, carrying
both defects, come out the far end with the sign contradiction withdrawing the cover **and**
the share count neither divided nor written? The readers, the normalizer, the restater and
the writer each pass alone. This is the test that they still agree.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from openpyxl import Workbook

from harness.restate import restated
from registries.errors import RegistryError

SOURCE = "sha256:" + "ab" * 32


def workbook() -> bytes:
    """A balance sheet in thousands with every sign inverted, and the one row a filer
    prints in shares - the two things nothing arithmetic can see."""
    book = Workbook()
    sheet = book.active
    sheet.title = "BS"
    for row in (
        ["Balance Sheet", None],
        ["($000s, except share data)", None],
        [None, "FY2025"],
        ["Cash", -12_000],
        ["Receivables", -3_000],
        ["Total current assets", -15_000],
        ["Total assets", -15_000],
        ["Common stock, shares, issued (in shares)", 135_361_000],
    ):
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_the_cover_is_withdrawn_and_the_count_is_left_alone(
    store, parse_store, boundary, started, bus
) -> None:
    from intake.readers import read_source
    from tests.p17.conftest import ENGAGEMENT, intake_row
    from tools.normalize import timing_normalizer

    data = workbook()
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

    # P164: the block holds a contradiction, so nothing in it is covered - the share row
    # included, which sits under no total anyway.
    (locator,) = report.footing
    footing = report.footing[locator]
    assert [c.label for c in footing.contradictions] == ["Total current assets", "Total assets"]
    assert footing.covered_ordinals == frozenset()
    assert report.covered_rows == 0
    assert any("Total assets is -15,000.00" in line for line in report.signs_contradicted)

    # The rows, as the parse store holds them, into the normalizer with an identity
    # mapping - the same end-to-end shape `tests/p162` built, so a figure is made from the
    # real rows rather than from a dict typed here.
    source_id = intake_row("bs.xlsx", data, "spreadsheet").source_id
    rows = list(parse_store.rows(started, source_id, locator))
    sources = {
        SOURCE: {
            locator: [
                dict(label=r.label, value=r.value, raw=r.raw, ordinal=r.ordinal) for r in rows
            ]
        }
    }
    files = {SOURCE: {"scale": 1_000, "currency": "USD", "source_version": 1}}
    # A block locator reads `BS!B4:B8`; a row's ordinal is its sheet row, so its locator is
    # the block's sheet and column with that row - which is how `_row_for` resolves it.
    sheet_column, _first = locator.split(":")[0].rsplit("B", 1)
    mapping: dict[str, Any] = {
        "periods": [
            {
                "source_id": SOURCE,
                "block": locator,
                "label": "FY2025",
                "type": "FY",
                "end": "2025-12-31",
            }
        ],
        "line_items": [
            {
                "canonical_label": r.label,
                "kind": "exact",
                "sources": [
                    {
                        "source_id": SOURCE,
                        "locator": f"{sheet_column}B{r.ordinal}",
                        "label": r.label,
                    }
                ],
            }
            for r in rows
            if r.value is not None
        ],
    }
    out = timing_normalizer(mapping=mapping, sources=sources, files=files, model_pin="pin@1")
    figures = {
        item["canonical_label"]: item["values"][0]
        for item in out["output"]["normalized_historicals"]["line_items"]
    }
    shares = figures["Common stock, shares, issued (in shares)"]
    assets = figures["Total assets"]
    assert (shares["unit"], shares["scale"], shares["value"]) == ("shares", 1, 135_361_000.0)
    assert (assets["unit"], assets["scale"], assets["value"]) == ("currency", 1_000, -15_000.0)

    # P165: into a template in thousands, the count is left as it came and listed; the
    # dollar figure is already at that scale and untouched.
    moved, moves, left = restated({"shares": shares, "assets": assets}, 1_000)
    assert moved["shares"] is shares
    assert moves == ()
    assert [alone.figure_ref for alone in left] == ["shares"]

    # And a cell bound to the count is refused for what it is, not for its scale.
    from deliver.builder import _value_of

    with pytest.raises(RegistryError) as refused:
        _value_of(moved["shares"], 1_000, "USD", "Shares_FY1")
    assert "a count of shares" in str(refused.value)
    assert "does not happen in the writer" not in str(refused.value)
    assert _value_of(moved["assets"], 1_000, "USD", "Total_Assets_FY1") == -15_000.0
