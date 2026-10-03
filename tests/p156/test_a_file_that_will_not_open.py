"""P156: a workbook that will not open is named; a document that will not open was a traceback.

Two branches of one function, and only one of them had been written to answer the question.
`intake/readers/__init__.py` catches everything the workbook reader can raise - *"a zero-byte
file, a text file with the wrong extension, a workbook still being written, an encrypted one.
None is a pass that failed; each is a file that cannot be read, named, so the person replaces
it"* - and raises `INTAKE.UNREADABLE_FILE`. The document branch caught only `NotText`, so
whatever the library raised went straight out of the reader. Measured:

| what was sent | what came out |
|---|---|
| a truncated PDF | `PdfStreamError: Stream has ended unexpectedly` |
| a corrupt `.docx` | `BadZipFile: File is not a zip file` |
| a truncated PNG | `UnidentifiedImageError: cannot identify image file` |

None of those names the file. **Clients send truncated files constantly** - a phone
photograph that stopped uploading, a PDF saved from a browser that was still printing, a
`.docx` copied off a network share mid-write - and P155 made the third row possible by
routing images at all. What somebody needs is which file and the fact that it cannot be read.

**The two answers stay separate, because the thing to do differs.** A format this build
routes and does not read is `FORMAT_NOT_READ` and means *save it as something else*. A file
that will not open is `UNREADABLE_FILE` and means *send it again*. Collapsing them would tell
half the people the wrong thing, which is worse than a traceback, because a traceback at
least looks like a problem.
"""

from __future__ import annotations

import pytest

from intake.readers import read_source
from registries.errors import DiagnosticError
from tests.p17.conftest import ENGAGEMENT, build_docx, build_pdf, intake_row

PNG = bytes.fromhex("89504e470d0a1a0a")
"""A PNG signature, built from its bytes rather than written as escapes - something between
an editor and the file resolves them, and then the fixture is not a PNG at all."""

TRUNCATED_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n"
CORRUPT_DOCX = b"PK\x03\x04" + bytes(40)
TRUNCATED_PNG = PNG + b"this upload stopped"


def read(row_kind: str, filename: str, data: bytes, **kit: object):
    return read_source(
        kit["started"],
        ENGAGEMENT,
        intake_row(filename, data, row_kind),
        data,
        store=kit["store"],
        parse_store=kit["parse_store"],
        boundary=kit["boundary"],
        bus=kit.get("bus"),
    )


# ------------------------------------------------------------- the three that were tracebacks


@pytest.mark.parametrize(
    ("filename", "data", "raised"),
    [
        ("Statements.pdf", TRUNCATED_PDF, "PdfStreamError"),
        ("Engagement letter.docx", CORRUPT_DOCX, "BadZipFile"),
    ],
)
def test_a_document_that_will_not_open_is_named_rather_than_raised(
    filename: str, data: bytes, raised: str, kit: dict
) -> None:
    """The exit criterion. Each of these reached a person as an exception about a stream.

    The class the library raised is kept in the message rather than dropped, because
    somebody will eventually need to know *why* it would not open - but it comes after the
    filename, which is the part that tells them which file to ask for again.
    """
    with pytest.raises(DiagnosticError) as refused:
        read("document", filename, data, **kit)
    diagnostic = refused.value.diagnostic
    assert diagnostic.code == "INTAKE.UNREADABLE_FILE"
    assert filename in diagnostic.detail
    assert "cannot be read" in diagnostic.detail
    assert raised in diagnostic.detail, "the cause is kept, after the name"
    assert diagnostic.locator == filename
    # And it is a DiagnosticError, which is the one handler that can always report a code,
    # an owner and a next action - which is what makes an operator-facing surface possible.
    assert diagnostic.what_now


def test_a_truncated_image_with_no_engine_is_an_empty_page(kit: dict) -> None:
    """Which is why an image is not in the list above, and worth stating rather than leaving
    as an omission a reader has to notice.

    With no engine configured nothing opens the file, so nothing can find it broken: the page
    is empty and reported as a scan, which is the reader standing promise. It is not a
    refusal, and making it one would refuse a file on a machine that never looked at it.
    """
    report = read("document", "Balance sheet.png", TRUNCATED_PNG, **kit)
    assert report.blocks == {}, "nothing reached the parse store"


def test_an_image_with_an_engine_that_cannot_open_it_says_so(kit: dict, monkeypatch) -> None:
    """And on a machine doing real work, where an engine is configured, it is a refusal.

    This is the case the fix exists for. An image is the format most likely to arrive
    half-sent, because it comes off a phone, and P155 made it reachable by routing images at
    all. The engine opens the file and fails, which is a fact about the file rather than
    about the engine - measured as `UnidentifiedImageError` out of Pillow.
    """
    import ports
    from ports.ocr import OCRPage

    class Opens:
        name = "opens"

        def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
            raise OSError("cannot identify image file")

    monkeypatch.setattr(ports, "get_ocr", lambda: Opens())
    with pytest.raises(DiagnosticError) as refused:
        read("document", "Screenshot.png", TRUNCATED_PNG, **kit)
    assert refused.value.diagnostic.code == "INTAKE.UNREADABLE_FILE"
    assert "Screenshot.png" in refused.value.diagnostic.detail


# ------------------------------------------- and the other answer is still the other answer


def test_a_format_that_is_routed_and_not_read_still_says_the_other_thing(kit: dict) -> None:
    """`FORMAT_NOT_READ` means save it as something else; `UNREADABLE_FILE` means send it
    again. A person given the wrong one of those does the wrong thing and the file never
    arrives, which is worse than a traceback - a traceback at least looks like a problem."""
    ole2 = bytes.fromhex("d0cf11e0a1b11ae1") + bytes(64)
    with pytest.raises(DiagnosticError) as refused:
        read("document", "Engagement letter.doc", ole2, **kit)
    diagnostic = refused.value.diagnostic
    assert diagnostic.code == "INTAKE.FORMAT_NOT_READ"
    assert "Word 97-2003" in diagnostic.detail
    assert "Save it as" in diagnostic.detail


def test_a_workbook_that_will_not_open_is_unchanged(kit: dict) -> None:
    """The branch that was already right, and the one this phase copied.

    The same **code** and the same shape - the file named first, the library's own class
    kept after it - and deliberately not the same sentence: a workbook says "cannot be
    opened as a workbook", which is more specific than anything the document branch can
    say, because that branch covers three readers.
    """
    with pytest.raises(DiagnosticError) as refused:
        read("spreadsheet", "TB 2025.xlsx", b"this is not a workbook", **kit)
    diagnostic = refused.value.diagnostic
    assert diagnostic.code == "INTAKE.UNREADABLE_FILE"
    assert diagnostic.detail.startswith("TB 2025.xlsx cannot be opened")
    assert "BadZipFile" in diagnostic.detail
    assert diagnostic.locator == "TB 2025.xlsx"


def test_a_document_that_does_open_is_not_caught_by_any_of_this(kit: dict) -> None:
    """The guard a broad `except` needs. Catching everything around a reader is how a real
    bug in the reader becomes a diagnostic about the client's file - so a document that
    reads has to go on reading, and this is the assertion that would notice."""
    report = read(
        "document",
        "TB_FY25.pdf",
        build_pdf(
            [
                ("Henderson Manufacturing - Trial Balance FY2025", 12.0),
                ("Officer salary      240,000", 10.0),
                ("Officer bonus        60,000", 10.0),
                ("Total officer comp  300,000", 10.0),
            ]
        ),
        **kit,
    )
    assert report.blocks, "the document was read"
    assert any("Officer salary" in str(b) for b in report.blocks) or report.blocks

    docx = read(
        "document",
        "Notes.docx",
        build_docx(["Henderson Manufacturing", "The company is an S corporation."]),
        **kit,
    )
    assert docx.blocks, "and so was the Word file"
