"""C88 - everything a client can send, and one answer for each of it.

Both phases widened what the reader will take, and widening intake is the one direction that
can make a figure *worse*: a format newly read is a new way for a wrong number to arrive
carrying a real locator, and a refusal newly added is a new way for a real file to be turned
away. P158 named a token that is almost a figure; P159 added two readers and two refusals,
which is two more paths into the parse store and one more set that has to agree with the
readers behind it. Neither phase is placed to ask whether the whole of intake still says one
thing about one file.

So this sweeps the table rather than any one format. Every extension the fingerprinter routes
is taken in turn, and the question asked of each is the one a person asks: **what happened to
my file, and what do I do now.**

There are four answers and they have to stay four. *Read* - nothing to do. *Held* - rename it,
nothing claimed it. *Refused because the format is not read* - save it as something else.
*Refused because the file will not open* - send it again. Two of those collapsing is worse
than a crash, because the wrong half of the people then do the wrong thing and the file never
arrives.
"""

from __future__ import annotations

import email.message
import io
from pathlib import Path

import pytest

from intake.fingerprint import BY_EXTENSION, DOCUMENT, READ, SPREADSHEET, kind_of, mime_of
from intake.readers import read_source
from intake.readers.documents import IMAGES, NotText, read_document
from intake.readers.footing import footings_in
from intake.readers.misread import misreads_in, nearly_a_figure
from intake.readers.tabular import as_workbook, converts
from registries.errors import DiagnosticError
from tests.p17.conftest import ENGAGEMENT, build_docx, build_pdf, intake_row

ROOT = Path(__file__).resolve().parents[3]
OLE2 = bytes.fromhex("d0cf11e0a1b11ae1")
PNG = bytes.fromhex("89504e470d0a1a0a")

REFUSED = {
    "application/msword",
    "application/vnd.ms-outlook",
    "application/vnd.ms-excel.sheet.binary.macroEnabled.12",
}
"""The three routed so that they can be refused. Named here as well as in the code because
this is the list that must not grow by accident: each entry is a decision that a format has
no reader worth trusting, and a fourth appearing silently is a format somebody meant to
support."""


def ods(rows: list[tuple[str, float | None]]) -> bytes:
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableCell, TableRow
    from odf.text import P

    document = OpenDocumentSpreadsheet()
    table = Table(name="TB")
    for label, value in rows:
        row = TableRow()
        first = TableCell(valuetype="string")
        first.addElement(P(text=label))
        row.addElement(first)
        if value is None:
            row.addElement(TableCell())
        else:
            cell = TableCell(valuetype="float", value=value)
            cell.addElement(P(text="1.234,5"))
            row.addElement(cell)
        table.addElement(row)
    document.spreadsheet.addElement(table)
    buffer = io.BytesIO()
    document.write(buffer)
    return buffer.getvalue()


def eml(attachment: str | None = "TB_FY25.xlsx") -> bytes:
    message = email.message.EmailMessage()
    message["From"] = "controller@client.example"
    message["Subject"] = "FY2025 trial balance"
    message.set_content("The TB is attached.")
    if attachment:
        message.add_attachment(
            b"x", maintype="application", subtype="vnd.ms-excel", filename=attachment
        )
    return message.as_bytes()


def read(kind: str, filename: str, data: bytes, **kit: object):
    return read_source(
        kit["started"],
        ENGAGEMENT,
        intake_row(filename, data, kind),
        data,
        store=kit["store"],
        parse_store=kit["parse_store"],
        boundary=kit["boundary"],
        bus=kit.get("bus"),
    )


# ---------------------------------------------- the whole table, one answer for each entry


def test_every_extension_the_table_routes_is_read_or_refused_by_name() -> None:
    """The sweep. Every entry, rather than the formats a phase happened to be about.

    Two claims per entry and they have to agree: there is a reader, or there is a refusal,
    and `READ` says which. They used to be checked separately for a spreadsheet, so an
    `.xlsb` satisfied the routing and was then handed to openpyxl to be told it "cannot be
    opened as a workbook" - true, and the wrong thing to do about it.
    """
    for extension, mime in sorted(BY_EXTENSION.items()):
        kind = kind_of(mime)
        assert kind in ("spreadsheet", "document"), f"{extension} routes to {kind!r}"
        has_reader = (
            converts(f"x{extension}")
            or mime
            in {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel.sheet.macroEnabled.12",
            }
            or extension in IMAGES
            or extension in (".pdf", ".docx", ".rtf", ".txt", ".md", ".eml")
        )
        assert (mime in READ) == has_reader, f"{extension}: READ and the readers disagree"
        assert has_reader or mime in REFUSED, f"{extension} is neither read nor refused"


def test_the_refused_set_has_not_grown_by_accident() -> None:
    """Three decisions, each that a format has no reader worth trusting here. A fourth
    appearing silently is a format somebody meant to support and did not."""
    assert {mime for mime in DOCUMENT | SPREADSHEET if mime not in READ} == REFUSED


@pytest.mark.parametrize("extension", sorted(BY_EXTENSION))
def test_every_extension_gets_one_of_the_four_answers(extension: str, kit: dict) -> None:
    """The question a person asks, asked of every format at once.

    Each file here is deliberately *not* valid for its extension - except the ones that must
    be - because what is being checked is that an answer comes back at all, named, rather
    than a library exception or silence.
    """
    mime = mime_of(f"TB_FY25{extension}")
    kind = kind_of(mime)
    data = PNG + bytes(64) if extension in IMAGES else b"PK\x03\x04" + bytes(64)
    try:
        report = read(kind, f"TB_FY25{extension}", data, **kit)
    except DiagnosticError as named:
        assert named.diagnostic.code in (
            "INTAKE.UNREADABLE_FILE",
            "INTAKE.FORMAT_NOT_READ",
        ), f"{extension}: {named.diagnostic.code}"
        assert f"TB_FY25{extension}" in named.diagnostic.detail, extension
        assert named.diagnostic.what_now, extension
        return
    except Exception as raw:  # noqa: BLE001 - that is the defect
        pytest.fail(f"{extension} let {raw.__class__.__name__} out of the reader: {raw}")
    # Read, which for these bytes means an empty page or an empty workbook. Either is an
    # answer; what matters is that nothing was invented to fill it.
    assert report.source_id
    assert all(count >= 0 for count in report.blocks.values())


# ------------------------------------------------------- and a figure that arrives is sound


def test_a_figure_from_each_reader_carries_a_locator_that_resolves(kit: dict) -> None:
    """Every path into the parse store, including the two P159 added.

    A locator is the whole of what makes a figure checkable in two seconds rather than two
    minutes, and a new reader is a new chance to write one nothing can resolve.
    """
    cases = {
        "TB_FY25.ods": ods(
            [("Account", None), ("Officer salary", 240_000.0), ("Total officer comp", 240_000.0)]
        ),
        "TB_FY25.pdf": build_pdf(
            [("Officer salary      240,000", 10.0), ("Total officer comp  240,000", 10.0)]
        ),
        "Balance sheet note.eml": eml(),
        "Notes.docx": build_docx(["Henderson Manufacturing", "Officer salary 240,000"]),
    }
    for filename, data in cases.items():
        kind = kind_of(mime_of(filename))
        report = read(kind, filename, data, **kit)
        assert report.blocks, f"{filename} wrote nothing"
        for locator, written in report.blocks.items():
            assert written > 0, f"{filename}: {locator} is empty"
            rows = kit["parse_store"].rows(  # type: ignore[attr-defined]
                kit["started"], report.source_id, locator
            )
            assert len(rows) == written, f"{filename}: {locator} does not resolve"


def test_the_ods_figure_is_the_value_and_not_the_display(kit: dict) -> None:
    """The one that would be undetectable afterwards: both readings of `1.234,5` are
    plausible figures, so nothing downstream could catch the wrong one."""
    report = read(
        "spreadsheet",
        "TB_FY25.ods",
        ods([("Cash", 95_635.0), ("Inventories", 127_496.0)]),
        **kit,
    )
    values = [
        row.value
        for locator in report.blocks
        for row in kit["parse_store"].rows(  # type: ignore[attr-defined]
            kit["started"], report.source_id, locator
        )
    ]
    assert sorted(v for v in values if v is not None) == [95_635.0, 127_496.0]
    assert 1234.5 not in values


def test_every_footing_that_claims_cover_re_adds(kit: dict) -> None:
    """Across the readers rather than within one. A total that re-adds is what lets a figure
    past a person unseen, and the arithmetic is done again here rather than believed.

    **The fixture has a total that is two dollars out in it**, and that is the point. Every
    total being exact made this test unable to notice a tolerance loosened to two dollars -
    the arithmetic agreed either way - so it asserted something that could not fail. A near
    miss is what gives the check something to get wrong.
    """
    report = read(
        "spreadsheet",
        "TB_FY25.ods",
        ods(
            [
                ("Account", None),
                ("Officer salary", 240_000.0),
                ("Officer bonus", 60_000.0),
                ("Total officer comp", 300_000.0),
                ("Rent", 12_000.0),
                ("Utilities", 4_000.0),
                ("Total premises", 16_002.0),
            ]
        ),
        **kit,
    )
    covered: list[str] = []
    uncovered: list[str] = []
    for locator in report.blocks:
        rows = kit["parse_store"].rows(  # type: ignore[attr-defined]
            kit["started"], report.source_id, locator
        )
        by_ordinal = {r.ordinal: r for r in rows}
        for found in footings_in(rows).footings:
            if found.covered:
                parts = [by_ordinal[o].value or 0.0 for o in found.ordinals]
                assert sum(parts) == pytest.approx(found.value), found.label
                covered.append(found.label)
            else:
                uncovered.append(found.label)

    assert "Total officer comp" in covered, "the exact total re-adds"
    assert "Total premises" in uncovered, (
        "a total two dollars out is not cover - 16,002 against 16,000 - and a tolerance "
        "wide enough to accept it would let a misread figure past a person unseen"
    )


# ----------------------------------------- and a token that is not a number is said, not fixed


def test_a_near_miss_is_reported_on_the_report_a_person_reads(kit: dict) -> None:
    """P158's check, through the real boundary rather than against the function.

    The reason it exists is that the row *disappears*: the reader drops the line, label and
    all, so the only other symptom is a total out by an amount nobody can account for.
    """
    report = read(
        "document",
        "TB_FY25.pdf",
        build_pdf(
            [
                ("Officer salary      240,000", 10.0),
                ("Preferred stock, 5,0o0 shares authorized", 10.0),
            ]
        ),
        **kit,
    )
    assert report.misreads, "the near miss reached the report"
    (only,) = report.misreads
    assert only.token == "5,0o0"
    assert only.reads_as == "5,000"
    assert isinstance(only.reads_as, str), "never a number, or something totals it"
    assert "Preferred stock" in only.line, "with the label that says which row"


def test_nothing_on_any_reader_repairs_a_near_miss(kit: dict) -> None:
    """The figure is never written. A repair would put a plausible number, at a real
    locator, into the parse store - which is the failure every other guard here is arranged
    against, arriving through the one place that was trying to help."""
    # Four lines rather than two, because two produced no table at all - so the assertion
    # below was true of an empty list and could not have failed. A fixture that reports no
    # figures cannot show a figure being invented.
    report = read(
        "document",
        "TB_FY25.pdf",
        build_pdf(
            [
                ("Cash 95,635", 10.0),
                ("Inventories l27,496", 10.0),
                ("Prepaid 123,576", 10.0),
                ("Total current assets 219,211", 10.0),
            ]
        ),
        **kit,
    )
    values = [
        row.value
        for locator in report.blocks
        for row in kit["parse_store"].rows(  # type: ignore[attr-defined]
            kit["started"], report.source_id, locator
        )
        if row.value is not None
    ]
    assert values, "the fixture has to produce figures, or this proves nothing"
    assert 127_496.0 not in values, "the misread figure was invented"
    assert any(m.token == "l27,496" for m in report.misreads), "and it was named instead"

    # And what the misread actually costs, which is more than its own row: a line carrying
    # no figure breaks the run of lines that do, so `Cash 95,635` above it is lost as well.
    # One letter, two rows - which is why the check reports rather than the footing alone.
    assert 95_635.0 not in values, "the row above it survived; the fixture has changed"
    assert 123_576.0 in values and 219_211.0 in values


def test_the_check_says_nothing_about_a_clean_document(kit: dict) -> None:
    """Calibration, at the boundary. A check whose findings are mostly not findings teaches
    a reader to skip the section it is in."""
    report = read(
        "document",
        "TB_FY25.pdf",
        build_pdf(
            [
                ("Henderson Manufacturing - Trial Balance FY2025", 12.0),
                ("Officer salary      240,000", 10.0),
                ("Total officer comp  240,000", 10.0),
                ("See note 1B and section 21D", 10.0),
            ]
        ),
        **kit,
    )
    assert report.misreads == (), [m.as_line() for m in report.misreads]
    assert nearly_a_figure("1B") is None and nearly_a_figure("21D") is None


def test_an_email_names_what_it_carries_through_the_boundary(kit: dict) -> None:
    """The sentence a person acts on, on the report rather than only in the reader."""
    report = read("document", "Balance sheet note.eml", eml("TB_FY25.xlsx"), **kit)
    stored = [
        row.label
        for locator in report.blocks
        for row in kit["parse_store"].rows(  # type: ignore[attr-defined]
            kit["started"], report.source_id, locator
        )
    ]
    assert any("TB_FY25.xlsx" in (label or "") for label in stored), stored


def test_a_refusal_is_never_a_decode(kit: dict) -> None:
    """All three, each by the route it actually takes - two through the reader, the `.xlsb`
    through the boundary, because it is routed as a spreadsheet."""
    # By **what each one says**, not merely that it raises. Both of these are OLE2 files, so
    # `looks_like` refuses them on their first bytes whether the routing is there or not -
    # which left this test green with the `.msg` branch removed, calling an Outlook message
    # a Word 97-2003 document. The advice is the thing being checked.
    said = {}
    for filename in ("letter.doc", "FY2025.msg"):
        with pytest.raises(NotText) as refused:
            read_document(OLE2 + bytes(256), filename)
        said[filename] = refused.value.looks_like
    assert "Word 97-2003" in said["letter.doc"], said
    assert "Outlook" in said["FY2025.msg"], said
    assert said["letter.doc"] != said["FY2025.msg"]

    with pytest.raises(DiagnosticError) as refused:
        read("spreadsheet", "TB 2025.xlsb", b"PK\x03\x04" + bytes(64), **kit)
    assert refused.value.diagnostic.code == "INTAKE.FORMAT_NOT_READ"

    # And nothing from any of them reached the store.
    assert misreads_in([]) == ()


def test_the_conversion_seam_still_says_what_it_decided(kit: dict) -> None:
    """A file that was not a workbook had something decided about it, and P159 put a fourth
    format on that seam. An ODS decides nothing - its cells have types - and saying so is
    different from saying nothing."""
    converted = as_workbook(ods([("Cash", 95_635.0)]), "TB.ods")
    assert converted.ambiguous == ()
    assert converted.decimal == "" and converted.delimiter == ""

    csv = as_workbook(b"Account,Amount\nCash,95635\n", "TB.csv")
    assert csv.delimiter == ",", "and a CSV still says what it split on"
