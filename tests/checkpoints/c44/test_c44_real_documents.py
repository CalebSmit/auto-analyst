"""C44 - Two engines, one real document, and a rule widened on purpose.

P75 added a second local OCR engine; P76 put a real public filing in front of the reader
and pinned what it found. A checkpoint asks whether the two hold together and whether the
widened fixtures rule stayed a rule rather than becoming an exception.

The reason the filing matters is worth restating. Every other fixture here is synthetic,
and a synthetic document is written by whoever wrote the code that reads it - so it agrees
with that code. The first real financial statement this reader met, it read the wrong
column of. That is not a criticism of the reader; it is what a real document is for - and
P85 read it again to close B-030, finding three more rules the synthetic fixtures had no
way to teach: a label may contain figures of its own, a run's width is what most of its
rows agree on, and a header split across lines can offer the right number of tokens and
the wrong ones.
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


def test_the_real_filing_is_read_as_columns() -> None:
    """P76's finding, asked here so that a change to the reader meets it too.

    This pinned the defect until P85 closed it: the row used to store 171,324, the prior
    year, with the current year swallowed into the label. Both columns are read now, and
    the escalation has narrowed from every comparative page - which was every audited page
    - to the tables whose columns nobody named.
    """
    doc = read_document(FILING.read_bytes(), FILING.name)
    page = next(p for p in doc.pages if p.number == 56)

    table = next(
        t for t in page.tables
        if any(r.label.startswith("Cash and cash equivalents") for r in t.rows)
    )
    assert len(table.columns) == 2
    values = [
        next(r.value for r in c.rows if r.label.startswith("Cash and cash equivalents"))
        for c in table.columns
    ]
    assert values == [95635.0, 171324.0], values

    # This page's header is split over several lines, and until P163 that left its columns
    # unnamed and stopped the run on every block of it. The years `2025 2024` are three
    # bands above the first figure row, behind `ASSETS` and `Current assets:`; they are read
    # from there now, so every block says which column is which year and the run goes on.
    assert all(t.headings == ("2025", "2024") for t in page.tables)
    found = detect_periods(page.text, tables=page.tables)
    assert not [a for a in found.ambiguous if a.startswith("columns:")], found.ambiguous
    assert found.settled is True


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
