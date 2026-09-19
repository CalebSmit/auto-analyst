"""C43 - The scan is read here, and read before anything masks it.

P74 added the eighth port so a scanned page can be read at all. The checkpoint asks the
one thing that is not visible from inside that phase: whether the order the whole privacy
guarantee depends on still holds now that a new step sits at the front of it.

    image -> text -> mask -> model

Every downstream promise rests on the model seeing masked payloads only. OCR is upstream
of masking by necessity, because masking needs text to mask. So the danger is not that OCR
is wrong; it is that OCR becomes a model call, and the unmasked document reaches a model
before masking exists to stop it. Nothing downstream can recover from that, which is why
it is asked here as well as in the phase.
"""

from __future__ import annotations

import ast
from pathlib import Path

import ports

ROOT = Path(__file__).resolve().parents[3]


def imports_of(package: str) -> set[str]:
    found: set[str] = set()
    for path in sorted((ROOT / package).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
    return found


def test_the_ocr_path_cannot_reach_a_model() -> None:
    """The invariant the port exists for, asked of the package as a whole."""
    reached = imports_of("ports/ocr")
    assert not any(name.startswith("ports.llm") for name in reached)
    assert not any(name.split(".")[0] in {"anthropic", "openai"} for name in reached)


def test_the_document_reader_does_not_reach_a_model() -> None:
    """`documents.py` is where OCR is called from, and it must stay clear of a model - if
    reading a client's PDF pulled in an LLM adapter, the ordering would be one import away
    from being untrue.

    Deliberately about this module and not about `intake/readers` as a whole, which was the
    first thing this test asserted and was wrong: `workbook.py` has a model-assisted sheet
    selector that puts a workbook *survey* - sheet names and shapes - through the untrusted
    boundary and the door. That is a considered design and it predates this phase. "No
    reader ever touches a model" is not the invariant; "the path that reads a scan does
    not" is.
    """
    source = (ROOT / "intake" / "readers" / "documents.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("ports.llm"), node.module
        if isinstance(node, ast.Import):
            assert not any(a.name.startswith("ports.llm") for a in node.names)


def test_masking_is_still_deterministic_python() -> None:
    """`privacy/` is deterministic throughout, and OCR sitting in front of it must not have
    become a reason to relax that."""
    reached = imports_of("privacy")
    assert not any(name.startswith("ports.llm") for name in reached)
    assert not any(name.split(".")[0] in {"anthropic", "openai"} for name in reached)


def test_the_eighth_port_is_a_port_like_the_others() -> None:
    """Chosen by configuration, refusing an unknown name, with a default that is honest
    about a machine where nobody has installed anything."""
    assert ports.PORTS["ocr"].env_var == "AA_OCR_ADAPTER"
    assert ports.PORTS["ocr"].default == "none"
    # `rapidocr` joined at P75. Two local engines rather than one, because which reads
    # this firm's scans better is a benchmark's question and a benchmark needs two.
    assert set(ports.ready("ocr")) == {"none", "rapidocr", "tesseract"}


def test_a_machine_with_no_engine_reads_what_it_always_could() -> None:
    """The regression that would matter most to somebody who installs nothing: the
    documents that worked before must still work, and a scan must still be reported rather
    than read as an empty page."""
    from intake.readers.documents import read_document

    plain = read_document(b"Rent 120,400\nInsurance 44,120\n", "notes.txt")
    assert plain.pages[0].tables, "a text document stopped producing rows"

    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    scanned = read_document(buffer.getvalue(), "scan.pdf")
    assert scanned.pages[0].scanned
    assert scanned.pages[0].lines == []


def test_what_the_analyst_confirmed_is_what_was_built() -> None:
    """The engine is installable on the work machine, which is what unblocked this. The
    adapter that needs it is registered and buildable without it - so a clone, a container
    and the work laptop are the same code with different configuration."""
    engine = ports.get_ocr("tesseract")
    assert engine.name == "tesseract"
