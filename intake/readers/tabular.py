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
    contradiction: str = ""
    """Why no convention was settled, where the file itself is the reason: it holds a cell
    only readable one way and another only readable the other. Empty where the file told
    one story or none."""


_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
"""The first bytes of every Office 97-2003 file - and of a password-protected `.xlsx`,
which is an OOXML package wrapped in the same container."""


def converts(filename: str) -> bool:
    """Whether this file needs converting before the workbook reader sees it."""
    return filename.lower().endswith((".csv", ".tsv", ".xls", ".ods"))


def as_workbook(data: bytes, filename: str) -> Conversion:
    """The file as a workbook. Raises the way openpyxl does when it cannot be read, so the
    caller's one diagnostic covers every spreadsheet that will not open."""
    name = filename.lower()
    if name.endswith(".xls"):
        # Extremely common from legacy systems: a tab-separated text file saved under an
        # `.xls` name. It is readable content in the wrong wrapper, and xlrd's "Expected
        # BOF record" told a person to ask the client for another copy of a fine file.
        if not data.startswith(_OLE2) and b"\x00" not in data[:8192]:
            return _from_separated(data, filename)
        return _from_xls(data)
    if name.endswith(".ods"):
        return _from_ods(data)
    return _from_separated(data, filename)


# ------------------------------------------------------------------- separated values


def _from_separated(data: bytes, filename: str) -> Conversion:
    text, encoding = _decode(data)
    delimiter = _delimiter(text)
    grid = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not any(any(cell.strip() for cell in row) for row in grid):
        raise ValueError("the file holds no rows")

    decimal, ambiguous, contradiction = _convention(grid)
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
        contradiction=contradiction,
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
    # UTF-16 is what Excel's "Unicode Text" and a good many ERP exports write. Without this
    # the bytes fell through to cp1252, "succeeded" as NUL-interleaved text, and were
    # refused three layers later by openpyxl complaining about a NUL in a cell - a guard
    # that worked by coincidence, and told the person nothing about their file.
    for mark, encoding in ((codecs.BOM_UTF16_LE, "utf-16-le"), (codecs.BOM_UTF16_BE, "utf-16-be")):
        if data.startswith(mark):
            return data[len(mark):].decode(encoding), encoding
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


def _convention(grid: list[list[str]]) -> tuple[str, set[str], str]:
    """Which character is this file's decimal point, and what stays text because nothing
    said.

    Decided over every cell at once. One unambiguous cell settles the file - `1,234.56` can
    only be read one way - and a file with none of those is read as grouping thousands only
    where the grouping is regular. What is left over is named rather than guessed.
    """
    cells = [cell.strip() for row in grid for cell in row if cell.strip()]
    us = [cell for cell in cells if _US.match(cell)]
    eu = [cell for cell in cells if _EU.match(cell)]
    if us and eu:
        # The file is telling two stories, and this used to take the first one it met and
        # apply it to every cell - so `1.234,56` beside `402,000` read the second as 402.0,
        # a thousand times out, with nothing said, because the reporting lived behind "no
        # convention" and a settled one reported nothing. Two stories is no convention.
        decimal = ""
    elif us:
        decimal = "."
    elif eu:
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
    contradiction = ""
    if not decimal:
        for cell in cells:
            grouped_shape = any(shape.match(cell) for shape in _GROUPED_BY.values())
            if grouped_shape or _US.match(cell) or _EU.match(cell):
                ambiguous.add(cell)
        if us and eu:
            contradiction = (
                f"the file is telling two stories: {us[0]} reads one way and {eu[0]} the "
                f"other, so no decimal convention was settled and every grouped figure is "
                f"left as text"
            )
    else:
        # A cell written the other way under a settled convention is reported rather than
        # reinterpreted. `1.234,56` in a file that decided on `.` is not 1.23456 - and
        # `402,000` in a file that decided on `,` is not 402.0, which is the thousand-fold
        # error this was found by: the other story's *grouped* shape counts too, because
        # under the settled convention it would read as a decimal with three places.
        others = (_EU, _GROUPED_BY["."]) if decimal == "." else (_US, _GROUPED_BY[","])
        told = [cell for cell in cells if any(shape.match(cell) for shape in others)]
        ambiguous.update(told)
        if told:
            settled_by = (us or eu)[0]
            contradiction = (
                f"the file is telling two stories: {settled_by} settled the decimal point "
                f"as {decimal!r} and {told[0]} reads the other way, so it and "
                f"{len(told) - 1} more like it are left as text"
            )
    return decimal, ambiguous, contradiction


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


def _from_ods(data: bytes) -> Conversion:
    """An OpenDocument spreadsheet copied cell for cell into a workbook openpyxl can read.

    What a client on LibreOffice sends instead of an `.xlsx`, and until now it reached
    `kind="other"` - routed nowhere, read by nothing, and nothing said so. It belongs on this
    seam rather than in a reader of its own for the reason the `.csv` does: everything above
    the conversion goes on reading a workbook, including the `Sheet!A1` locator a figure will
    cite for as long as the figure exists.

    `odfpy` is pure Python and pulls in `defusedxml`, which is the right dependency to gain
    on a path that opens a client's file: an ODS is a zip of XML, and XML from outside is
    where entity-expansion attacks live.

    **A cell carries its type and its text separately**, and the type is what to read. The
    text is a *display* string - LibreOffice writes `1,234.5` or `1.234,5` there depending on
    the locale the file was saved in, and parsing that back would reinvent the ambiguity the
    separated-values path above exists to resolve. `office:value` is the number itself, in a
    fixed format, always with a period. So there is no convention work here and nothing to
    report as ambiguous: a number in an ODS is a number and was never text.
    """
    import io as _io

    from odf.opendocument import load
    from odf.table import Table, TableCell, TableRow
    from openpyxl import Workbook

    document = load(_io.BytesIO(data))
    book = Workbook()
    book.remove(book.active)
    for table in document.getElementsByType(Table):
        sheet = book.create_sheet(_sheet_name(str(table.getAttribute("name") or "Sheet")))
        for row in table.getElementsByType(TableRow):
            cells: list[object] = []
            for cell in row.getElementsByType(TableCell):
                # A cell may say it stands for several columns - that is how an ODS writes a
                # run of empty ones - and dropping the repeat would shift every figure on the
                # row to the left, which is exactly the class of error this build is about.
                repeat = cell.getAttribute("numbercolumnsrepeated")
                for _ in range(max(1, int(repeat) if repeat and repeat.isdigit() else 1)):
                    cells.append(_ods_value(cell))
            while cells and cells[-1] is None:
                cells.pop()
            sheet.append(cells)
    if not book.worksheets:
        raise ValueError("the spreadsheet holds no sheets")
    out = io.BytesIO()
    book.save(out)
    return Conversion(workbook=out.getvalue())


def _ods_value(cell: object) -> object:
    """One ODS cell, by the type it declares rather than by the text it displays.

    `office:value-type` says what it is and `office:value` carries the number, so a float
    arrives as a float and a date keeps its own string. Reading the displayed text instead
    would make `1.234` four hundred times too small or too large depending on where the file
    was saved, which is undetectable afterwards because both are plausible figures.
    """
    kind = str(cell.getAttribute("valuetype") or "")  # type: ignore[attr-defined]
    if kind in ("float", "percentage", "currency"):
        raw = cell.getAttribute("value")  # type: ignore[attr-defined]
        try:
            return float(str(raw))
        except (TypeError, ValueError):
            return str(cell).strip() or None
    if kind == "boolean":
        return str(cell.getAttribute("booleanvalue") or "")  # type: ignore[attr-defined]
    if kind == "date":
        return str(cell.getAttribute("datevalue") or "")  # type: ignore[attr-defined]
    if kind == "time":
        return str(cell.getAttribute("timevalue") or "")  # type: ignore[attr-defined]
    text = str(cell).strip()
    return text or None


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
