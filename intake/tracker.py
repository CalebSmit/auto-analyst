"""The due-diligence tracker: read the folder, update the list, leave his notes alone.

His words for it: *"it just reads what we asked for and what we received, and updates it
whenever we get info from the client."* Pointed at a folder from the dashboard.

The workbook **is** the list (2026-09-18-1). The firm sends a request list and then tracks
against the same file, each item carrying `In Model?`, notes, and whether it has been
provided or does not apply. So there is one artefact here rather than two, and for an
engagement that has no list at all it is also how the list comes into existence.

**The rule that matters more than any of the matching.** A re-run preserves everything a
person wrote. Notes, `In Model?`, `Not Applicable` - all of it survives, because an update
that overwrote them would be worse than no update at all: they would have to be re-entered
after every refresh, and so they would stop being entered. What the tool owns is the three
columns it derives - the status, how it decided, and the evidence. What a person owns, it
reads and writes back unchanged.

**Matching is deliberately shallow here.** A file is classified from its name, its sheet
names and its first rows - not from a full parse, no OCR, no model. That is enough to
recognise a trial balance and cheap enough to run on a button press over a folder of
sixty documents. Anything it cannot place is *reported*, not guessed at: a file that
answered nothing is the thing a person most needs to see, because it is either a document
nobody asked for or an item nobody matched.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from intake.readers.classify import Evidence, classify
from intake.request_list import (
    Arrived,
    ItemRef,
    RequestList,
    Status,
    parse_ref,
)

__all__ = [
    "DERIVED",
    "THEIRS",
    "Seen",
    "Tracker",
    "look_at",
    "read_tracker",
    "write_tracker",
]

THEIRS = ("In Model?", "Notes", "Not Applicable")
"""The columns a person owns. Read, carried across a refresh, and never written over.

`Not Applicable` is a person's decision about the engagement and the tool has no business
forming a view on it. `In Model?` and `Notes` are their working record. A refresh that
cleared any of the three would make the tracker something you fill in once.
"""

DERIVED = ("Status", "Matched by", "Evidence", "Checked")
"""The columns the tool owns. Rewritten on every run, because they are its answer."""

_HEADERS = ("Ref", "Section", "Item", "Essential", *THEIRS, *DERIVED)

_SHALLOW_ROWS = 12
"""How much of a file to look at. Enough for a header block and the start of a table;
little enough that a folder of sixty documents is a button press rather than a job."""


@dataclass(frozen=True)
class Seen:
    """One file in the folder, and what could be made of it cheaply."""

    path: str
    kind: str | None
    confidence: float = 0.0
    ref: ItemRef | None = None

    def arrival(self) -> Arrived:
        return Arrived(path=self.path, ref=self.ref, kind=self.kind)


@dataclass
class Tracker:
    """A request list, what has arrived against it, and what a person has written."""

    request_list: RequestList
    seen: tuple[Seen, ...] = ()
    theirs: dict[str, dict[str, str]] = field(default_factory=dict)
    """Per item reference, the columns a person owns. Carried across a refresh."""

    @property
    def not_applicable(self) -> frozenset[ItemRef]:
        """Read from what a person wrote, not from the code's own opinion."""
        marked = set()
        for ref, columns in self.theirs.items():
            if str(columns.get("Not Applicable", "")).strip().lower() in ("y", "yes", "x", "true"):
                parsed = parse_ref(ref)
                if parsed is not None:
                    marked.add(parsed)
        return frozenset(marked)

    def report(self) -> dict[str, Any]:
        listing = RequestList(
            self.request_list.items,
            self.not_applicable,
            name=self.request_list.name,
            origin=self.request_list.origin,
        )
        out = listing.report(s.arrival() for s in self.seen)
        out["unmatched_files"] = list(self.unmatched())
        out["files_seen"] = len(self.seen)
        return out

    def unmatched(self) -> tuple[str, ...]:
        """Files that answered nothing, which is what a person most needs to see.

        Either a document nobody asked for - worth knowing, it may answer an item that is
        not on the list - or one the matching failed on. Both want a look, and neither is
        visible from a coverage report, which only ever lists items.
        """
        answered = {
            path
            for row in self.report_rows()
            for path in row.evidence
        }
        return tuple(s.path for s in self.seen if s.path not in answered)

    def report_rows(self) -> tuple[Any, ...]:
        listing = RequestList(
            self.request_list.items,
            self.not_applicable,
            name=self.request_list.name,
            origin=self.request_list.origin,
        )
        return listing.coverage(s.arrival() for s in self.seen)


def look_at(storage: Any, prefix: str = "") -> tuple[Seen, ...]:
    """Every file under the prefix, classified from what can be read cheaply.

    Shallow on purpose: the filename, the sheet names and the first rows. No full parse,
    no OCR, no model - this runs on a button press over a folder that may hold sixty
    documents, and a tracker that took four minutes would be a tracker nobody refreshes.

    A file that cannot be read at all is still *seen*, with no kind. Dropping it would
    make an unreadable document indistinguishable from one that is not there, and the
    first is something to chase.
    """
    out: list[Seen] = []
    for ref in storage.list(prefix):
        kind, confidence = _what_is_it(storage, ref.path)
        out.append(Seen(ref.path, kind, confidence, parse_ref(ref.path)))
    return tuple(out)


def _what_is_it(storage: Any, path: str) -> tuple[str | None, float]:
    """Classify one file. The filename always; its contents where they are cheap to read.

    Returns `(None, 0)` when nothing could be read *and* the name said nothing, which is
    different from `("other", ...)` - the second means it was looked at.
    """
    sheets: list[str] = []
    rows: list[str] = []
    try:
        data = storage.read(_as_ref(path))
    except Exception:  # noqa: BLE001 - an unreadable file is a result, not a crash
        data = b""

    if data:
        sheets, rows = _peek(data, path)

    evidence = Evidence(filename=Path(path).name, first_rows=rows, sheet_names=sheets)
    found = classify(evidence)
    if found.document_type == "other" and not data and not rows:
        # Nothing was read and the name said nothing. "Nobody looked" rather than
        # "looked and it was nothing in particular" - `Arrived.kind` draws that line, and
        # a request item is never satisfied by the first.
        return None, 0.0
    return found.document_type, float(getattr(found, "score", 0.0) or 0.0)


def _peek(data: bytes, path: str) -> tuple[list[str], list[str]]:
    """Sheet names and a few rows, for the formats that give them up cheaply."""
    suffix = Path(path).suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return _peek_workbook(data)
    if suffix in (".csv", ".txt"):
        text = data[:64_000].decode("utf-8", errors="replace")
        return [], text.splitlines()[:_SHALLOW_ROWS]
    if suffix == ".pdf":
        return [], _peek_pdf(data)
    if suffix == ".docx":
        return [], _peek_docx(data)
    return [], []


def _peek_pdf(data: bytes) -> list[str]:
    """The first page's text, and only the first page.

    Worth the round trip: most of what this firm's clients send is PDF, and without this
    a set of financial statements lands in "not matched" beside the holiday photos. One
    page is enough for a title block and is quick even on a long filing.

    A scan yields nothing, which is correct and is not this module's problem to solve -
    text from a scan needs OCR, OCR here is a configured engine, and a page that yields
    nothing is reported as nothing rather than guessed at.
    """
    import logging  # noqa: PLC0415

    try:
        from pypdf import PdfReader  # noqa: PLC0415

        # pypdf writes "invalid pdf header" and "EOF marker not found" to the log for
        # every file that is not a PDF despite its extension. On a client folder that is
        # a page of noise around the one line worth reading, and none of it is news -
        # what the caller gets back is "nothing could be read", which is the same answer.
        chatter = logging.getLogger("pypdf")
        was = chatter.level
        chatter.setLevel(logging.CRITICAL)
        try:
            reader = PdfReader(io.BytesIO(data))
        finally:
            chatter.setLevel(was)
        if not reader.pages:
            return []
        text = reader.pages[0].extract_text() or ""
    except Exception:  # noqa: BLE001 - an unreadable PDF is a result
        return []
    return [line for line in text.splitlines() if line.strip()][:_SHALLOW_ROWS]


def _peek_docx(data: bytes) -> list[str]:
    try:
        from docx import Document  # noqa: PLC0415

        document = Document(io.BytesIO(data))
    except Exception:  # noqa: BLE001
        return []
    lines = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    return lines[:_SHALLOW_ROWS]


def _peek_workbook(data: bytes) -> tuple[list[str], list[str]]:
    try:
        from openpyxl import load_workbook  # noqa: PLC0415

        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:  # noqa: BLE001 - a workbook that will not open is a result
        return [], []
    try:
        sheets = list(book.sheetnames)
        rows: list[str] = []
        for sheet in book.worksheets[:2]:
            for row in sheet.iter_rows(max_row=_SHALLOW_ROWS, values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    rows.append(" ".join(cells))
        return sheets, rows[:_SHALLOW_ROWS]
    finally:
        book.close()


def _as_ref(path: str) -> Any:
    from ports.storage import FileRef  # noqa: PLC0415

    return FileRef(path)


# ---------------------------------------------------------------- the workbook


def read_tracker(path: Path | str) -> dict[str, dict[str, str]]:
    """What a person has written in an existing tracker, keyed by item reference.

    Returns empty for a file that is not there - a first run has nothing to preserve, and
    that is not a failure.
    """
    target = Path(path)
    if not target.is_file():
        return {}

    from openpyxl import load_workbook  # noqa: PLC0415

    book = load_workbook(target, data_only=True)
    try:
        sheet = book.active
        header = [str(c.value or "").strip() for c in next(sheet.iter_rows(max_row=1))]
        if "Ref" not in header:
            return {}
        columns = {name: i for i, name in enumerate(header)}
        held: dict[str, dict[str, str]] = {}
        for row in sheet.iter_rows(min_row=2, values_only=True):
            ref = str(row[columns["Ref"]] or "").strip()
            if not ref:
                continue
            held[ref] = {
                name: str(row[columns[name]] or "").strip()
                for name in THEIRS
                if name in columns and columns[name] < len(row)
            }
        return held
    finally:
        book.close()


def write_tracker(tracker: Tracker, path: Path | str) -> Path:
    """Write the tracker, carrying across everything a person wrote.

    Written whole rather than edited in place: openpyxl cannot preserve everything about
    a workbook it did not create, and a file that quietly loses a chart or a second sheet
    on every refresh is worse than one that is plainly rebuilt. What must survive is what
    a person typed, and that is read back in first.
    """
    from openpyxl import Workbook  # noqa: PLC0415
    from openpyxl.styles import Alignment, Font  # noqa: PLC0415

    target = Path(path)
    tracker.theirs = {**read_tracker(target), **tracker.theirs}

    book = Workbook()
    sheet = book.active
    sheet.title = "Request list"

    sheet.append(list(_HEADERS))
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(vertical="top", wrap_text=True)

    checked = datetime.now(tz=UTC).isoformat(timespec="seconds")
    for row in tracker.report_rows():
        ref = str(row.item.ref)
        mine = tracker.theirs.get(ref, {})
        sheet.append(
            [
                ref,
                row.item.ref.section_title,
                row.item.text,
                "Y" if row.item.essential else "",
                *(mine.get(name, "") for name in THEIRS),
                row.status.value,
                # Said in the sheet, not only in the code: an inferred match is the tool's
                # reading of a document rather than somebody's word about it, and the
                # person reading the tracker is the one who can settle it.
                _how(row),
                "\n".join(row.evidence),
                checked if row.status is Status.PROVIDED else "",
            ]
        )

    widths = (8, 24, 58, 10, 10, 34, 14, 14, 16, 46, 22)
    for column, width in zip(sheet.column_dimensions, widths, strict=False):
        sheet.column_dimensions[column].width = width
    for line in sheet.iter_rows(min_row=2):
        for cell in line:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    sheet.freeze_panes = "A2"

    _add_the_leftovers(book, tracker)

    target.parent.mkdir(parents=True, exist_ok=True)
    book.save(target)
    return target


def _how(row: Any) -> str:
    if row.status is not Status.PROVIDED:
        return ""
    return "inferred from the document" if row.inferred else "filed under its number"


def _add_the_leftovers(book: Any, tracker: Tracker) -> None:
    """A second sheet for files that answered nothing.

    On its own sheet rather than appended to the list, because they are not items - they
    are documents with no home, and the two questions ("what is still owed" and "what is
    this") are asked at different times by the same person.
    """
    from openpyxl.styles import Font  # noqa: PLC0415

    sheet = book.create_sheet("Not matched")
    sheet.append(["File", "What it looks like", "Why it is here"])
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    unmatched = set(tracker.unmatched())
    for seen in tracker.seen:
        if seen.path not in unmatched:
            continue
        sheet.append(
            [
                seen.path,
                seen.kind or "could not be read",
                "answers nothing on the list - either it was not asked for, or the item "
                "it answers is worded differently",
            ]
        )
    sheet.column_dimensions["A"].width = 56
    sheet.column_dimensions["B"].width = 24
    sheet.column_dimensions["C"].width = 64
