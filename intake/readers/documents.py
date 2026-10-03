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
from typing import Any

from intake.readers.layout import LaidOutTable, lay_out, lay_out_words
from ops.source_parse import Row

__all__ = [
    "Column",
    "Line",
    "NotText",
    "Page",
    "ParsedDocument",
    "Table",
    "looks_like",
    "read_document",
]

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


class NotText(Exception):
    """The file is whole and this build does not read its format.

    Different from a file that will not open, and the answer a person gets is different:
    save it as something that is read, rather than ask the client for it again. Carries what
    the file actually is, read from its first bytes rather than from its name.
    """

    def __init__(self, looks_like: str) -> None:
        super().__init__(looks_like)
        self.looks_like = looks_like


IMAGES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")
"""The extensions that go to the OCR port rather than to a decoder.

Spelled here as well as in `intake/fingerprint.py`, because the two answer different
questions - that table says what a file *is* for the manifest, this says which reader takes
it - and importing the one into the other would drag a database session into a module that
reads bytes. `tests/p155` holds the two to naming the same formats, which is the cheaper
half of the trade and the half that catches a format added to one and forgotten in the other.
"""

# What a file's first bytes say it is, whatever its name says. A `.doc` renamed `.txt` is
# still an OLE2 compound file, and a reader that trusted the extension would decode it.
SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "a Word 97-2003 or Excel 97-2003 file (OLE2)"),
    (b"PK\x03\x04", "a zip archive - a .docx, .xlsx or .pptx under another name"),
    (b"\x89PNG\r\n\x1a\n", "a PNG image"),
    (b"\xff\xd8\xff", "a JPEG image"),
    (b"GIF8", "a GIF image"),
    (b"II*\x00", "a TIFF image"),
    (b"MM\x00*", "a TIFF image"),
    (b"%PDF", "a PDF under another name"),
    (b"\x1f\x8b", "a gzip archive"),
    (b"Rar!", "a RAR archive"),
    (b"\x7fELF", "a program"),
    (b"MZ", "a program"),
)


def looks_like(data: bytes) -> str | None:
    """What this file is, or `None` where it reads as text.

    Signatures first, so the answer names the format. Then a NUL byte, which is the one
    thing a text file in any encoding does not contain and every binary format does - a
    general catch for the formats nobody listed, which is the group that matters, because
    the list will always be shorter than the world.
    """
    for magic, name in SIGNATURES:
        if data.startswith(magic):
            return name
    if b"\x00" in data[:8192]:
        return "a binary file"
    return None


def read_document(data: bytes, filename: str) -> ParsedDocument:
    name = filename.lower()
    if name.endswith(".pdf"):
        return _read_pdf(data, filename)
    if name.endswith(".docx"):
        return _read_docx(data, filename)
    if name.endswith(".rtf"):
        return _read_rtf(data, filename)
    # Before `looks_like`, which would refuse every one of these on its first bytes - a PNG
    # signature is exactly what that function exists to catch. An image is not a file that
    # failed to be text; it is a page with no text layer, and there is a port for that.
    if name.endswith(IMAGES):
        return _read_image(data, filename)
    if name.endswith(".eml"):
        return _read_email(data, filename)
    if name.endswith((".msg", ".xlsb")):
        # Routed so they can be refused by name, which is what routing is for. Both are
        # binary and both have readers in the world; neither has a real example on this
        # machine to measure one against, and a half-working parser for a binary format
        # produces plausible partial content - the failure this repository is most careful
        # about. `.msg` is also an OLE2 file, so `looks_like` would name it a Word document,
        # which is the wrong advice entirely.
        raise NotText(
            "an Outlook message (.msg)" if name.endswith(".msg")
            else "an Excel binary workbook (.xlsb)"
        )
    # Everything left is read as text, and so everything left has to *be* text. This branch
    # used to take anything: an RTF arrived as one line of `{\rtf1\ansi\ansicpg1252...`, and
    # a `.doc` arrived as replacement characters and a dump of the bytes 0 to 255 - both
    # written to the parse store as rows a figure could cite, both classified, and both
    # appended to the text a model is sent. Content, not an error, and nothing downstream
    # could tell either from a sentence somebody wrote.
    found = looks_like(data)
    if found is not None:
        raise NotText(found)
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
    # Which pages were scanned is settled before OCR runs, because OCR fills the lines in
    # and the question would otherwise answer itself wrongly.
    recognised = _ocr_the_scanned_pages(doc, data)

    # Where the words are, if they can be had. A page with a text layer is laid out from the
    # page; a page that had none is laid out from the boxes the engine returned, through the
    # same reader. Only a page nobody could give coordinates for falls back to reading its
    # lines - and that is a real case, not a formality: an engine offering no geometry, and
    # a PDF whose every line is one drawn string with no column structure at all.
    laid_out = lay_out(data)
    for parsed in doc.pages:
        from_text_layer = None if laid_out is None else laid_out.get(parsed.number)
        words = recognised.get(parsed.number)
        if parsed.number not in scanned and from_text_layer:
            parsed.tables.extend(_tables_from_layout(parsed.number, from_text_layer))
        elif words:
            parsed.tables.extend(
                _tables_from_layout(parsed.number, lay_out_words(parsed.number, words))
            )
        else:
            parsed.tables.extend(
                _tables_from_lines(
                    parsed.number, [line for line in parsed.lines if not line.hidden]
                )
            )
    return doc


def _read_image(data: bytes, filename: str) -> ParsedDocument:
    """A screenshot, a photograph of a page, an image somebody pasted into an email.

    The clients send these constantly and until now they reached no reader at all - routed
    nowhere, so the figures on them were keyed by hand with nothing recording where they came
    from.

    An image is a one-page document with no text layer, which is exactly what a scanned PDF
    page is. So it is built as one empty page and handed to the same OCR seam, and from there
    it travels the road a scan travels: boxes, then bands, then rows, then tables, then the
    locators a figure cites.

    Nothing is invented where no engine is configured. The page stays empty, `Page.scanned`
    stays true, and that is what the manifest carries - the same honest answer a scanned PDF
    gets, rather than a blank the pipeline filled in.
    """
    doc = ParsedDocument(filename=filename, kind="image", pages=[Page(number=1)])
    recognised = _ocr_the_scanned_pages(doc, data, kind="image")
    for parsed in doc.pages:
        words = recognised.get(parsed.number)
        if words:
            parsed.tables.extend(
                _tables_from_layout(parsed.number, lay_out_words(parsed.number, words))
            )
        else:
            parsed.tables.extend(_tables_from_lines(parsed.number, parsed.lines))
    return doc


def _ocr_the_scanned_pages(
    doc: ParsedDocument, data: bytes, kind: str = "pdf"
) -> dict[int, list[dict[str, Any]]]:
    """Fill in the pages that had no text layer, if an engine is configured.

    Returns the words and their boxes for each page it read, so the caller can lay the page
    out the way it lays out a text layer. Tables are built afterwards rather than here: from
    this point a scan and a text layer travel the same road, and no locator, guard or
    citation downstream needs to know which it was.

    **The boxes are the whole of it.** Before they were carried, this appended the engine's
    text and nothing else, and some engines return a *cell* at a time - `Total assets`, then
    `521,728`, then `608,846`. The line reader wants a line carrying a label and all of its
    figures, so a scanned balance sheet came out as 122 lines, 0 tables and 0 rows, with
    every figure read correctly and all of them discarded.

    Nothing is invented. With no engine the port raises, the pages stay empty, and
    `Page.scanned` goes on being true - which is what the manifest has always carried and is
    the honest answer. An engine that fails mid-document leaves the pages it did not reach in
    exactly that state, and a page whose geometry nobody could give is returned without
    words rather than with a guess at them.
    """
    if not any(page.scanned for page in doc.pages):
        return {}
    from ports import get_ocr  # noqa: PLC0415 - deferred: reading a text PDF must not need it
    from ports.ocr import OCRUnavailable  # noqa: PLC0415

    try:
        read = get_ocr().read(data, kind=kind)
    except OCRUnavailable:
        return {}

    words: dict[int, list[dict[str, Any]]] = {}
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
        laid_out = found.laid_out()
        if laid_out:
            words[page.number] = laid_out
    return words


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


def _read_rtf(data: bytes, filename: str) -> ParsedDocument:
    """An RTF, as the words a person reads.

    An RTF is text with its formatting written into the same stream, so the fallback reader
    stored the control words as the document: one line beginning `{` and naming the fonts.
    `striprtf` leaves the font table, the stylesheet and the generator behind and turns the
    escapes back into characters - `'24` into a dollar sign, `'e9` into an accented e, and
    the numeric ones into what they stand for, which matters here because an em dash is one
    of the things the prose checks are about.

    Read as a page of lines, like a text file, because that is what an RTF is: a letter or a
    memorandum. Nothing claims it has tables.
    """
    from striprtf.striprtf import rtf_to_text

    markup, _ = _decode_text(data)
    # striprtf ships no type information, so the call is annotated here rather than the
    # whole module being excused from type checking.
    words: str = rtf_to_text(markup)  # type: ignore[no-untyped-call]
    return _read_text(words.encode("utf-8"), filename)


def _read_email(data: bytes, filename: str) -> ParsedDocument:
    """A saved email: its message, and the names of what it carries.

    What arrives when somebody saves the email instead of the attachment, which happens
    constantly - and until now it reached `kind="other"`, so the trial balance inside it was
    not read and nothing said there was one.

    **The attachments are named and not extracted.** Extracting one would make a file out of
    a file, and every guarantee downstream is built on a `source_id` that is the hash of
    something a person put in a folder: a figure citing `p3/t1/r7` of an attachment that
    exists only inside another document has a locator nobody can open. Naming them is the
    answer somebody can act on - *this email carries TB_FY25.xlsx, send me that* - and it is
    the request list's job from there.

    The body is read as the text it is, so an instruction in an email is covered by the same
    Untrusted Content Boundary as an instruction in a letter.
    """
    import email
    from email import policy

    message = email.message_from_bytes(data, policy=policy.default)
    lines: list[str] = []
    for header in ("Date", "From", "To", "Subject"):
        said = message.get(header)
        if said:
            lines.append(f"{header}: {said}")

    attachments: list[str] = []
    bodies: list[str] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        name = part.get_filename()
        if name or part.get_content_disposition() == "attachment":
            attachments.append(str(name or "an unnamed attachment"))
            continue
        if part.get_content_type() == "text/plain":
            try:
                bodies.append(str(part.get_content()))
            except (LookupError, UnicodeDecodeError):  # pragma: no cover - a broken charset
                continue

    for body in bodies:
        lines.extend(line.strip() for line in body.splitlines() if line.strip())
    if attachments:
        # On the page rather than only in a payload, because this is the sentence a person
        # acts on, and it is the whole reason an email is worth reading at all.
        lines.append(
            "This email carries "
            + ", ".join(attachments)
            + " - the figures are in there, and this build reads a file a person saves, "
            "not a file inside a file. Save the attachment and send that."
        )

    doc = ParsedDocument(filename=filename, kind="email", pages=[Page(number=1)])
    doc.pages[0].lines.extend(Line(line) for line in lines)
    doc.pages[0].tables.extend(_tables_from_lines(1, doc.pages[0].lines))
    return doc


def _decode_text(data: bytes) -> tuple[str, str]:
    """A text file's characters and the encoding that read them.

    The same order the spreadsheet reader uses and for the same reason: a byte order mark is
    checked rather than tried, strict UTF-8 next, and cp1252 last because it decodes almost
    any byte without complaining and would quietly accept a UTF-8 file.
    """
    import codecs

    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig"), "utf-8-sig"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), "cp1252"


def _read_text(data: bytes, filename: str) -> ParsedDocument:
    page = Page(number=1)
    for raw in _decode_text(data)[0].splitlines():
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
