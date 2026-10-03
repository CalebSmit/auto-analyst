"""The spreadsheets that are not `.xlsx`, presented as ones that are.

`intake/fingerprint.py` declares four spreadsheet types and the reader behind them calls
openpyxl, which opens two of them. A trial balance sent as a CSV was refused, and the reason
a person was given read **"TB.csv cannot be opened as a workbook (BadZipFile: File is not a
zip file)"**. An `.xls` the same. That had been true since the routing table was written and
the rehearsal passed over it every time, because a refusal on the record counts as an
outcome and nothing asked whether the refusal was right.

So each is converted to a workbook here, at the door, and **nothing above this changes**:
sheet selection, normalisation, the footing check and the `Sheet!A1:B20` locator a figure
cites all go on working on a real openpyxl workbook with real cells. A CSV becomes one
sheet; an `.xls` becomes the sheets it has.

**The part that needs care is the numbers.** A CSV has no types - every cell is text - and
turning `402,000` into a number is a decision about what the comma means. In the United
States it groups thousands and in much of Europe it is the decimal point, so `402,000` is
either four hundred and two thousand or four hundred and two. Writing the wrong one into a
model is the silent error this build exists to prevent, and it is not detectable afterwards
because both readings are plausible figures.

The convention is therefore decided **once per file, from the whole file**, on evidence that
can only mean one thing:

* a cell like `1,234.56` has grouped thousands and a dot decimal - that file is US;
* a cell like `1.234,56` is the other way round - that file is European;
* a separator that always has exactly three digits after it, and never anything else, is
  grouping thousands whichever character it is.

Where nothing in the file decides it, **an ambiguous cell is left as text and reported**
rather than read as a number. A label is a thing a person can see is wrong; a figure that is
a thousand times out is not.
"""

from __future__ import annotations

import codecs
import csv
import io
import re
from dataclasses import dataclass, field

__all__ = ["Conversion", "as_workbook", "converts"]

# What a delimiter can be. Semicolon is what a European Excel writes when the comma is
# already the decimal point, which is exactly the file this module is most careful about.
DELIMITERS = (",", ";", "\t", "|")

_US = re.compile(r"^\(?-?[$£€]?\s*\d{1,3}(?:,\d{3})+\.\d+\)?$")
_EU = re.compile(r"^\(?-?[$£€]?\s*\d{1,3}(?:\.\d{3})+,\d+\)?$")
_GROUPED_BY = {",": re.compile(r"^\(?-?[$£€]?\s*\d{1,3}(?:,\d{3})+\)?$"),
               ".": re.compile(r"^\(?-?[$£€]?\s*\d{1,3}(?:\.\d{3})+\)?$")}


@dataclass(frozen=True)
class Conversion:
    """A workbook, and what had to be decided to make one."""

    workbook: bytes
    """`.xlsx` bytes, which `survey_workbook` and `normalize_workbook` already read."""
    encoding: str = ""
    delimiter: str = ""
    decimal: str = ""
    """`.` or `,` where the file said which, empty where nothing in it did."""
    ambiguous: tuple[str, ...] = field(default_factory=tuple)
    """Cells that could have been two numbers. Left as text, and named here so a person is
    told rather than a figure being guessed."""


def converts(filename: str) -> bool:
    """Whether this file needs converting before the workbook reader sees it."""
    return filename.lower().endswith((".csv", ".tsv", ".xls"))


def as_workbook(data: bytes, filename: str) -> Conversion:
    """The file as a workbook. Raises the way openpyxl does when it cannot be read, so the
    caller's one diagnostic covers every spreadsheet that will not open."""
    if filename.lower().endswith(".xls"):
        return _from_xls(data)
    return _from_separated(data, filename)


# ------------------------------------------------------------------- separated values


def _from_separated(data: bytes, filename: str) -> Conversion:
    text, encoding = _decode(data)
    delimiter = _delimiter(text)
    grid = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not any(any(cell.strip() for cell in row) for row in grid):
        raise ValueError("the file holds no rows")

    decimal, ambiguous = _convention(grid)
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    # Named for the file, because a locator reads `TB 2025!B4` and a sheet called `Sheet`
    # would tell a person nothing about which of three files a figure came from.
    sheet.title = _sheet_name(filename)
    for row in grid:
        sheet.append([_cell(value, decimal, ambiguous) for value in row])
    out = io.BytesIO()
    book.save(out)
    return Conversion(
        workbook=out.getvalue(),
        encoding=encoding,
        delimiter=delimiter,
        decimal=decimal,
        ambiguous=tuple(sorted(ambiguous)[:20]),
    )


def _decode(data: bytes) -> tuple[str, str]:
    """The file's text and the encoding that read it.

    The byte order mark is checked first rather than tried first. `utf-8-sig` decodes a file
    that has no mark perfectly well - the suffix only means it strips one if it is there -
    so trying it first reported every UTF-8 file as `utf-8-sig`, which is a record that
    says something the file does not.

    Then strict UTF-8, then cp1252, which is what Excel on Windows writes and never says.
    cp1252 decodes almost any byte without complaining, so it has to be last or it would
    quietly accept a UTF-8 file and turn every accented name into two characters.
    """
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig"), "utf-8-sig"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), "cp1252"


def _delimiter(text: str) -> str:
    """The character that cuts this file into the same number of fields on every line.

    `csv.Sniffer` guesses from one sample and is wrong on a file whose first rows are a
    title block - which is what an accountant's export looks like. Counting is not clever
    and does not need to be: the delimiter is the one that gives a consistent row width.
    """
    lines = [line for line in text.splitlines() if line.strip()][:50]
    if not lines:
        return ","
    best, score = ",", -1.0
    for candidate in DELIMITERS:
        widths = [len(line.split(candidate)) for line in lines]
        if max(widths) < 2:
            continue
        commonest = max(set(widths), key=widths.count)
        agreement = widths.count(commonest) / len(widths)
        # Width breaks a tie: two delimiters can both be perfectly consistent when one of
        # them simply never appears, and the one that cuts more columns is the real one.
        rank = agreement * 100 + commonest
        if rank > score:
            best, score = candidate, rank
    return best


# ----------------------------------------------------------------------- the numbers


def _convention(grid: list[list[str]]) -> tuple[str, set[str]]:
    """Which character is this file's decimal point, and what stays text because nothing
    said.

    Decided over every cell at once. One unambiguous cell settles the file - `1,234.56` can
    only be read one way - and a file with none of those is read as grouping thousands only
    where the grouping is regular. What is left over is named rather than guessed.
    """
    cells = [cell.strip() for row in grid for cell in row if cell.strip()]
    if any(_US.match(cell) for cell in cells):
        decimal = "."
    elif any(_EU.match(cell) for cell in cells):
        decimal = ","
    else:
        grouped = {
            separator for separator, shape in _GROUPED_BY.items()
            if any(shape.match(cell) for cell in cells)
        }
        # Exactly one separator ever appears in a grouped shape, so that is the grouper and
        # the other is free to be the decimal point. Both, and the file is telling two
        # stories; neither, and there is nothing to decide.
        decimal = {",": ".", ".": ","}[grouped.pop()] if len(grouped) == 1 else ""

    ambiguous: set[str] = set()
    if not decimal:
        for cell in cells:
            if any(shape.match(cell) for shape in _GROUPED_BY.values()):
                ambiguous.add(cell)
    return decimal, ambiguous


def _cell(value: str, decimal: str, ambiguous: set[str]) -> str | float:
    """One cell: a number where it can only be one number, and the text as written where it
    could be two."""
    text = value.strip()
    if not text or text in ambiguous:
        return value
    number = _number(text, decimal)
    return value if number is None else number


def _number(text: str, decimal: str) -> float | None:
    negative = text.startswith("(") and text.endswith(")")
    body = text.strip("()").strip()
    for mark in ("$", "£", "€"):
        body = body.replace(mark, "")
    body = body.strip()
    if not body:
        return None
    # A European file's dots group and its commas decide; everywhere else the commas group.
    # With no convention settled the commas still group, because a cell that could have gone
    # either way never reaches here - it was named as ambiguous and left as text.
    body = (
        body.replace(".", "").replace(",", ".") if decimal == "," else body.replace(",", "")
    )
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", body):
        return None
    value = float(body)
    return -value if negative else value


def _sheet_name(filename: str) -> str:
    """Excel's own rule: thirty-one characters, and none of `[]:*?/\\`."""
    stem = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    stem = stem.rsplit(".", 1)[0] if "." in stem else stem
    for bad in "[]:*?/\\":
        stem = stem.replace(bad, " ")
    return (stem.strip() or "Sheet")[:31]


# ------------------------------------------------------------------------- old excel


def _from_xls(data: bytes) -> Conversion:
    """An `.xls` copied cell for cell into a workbook openpyxl can read.

    xlrd reads the old binary format and nothing else, which is the whole of why it is here.
    Values come back already typed, so none of the convention work above applies: a number
    in an `.xls` is a number and was never text.
    """
    import xlrd
    from openpyxl import Workbook

    source = xlrd.open_workbook(file_contents=data)
    book = Workbook()
    book.remove(book.active)
    for name in source.sheet_names():
        old = source.sheet_by_name(name)
        sheet = book.create_sheet(_sheet_name(name))
        for r in range(old.nrows):
            sheet.append([_xls_value(old.cell(r, c), source) for c in range(old.ncols)])
    if not book.worksheets:
        raise ValueError("the workbook holds no sheets")
    out = io.BytesIO()
    book.save(out)
    return Conversion(workbook=out.getvalue())


def _xls_value(cell: object, book: object) -> object:
    """One `.xls` cell. A date comes back as a number and a mode, and losing the mode turns
    a year end into forty-five thousand."""
    import xlrd

    kind = cell.ctype  # type: ignore[attr-defined]
    value = cell.value  # type: ignore[attr-defined]
    if kind == xlrd.XL_CELL_DATE:
        return xlrd.xldate_as_datetime(value, book.datemode)  # type: ignore[attr-defined]
    if kind == xlrd.XL_CELL_BOOLEAN:
        return bool(value)
    if kind == xlrd.XL_CELL_EMPTY:
        return None
    if kind == xlrd.XL_CELL_ERROR:
        return None
    return value
