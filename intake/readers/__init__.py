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
from typing import Any

from guards.untrusted import UntrustedBoundary, Wrapped
from intake.readers.classify import Classification, Evidence, classify
from intake.readers.documents import ParsedDocument, read_document
from intake.readers.periods import PeriodDetection, detect_periods
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
from registries.errors import UNREADABLE_FILE, DiagnosticError, diagnose

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
    wrapped: Wrapped | None = None
    hidden_text: tuple[str, ...] = ()
    review_item_id: str | None = None
    block_headers: dict[str, str] = field(default_factory=dict)
    """locator -> the header above the block's column, for the timing skill's period hint."""

    @property
    def locators(self) -> tuple[str, ...]:
        return tuple(sorted(self.blocks))


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

    if row.kind == "spreadsheet":
        try:
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
            report.block_headers.update(table.block_headers)
            first_rows.extend(table.first_rows)
            text_for_model.append(table.as_text())
    else:
        parsed: ParsedDocument = read_document(data, row.filename)
        for locator, rows in parsed.blocks().items():
            report.blocks[locator] = parse_store.write(run_id, row.source_id, locator, rows)
        headers = parsed.headers()
        first_rows = parsed.first_rows()
        report.hidden_text = parsed.hidden_text()
        text_for_model.append(parsed.as_text())

    evidence = Evidence(
        filename=row.filename, headers=headers, first_rows=first_rows, sheet_names=sheet_names
    )
    report.classification = classify(evidence)
    report.periods = detect_periods("\n".join([*headers, *first_rows]))

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
