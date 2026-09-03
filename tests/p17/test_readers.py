"""read_source: one file, read once, into the parse store, classified, timed, wrapped."""

from __future__ import annotations

import pytest

from guards.untrusted import BEGIN, UntrustedBoundary
from intake.readers import read_source
from intake.readers.workbook import ScriptedSelector
from ops.run_store import LateResult, SqlRunStore
from ops.source_parse import SourceParseStore
from tests.p17.conftest import ENGAGEMENT, TB_ROWS, build_pdf, build_xlsx, intake_row


def test_a_workbook_is_read_once_into_the_parse_store(
    store: SqlRunStore,
    parse_store: SourceParseStore,
    boundary: UntrustedBoundary,
    bus,
    started: str,
) -> None:
    data = build_xlsx(
        {"TB_FY25": [["Trial balance ($ in thousands)"], *TB_ROWS], "Notes": [["hello"]]}
    )
    row = intake_row("TB_FY25.xlsx", data, "spreadsheet")
    report = read_source(
        started,
        ENGAGEMENT,
        row,
        data,
        store=store,
        parse_store=parse_store,
        boundary=boundary,
        bus=bus,
    )

    assert set(report.locators) == {"TB_FY25!B3:B10", "TB_FY25!C3:C10"}
    assert report.blocks["TB_FY25!B3:B10"] == 8
    assert report.selection is not None
    assert {c.sheet: c.reason for c in report.selection.skipped} == {"Notes": "no numeric cells"}
    assert (
        report.classification is not None and report.classification.document_type == "trial_balance"
    )
    assert report.periods is not None and report.periods.scale == 1000
    assert report.wrapped is not None and report.wrapped.text.startswith(BEGIN)
    assert "Officer salary = 240,000" in report.wrapped.text
    assert parse_store.exists(started, row.source_id, "TB_FY25!B5:B8")
    read = [e for e in store.events(started) if e.type == "intake.read"]
    assert len(read) == 1 and read[0].payload["skipped_sheets"] == [
        {"sheet": "Notes", "reason": "no numeric cells"}
    ]

    with pytest.raises(LateResult):
        read_source(
            started,
            ENGAGEMENT,
            row,
            data,
            store=store,
            parse_store=parse_store,
            boundary=boundary,
        )


def test_a_scripted_selection_is_honoured_and_completed(
    store: SqlRunStore, parse_store: SourceParseStore, boundary: UntrustedBoundary, started: str
) -> None:
    data = build_xlsx({"TB_FY25": TB_ROWS, "Scratch": [["x", 1]]})
    report = read_source(
        started,
        ENGAGEMENT,
        intake_row("TB.xlsx", data, "spreadsheet"),
        data,
        store=store,
        parse_store=parse_store,
        boundary=boundary,
        selector=ScriptedSelector({"TB_FY25": "the TB"}),
    )
    assert all(loc.startswith("TB_FY25!") for loc in report.locators)
    assert report.selection is not None
    assert {c.sheet: c.reason for c in report.selection.skipped} == {
        "Scratch": "not selected by the scripted selector"
    }


def test_an_unrecognisable_document_opens_a_review_item(
    store: SqlRunStore,
    parse_store: SourceParseStore,
    boundary: UntrustedBoundary,
    bus,
    started: str,
) -> None:
    data = build_pdf(
        [
            ("Schedule C", 12.0),
            ("Attachment 4", 10.0),
            ("Line 7      4,120", 10.0),
            ("Line 9      1,000", 10.0),
        ]
    )
    report = read_source(
        started,
        ENGAGEMENT,
        intake_row("Schedule_C_final(2).pdf", data, "document"),
        data,
        store=store,
        parse_store=parse_store,
        boundary=boundary,
        bus=bus,
    )
    assert report.classification is not None and report.classification.document_type == "other"
    (item,) = store.review_items(started)
    assert item.kind == "classification" and item.item_id == report.review_item_id
    assert item.detail["proposal"] == {"document_type": "other"}
    queued = [e for e in store.events(started) if e.type == "hitl.item.queued"]
    assert len(queued) == 1 and queued[0].node_id == "doc_classifier"


def test_the_periods_ambiguity_travels_with_the_read(
    store: SqlRunStore,
    parse_store: SourceParseStore,
    boundary: UntrustedBoundary,
    bus,
    started: str,
) -> None:
    data = build_xlsx({"TB_FY25": TB_ROWS})
    report = read_source(
        started,
        ENGAGEMENT,
        intake_row("TB_FY25.xlsx", data, "spreadsheet"),
        data,
        store=store,
        parse_store=parse_store,
        boundary=boundary,
        bus=bus,
    )
    assert report.periods is not None and report.periods.scale is None
    (read,) = [e for e in store.events(started) if e.type == "intake.read"]
    assert read.payload["scale"] is None
    assert any(a.startswith("scale") for a in read.payload["ambiguous"])
