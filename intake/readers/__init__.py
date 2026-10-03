"""Readers: turn files into an addressable parse that provenance and tie-out read from.

Four nodes and the store they write to:

* `documents.py` - the Document Reader: pypdf and python-docx, deterministic, every
                   emitted item carrying source_id and a page/table/row locator.
* `workbook.py`  - the Workbook Reader: a structural read of sheet names and headers, one
                   model call that selects sheets *with reasons*, deterministic code that
                   normalises only those. Every skipped sheet is reported with a reason.
* `classify.py`  - the Document Classifier: a closed set, with "other" a first-class
                   answer that routes to a person.
* `periods.py`   - the Period & Timing Detector: period type, period ends, fiscal year
                   end, currency and scale - with an explicit `ambiguous` flag rather than
                   an assumption. Thousands versus units is the most expensive silent
                   error available here.

`read_source` runs one file through all of them and writes the Source Parse Store.
The text that would reach a model leaves through the Untrusted Content Boundary,
wrapped as data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from guards.untrusted import UntrustedBoundary, Wrapped
from intake.readers.classify import Classification, Evidence, audited_evidence, classify
from intake.readers.documents import NotText, ParsedDocument, read_document
from intake.readers.footing import FootingReport, TwoSides, footings_in, two_sides
from intake.readers.periods import PeriodDetection, detect_periods
from intake.readers.tabular import Conversion, as_workbook, converts
from intake.readers.workbook import (
    Selection,
    SheetSelector,
    StructuralSelector,
    normalize_workbook,
    survey_workbook,
)
from intake.store import IntakeRow
from ops.events import EventBus
from ops.run_store import SqlRunStore
from ops.source_parse import Row, SourceParseStore
from registries.errors import (
    FORMAT_NOT_READ,
    UNREADABLE_FILE,
    DiagnosticError,
    diagnose,
)

__all__ = ["ReadReport", "read_source"]

NODE = "source_parse"


@dataclass
class ReadReport:
    source_id: str
    filename: str
    kind: str
    blocks: dict[str, int] = field(default_factory=dict)
    """locator -> rows written."""
    selection: Selection | None = None
    classification: Classification | None = None
    periods: PeriodDetection | None = None
    balances: tuple[tuple[str, TwoSides], ...] = ()
    """Where a statement states both sides of a balance sheet, whether they agree.

    Per statement rather than per block: a total only ever sums what stands above it, and
    on a real filing the assets total and the line that totals the other side are in
    different blocks, because the reader starts a new one at every heading. Empty for a
    document that states no balance sheet, which is most of them."""
    conversion: Conversion | None = None
    """What had to be decided to read a file that was not already a workbook - the
    delimiter, the encoding, the decimal point, and any cell that could have been two
    numbers. `None` for a file that needed no converting."""
    wrapped: Wrapped | None = None
    hidden_text: tuple[str, ...] = ()
    review_item_id: str | None = None
    block_headers: dict[str, str] = field(default_factory=dict)
    """locator -> the header above the block's column, for the timing skill's period hint."""
    audited: str | None = None
    """The audit-opinion phrase found in a financial statements file, or None."""
    footing: dict[str, FootingReport] = field(default_factory=dict)
    """locator -> which of that block's totals re-added, and the rows they cover.

    The producer `review/router.py` has been waiting for since P37: an extracted figure is
    shown to a person unless a total it feeds was re-added from its rows, and until P99
    nothing set that. Kept per block because a block is a column of one statement, and a
    statement footing in 2023 says nothing about the same statement in 2022."""

    @property
    def covered_rows(self) -> int:
        return sum(len(f.covered_ordinals) for f in self.footing.values())

    @property
    def totals_that_did_not_foot(self) -> tuple[str, ...]:
        """Every total that re-added from nothing, named, worst first.

        What an analyst wants the moment a client's statement arrives, and what this build
        could not answer before: does it add up."""
        out = [
            (abs(f.delta or 0.0), f"{locator}: {f.label} is out by {f.delta:,.2f}")
            for locator, report in self.footing.items()
            for f in report.uncovered
            if f.delta is not None
        ]
        return tuple(line for _, line in sorted(out, reverse=True))

    @property
    def locators(self) -> tuple[str, ...]:
        return tuple(sorted(self.blocks))


def _folders_of(path: str, filename: str) -> list[str]:
    """The folders between the watched root and the file, outermost first.

    Takes the filename too because a watch's `path` is only sometimes a path: some ports
    hand back the bare name, and `PurePosixPath("x.pdf").parts[:-1]` is empty either way,
    but a port that returns a Windows-shaped path would otherwise be read as one folder
    called the whole path.
    """
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if parts and parts[-1] == PurePosixPath(filename.replace("\\", "/")).name:
        parts = parts[:-1]
    return [part for part in parts if part not in ("", ".", "/")]


def _two_sides_of(statements: dict[str, list[Any]]) -> tuple[tuple[str, TwoSides], ...]:
    """The balance-sheet check over each statement, keeping only the ones that state both
    sides. A statement that states neither is not a failure and must not read as one."""
    found = []
    for where, rows in statements.items():
        got = two_sides(rows)
        if got.stated:
            found.append((where, got))
    return tuple(found)


def read_source(
    run_id: str,
    engagement_id: str,
    row: IntakeRow,
    data: bytes,
    *,
    store: SqlRunStore,
    parse_store: SourceParseStore,
    boundary: UntrustedBoundary,
    bus: EventBus | None = None,
    selector: SheetSelector | None = None,
    step_id: str | None = None,
) -> ReadReport:
    """One file, read once: parse rows written, classified, timing detected, and the text
    a model would see wrapped as data. Raises on a strong injection hit, before any of
    that text could leave."""
    report = ReadReport(source_id=row.source_id, filename=row.filename, kind=row.kind)
    text_for_model: list[str] = []
    headers: list[str] = []
    first_rows: list[str] = []
    sheet_names: list[str] = []
    read_tables: list[Any] = []
    """The tables a document reader found, for the columns check. Empty for a workbook,
    whose columns are cells and were never in doubt."""

    if row.kind == "spreadsheet":
        try:
            # A CSV and an .xls are spreadsheets this build accepts and openpyxl cannot
            # open. Converted here, once, so everything below reads a workbook - including
            # the Sheet!A1 locator a figure will cite for as long as the figure exists.
            if converts(row.filename):
                converted = as_workbook(data, row.filename)
                data = converted.workbook
                report.conversion = converted
            survey = survey_workbook(data)
        except Exception as broken:  # noqa: BLE001 - openpyxl raises a zoo, all meaning "not a workbook"
            # A zero-byte file, a text file with the wrong extension, a workbook still
            # being written, an encrypted one. None is a pass that failed; each is a file
            # that cannot be read, named, so the person replaces it.
            raise DiagnosticError(
                diagnose(
                    UNREADABLE_FILE,
                    f"{row.filename} cannot be opened as a workbook "
                    f"({broken.__class__.__name__}: {str(broken)[:100]})",
                    locator=row.filename,
                    found=f"{len(data)} bytes",
                )
            ) from broken
        selection = (selector or StructuralSelector()).select(survey)
        selection = selection.accounting_for(survey)
        report.selection = selection
        sheet_names = [s.name for s in survey.sheets]
        for sheet in survey.sheets:
            headers.extend(sheet.headers)
        for table in normalize_workbook(data, [s.sheet for s in selection.selected]):
            for locator, rows in table.blocks.items():
                report.blocks[locator] = parse_store.write(run_id, row.source_id, locator, rows)
                report.footing[locator] = footings_in(rows)
            report.block_headers.update(table.block_headers)
            first_rows.extend(table.first_rows)
            text_for_model.append(table.as_text())
            report.balances += _two_sides_of(
                {locator: list(rows) for locator, rows in table.blocks.items()}
            )
    else:
        try:
            parsed: ParsedDocument = read_document(data, row.filename)
        except NotText as not_text:
            # Whole, and in a format this build does not read. Said as its own thing rather
            # than as UNREADABLE_FILE, because what a person should do differs: save it as
            # something that is read, not ask the client for it again. What it actually is
            # comes from its first bytes, so a `.doc` renamed `.txt` is still named a Word
            # 97-2003 file rather than described as whatever its extension claimed.
            raise DiagnosticError(
                diagnose(
                    FORMAT_NOT_READ,
                    f"{row.filename} is {not_text.looks_like}, which this build does not "
                    f"read. Save it as a .docx or a PDF and send it again.",
                    locator=row.filename,
                    found=f"{len(data)} bytes",
                )
            ) from not_text
        read_tables = [t for page in parsed.pages for t in page.tables]
        for locator, rows in parsed.blocks().items():
            report.blocks[locator] = parse_store.write(run_id, row.source_id, locator, rows)
            report.footing[locator] = footings_in(rows)
        headers = parsed.headers()
        first_rows = parsed.first_rows()
        report.hidden_text = parsed.hidden_text()
        text_for_model.append(parsed.as_text())
        # One statement is a page read down one column, across whatever blocks the reader
        # split it into - it starts a new one at every heading, and a balance sheet has
        # three. Tables on a page need not be the same width, so a table without this
        # column contributes nothing to it rather than raising.
        widest = {
            page.number: max((len(t.columns) for t in page.tables), default=0)
            for page in parsed.pages
        }
        report.balances = _two_sides_of(
            {
                f"p{page.number} column {n + 1}": [
                    row
                    for table in page.tables
                    if n < len(table.columns)
                    for row in table.columns[n].rows
                ]
                for page in parsed.pages
                for n in range(widest[page.number])
            }
        )

    evidence = Evidence(
        filename=row.filename,
        headers=headers,
        first_rows=first_rows,
        sheet_names=sheet_names,
        # The folders the client filed it under. `IntakeRow` has carried the full path since
        # P12 and this call used only the last part of it, so the plainest thing a client
        # says about a document - `Board Minutes/2023.pdf` - reached the classifier nowhere.
        # P96 fixed that in the tracker; this is the same seam on the path a run takes.
        folders=_folders_of(row.path, row.filename),
    )
    report.classification = classify(evidence)
    # The tables, not only a sample of the text. The columns check asks whether every
    # multi-column table names its columns, and it can only ask that of tables it has -
    # given page-one headers and one table's first rows it said nothing at all about a
    # filing whose other fifty-eight tables were comparative and read wrong.
    report.periods = detect_periods("\n".join([*headers, *first_rows]), tables=read_tables)
    if report.classification.document_type == "financial_statements":
        report.audited = audited_evidence("\n".join(text_for_model))

    if report.classification.document_type == "other":
        item_id = f"classification:{row.source_id[7:19]}"
        store.open_review_item(
            run_id,
            item_id,
            kind="classification",
            subject=f"{row.filename}: what is this document?",
            detail={
                "source_id": row.source_id,
                "reasons": list(report.classification.reasons),
                "headers": headers[:12],
                # The headers again, under the name the review surface reads.
                #
                # `ReviewSurface.show` takes the excerpt from `source_excerpt`, and this
                # item wrote the headers under `headers` - so twelve headers were captured
                # for a reviewer and never reached one. The modal showed no source and
                # still said "Read the source first", which is advice nobody could follow,
                # on the one question that is *only* answerable by looking: what is this
                # document. They are what the classifier itself looked at, so they are
                # exactly what a person needs to disagree with it.
                "source_excerpt": " | ".join(h for h in headers[:12] if h.strip()),
                "locator": row.path or row.filename,
                "proposal": {"document_type": "other"},
                "confidence": report.classification.confidence,
            },
        )
        report.review_item_id = item_id
        if bus is not None:
            bus.emit(
                run_id=run_id,
                engagement_id=engagement_id,
                node_id="doc_classifier",
                type="hitl.item.queued",
                message=f"{row.filename}: classified other; routed to a person",
                level="warn",
                step_id=step_id,
                payload={"item_id": item_id, "source_id": row.source_id},
            )

    if bus is not None:
        bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type="intake.read",
            message=(
                f"{row.filename}: {len(report.blocks)} block(s) written; "
                f"{report.classification.document_type} "
                f"({report.classification.confidence:.2f})"
                + (
                    f"; ambiguous: {', '.join(report.periods.ambiguous)}"
                    if report.periods.ambiguous
                    else ""
                )
                # Named, not counted. "3 totals did not re-add" sends somebody looking
                # through a hundred rows; naming them and the amount they are out by is the
                # difference between a warning and a finding.
                + (
                    "; did not re-add: " + "; ".join(report.totals_that_did_not_foot[:3])
                    if report.totals_that_did_not_foot
                    else ""
                )
                # A file that was not a workbook had its separator, its encoding and its
                # decimal point decided here, and a cell that could have been two numbers
                # was left as text. Said in the message rather than only in the payload,
                # because it is the kind of thing a person wants to see without opening a
                # record: `402,000` is four hundred thousand or it is four hundred and two.
                # The check an analyst makes before any other, said in the line rather
                # than only in the payload. A balance sheet that does not balance is the
                # one thing nobody should have to open a record to find out.
                + "".join(
                    f"; {where}: {sides.as_line()}"
                    for where, sides in report.balances
                    if not sides.balances
                )
                + (
                    f"; read as {report.conversion.encoding}"
                    f" split on {report.conversion.delimiter!r}"
                    + (
                        f", decimal {report.conversion.decimal!r}"
                        if report.conversion.decimal
                        else ", no decimal convention in the file"
                    )
                    + (
                        "; left as text because it could be two numbers: "
                        + ", ".join(report.conversion.ambiguous[:3])
                        if report.conversion.ambiguous
                        else ""
                    )
                    if report.conversion and report.conversion.delimiter
                    else ""
                )
            ),
            step_id=step_id,
            payload={
                "source_id": row.source_id,
                "kind": row.kind,
                "blocks": report.locators,
                "skipped_sheets": [
                    {"sheet": s.sheet, "reason": s.reason}
                    for s in (report.selection.skipped if report.selection else ())
                ],
                "block_headers": dict(report.block_headers),
                "document_type": report.classification.document_type,
                "scale": report.periods.scale,
                "currency": report.periods.currency,
                "period_type": report.periods.period_type,
                "period_ends": list(report.periods.period_ends),
                "ambiguous": list(report.periods.ambiguous),
                "hidden_text": len(report.hidden_text),
                "balances": [
                    {
                        "statement": where,
                        "assets": sides.assets,
                        "liabilities_and_equity": sides.liabilities_and_equity,
                        "agrees": sides.balances,
                        "out_by": sides.out_by,
                    }
                    for where, sides in report.balances
                ],
                "converted": (
                    {
                        "encoding": report.conversion.encoding,
                        "delimiter": report.conversion.delimiter,
                        "decimal": report.conversion.decimal,
                        "ambiguous": list(report.conversion.ambiguous),
                    }
                    if report.conversion
                    else None
                ),
                "audited": report.audited,
                # The evidence `review/router.py` routes on. Counts and names rather than
                # the runs themselves: the ordinals live in the parse store, and an event
                # payload holding two thousand of them is a record nobody can read.
                "totals": sum(f.totals for f in report.footing.values()),
                "totals_that_re_added": sum(
                    f.totals - len(f.uncovered) for f in report.footing.values()
                ),
                "rows_covered_by_a_total": report.covered_rows,
                "did_not_re_add": list(report.totals_that_did_not_foot[:10]),
            },
        )

    body = "\n".join(text_for_model)
    if report.hidden_text:
        body += "\n[hidden text in the document, shown as data]\n" + "\n".join(report.hidden_text)
    report.wrapped = boundary.wrap(
        body,
        source_id=row.source_id,
        label=f"{row.kind}:{row.filename}",
        run_id=run_id,
        engagement_id=engagement_id,
        step_id=step_id,
    )
    return report


def _unused(_: Row, __: Any) -> None:  # pragma: no cover - keeps Row imported for readers
    return None
