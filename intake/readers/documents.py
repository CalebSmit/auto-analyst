"""The Document Reader: pulls text and tables out of PDFs and Word files.

Deterministic extraction to structured rows, attaching a page/table/row locator to every
emitted item. No model: extraction is mechanical work, and a model here would cost more,
add latency and introduce paraphrase risk on figures that must be verbatim.

Two things this reader is careful about:

* **Hidden text is surfaced, not dropped.** Text drawn at a font size no person reads is
  extracted like everything else and kept apart as `hidden`, so the Untrusted Content
  Boundary sees it and a reviewer can. A PDF's instructions in 1pt white are still in
  the document; pretending otherwise is how they reach a model unannounced.
* **The locator is the part that matters.** "Page 14, table 2, row 7" is what lets a
  reviewer check a number in two seconds instead of two minutes.

Tables in a PDF are recovered from lines that end in a number - a label and a figure -
which is what a trial balance or a schedule looks like once pypdf has flattened it. Word
tables are real tables and are read as such. Scanned pages (no text layer) are reported,
not OCR'd: the OCR path is a later adapter, and a page that yields nothing is a fact the
manifest should carry rather than a blank the pipeline fills in.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from ops.source_parse import Row

__all__ = ["Line", "Page", "ParsedDocument", "Table", "read_document"]

HIDDEN_BELOW_PT = 4.0
_NUMBER_AT_END = re.compile(
    r"^(?P<label>.*?\S)\s{2,}(?P<num>\(?-?\$?\s?[\d,]+(?:\.\d+)?\)?)\s*$|"
    r"^(?P<label2>.*?[A-Za-z].*?)\s+(?P<num2>\(?-?\$?[\d,]{4,}(?:\.\d+)?\)?)\s*$"
)


@dataclass(frozen=True)
class Line:
    text: str
    hidden: bool = False
    font_size: float | None = None

    ocr: bool = False
    """Read by an engine off an image, rather than lifted out of a text layer.

    Carried all the way to a person. A figure a machine recognised on a scan is weaker
    evidence than the same figure copied from a text layer, and the acceptance rule turns
    on evidence rather than on a score - so which of the two it was must not be lost here,
    where it is the only place that knows."""

    confidence: float | None = None
    """What the engine thought of this line, 0 to 1, where one read it."""


@dataclass(frozen=True)
class Table:
    page: int
    index: int
    rows: tuple[Row, ...]

    @property
    def locator(self) -> str:
        return f"p{self.page}/t{self.index}"


@dataclass
class Page:
    number: int
    lines: list[Line] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines if not line.hidden)

    @property
    def hidden(self) -> tuple[str, ...]:
        return tuple(line.text for line in self.lines if line.hidden)

    @property
    def scanned(self) -> bool:
        return not any(line.text.strip() for line in self.lines)


@dataclass
class ParsedDocument:
    filename: str
    kind: str
    pages: list[Page] = field(default_factory=list)

    def blocks(self) -> dict[str, tuple[Row, ...]]:
        """Every block this document writes to the Source Parse Store."""
        out: dict[str, tuple[Row, ...]] = {}
        for page in self.pages:
            visible = [line.text for line in page.lines if not line.hidden and line.text.strip()]
            if visible:
                out[f"p{page.number}/text"] = tuple(
                    Row(label=text, value=None, raw=text, ordinal=n)
                    for n, text in enumerate(visible, start=1)
                )
            for table in page.tables:
                out[table.locator] = table.rows
        return out

    def headers(self) -> list[str]:
        first = self.pages[0] if self.pages else None
        return [line.text for line in first.lines[:8] if not line.hidden] if first else []

    def first_rows(self) -> list[str]:
        rows: list[str] = []
        for page in self.pages:
            for table in page.tables:
                rows.extend(r.raw for r in table.rows[:5])
            if rows:
                break
        return rows

    def hidden_text(self) -> tuple[str, ...]:
        return tuple(text for page in self.pages for text in page.hidden)

    def scanned_pages(self) -> tuple[int, ...]:
        return tuple(p.number for p in self.pages if p.scanned)

    def as_text(self) -> str:
        return "\n".join(f"[page {p.number}]\n{p.text}" for p in self.pages)


def read_document(data: bytes, filename: str) -> ParsedDocument:
    name = filename.lower()
    if name.endswith(".pdf"):
        return _read_pdf(data, filename)
    if name.endswith(".docx"):
        return _read_docx(data, filename)
    return _read_text(data, filename)


# --------------------------------------------------------------------- pdf


def _read_pdf(data: bytes, filename: str) -> ParsedDocument:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    doc = ParsedDocument(filename=filename, kind="pdf")
    for number, page in enumerate(reader.pages, start=1):
        segments = _segments(page)
        parsed = Page(number=number)
        for text, size in segments:
            hidden = size is not None and 0 < size < HIDDEN_BELOW_PT
            for raw_line in text.splitlines():
                if raw_line.strip():
                    parsed.lines.append(Line(raw_line.strip(), hidden=hidden, font_size=size))
        doc.pages.append(parsed)

    _ocr_the_scanned_pages(doc, data)
    for parsed in doc.pages:
        parsed.tables.extend(
            _tables_from_lines(
                parsed.number, [line for line in parsed.lines if not line.hidden]
            )
        )
    return doc


def _ocr_the_scanned_pages(doc: ParsedDocument, data: bytes) -> None:
    """Fill in the pages pypdf found nothing on, if an engine is configured.

    Tables are built afterwards rather than before, so an OCR'd page reaches
    `_tables_from_lines` exactly as a page with a text layer does - which is the point:
    from here on a scan and a text layer travel the same road, and no locator, guard or
    citation downstream needs to know which it was.

    Nothing is invented. With no engine the port raises, the pages stay empty, and
    `Page.scanned` goes on being true - which is what the manifest has always carried and
    is the honest answer. An engine that fails mid-document leaves the pages it did not
    reach in exactly that state.
    """
    if not any(page.scanned for page in doc.pages):
        return
    from ports import get_ocr  # noqa: PLC0415 - deferred: reading a text PDF must not need it
    from ports.ocr import OCRUnavailable  # noqa: PLC0415

    try:
        read = get_ocr().read(data, kind="pdf")
    except OCRUnavailable:
        return

    by_number = {page.number: page for page in read}
    for page in doc.pages:
        if not page.scanned:
            continue
        found = by_number.get(page.number)
        if found is None:
            continue
        for line in found.lines:
            if line.text.strip():
                page.lines.append(
                    Line(line.text.strip(), ocr=True, confidence=line.confidence)
                )


def _tables_from_lines(page: int, lines: list[Line]) -> list[Table]:
    """Consecutive lines that end in a figure form a table. One per run of them."""
    tables: list[Table] = []
    current: list[Row] = []

    def flush() -> None:
        if len(current) >= 2:
            tables.append(Table(page=page, index=len(tables) + 1, rows=tuple(current)))
        current.clear()

    for line in lines:
        match = _NUMBER_AT_END.match(line.text)
        if match:
            label = match.group("label") or match.group("label2") or ""
            num = match.group("num") or match.group("num2") or ""
            current.append(
                Row(
                    label=label.strip(), value=_number(num), raw=line.text, ordinal=len(current) + 1
                )
            )
        else:
            flush()
    flush()
    return tables


# -------------------------------------------------------------------- docx


def _read_docx(data: bytes, filename: str) -> ParsedDocument:
    import docx

    document = docx.Document(io.BytesIO(data))
    page = Page(number=1)
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        hidden = any(
            run.font.hidden or (run.font.size is not None and run.font.size.pt < HIDDEN_BELOW_PT)
            for run in paragraph.runs
            if run.text.strip()
        )
        page.lines.append(Line(text, hidden=hidden))
    for index, table in enumerate(document.tables, start=1):
        rows: list[Row] = []
        for ordinal, row in enumerate(table.rows, start=1):
            cells = [c.text.strip() for c in row.cells]
            if not any(cells):
                continue
            value = next((_number(c) for c in reversed(cells) if _number(c) is not None), None)
            rows.append(Row(label=cells[0], value=value, raw=" | ".join(cells), ordinal=ordinal))
        if rows:
            page.tables.append(Table(page=1, index=index, rows=tuple(rows)))
    return ParsedDocument(filename=filename, kind="docx", pages=[page])


# -------------------------------------------------------------------- text


def _read_text(data: bytes, filename: str) -> ParsedDocument:
    page = Page(number=1)
    for raw in data.decode("utf-8", errors="replace").splitlines():
        if raw.strip():
            page.lines.append(Line(raw.rstrip()))
    page.tables.extend(_tables_from_lines(1, page.lines))
    return ParsedDocument(filename=filename, kind="text", pages=[page])


# ----------------------------------------------------------------- numbers


def _number(text: str) -> float | None:
    cleaned = text.strip().replace("$", "").replace(",", "").replace(" ", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return None
    value = float(cleaned)
    return -value if negative else value


def _segments(page: object) -> list[tuple[str, float | None]]:
    """Every text run on a page with its effective font size, via pypdf's visitor."""
    found: list[tuple[str, float | None]] = []

    def visit(text: str, cm: object, tm: list[float], font: object, size: float | None) -> None:
        if not text:
            return
        scale = max(abs(tm[0]), abs(tm[3])) if tm else 1.0
        effective = size * (scale or 1.0) if size else None
        found.append((text, effective))

    page.extract_text(visitor_text=visit)  # type: ignore[attr-defined]
    return found
