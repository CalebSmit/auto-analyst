"""C87 - what a run says it did with a file.

Two phases, two halves of one question, and neither phase is placed to ask the other's half.

* **P156.** A document that will not open was whatever the library raised. A truncated PDF
  gave `PdfStreamError`, a corrupt `.docx` gave `BadZipFile`, a truncated image gave
  `UnidentifiedImageError` - none of them naming the file, where the workbook branch beside
  them had named its file since it was written. Worse than confusing: the run was left in
  `running`, holding the client's lock.
* **P157.** The rehearsal could not tell a file it read from a file it held. The case called
  `pdf` had never read a PDF - its `Statements.pdf` carried no document-type token, so the
  binder held it and three runs ended on three workbooks, green every time.

The second is why the first is believable. P156's own rehearsal case read as a pass while
testing nothing, exactly as the `pdf` case had for far longer, and it took renaming the file
to find out. **A phase whose evidence comes from a harness that cannot see the thing is a
phase with no evidence**, and that is the pairing worth a checkpoint.

So what is asked here is the question from the outside: for every answer this system can give
about a file, is it the answer a person can act on? There are four - read, held, refused
because the format is not read, refused because the file will not open - and they mean four
different things to do.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from intake.bind import bind_document_type
from intake.readers import read_source
from intake.readers.documents import NotText, read_document
from registries.errors import DiagnosticError
from tests.p17.conftest import ENGAGEMENT, build_docx, build_pdf, intake_row
from tools.simulate_files import (
    CASES,
    EVERY_FILE_IS_READABLE,
    INLINE_CASES,
    MUST_BE_READ,
    ONE_FILE_IS_UNREADABLE,
    ONE_PIXEL_PNG,
    pdf,
)

PNG = bytes.fromhex("89504e470d0a1a0a")
OLE2 = bytes.fromhex("d0cf11e0a1b11ae1")
TRUNCATED = b"%PDF-1.4" + bytes([10]) + b"1 0 obj<<>>endobj" + bytes([10])
"""A PDF whose upload stopped. Built from its bytes because every layer between an
editor and this file has an opinion about an escape, and one of them acts on it."""

CONVENTIONS = {
    "trial_balance": ("tb", "tb_", "trial balance", "trialbalance", "susa"),
    "financial_statements": ("income statement", "balance sheet", "is", "bs", "fs"),
}


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


# ------------------------------------------------- the four answers, and the four next steps


def test_each_answer_a_file_can_get_is_a_different_thing_to_do(kit: dict) -> None:
    """All four at once, because the value is in their being distinguishable.

    A person holding a diagnostic has one question - what do I do now - and the four answers
    are: nothing, it was read; rename it, nothing claimed it; save it as something else, the
    format is not read; send it again, the file will not open. Two of those collapsing into
    one is worse than a traceback, because the wrong half of the people then do the wrong
    thing and the file never arrives.
    """
    answers: dict[str, str] = {}

    # Read.
    report = read("document", "TB_FY25.pdf", build_pdf([("Officer salary 240,000", 10.0)]), **kit)
    answers["read"] = "blocks" if report.blocks else "nothing"

    # Refused because the format is not read.
    with pytest.raises(DiagnosticError) as not_read:
        read("document", "letter.doc", OLE2 + bytes(64), **kit)
    unread = not_read.value.diagnostic

    with pytest.raises(DiagnosticError) as broken:
        read("document", "TB_FY25.pdf", TRUNCATED, **kit)
    cannot = broken.value.diagnostic

    # Both end with the file arriving again, which is why that phrase cannot be the test -
    # the difference is what somebody does *first*. One converts the file they already have,
    # the other has to go back to the client, and only the first mentions saving it.
    assert "Save it as" in unread.detail
    assert "Save it as" not in cannot.detail
    assert "cannot be read" in cannot.detail
    assert "TB_FY25.pdf" in cannot.detail and "letter.doc" in unread.detail
    assert unread.what_now != cannot.what_now, "two refusals, two things to do first"
    assert "save it in a format that is read" in unread.what_now
    assert "readable copy" in cannot.what_now


def test_no_reader_lets_a_library_exception_out(kit: dict) -> None:
    """Asked of all three document readers rather than of the one that showed it.

    Three libraries, three exception types, and the branch caught one of them. A fourth
    reader added later is the case this would notice - which is why it is asked by format
    rather than by exception class.
    """
    broken_by_format = {
        "TB_FY25.pdf": TRUNCATED,
        "TB_FY25.docx": b"PK\x03\x04" + bytes(40),
        "Balance sheet.rtf": b"{\\rtf1" + bytes([0]) * 8,
    }
    for filename, data in broken_by_format.items():
        try:
            read("document", filename, data, **kit)
        except DiagnosticError as named:
            assert named.diagnostic.code in (
                "INTAKE.UNREADABLE_FILE",
                "INTAKE.FORMAT_NOT_READ",
            ), f"{filename}: {named.diagnostic.code}"
            assert filename in named.diagnostic.detail, filename
        except Exception as raw:  # noqa: BLE001 - that is the defect
            pytest.fail(f"{filename} let {raw.__class__.__name__} out of the reader")


def test_a_document_that_opens_is_still_read(kit: dict) -> None:
    """The guard a broad `except` needs. Catching everything around a reader is how a real
    bug in the reader becomes a diagnostic about the client's file."""
    assert read("document", "TB_FY25.pdf", build_pdf([("Cash 95,635", 10.0)]), **kit).blocks
    assert read("document", "Notes.docx", build_docx(["Henderson Manufacturing"]), **kit).blocks
    assert read(
        "document", "Balance sheet.rtf", b"{\\rtf1\\ansi Cash 95,635\\par\n}", **kit
    ).blocks


# -------------------------------------------- and the harness can see which answer it got


def test_the_rehearsal_names_the_file_every_case_is_about() -> None:
    """Without this the phase above has no evidence, which is the pairing this checkpoint is
    for. Three cases in a row passed while never looking at their own file."""
    assert MUST_BE_READ, "the set exists"
    assert ONE_FILE_IS_UNREADABLE, "and so does its other half"
    known = set(CASES) | set(INLINE_CASES)
    for name in {*MUST_BE_READ, *ONE_FILE_IS_UNREADABLE, *EVERY_FILE_IS_READABLE}:
        assert name in known, f"{name} is checked and is not a case"


def test_every_file_a_case_is_about_would_actually_be_bound() -> None:
    """The defect itself, from the name alone. A file nothing claims reaches no reader, and
    the run ends on the others in the folder - which is invisible in an ending."""
    for case, filename in {**MUST_BE_READ, **ONE_FILE_IS_UNREADABLE}.items():
        assert bind_document_type(filename, CONVENTIONS) is not None, (
            f"{case}: {filename} would be held, so the case would test nothing"
        )


def test_the_rehearsals_own_fixtures_are_what_they_claim() -> None:
    """A fixture nothing can open does not make a simpler test, it makes a different one.

    The PDF the `pdf` case used raised `PdfReadError` and nobody had met it, because the
    file was never opened. Both fixtures are put through the real reader here.
    """
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "TB_FY25.pdf"
        pdf(path, ["Officer salary      240,000", "Officer bonus        60,000"])
        doc = read_document(path.read_bytes(), path.name)
    assert [
        (row.label, row.value)
        for table in doc.pages[0].tables
        for column in table.columns
        for row in column.rows
        if row.value is not None
    ] == [("Officer salary", 240_000.0), ("Officer bonus", 60_000.0)]

    shot = read_document(ONE_PIXEL_PNG, "Balance sheet screenshot.png")
    assert shot.kind == "image", "an image, not a file refused as binary"
    assert [page.scanned for page in shot.pages] == [True]


def test_an_image_is_still_an_image_and_not_a_binary_refusal() -> None:
    """The two answers that look identical from outside: a PNG read as an empty page, and a PNG
    refused for being a PNG. `looks_like` catches that signature on purpose, so the order of
    those two branches is the only thing keeping them apart."""
    assert read_document(PNG + bytes(64), "shot.png").kind == "image"
    with pytest.raises(NotText) as refused:
        read_document(PNG + bytes(64), "notes.txt")
    assert "PNG" in refused.value.looks_like
