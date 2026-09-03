"""The Workbook Reader: survey, select with reasons, normalise only what was selected."""

from __future__ import annotations

import pytest

from guards.provenance import ProvenanceGate
from guards.tieout import TieoutGate
from guards.untrusted import BEGIN, SENTINEL_RULE, UntrustedBoundary
from harness.budget import BudgetGovernor
from harness.door import ModelDoor
from intake.readers.workbook import (
    ModelSheetSelector,
    ScriptedSelector,
    StructuralSelector,
    normalize_workbook,
    survey_workbook,
)
from ops.cost import CostMeter
from ops.run_store import SqlRunStore
from ops.source_parse import SourceParseStore, parse_locator
from ports.llm import LLMRequest, LLMResponse, ModelPin, Usage
from privacy.payload_scan import IdentifierList, PayloadScan
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from tests.p13.conftest import figure
from tests.p17.conftest import ENGAGEMENT, TB_ROWS, build_xlsx
from tools.recompute import recompute

SOURCE = "sha256:" + "ef" * 32


@pytest.fixture
def workbook() -> bytes:
    return build_xlsx(
        {
            "TB_FY25": TB_ROWS,
            "Notes": [["Prepared by the controller"], ["Unaudited"]],
            "Scratch": [["x", 1], ["y", 2]],
            "Income Stmt": [
                ["Line", "FY2024", "FY2025"],
                ["Revenue", 4_401_900, 4_812_300],
                ["EBITDA", 612_000, 704_500],
            ],
        },
        hidden=("Scratch",),
        chart="Revenue chart",
    )


def test_the_survey_reads_structure_only(workbook: bytes) -> None:
    survey = survey_workbook(workbook)
    by_name = {s.name: s for s in survey.sheets}
    assert set(by_name) == {"TB_FY25", "Notes", "Scratch", "Income Stmt", "Revenue chart"}
    tb = by_name["TB_FY25"]
    assert tb.state == "visible" and tb.headers[:3] == ("Account", "FY2025", "FY2024")
    assert tb.numeric_cells == 16 and tb.rows == 9
    assert by_name["Scratch"].state == "hidden"
    assert by_name["Revenue chart"].kind == "chartsheet"
    assert "240,000" not in survey.as_prompt() and "240000" not in survey.as_prompt()


def test_every_skipped_sheet_is_reported_with_a_reason(workbook: bytes) -> None:
    """The exit criterion. Structurally, and then when a selector forgets a sheet."""
    survey = survey_workbook(workbook)
    structural = StructuralSelector().select(survey).accounting_for(survey)
    assert {c.sheet for c in structural.selected} == {"TB_FY25", "Income Stmt"}
    skipped = {c.sheet: c.reason for c in structural.skipped}
    assert skipped == {
        "Notes": "no numeric cells",
        "Scratch": "sheet is hidden",
        "Revenue chart": "chartsheet: no cells to read",
    }

    forgetful = ScriptedSelector({"TB_FY25": "the trial balance"}).select(survey)
    accounted = forgetful.accounting_for(survey)
    assert [c.sheet for c in accounted.selected] == ["TB_FY25"]
    assert {c.sheet: c.reason for c in accounted.skipped} == {
        "Notes": "not selected by the scripted selector",
        "Scratch": "not selected by the scripted selector",
        "Income Stmt": "not selected by the scripted selector",
        "Revenue chart": "not selected by the scripted selector",
    }
    assert {c.sheet for c in accounted.selected} | {c.sheet for c in accounted.skipped} == {
        s.name for s in survey.sheets
    }


def test_a_selector_naming_a_sheet_that_does_not_exist_is_not_believed(workbook: bytes) -> None:
    survey = survey_workbook(workbook)
    accounted = (
        ScriptedSelector({"TB_FY25": "ok", "Ghost": "made up"})
        .select(survey)
        .accounting_for(survey)
    )
    assert [c.sheet for c in accounted.selected] == ["TB_FY25"]


def test_normalisation_writes_one_block_per_numeric_column(workbook: bytes) -> None:
    sheets = normalize_workbook(workbook, ["TB_FY25", "Income Stmt"])
    tb = next(s for s in sheets if s.sheet == "TB_FY25")
    assert tb.label_column == "A"
    assert set(tb.blocks) == {"TB_FY25!B2:B9", "TB_FY25!C2:C9"}
    rows = tb.blocks["TB_FY25!B2:B9"]
    assert [r.ordinal for r in rows] == list(range(2, 10)), "ordinals are sheet rows"
    assert (rows[2].label, rows[2].value, rows[2].raw) == ("Officer salary", 240000.0, "240,000")
    stmt = next(s for s in sheets if s.sheet == "Income Stmt")
    assert set(stmt.blocks) == {"'Income Stmt'!B2:B3", "'Income Stmt'!C2:C3"}


def test_every_figure_resolves_by_source_and_locator_through_one_interface(
    workbook: bytes, parse_store: SourceParseStore, started: str
) -> None:
    """The exit criterion. A sub-range the reader never wrote as a key, a quoted sheet,
    a single cell, a multi-column range - all through `resolve`."""
    for sheet in normalize_workbook(workbook, ["TB_FY25", "Income Stmt"]):
        for locator, rows in sheet.blocks.items():
            parse_store.write(started, SOURCE, locator, rows)

    four = parse_store.resolve(started, SOURCE, "TB_FY25!B4:B7")
    assert [r.label for r in four] == [
        "Officer salary",
        "Officer bonus",
        "Auto allowance",
        "Health premium",
    ]
    assert sum(r.value or 0 for r in four) == 331000.0
    (cell,) = parse_store.resolve(started, SOURCE, "TB_FY25!B8")
    assert cell.value == 331000.0
    (ebitda,) = parse_store.resolve(started, SOURCE, "'Income Stmt'!C3")
    assert ebitda.value == 704500.0
    both = parse_store.resolve(started, SOURCE, "'Income Stmt'!B3:C3")
    assert [r.value for r in both] == [612000.0, 704500.0]
    assert parse_store.resolve(started, SOURCE, "TB_FY25!B40:B47") == (), "outside every block"
    assert parse_store.resolve(started, SOURCE, "TB_FY25!D2") == (), "a column nobody wrote"
    assert parse_store.resolve(started, SOURCE, "Ghost!A1") == ()


def test_the_guards_read_workbook_rows_through_the_same_interface(
    workbook: bytes, parse_store: SourceParseStore, started: str, contracts: ContractRegistry
) -> None:
    for sheet in normalize_workbook(workbook, ["TB_FY25"]):
        for locator, rows in sheet.blocks.items():
            parse_store.write(started, SOURCE, locator, rows)
    total = figure(331000.0, "TB_FY25!B8", {"op": "sum", "of": ["TB_FY25!B4:B7"]}, source_id=SOURCE)
    assert TieoutGate(parse_store, recompute, 1.0).check({"f": total}, started).passed
    wrong = figure(332324.0, "TB_FY25!B8", {"op": "sum", "of": ["TB_FY25!B4:B7"]}, source_id=SOURCE)
    assert not TieoutGate(parse_store, recompute, 1.0).check({"f": wrong}, started).passed
    assert ProvenanceGate(contracts, parse_store).check({"f": total}, started, {SOURCE: 1}).passed
    stray = figure(1.0, "TB_FY25!B44", source_id=SOURCE)
    assert (
        not ProvenanceGate(contracts, parse_store).check({"f": stray}, started, {SOURCE: 1}).passed
    )


@pytest.mark.parametrize(
    "text",
    ["TB_FY25!B44:B47", "'Income Stmt'!C12", "p14/t2/r7", "p14/t2", "p3/text", "p3/text/r2"],
)
def test_the_two_locator_shapes_parse(text: str) -> None:
    parse_locator(text)


@pytest.mark.parametrize("text", ["B44", "TB_FY25!B47:B44", "page 14 table 2", "p14/t2/r7/x", ""])
def test_anything_else_is_not_a_locator(text: str) -> None:
    with pytest.raises(ValueError):
        parse_locator(text)


def test_a_block_is_written_under_a_locator_the_resolver_can_read(
    parse_store: SourceParseStore, started: str
) -> None:
    with pytest.raises(ValueError):
        parse_store.write(started, SOURCE, "sheet one, column B", [])


# ------------------------------------------------------ the one model call


class SelectsTheTB:
    name = "selects"

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            text=(
                '{"selected": [{"sheet": "TB_FY25", "reason": "the trial balance"}], '
                '"skipped": [{"sheet": "Notes", "reason": "prose"}, '
                '{"sheet": "Scratch", "reason": "hidden scratch sheet"}]}'
            ),
            model=request.pin.model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=300, output_tokens=60),
        )


def test_the_model_selects_from_the_survey_wrapped_as_data(
    workbook: bytes, store: SqlRunStore, bus, started: str
) -> None:
    port = SelectsTheTB()
    meter = CostMeter(store)
    door = ModelDoor(
        port,
        PayloadScan(bus),
        BudgetGovernor(ConstraintRegistry.load(), meter, bus, store),
        meter,
        bus,
    )
    selector = ModelSheetSelector(
        door,
        IdentifierList.of(ENGAGEMENT, []),
        UntrustedBoundary(bus),
        ModelPin.for_tier("mid"),
        run_id=started,
        step_id="intake",
    )
    survey = survey_workbook(workbook)
    selection = selector.select(survey).accounting_for(survey)

    assert selector.calls == 1 and len(port.requests) == 1
    request = port.requests[0]
    assert SENTINEL_RULE in request.system
    assert request.messages[0].content.startswith(BEGIN)
    assert '"sheet": "TB_FY25"' in request.messages[0].content
    assert "240000" not in request.messages[0].content, "cells never enter the model"
    assert [c.sheet for c in selection.selected] == ["TB_FY25"]
    skipped = {c.sheet: c.reason for c in selection.skipped}
    assert skipped["Notes"] == "prose"
    assert skipped["Income Stmt"] == "not selected by the model selector"
    assert skipped["Revenue chart"] == "not selected by the model selector"
    assert store.run(started).model_calls == 1
