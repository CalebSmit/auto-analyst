"""Where a row and a column are on the page.

The Document Reader read a PDF as a stream of text lines and treated each line as a
statement row. On a real filing that is not true, and it fails in both directions at once.

**A row can be two lines.** An audited statement sets its grand total on a ruled row, and
the PDF emits the label and the figures as separate runs. Page 56 of the filing in
`fixtures/public` reads:

    Total assets
    $ 521,728 $ 608,846

so the run of figure-carrying lines broke at the label, the label became a plain line, and
**Total assets 521,728 was built by nothing at all.** Total liabilities went the same way.
Those are the two figures a balance sheet exists to state.

**A line can be more than a row.** The Common stock line wraps, and the first of its two
lines reads `Common stock, $0.001 par value, authorized 220,000 shares; shares issued
145,581 and`. Taking the last figures on the line stored Common stock as **220,000** - the
authorized share count - where the balance is 146. A share count, in the equity section,
confidently, past every guard: provenance passes because the number is at that locator, and
footing passes because the row is not a total.

Both are the same mistake. **A row is a band of the page and a column is a band too**, and
the text stream knows neither. On page 56 the two figure columns sit within three points of
x=482 and x=549 - thirty-one figures on one, thirty-two on the other - and the 220,000
inside that label sits at x=234, nowhere near either. Coordinates separate those; no amount
of reading the text can.

**Figures align on their right edge**, which is what makes a column findable: left edges
scatter with the width of the number (449, 454, 459 on one column) and right edges do not.
Measured across the filing's statement pages, the right edges cluster into exactly as many
groups as the statement has columns, every time.

**A column belongs to a table, not to a page.** Clustering a whole page at once gave page 30
nine columns and page 61 six, because those pages carry several tables whose columns are at
different places - and then no table's headings lined up with its own figures. Each run of
figure-bearing rows is clustered on its own.

**And this reader does not take every page.** A PDF whose lines are each one drawn string
has no column geometry at all: the figures end wherever the text ends, and whatever clusters
out of that is a coincidence. Such a page is read the way it always was. The test is whether
a run resolves into **two or more** columns, because one column is exactly the case the line
reader already handles and the multi-column case is where its "last few figures on the line"
rule does the damage.

What this module does **not** do is decide anything about meaning. It reports where the
words were. Every rule about what a figure is, what a heading says and what a label means
stays where it was.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

__all__ = ["LaidOutRow", "LaidOutTable", "lay_out"]

# What pdfplumber hands back for a word: its text and where it is.
Word = dict[str, Any]

# How far apart two words can be and still be one word. Measured on the filing: at 3
# (pdfplumber's default) `Total assets` came back merged with the rest of its row and the
# row was unfindable; at 1.5 the page reads as a person does. A PDF positions glyphs and
# does not always write the spaces between them.
WORD_GAP = 1.5

# How much of their height two words must share to be on the same row.
#
# Not a distance between baselines, because a figure set against a label that wraps over two
# lines is centred on the pair and sits on neither. On the filing's balance sheet the Common
# stock balance - 146 and 136 - is printed 4.5 points above the second line of its own
# label, so a baseline rule either misses it or is loose enough to start merging rows.
#
# Overlap says it directly and scales with the type size. Measured over nine statement pages
# of the filing: a word is 8 to 10 points tall, consecutive baselines within one row differ
# by 0, 1 or 4 points, and the next row down is 12 to 16 away. **Nothing falls between 5 and
# 11.** Three points of shared height is inside that gap from both sides - it joins
# everything printed on one row and cannot reach the row below.
ROW_OVERLAP = 3.0

# How far a figure's right edge can be from a column's and still be in it. The same figure
# column measured 549 and 552 on two pages of one document, because a trailing `)` on a
# negative sits outside the digits.
COLUMN_BAND = 4.0

# A column has to run down the table. Two figures that happen to end at the same x are a
# coincidence; a statement's column is on most of its rows.
COLUMN_NEEDS = 3

# There was a second test here - that a cluster also had to hold a fair share of its table's
# fullest column - added when a `2025` in a header and a `$0.001` in a sentence made a third
# column on the balance sheet at x=142. It is gone, because `_ESTABLISHES` below already
# excludes both: neither is money-shaped. Measured over all 108 pages of the filing with the
# share test at 0.2 and at 0, **not one page differs**. A threshold that never binds is a
# threshold nobody can check, and its comment was still describing a phantom that can no
# longer form.

# One column is the case the line reader already reads correctly, and taking it here only
# risks finding a column where the page has none.
COLUMNS_NEEDED = 2

# What may establish a column, and what may fill one, are deliberately different.
#
# **A column is established by a figure a statement writes as money**: grouped with commas,
# or parenthesised because it is negative. Bare digits are not enough, and the reason is a
# header row: `2025 2024 Change` is three bare numbers, and treating those as figures put
# the header inside the table as its first row and left every column with no heading at
# all. This is the same judgement `documents._FIGURES` already made for the line reader -
# a page number, a note reference and a year are all numbers and none is a column.
_ESTABLISHES = re.compile(r"^\(?[$£€]?\s*-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?$|^\(-?[\d.]+\)$")

# **A column is filled by whatever is printed at its position.** Once the column exists,
# a bare number in it is that column's value - which is how the balance sheet's Common
# stock balance of 146, four figures short of needing a comma, is read at all.
_FILLS = re.compile(r"^\(?[$£€]?\s*-?[\d,]+(?:\.\d+)?\)?$")
_NIL = re.compile(r"^[$£€]?\s*[—–-]$")


@dataclass(frozen=True)
class LaidOutRow:
    """One band of the page: what it says, and which of its table's columns it fills."""

    text: str
    """Every word on the row in reading order - what a person reads."""
    label: str
    """The words to the left of the first column. A number in here is part of the label,
    which is the point: `authorized 220,000 shares` is not a column."""
    cells: tuple[str | None, ...]
    """One per column, in page order. `None` where the row puts nothing in that column,
    which is not the same as a column holding a dash."""


@dataclass(frozen=True)
class LaidOutTable:
    page: int
    heading_line: str
    """The last row above this one that carried no figures - where a statement writes its
    years. Passed up as text; what it means is the reader's business, not this module's."""
    headings: tuple[str, ...]
    """The word printed above each column, matched by where it sits rather than by counting
    tokens. `(in thousands) 2025 2024 Change` is five tokens over three columns and a count
    can make nothing of it; the page says plainly that 2025 is above the first column.

    Empty where any column has no word above it. A partial naming is no naming: a header
    offering two years over three columns cannot say which column is the unnamed one."""
    rows: tuple[LaidOutRow, ...]
    columns: tuple[float, ...]


def lay_out(data: bytes) -> dict[int, list[LaidOutTable]] | None:
    """Every page's tables, read off the page, or `None` if it cannot be read that way.

    `None` rather than an exception or an empty result: a PDF this cannot open is one the
    caller should read the way it always did, and a caller that cannot tell "no columns
    here" from "I could not look" will quietly lose a document.
    """
    try:
        import pdfplumber
    except ImportError:  # pragma: no cover - declared in pyproject
        return None
    try:
        with pdfplumber.open(io.BytesIO(data)) as doc:
            return {
                number: _tables(number, page.extract_words(x_tolerance=WORD_GAP))
                for number, page in enumerate(doc.pages, start=1)
            }
    except Exception:  # noqa: BLE001 - pdfminer raises a zoo, all meaning "not readable"
        return None


def _tables(page: int, words: list[Word]) -> list[LaidOutTable]:
    tables: list[LaidOutTable] = []
    run: list[list[Word]] = []

    heading_band: list[Word] = []
    last_plain_band: list[Word] = []

    def flush() -> None:
        nonlocal heading_band
        built = _table(page, run, heading_band)
        if built is not None:
            tables.append(built)
        run.clear()
        heading_band = []

    for band in _bands(words):
        if any(_is_figure(word["text"]) for word in band):
            if not run:
                heading_band = last_plain_band
            run.append(band)
        else:
            flush()
            if " ".join(word["text"] for word in band).strip():
                last_plain_band = band
    flush()
    return tables


def _is_figure(text: str) -> bool:
    """Money-shaped: enough to say a column is here."""
    return bool(_ESTABLISHES.match(text)) and any(c.isdigit() for c in text)


def _fills_a_cell(text: str) -> bool:
    """Number-shaped, or the dash a statement writes where a figure would be."""
    return bool(_NIL.match(text)) or (
        bool(_FILLS.match(text)) and any(c.isdigit() for c in text)
    )


def _bands(words: list[Word]) -> list[list[Word]]:
    """Words grouped into the rows they are printed on, top of the page first.

    A band grows while each new word still shares height with it, so a wrapped label and the
    figures centred against it end up together: the figures overlap both lines of the label
    even where the two lines do not overlap each other.
    """
    bands: list[list[Word]] = []
    spans: list[tuple[float, float]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if bands:
            top, bottom = spans[-1]
            shared = min(bottom, word["bottom"]) - max(top, word["top"])
            if shared >= ROW_OVERLAP:
                bands[-1].append(word)
                spans[-1] = (min(top, word["top"]), max(bottom, word["bottom"]))
                continue
        bands.append([word])
        spans.append((word["top"], word["bottom"]))
    # Reading order, not x order. A band that joined a wrapped label to its figures holds
    # words from more than one printed line, and sorting the lot by x alone interleaves
    # them: `Common 135,510 as stock, of December $0.001 par 31, value,` is that row's words
    # in x order and is not a label anybody can read.
    return [sorted(band, key=lambda w: (round(w["top"], 1), w["x0"])) for band in bands]


def _columns(run: list[list[Word]]) -> tuple[float, ...]:
    """The right edges that enough of this run's figures share.

    Clustered on the right edge because that is the edge a statement aligns. Taking the left
    edge instead finds one cluster per number width, which on the filing's balance sheet was
    six clusters for two columns.
    """
    edges = sorted(word["x1"] for band in run for word in band if _is_figure(word["text"]))
    clusters: list[list[float]] = []
    for edge in edges:
        if clusters and edge - clusters[-1][-1] <= COLUMN_BAND:
            clusters[-1].append(edge)
        else:
            clusters.append([edge])
    if not clusters:
        return ()
    return tuple(
        sum(cluster) / len(cluster) for cluster in clusters if len(cluster) >= COLUMN_NEEDS
    )


def _table(page: int, run: list[list[Word]], heading_band: list[Word]) -> LaidOutTable | None:
    if len(run) < 2:
        return None
    columns = _columns(run)
    if len(columns) < COLUMNS_NEEDED:
        return None
    rows = tuple(_row(band, columns) for band in run)
    if sum(1 for row in rows if row.label and any(row.cells)) < 2:
        return None
    return LaidOutTable(
        page=page,
        heading_line=" ".join(word["text"] for word in heading_band),
        headings=_headings(heading_band, columns),
        rows=rows,
        columns=columns,
    )


def _headings(band: list[Word], columns: tuple[float, ...]) -> tuple[str, ...]:
    """The word above each column, by nearest right edge.

    Measured on the filing: a heading sits about twenty points to the left of its column's
    right edge and the columns are about sixty-seven apart, while a prefix like
    `(in thousands)` is three to four hundred points away. So "nearest, and nearer than
    half the way to the next column" separates them with no tuned distance in it.
    """
    if not band or len(columns) < 2:
        return ()
    found: list[str] = []
    for position, column in enumerate(columns):
        nearest = min(band, key=lambda word: abs(word["x1"] - column))
        reach = min(abs(column - other) for n, other in enumerate(columns) if n != position) / 2
        if abs(nearest["x1"] - column) > reach or not _names_a_column(nearest["text"]):
            return ()
        found.append(nearest["text"])
    return tuple(found)


def _names_a_column(text: str) -> bool:
    """Whether a word can be a column's name at all.

    The word nearest a column is sometimes a currency mark or a percent sign: page 34 of the
    filing heads its columns over six lines and the last of them reads `2024 $ %`. Calling
    the `$` a heading named one column `$`; skipping it and reaching for the next word named
    the 2025 column 2024, which is worse. A column whose nearest word is not a name is a
    column nobody named, and this build escalates that to a person rather than guessing it.
    """
    stripped = text.strip().strip("()")
    # Two characters, so a footnote marker is not a name either. Page 67 heads a column
    # `(a)` and the matcher called that column `(a)`, which tells a reader exactly as much
    # as `$` did and reads as though somebody decided it.
    return sum(1 for c in stripped if c.isalnum()) >= 2


def _row(band: list[Word], columns: tuple[float, ...]) -> LaidOutRow:
    cells: list[str | None] = [None] * len(columns)
    taken: set[int] = set()
    for position, column in enumerate(columns):
        for index, word in enumerate(band):
            if index in taken or abs(word["x1"] - column) > COLUMN_BAND:
                continue
            if not _fills_a_cell(word["text"]):
                continue
            cells[position] = word["text"]
            taken.add(index)
            break

    # The label stops where the first column starts. A word reaching into the first column's
    # space belongs to that column or to nothing; it is never label.
    edge = columns[0] - COLUMN_BAND
    label_words = [
        word["text"]
        for index, word in enumerate(band)
        if index not in taken and word["x1"] < edge
    ]
    # A currency mark printed at the left of a figure column belongs to the figure, not to
    # the label it follows: a statement writes `$` on its first row and its total row and
    # nowhere else, so leaving it on made two different labels of `Total assets`.
    while label_words and label_words[-1] in ("$", "£", "€"):
        label_words.pop()
    return LaidOutRow(
        text=" ".join(word["text"] for word in band),
        label=" ".join(label_words).strip(),
        cells=tuple(cells),
    )
