"""P41: when two sources disagree about a period, the analyst's rules settle what they can.

The rules (knowledge, 2026-09-17-2): audited statements over internal ones; within the same
kind, the most recently received file - including a restated prior year. An older audited
file against a newer internal one the analyst was not sure about, so a person decides. Every
disagreement stays in the alignment report, settled or not.

Run against the timing fixtures' own conflict case: a FY2024 income statement and a restated
one that disagree on revenue and gross profit.
"""

from __future__ import annotations

from typing import Any

import pytest

from guards.provenance import ProvenanceGate
from guards.tieout import TieoutGate
from harness.procedures.timing_normalization import SETTLED_BY_RULE, TimingNormalization
from intake.readers.classify import audited_evidence
from ops.source_parse import SourceParseStore
from registries.contracts import ContractRegistry
from tests.p18.conftest import load_case, tool_inputs, write_blocks
from tools.normalize import TAKEN_BY_RULE, settle, timing_normalizer
from tools.recompute import recompute

ORIGINAL = "IS_FY24.xlsx"
RESTATED = "IS_FY24_restated.xlsx"


def run(meta: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, str], Any]:
    inputs, proposal, _ = load_case("conflict")
    assert proposal is not None
    sources, files = tool_inputs(inputs)
    sid = {f.filename: f.source_id for f in inputs.files}
    for filename, extra in meta.items():
        files[sid[filename]].update(extra)
    out = timing_normalizer(proposal, sources, files, "pin")["output"]
    return out, sid, inputs


def revenue(out: dict[str, Any]) -> list[float]:
    items = {i["canonical_label"]: i for i in out["normalized_historicals"]["line_items"]}
    return [v["value"] for v in items["Revenue"]["values"]] if "Revenue" in items else []


def test_with_nothing_to_order_by_no_figure_is_taken() -> None:
    """The fixture's original behaviour, unchanged: two disagreements, both to a person."""
    out, _, _ = run({})
    conflicts = out["alignment_report"]["conflicts"]
    assert len(conflicts) == 2 and revenue(out) == []
    assert all(TAKEN_BY_RULE not in c["detail"] for c in conflicts)
    assert all("no arrival time" in c["detail"] for c in conflicts)


def test_the_most_recent_file_wins_within_the_same_kind() -> None:
    out, sid, _ = run(
        {
            ORIGINAL: {"received_at": "2026-03-01T10:00:00Z"},
            RESTATED: {"received_at": "2026-04-15T09:00:00Z"},
        }
    )
    assert revenue(out) == [4405000.0], "the restated year, received later"
    conflicts = out["alignment_report"]["conflicts"]
    assert len(conflicts) == 2, "settled disagreements stay in the report"
    assert all("most recently received internal file" in c["detail"] for c in conflicts)
    assert all("4,401,900.00" in c["detail"] or "1,713,500.00" in c["detail"] for c in conflicts)


def test_audited_wins_over_an_older_internal_file() -> None:
    out, _, _ = run(
        {
            ORIGINAL: {"received_at": "2026-03-01T10:00:00Z"},
            RESTATED: {"received_at": "2026-04-15T09:00:00Z", "audited": True},
        }
    )
    assert revenue(out) == [4405000.0]
    assert all("audited over internal" in c["detail"] for c in out["alignment_report"]["conflicts"])


def test_an_older_audited_file_against_a_newer_internal_one_goes_to_a_person() -> None:
    out, _, _ = run(
        {
            ORIGINAL: {"received_at": "2026-03-01T10:00:00Z", "audited": True},
            RESTATED: {"received_at": "2026-04-15T09:00:00Z"},
        }
    )
    assert revenue(out) == []
    for conflict in out["alignment_report"]["conflicts"]:
        assert TAKEN_BY_RULE not in conflict["detail"]
        assert "audited is the likely answer" in conflict["detail"]


def test_files_that_arrived_together_cannot_be_ordered() -> None:
    same = "2026-04-15T09:00:00Z"
    out, _, _ = run({ORIGINAL: {"received_at": same}, RESTATED: {"received_at": same}})
    assert revenue(out) == []
    assert all("arrived together" in c["detail"] for c in out["alignment_report"]["conflicts"])


@pytest.mark.parametrize(
    ("meta", "winner"),
    [
        ({"a": ("2026-01", True), "b": ("2026-02", True)}, "b"),
        ({"a": ("2026-02", True), "b": ("2026-01", False)}, "a"),
        ({"a": ("2026-01", False), "b": ("2026-02", False)}, "b"),
        ({"a": ("2026-01", True), "b": ("2026-02", False)}, None),
        ({"a": ("2026-02", True), "b": ("2026-02", True)}, None),
        ({"a": ("", False), "b": ("2026-02", False)}, None),
    ],
)
def test_settle_follows_the_rules_exactly(
    meta: dict[str, tuple[str, bool]], winner: str | None
) -> None:
    files = {k: {"received_at": at, "audited": audited} for k, (at, audited) in meta.items()}
    chosen, why = settle(dict.fromkeys(meta, 1.0), files)
    assert chosen == winner, why


def test_a_settled_figure_still_ties_and_cites_the_file_it_came_from(
    parse_store: SourceParseStore, started: str, contracts: ContractRegistry
) -> None:
    out, sid, inputs = run(
        {
            ORIGINAL: {"received_at": "2026-03-01T10:00:00Z"},
            RESTATED: {"received_at": "2026-04-15T09:00:00Z"},
        }
    )
    write_blocks(parse_store, started, inputs)
    items = {i["canonical_label"]: i for i in out["normalized_historicals"]["line_items"]}
    figure = items["Revenue"]["values"][0]
    assert figure["source_id"] == sid[RESTATED]
    assert TieoutGate(parse_store, recompute, 0.0).check(out, started).passed
    versions = {f.source_id: f.source_version for f in inputs.files}
    assert ProvenanceGate(contracts, parse_store).check(out, started, versions).passed
    assert contracts.check("skills/timing-normalization@1.0.0", out) == ()


def test_only_open_disagreements_reach_a_person() -> None:
    settled, _, _ = run(
        {
            ORIGINAL: {"received_at": "2026-03-01T10:00:00Z"},
            RESTATED: {"received_at": "2026-04-15T09:00:00Z"},
        }
    )
    open_, _, _ = run({})
    procedure = TimingNormalization()
    assert [
        i for i in procedure.review_items(settled, {}) if i.item_id.startswith("conflict:")
    ] == []
    assert (
        len([i for i in procedure.review_items(open_, {}) if i.item_id.startswith("conflict:")])
        == 2
    )


def test_the_procedure_and_the_tool_agree_on_the_marker() -> None:
    assert SETTLED_BY_RULE == TAKEN_BY_RULE


# ------------------------------------------------------------ reading an audit


@pytest.mark.parametrize(
    "text",
    [
        "INDEPENDENT AUDITOR'S REPORT\nTo the Board of Directors",
        "Independent Auditors' Report",
        "Report of Independent Registered Public Accounting Firm",
        "In our opinion, the accompanying financial statements present fairly, in all material",
    ],
)
def test_an_audit_opinion_is_recognised(text: str) -> None:
    assert audited_evidence(text)


@pytest.mark.parametrize(
    "text",
    [
        "Independent Accountant's Compilation Report",
        "Independent Accountant's Review Report",
        "Balance Sheet\nTotal assets",
        "",
    ],
)
def test_a_compilation_or_review_is_not_an_audit(text: str) -> None:
    assert audited_evidence(text) is None
