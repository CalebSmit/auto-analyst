"""Checkpoint C18 - what the third interview changed.

Proves: an audit opinion in a real PDF reaches the timing step, and there - with the arrival
order intake recorded - two statements that disagree are settled by the analyst's rules into a
figure that ties, while the case the analyst was unsure of still reaches a person. And the pilot
recipe waits for the comps before the cost of capital.

P41 carried a fact from the reader (P17) through the driver's source files (P34) into the timing
procedure and the normalizer (P18). Each hop was tested alone; a flag dropped between any two of
them would leave every unit green and every disagreement unsettled. This walks all of them.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from graph.compile import PlanContext, compile_recipe
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver
from harness.procedures.timing_normalization import SourceFile, TimingInputs, TimingNormalization
from intake.readers import read_source
from ops.events import EventBus
from ops.run_store import SqlRunStore
from ops.source_parse import SourceParseStore
from tests.p17.conftest import ENGAGEMENT, build_pdf, intake_row
from tests.p18.conftest import load_case
from tools.normalize import timing_normalizer

AUDIT = [
    ("INDEPENDENT AUDITOR'S REPORT", 12.0),
    ("In our opinion, the financial statements present fairly, in all material respects", 10.0),
    ("Statement of Income", 12.0),
    ("Revenue 4,405,000", 10.0),
    ("Net income 310,000", 10.0),
]


class Tools(dict):
    engagement_id = ENGAGEMENT


def test_an_audit_opinion_in_a_pdf_is_on_the_record(
    started: str, store: SqlRunStore, parse_store: SourceParseStore, boundary: Any, bus: EventBus
) -> None:
    data = build_pdf(AUDIT)
    report = read_source(
        started,
        ENGAGEMENT,
        intake_row("FY24 audited financial statements.pdf", data, "document"),
        data,
        store=store,
        parse_store=parse_store,
        boundary=boundary,
        bus=bus,
    )
    assert report.classification is not None
    assert report.classification.document_type == "financial_statements"
    assert report.audited and "auditor" in report.audited.lower()
    (read,) = [e for e in store.events(started) if e.type == "intake.read"]
    assert read.payload["audited"] == report.audited, "a resume rebuilds the source from this"


def test_the_timing_step_settles_what_the_rules_settle_and_nothing_more() -> None:
    inputs, proposal, _ = load_case("conflict")
    assert proposal is not None
    original, restated = inputs.files

    def with_(f: SourceFile, **changes: Any) -> SourceFile:
        return dataclasses.replace(f, **changes)

    def through_the_procedure(files: tuple[SourceFile, ...]) -> tuple[dict[str, Any], list[Any]]:
        tools = Tools(
            timing_normalizer=lambda **kw: type(
                "R",
                (),
                {
                    "value": timing_normalizer(
                        kw["mapping"], kw["sources"], kw["files"], kw["model_pin"]
                    )
                },
            )()
        )
        procedure = TimingNormalization()
        out = procedure.apply(proposal, tools, TimingInputs(files), "pin")  # type: ignore[arg-type]
        return out, [
            i for i in procedure.review_items(out, {}) if i.item_id.startswith("conflict:")
        ]

    settled, open_items = through_the_procedure(
        (
            with_(original, received_at="2026-03-01T10:00:00Z"),
            with_(restated, received_at="2026-04-15T09:00:00Z", audited=True),
        )
    )
    revenue = {i["canonical_label"]: i for i in settled["normalized_historicals"]["line_items"]}
    assert [v["value"] for v in revenue["Revenue"]["values"]] == [4405000.0]
    assert open_items == [] and len(settled["alignment_report"]["conflicts"]) == 2

    unsure, open_items = through_the_procedure(
        (
            with_(original, received_at="2026-03-01T10:00:00Z", audited=True),
            with_(restated, received_at="2026-04-15T09:00:00Z"),
        )
    )
    lines = {i["canonical_label"]: i for i in unsure["normalized_historicals"]["line_items"]}
    assert lines["Revenue"]["values"] == [], "the line stays; no figure is taken for it"
    assert len(open_items) == 2, "the case the analyst was unsure of reaches a person"


def test_the_pilot_waits_for_the_comps_before_the_cost_of_capital() -> None:
    plan = compile_recipe(
        load_recipe("mature-company-valuation"),
        PlanContext(
            engagement_id="PILOT-3",
            scope=ScopeResolver().resolve("valuation/non-esop/repeat"),
            taxonomy_version="coa-taxonomy@1.0.0",
            precedent_snapshot="snap-pilot",
        ),
    )
    order = list(plan.order)
    assert order.index("gpc") < order.index("wacc") < order.index("dcf")
