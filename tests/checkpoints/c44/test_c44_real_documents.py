"""C44 - Two engines, one real document, and a rule widened on purpose.

P75 added a second local OCR engine; P76 put a real public filing in front of the reader
and pinned what it found. A checkpoint asks whether the two hold together and whether the
widened fixtures rule stayed a rule rather than becoming an exception.

The reason the filing matters is worth restating. Every other fixture here is synthetic,
and a synthetic document is written by whoever wrote the code that reads it - so it agrees
with that code. The first real financial statement this reader met, it read the wrong
column of. That is not a criticism of the reader; it is what a real document is for.
"""

from __future__ import annotations

from pathlib import Path

import ports
from intake.readers.documents import read_document
from intake.readers.periods import detect_periods
from ports.ocr import OCRPort

ROOT = Path(__file__).resolve().parents[3]
FILING = ROOT / "fixtures" / "public" / "sec-ars-3d-systems-2025.pdf"


def test_every_ocr_adapter_is_local_and_reaches_no_model() -> None:
    """P74's invariant, asked of every engine now registered rather than of the one that
    existed when it was written."""
    for adapter in ports.ready("ocr"):
        source = (ROOT / "ports" / "ocr" / f"{adapter}.py").read_text(encoding="utf-8")
        for reaching in ("ports.llm", "anthropic", "openai", "requests", "httpx", "boto3"):
            assert reaching not in source, f"{adapter} reaches {reaching}"


def test_every_ocr_adapter_can_be_built_without_its_dependencies() -> None:
    """A machine that has installed none of them still lists, builds and type-checks them
    all - which is what makes choosing one configuration rather than a deployment."""
    for adapter in ports.ready("ocr"):
        assert isinstance(ports.get_ocr(adapter), OCRPort), adapter


def test_the_engines_are_alternatives_rather_than_a_fallback_chain() -> None:
    """Nothing silently tries the next engine. A run reading a scan with an engine nobody
    chose is the failure the ports exist to prevent, and it would make the benchmark
    meaningless besides."""
    for adapter in ports.ready("ocr"):
        source = (ROOT / "ports" / "ocr" / f"{adapter}.py").read_text(encoding="utf-8")
        for other in ports.ready("ocr"):
            if other != adapter:
                assert f"ports.ocr.{other}" not in source, f"{adapter} falls back to {other}"


def test_the_real_filing_is_read_and_what_it_gets_wrong_is_pinned() -> None:
    """P76's finding, asked here so that a change to the reader meets it too."""
    doc = read_document(FILING.read_bytes(), FILING.name)
    page = next(p for p in doc.pages if p.number == 56)

    row = next(
        r for t in page.tables for r in t.rows if r.label.startswith("Cash and cash equivalents")
    )
    assert row.value == 171324.0, "still the prior year - B-030 is not built"
    escalated = [a for a in detect_periods(page.text).ambiguous if a.startswith("columns:")]
    assert escalated, "and the escalation is the only thing that stops the run"


def test_the_widened_rule_still_forbids_what_it_always_forbade() -> None:
    """`public` was added beside masked and synthetic. The rule it serves is unchanged: no
    client data, ever. If the words that carry that ever go, the widening became a loophole.
    """
    for where in ("CLAUDE.md", "fixtures/README.md"):
        text = (ROOT / where).read_text(encoding="utf-8")
        assert "No client data" in text or "no client data" in text.lower(), where
    readme = (ROOT / "fixtures" / "public" / "README.md").read_text(encoding="utf-8")
    assert "Nothing a client sent this firm" in readme
    assert "https://www.sec.gov/" in readme, "a public document names where it is published"


def test_the_public_fixture_holds_nothing_the_register_would_catch() -> None:
    """The register is the boundary for client identifiers, and it covers every committed
    file. A public filing must pass it like anything else - the point is that it is public,
    not that it is exempt."""
    from tools import interview

    names = interview.identifiers()
    assert names, "the register is empty, so this checked nothing"
    hits = interview.scan([FILING], names)
    assert hits == [], hits
