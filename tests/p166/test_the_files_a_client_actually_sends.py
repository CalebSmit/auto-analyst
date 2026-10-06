"""P166: the files a client actually sends.

Sixty-three malformed, hostile and degenerate files were put through the readers. Every
refusal came back as one of the two intended codes, and every finding was on the other
side - on a file that was *read*:

* a CSV holding two decimal conventions read `402,000` as **402.0**, a thousand times out,
  with nothing said, because the convention was taken from the first cell that settled it
  and the reporting lived behind "no convention";
* `(12,000 )` - a space before the parenthesis, which several packages pad - read as
  **+12,000**, because `_number` wanted both ends and threw the orphan away; `12,000-` and
  the unicode minus read as positive in one reader and made the other return no table;
* a PNG read with no OCR engine was recorded exactly like a readable file that held no
  figures - `0 block(s) written`, classified, no review item - although
  `ParsedDocument.scanned_pages()` had the answer and one test called it;
* a password-protected workbook was reported as corrupt, with advice to ask the client for
  a readable copy of a file that was whole; a PDF under an .xlsx name got `BadZipFile`
  where the document branch would have said what it was; a tab-separated file under an
  .xls name got xlrd's "Expected BOF record"; a UTF-16 export was refused by coincidence,
  three layers down, by openpyxl objecting to a NUL.

Each is reported rather than resolved, and each is calibrated: the three public filings
read exactly as they did, to the row.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from openpyxl import load_workbook

from intake.readers.documents import _number, read_document
from intake.readers.layout import _ESTABLISHES, _FILLS, _NIL
from intake.readers.tabular import _convention, _decode, as_workbook
from registries.errors import DiagnosticError
from tests.p156.test_a_file_that_will_not_open import PNG, read

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "fixtures" / "public"
OLE2 = bytes.fromhex("d0cf11e0a1b11ae1")


def grid(*rows: str) -> list[list[str]]:
    return [row.split(";") for row in rows]


# ------------------------------------------------------------- two decimal conventions


def test_a_grouped_figure_the_other_way_is_not_read_as_a_decimal() -> None:
    """The thousand-fold error this was found by: `1.234,56` settles the decimal as `,`
    and then `402,000` - a comma-grouped integer - read as 402.0."""
    decimal, ambiguous, why = _convention(grid("Revenue;1.234,56", "Cash;402,000"))
    assert decimal == ","
    assert ambiguous == {"402,000"}
    assert why.startswith("the file is telling two stories")

    done = as_workbook(b"Account;Amount\nRevenue;1.234,56\nCash;402,000\n", "tb.csv")
    assert done.decimal == ","
    assert done.contradiction == why
    sheet = load_workbook(io.BytesIO(done.workbook)).active
    values = [row[1].value for row in sheet.iter_rows(min_row=2)]
    assert values == [1234.56, "402,000"], "the settled one read, the other left as text"
    assert 402.0 not in values


def test_two_decimal_shapes_decide_nothing_and_say_so() -> None:
    """`1,234.56` beside `1.234,56`: each can only be read one way and they disagree, so
    the file decides nothing and every grouped figure is left as text."""
    decimal, ambiguous, why = _convention(grid("Revenue;1,234.56", "Odd;1.234,56", "Cash;402,000"))
    assert decimal == ""
    assert ambiguous == {"1,234.56", "1.234,56", "402,000"}
    assert "two stories" in why
    done = as_workbook(b"Account;Amount\nRevenue;1,234.56\nOdd;1.234,56\nCash;402,000\n", "tb.csv")
    sheet = load_workbook(io.BytesIO(done.workbook)).active
    values = [row[1].value for row in sheet.iter_rows(min_row=2)]
    assert values == ["1,234.56", "1.234,56", "402,000"]
    assert 1.23456 not in values and 402.0 not in values


def test_one_story_still_reads_as_it_did() -> None:
    assert _convention(grid("Revenue;1,234.56", "Cash;402,000")) == (".", set(), "")
    assert _convention(grid("Revenue;1.234,56", "Cash;402.000")) == (",", set(), "")


# ---------------------------------------------------------------------- signs and glyphs


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("(12,000)", -12_000.0),
        ("(12,000 )", -12_000.0),
        ("( 12,000)", -12_000.0),
        ("12,000-", -12_000.0),
        ("−12,000", -12_000.0),
        ("$−12,000", -12_000.0),
        ("-12,000", -12_000.0),
        ("12,000", 12_000.0),
        ("12,000)", None),
        ("(12,000", None),
        ("-", None),
    ],
)
def test_the_document_number_parser(text: str, value: float | None) -> None:
    assert _number(text) == value


def test_the_line_reader_reads_padded_and_trailing_negatives() -> None:
    statement = "\n".join(
        [
            "CONSOLIDATED STATEMENT OF CASH FLOWS",
            "(in thousands of US dollars)",
            "                                          2025        2024",
            "Purchases of property and equipment    (12,000 )   (10,000 )",
            "Accumulated depreciation                12,000-     10,000-",
            "Research and development               −12,000    −10,000",
            "Net cash used in investing activities  (36,000 )   (30,000 )",
        ]
    ).encode("utf-8")
    doc = read_document(statement, "cf.txt")
    values = {
        row.label: row.value
        for page in doc.pages
        for table in page.tables
        for row in table.columns[0].rows
    }
    assert values == {
        "Purchases of property and equipment": -12_000.0,
        "Accumulated depreciation": -12_000.0,
        "Research and development": -12_000.0,
        "Net cash used in investing activities": -36_000.0,
    }, values


def test_the_coordinate_reader_admits_the_same_shapes() -> None:
    for word in ("12,000-", "−12,000", "(12,000)", "1,234"):
        assert _ESTABLISHES.match(word), word
        assert _FILLS.match(word), word
    assert _NIL.match("−")
    assert not _ESTABLISHES.match("2025")


# ------------------------------------------------------------- a scan that read nothing


def test_a_scan_that_read_nothing_is_said_to_be_one(kit: dict, monkeypatch) -> None:
    """With no OCR engine, a PNG is a page with no text layer and nothing read from it.
    That is now on the report and on the event, and in the message a person reads - where
    it used to be `0 block(s) written`, indistinguishable from a readable file with no
    figures."""
    import ports

    none = ports.get_ocr("none")
    monkeypatch.setattr(ports, "get_ocr", lambda *a, **k: none)
    report = read("document", "Trial balance.png", PNG + bytes(64), **kit)
    assert report.scanned == (1,)
    assert report.blocks == {}
    (event,) = [e for e in kit["store"].events(kit["started"]) if e.type == "intake.read"]
    assert event.payload["scanned_pages"] == [1]
    assert "1 page(s) with no text layer" in event.message
    assert "a scan, and no OCR engine read it" in event.message


def test_a_document_with_a_text_layer_reports_no_scanned_pages(kit: dict) -> None:
    statement = b"Statement\n(in thousands)\n            2025\nRevenue   1,482,113\nCost     912,004\n"
    report = read("document", "is.txt", statement, **kit)
    assert report.scanned == ()
    (event,) = [e for e in kit["store"].events(kit["started"]) if e.type == "intake.read"]
    assert event.payload["scanned_pages"] == []
    assert "no text layer" not in event.message


# ------------------------------------------------- the refusals say the true thing


def test_a_protected_workbook_is_refused_as_protected(kit: dict) -> None:
    with pytest.raises(DiagnosticError) as refused:
        read("spreadsheet", "TB 2025.xlsx", OLE2 + bytes(512), **kit)
    said = refused.value.diagnostic
    assert said.code == "INTAKE.FORMAT_NOT_READ"
    assert "protected with a password" in said.detail
    assert "the file itself is whole" in said.detail
    assert "readable copy" not in said.detail


def test_a_pdf_under_a_spreadsheet_name_is_named_a_pdf(kit: dict) -> None:
    from tests.p17.conftest import build_pdf

    pdf = build_pdf([("Revenue 1,482,113", 100.0)])
    with pytest.raises(DiagnosticError) as refused:
        read("spreadsheet", "TB 2025.xlsx", pdf, **kit)
    said = refused.value.diagnostic
    assert said.code == "INTAKE.FORMAT_NOT_READ"
    assert "is a PDF under a spreadsheet name" in said.detail
    assert "rename it .pdf" in said.detail


def test_an_xlsx_under_an_xls_name_and_a_zip_under_a_csv_name(kit: dict) -> None:
    with pytest.raises(DiagnosticError) as refused:
        read("spreadsheet", "TB 2025.xls", b"PK\x03\x04" + bytes(64), **kit)
    assert "is an .xlsx under an .xls name" in refused.value.diagnostic.detail
    with pytest.raises(DiagnosticError) as refused:
        read("spreadsheet", "TB 2025.csv", b"PK\x03\x04" + bytes(64), **kit)
    assert "under a text name" in refused.value.diagnostic.detail


def test_a_text_file_under_an_xlsx_name_is_still_the_refusal_it_was(kit: dict) -> None:
    """P156's case, unchanged on purpose: the bytes name no format, so there is nothing
    truer to say than that it will not open as a workbook."""
    with pytest.raises(DiagnosticError) as refused:
        read("spreadsheet", "TB 2025.xlsx", b"this is not a workbook", **kit)
    assert refused.value.diagnostic.code == "INTAKE.UNREADABLE_FILE"


def test_a_tab_separated_file_under_an_xls_name_is_read(kit: dict) -> None:
    tsv = b"Account\tFY2025\nRevenue\t1,482,113\nCost of sales\t912,004\nGross profit\t570,109\n"
    report = read("spreadsheet", "TB 2025.xls", tsv, **kit)
    assert report.conversion is not None
    assert report.conversion.delimiter == "\t"
    assert report.blocks, "the rows reached the parse store"


def test_a_utf16_export_is_read(kit: dict) -> None:
    text = "Account,FY2025\nRevenue,\"1,482,113\"\nCost of sales,\"912,004\"\nGross profit,\"570,109\"\n"
    for encoding in ("utf-16", "utf-16-be"):
        data = text.encode(encoding)
        if encoding == "utf-16-be":
            data = b"\xfe\xff" + data
        decoded, named = _decode(data)
        assert decoded == text, encoding
        assert named.startswith("utf-16"), named
    report = read("spreadsheet", "TB 2025.csv", text.encode("utf-16"), **kit)
    assert report.conversion is not None
    assert report.conversion.encoding == "utf-16-le"
    assert report.blocks


def test_a_protected_pdf_is_refused_as_protected(kit: dict) -> None:
    from pypdf import PdfReader, PdfWriter

    from tests.p17.conftest import build_pdf

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(build_pdf([("Revenue 1,482,113", 100.0)]))))
    writer.encrypt("secret")
    out = io.BytesIO()
    writer.write(out)
    with pytest.raises(DiagnosticError) as refused:
        read("document", "Statements.pdf", out.getvalue(), **kit)
    said = refused.value.diagnostic
    assert said.code == "INTAKE.FORMAT_NOT_READ"
    assert "protected with a password" in said.detail
    assert "readable copy" not in said.detail


# ------------------------------------------------------------- nothing that read, moved


@pytest.fixture(scope="module")
def filings():
    return {
        name: read_document((PUBLIC / name).read_bytes(), name)
        for name in ("sec-ars-3d-systems-2025.pdf", "sec-ars-resmed-2026.pdf")
    }


def test_the_three_public_filings_read_exactly_as_they_did(filings) -> None:
    """The numbers C86, P163 and P164 assert, re-asserted after widening what a figure may
    look like: not one row, table or named column moved on either filing, because none of
    the admitted shapes occurs on them."""
    for name, tables, rows, named in (
        ("sec-ars-3d-systems-2025.pdf", 72, 815, 48),
        ("sec-ars-resmed-2026.pdf", 70, 960, 62),
    ):
        doc = filings[name]
        assert sum(len(p.tables) for p in doc.pages) == tables, name
        assert (
            sum(
                1
                for p in doc.pages
                for t in p.tables
                for c in t.columns
                for r in c.rows
                if r.value is not None
            )
            == rows
        ), name
        assert (
            sum(1 for p in doc.pages for t in p.tables if t.headings and all(t.headings))
            == named
        ), name
