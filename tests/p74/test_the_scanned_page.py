"""P74: the scanned page, read locally.

Every PDF this firm's clients send is a scan, they send a lot of them, and keying those
by hand is the one to three hours a repeat engagement costs. `intake/readers/documents.py`
has always reported such a page rather than reading it, and said in as many words that the
OCR path was a later adapter. This is that adapter.

**Why local is the requirement and not a preference.** The guarantee downstream is that a
model only ever sees masked payloads. Masking needs text; text from a scan needs OCR. An
OCR step that was itself a model call would put the unmasked client document in front of a
model *before* masking could happen - inverting the order the guarantee rests on, in a way
nothing downstream could recover. `test_nothing_on_this_path_can_reach_a_model` holds that,
and it is the most important test in this file.

`test_with_no_engine_a_scanned_page_is_still_reported` is the other one that matters: the
reader's promise was that a page yielding nothing is a fact the manifest carries rather
than a blank the pipeline fills in, and adding an engine must not quietly turn a missing
one into an empty page.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import ports
from intake.readers.documents import Line, read_document
from ports.ocr import OCRLine, OCRPage, OCRPort, OCRUnavailable

ROOT = Path(__file__).resolve().parents[2]

def _scanned_pdf() -> bytes:
    """A real one-page PDF with no text layer - what pypdf sees when it meets a scan.

    Built rather than hand-rolled: a PDF assembled by hand tests whether the parser
    tolerates the handwriting, and what is under test here is what happens to a page that
    yields no text.
    """
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


SCANNED_PDF = _scanned_pdf()


class FakeOCR:
    """An engine that read a trial balance off an image."""

    name = "fake_ocr"

    def __init__(self, pages: tuple[OCRPage, ...] | None = None) -> None:
        self.pages = (
            pages
            if pages is not None
            else (
                OCRPage(
                    number=1,
                    lines=(
                        OCRLine("Henderson Manufacturing", confidence=0.98),
                        OCRLine("Rent 120,400", confidence=0.91),
                        OCRLine("Insurance 44,120", confidence=0.72),
                        OCRLine("Repairs 9,010", confidence=0.88),
                    ),
                ),
            )
        )
        self.asked: list[str] = []

    def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
        self.asked.append(kind)
        return self.pages


@pytest.fixture
def with_ocr(monkeypatch: pytest.MonkeyPatch) -> FakeOCR:
    engine = FakeOCR()
    monkeypatch.setattr(ports, "get_ocr", lambda adapter=None: engine)
    return engine


# ------------------------------------------------------------------ the page is read


def test_a_scanned_page_gains_the_lines_the_engine_read(with_ocr: FakeOCR) -> None:
    doc = read_document(SCANNED_PDF, "FY2025 trial balance.pdf")
    assert with_ocr.asked == ["pdf"]
    assert "Rent 120,400" in doc.pages[0].text


def test_its_lines_become_rows_with_the_locators_a_text_layer_would_have_given(
    with_ocr: FakeOCR,
) -> None:
    """The reason the port returns lines. From here a scan and a text layer travel the same
    road, and nothing downstream needs to know which it was."""
    doc = read_document(SCANNED_PDF, "tb.pdf")
    tables = doc.pages[0].tables
    assert tables, "the recovered lines produced no table"
    assert tables[0].locator == "p1/t1"
    assert [row.label for row in tables[0].rows] == ["Rent", "Insurance", "Repairs"]
    assert tables[0].rows[0].value == 120400


def test_an_ocr_line_says_it_came_from_an_engine(with_ocr: FakeOCR) -> None:
    """A figure a machine recognised on a scan is weaker evidence than the same figure
    copied out of a text layer, and this is the only place that knows the difference."""
    doc = read_document(SCANNED_PDF, "tb.pdf")
    assert all(line.ocr for line in doc.pages[0].lines)
    assert doc.pages[0].lines[2].confidence == pytest.approx(0.72)


def test_a_line_from_a_text_layer_does_not() -> None:
    plain = Line("Rent 120,400")
    assert not plain.ocr
    assert plain.confidence is None


# ------------------------------------------------------------------ absence is not a pass


def test_with_no_engine_a_scanned_page_is_still_reported() -> None:
    """The reader's standing promise: a page that yields nothing is a fact the manifest
    carries rather than a blank the pipeline fills in. Adding a port must not turn a
    missing engine into an empty page that reads as 'this sheet was blank'."""
    doc = read_document(SCANNED_PDF, "tb.pdf")
    assert doc.pages[0].scanned
    assert doc.pages[0].lines == []


def test_the_default_adapter_refuses_rather_than_returning_nothing() -> None:
    engine = ports.get_ocr("none")
    with pytest.raises(OCRUnavailable, match="no OCR engine is configured"):
        engine.read(SCANNED_PDF, kind="pdf")


def test_a_page_the_engine_did_not_reach_stays_scanned(monkeypatch: pytest.MonkeyPatch) -> None:
    """An engine that returned nothing for page 1 leaves it exactly as it was."""
    monkeypatch.setattr(ports, "get_ocr", lambda adapter=None: FakeOCR(pages=()))
    doc = read_document(SCANNED_PDF, "tb.pdf")
    assert doc.pages[0].scanned


def test_a_document_that_is_not_a_pdf_never_asks_for_an_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reading what this machine could always read must not start needing an engine."""
    called: list[str] = []

    def boom(adapter: str | None = None) -> object:
        called.append("asked")
        raise AssertionError("a non-pdf asked for OCR")

    monkeypatch.setattr(ports, "get_ocr", boom)
    doc = read_document(b"Rent 120,400\nInsurance 44,120\n", "notes.txt")
    assert not called
    assert doc.kind != "pdf"


# ------------------------------------------------------------------ no model on this path


def test_nothing_on_this_path_can_reach_a_model() -> None:
    """The invariant the whole port exists for.

    Masking happens after the text exists. An OCR adapter that called a model would hand it
    the unmasked client document first, and nothing downstream could undo that. So the
    import walk is the guarantee, not the docstring.
    """
    offenders = []
    for path in sorted((ROOT / "ports" / "ocr").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if name.startswith(("ports.llm", "anthropic", "openai")) or name == "harness.door":
                    offenders.append(f"{path.name} imports {name}")
    assert not offenders, offenders


def test_the_adapters_are_local_code_and_not_a_service() -> None:
    """A network call here is the same failure in different clothes: the page would leave
    this machine before anything masked it."""
    for adapter in ("none.py", "tesseract.py"):
        source = (ROOT / "ports" / "ocr" / adapter).read_text(encoding="utf-8")
        for reaching in ("requests", "httpx", "urllib.request", "boto3"):
            assert reaching not in source, f"{adapter} reaches out with {reaching}"


# ------------------------------------------------------------------ the port, as a port


def test_it_is_registered_beside_the_others() -> None:
    assert "ocr" in ports.PORTS
    assert ports.PORTS["ocr"].env_var == "AA_OCR_ADAPTER"
    assert ports.PORTS["ocr"].default == "none"
    assert set(ports.adapters("ocr")) == {"none", "tesseract"}


def test_both_adapters_satisfy_the_port() -> None:
    assert isinstance(ports.get_ocr("none"), OCRPort)
    assert isinstance(ports.get_ocr("tesseract"), OCRPort)


def test_an_unknown_adapter_is_a_refusal_not_a_fallback() -> None:
    from registries.errors import RegistryError

    with pytest.raises(RegistryError):
        ports.get_ocr("wishful")


def test_the_weakest_line_is_the_pages_confidence() -> None:
    """A row whose label read cleanly and whose figure did not is the case worth
    surfacing, and an average hides it."""
    page = OCRPage(1, (OCRLine("Rent", 0.99), OCRLine("120,400", 0.41)))
    assert page.confidence == pytest.approx(0.41)


def test_a_page_nobody_scored_has_no_confidence() -> None:
    assert OCRPage(1, (OCRLine("Rent"),)).confidence is None


# ------------------------------------------------------------------ and readiness says so


def test_readiness_reports_that_a_scan_cannot_be_read_here() -> None:
    """`readiness()` is what CLAUDE.md calls the honest answer to "does this work yet", and
    it derives what is joined by asking the code. With no engine, most of this firm's
    inbound path reads as nothing - which is the single most useful thing that report can
    say on a fresh work machine."""
    from tools.serve import readiness

    seam = next(s for s in readiness() if s.name == "reading a scan")
    assert not seam.ready
    assert "AA_OCR_ADAPTER" in seam.detail
    assert "reported as scanned" in seam.detail
    assert seam.needs_installing, (
        "this waits on software rather than on wiring, and calling it an unmade seam would "
        "make every machine without an engine report an unfinished build"
    )


def test_readiness_goes_green_when_an_engine_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other side. A report that can only say no is not a report."""
    import tools.serve as serve

    monkeypatch.setattr(serve, "scans_can_be_read", lambda: (True, "tesseract"))
    seam = next(s for s in serve.readiness() if s.name == "reading a scan")
    assert seam.ready
    assert "tesseract" in seam.detail


def test_an_engine_that_is_selected_but_broken_is_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The case configuration alone cannot distinguish: an adapter named, and its
    executable missing. It looks identical to a working one from the variable."""
    import ports

    class Broken:
        name = "tesseract"

        def read(self, data: bytes, *, kind: str = "pdf") -> tuple[OCRPage, ...]:
            raise RuntimeError("tesseract is not installed")

    monkeypatch.setattr(ports, "get_ocr", lambda adapter=None: Broken())
    from tools.serve import scans_can_be_read

    ready, detail = scans_can_be_read()
    assert not ready
    assert "failed" in detail
