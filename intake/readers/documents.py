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

from intake.readers.layout import LaidOutTable, lay_out
from ops.source_parse import Row

__all__ = ["Column", "Line", "Page", "ParsedDocument", "Table", "read_document"]

HIDDEN_BELOW_PT = 4.0
# A money-shaped figure, the same shape the period detector counts with: grouped with
# commas or at least four digits, optionally parenthesised or carrying a currency mark.
# Deliberately not "any number" - a page number, a note reference and a year are all
# numbers and none of them is a column of figures.
_FIGURES = re.compile(
    # A figure, or the dash a statement writes where a figure would be. `Assets held for
    # sale — 3,176` is one of each and two columns; counting only the figure made it a
    # one-column row in a two-column table, so it was dropped and the line disappeared.
    # A dash is a cell with nothing in it, which is not the same as a cell that is not
    # there, and `Row.value` is `float | None` precisely so the difference survives.
    r"(?<![\w.])\(?-?[$£€]?\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?(?![\w.])"
    r"|(?<![\w.-])[$£€]?\s?[—–-](?![\w.-])"
)
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
class Column:
    """One column of figures in a table, under whatever the document called it."""

    index: int
    """1-based, left to right as the document prints them."""
    heading: str
    """What the header row said above this column - `2025`, `December 31, 2024`, or empty
    where no header could be found. The text as written, not a parsed date: a column
    headed 2025 names a year and not a year end, and the fiscal calendar that would turn
    one into the other is on the engagement profile, not in the document."""
    rows: tuple[Row, ...]


@dataclass(frozen=True)
class Table:
    page: int
    index: int
    columns: tuple[Column, ...]

    @property
    def rows(self) -> tuple[Row, ...]:
        """The first column. What a table meant before one could have more than one, and
        what a single-column table still means - so everything that read `table.rows`
        before this goes on reading the same rows."""
        return self.columns[0].rows if self.columns else ()

    @property
    def locator(self) -> str:
        return f"p{self.page}/t{self.index}"

    def locator_for(self, column: Column) -> str:
        """Where this column's rows are written.

        A single-column table keeps the locator it always had. Only a table that really
        has more than one column gains the `/c` segment, so no locator written before this
        phase means anything different afterwards - which matters because a locator is
        what a figure cites and citations outlive the code that made them.
        """
        if len(self.columns) == 1:
            return self.locator
        return f"{self.locator}/c{column.index}"

    @property
    def headings(self) -> tuple[str, ...]:
        return tuple(c.heading for c in self.columns)


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
                for column in table.columns:
                    out[table.locator_for(column)] = column.rows
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

    scanned = {page.number for page in doc.pages if page.scanned}
    _ocr_the_scanned_pages(doc, data)

    # Where the words are, if they can be had. A page with a text layer gets its rows and
    # columns from the page; a page that had none and was OCR'd has no coordinates to read
    # - the engine gave lines - so it keeps the path it always had. Which of the two it was
    # is settled before OCR runs, because OCR fills the lines in and the question would
    # otherwise answer itself wrongly.
    laid_out = lay_out(data)
    for parsed in doc.pages:
        page_layout = None if laid_out is None else laid_out.get(parsed.number)
        if page_layout and parsed.number not in scanned:
            parsed.tables.extend(_tables_from_layout(parsed.number, page_layout))
        else:
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
    """Consecutive lines carrying figures form a table, as many columns wide as most of
    them agree on.

    Every audited statement is comparative, and this used to anchor on the *last* figure
    on a line. On the real filing in `fixtures/public`, `Revenue $ 386,902 $ 440,121 $
    (53,219)` gave a label of `Revenue $ 386,902 $ 440,121 $` and a value of -53,219 - the
    *Change* column, not a year at all - and `Loss from operations` came out as +181,317
    in a year the company lost 96,083. Silently, and past every guard: provenance passed
    because the number really was at that locator, and footing passed because every row
    was consistently the same wrong column so the totals still re-added.

    **The columns are the trailing figures, and a label may contain numbers of its own.**
    `Accounts receivable, net of reserves - $3,608 and $2,433  83,806  101,471` carries
    four figures and two columns. So the width is what most rows in the run agree on, and
    each row gives up its last `width` figures; taking every figure on every line instead
    made that row four columns wide, broke the run, and dropped the balance sheet's cash
    line entirely.
    """
    tables: list[Table] = []
    run: list[tuple[Line, list[re.Match[str]]]] = []
    heading_line = ""
    last_plain = ""

    def flush() -> None:
        nonlocal heading_line
        table = _table_from_run(page, len(tables) + 1, run, heading_line)
        if table is not None:
            tables.append(table)
        run.clear()
        heading_line = ""

    for line in lines:
        found = list(_FIGURES.finditer(line.text))
        if found and line.text[: found[0].start()].strip(" .â€¦	"):
            if not run:
                # The line above the first figure row is where a statement writes its
                # years. Captured when the run opens, because by the time it closes the
                # last plain line is whatever came after the table.
                heading_line = last_plain
            run.append((line, found))
        else:
            flush()
            if line.text.strip():
                last_plain = line.text
    flush()
    return tables


def _table_from_run(
    page: int, index: int, run: list[tuple[Line, list[re.Match[str]]]], heading_line: str
) -> Table | None:
    """One table out of a run of figure-carrying lines, or nothing.

    The width is the commonest figure count in the run rather than the largest or the
    smallest: a statement's rows agree, and the ones that do not are carrying a number
    inside their label. A row with fewer figures than the width cannot fill the columns
    and is left out rather than guessed at.
    """
    if len(run) < 2:
        return None
    counts = [len(found) for _, found in run]
    width = max(set(counts), key=counts.count)
    body: list[tuple[str, list[float | None], str]] = []
    for line, found in run:
        if len(found) < width:
            continue
        columns = found[-width:]
        label = line.text[: columns[0].start()].strip(" .â€¦	")
        if not label:
            continue
        body.append((label, [_number(m.group(0)) for m in columns], line.text))
    if len(body) < 2:
        return None
    headings = _headings_for(heading_line, width)
    return Table(
        page=page,
        index=index,
        columns=tuple(
            Column(
                index=n + 1,
                heading=headings[n],
                rows=tuple(
                    Row(label=label, value=values[n], raw=raw, ordinal=ordinal)
                    for ordinal, (label, values, raw) in enumerate(body, start=1)
                ),
            )
            for n in range(width)
        ),
    )


def _cell_value(cell: str | None) -> float | None:
    """A cell's figure, where it holds one. An empty cell and a cell holding the dash a
    statement writes for nil both read as nothing, which is what `Row.value` is nullable
    for - and they are different facts the raw text still carries."""
    return _number(cell) if cell else None


def _tables_from_layout(page: int, laid_out: list[LaidOutTable]) -> list[Table]:
    """The page's tables, where the page had columns to read."""
    built: list[Table] = []
    for table in laid_out:
        made = _table_from_laid_out(page, len(built) + 1, table)
        if made is not None:
            built.append(made)
    return built


def _table_from_laid_out(page: int, index: int, laid_out: LaidOutTable) -> Table | None:
    body = [row for row in laid_out.rows if row.label and any(row.cells)]
    if len(body) < 2:
        return None
    width = len(laid_out.columns)
    # The page's own answer first - a heading matched to the column it is printed over.
    # The token count is the fallback, for a heading line the layout could not place.
    headings = laid_out.headings or _headings_for(laid_out.heading_line, width)
    return Table(
        page=page,
        index=index,
        columns=tuple(
            Column(
                index=n + 1,
                heading=headings[n],
                rows=tuple(
                    Row(
                        label=row.label,
                        value=_cell_value(row.cells[n]),
                        raw=row.text,
                        ordinal=ordinal,
                    )
                    for ordinal, row in enumerate(body, start=1)
                ),
            )
            for n in range(width)
        ),
    )


def _split_figures(text: str) -> tuple[str, list[float | None]]:
    """A line's label and every money-shaped figure on it, left to right.

    The label is what comes before the first figure, which is the whole difference from
    the version that took what came before the last one.
    """
    found = list(_FIGURES.finditer(text))
    if not found:
        return "", []
    label = text[: found[0].start()].strip(" .…	")
    if not label:
        return "", []
    return label, [_number(m.group(0)) for m in found]


def _headings_for(line: str, width: int) -> tuple[str, ...]:
    """The column headings, when the line above the figures names as many as there are.

    A partial match is no match. A header row offering two years over three columns cannot
    say which column is unlabelled, and labelling two of them and leaving one blank is a
    worse answer than saying nothing - the run stops on unlabelled columns, and a column
    wrongly labelled would not stop anything.
    """
    from intake.readers.periods import headings_in

    found = headings_in(line)
    if len(found) == width:
        return found
    # The commonest real header is not all dates: `2025 2024 Change` puts two periods and
    # a derived column over three columns of figures, and reading only the dates finds two
    # headings for three and gives up. So the line's own words are the fallback - but only
    # where every one of them could be a heading and at least one names a period.
    #
    # Without that guard this produced the error it exists to prevent. On page 34 of the
    # filing in fixtures/public the header is split over six lines by the extraction, and
    # the last of them is `2024 $ %`: three tokens over three columns, so the column
    # holding 2025 was labelled 2024 and the other two were labelled with punctuation. A
    # wrong heading is worse than none, because none stops the run and a wrong one does not.
    words = line.split()
    if (
        len(words) == width
        and all(_could_be_a_heading(w) for w in words)
        and any(headings_in(w) for w in words)
    ):
        return tuple(words)
    return ("",) * width


def _could_be_a_heading(word: str) -> bool:
    """A currency mark and a percent sign are what a column is measured in, not what it is
    called. A heading has a letter or a digit in it."""
    return any(ch.isalnum() for ch in word)


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
        # A Word table already has its cells, so the columns are read rather than found.
        # The first cell is the label and every numeric cell after it is a column, which
        # is the same rule the PDF reader applies to a line - and the header row, if the
        # document has one, names them.
        body: list[tuple[str, list[float | None], str]] = []
        heading_cells: list[str] = []
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if not any(cells):
                continue
            values = [_number(c) for c in cells[1:]]
            if not any(v is not None for v in values):
                if not body:
                    heading_cells = cells[1:]
                continue
            body.append((cells[0], values, " | ".join(cells)))
        if not body:
            continue
        # Only the cell positions that actually hold figures. A response column beside an
        # amount column is prose, and a column of nothing but None is not a column - it is
        # a place where a figure would have gone if this had been a different table.
        reach = max(len(v) for _, v, _ in body)
        numeric = [n for n in range(reach) if any(
            n < len(values) and values[n] is not None for _, values, _ in body
        )]
        if not numeric:
            continue
        headings = tuple(
            heading_cells[n].strip() if n < len(heading_cells) else "" for n in numeric
        )
        page.tables.append(
            Table(
                page=1,
                index=index,
                columns=tuple(
                    Column(
                        index=place + 1,
                        heading=headings[place],
                        rows=tuple(
                            Row(
                                label=label,
                                value=values[n] if n < len(values) else None,
                                raw=raw,
                                ordinal=ordinal,
                            )
                            for ordinal, (label, values, raw) in enumerate(body, start=1)
                        ),
                    )
                    for place, n in enumerate(numeric)
                ),
            )
        )
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


def _is_nil(text: str) -> bool:
    """A dash where a figure would be: nothing, as a statement writes it."""
    return not any(ch.isdigit() for ch in text)


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
