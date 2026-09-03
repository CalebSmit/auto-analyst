"""The Timing Normalizer: every figure re-derives, nothing is interpolated or chosen."""

from __future__ import annotations

import copy

import pytest

from guards.tieout import TieoutGate
from ops.source_parse import SourceParseStore
from registries.contracts import ContractRegistry
from tests.p18.conftest import load_case, tool_inputs, write_blocks
from tools.normalize import timing_normalizer
from tools.recompute import recompute

GOLDEN = ("annual_drift", "monthly_gap", "conflict")


@pytest.mark.parametrize("case", GOLDEN)
def test_the_tool_agrees_with_the_independently_computed_expectations(case: str) -> None:
    inputs, proposal, expected = load_case(case)
    assert proposal is not None
    sources, files = tool_inputs(inputs)
    out = timing_normalizer(proposal, sources, files, "pin")["output"]
    by_label = {i["canonical_label"]: i for i in out["normalized_historicals"]["line_items"]}
    label_of_end = {p["end"]: p["label"] for p in proposal["periods"]}
    for label, per_period in expected["values"].items():
        got = {label_of_end[v["period"]["end"]]: v["value"] for v in by_label[label]["values"]}
        assert got == per_period, label
    report = out["alignment_report"]
    assert len(report["matched"]) == expected["matched"]
    assert len(report["unmatched"]) == expected["unmatched"]
    assert [g["period_label"] for g in report["period_gaps"]] == expected["period_gaps"]
    assert len(report["conflicts"]) == expected["conflicts"]


@pytest.mark.parametrize("case", GOLDEN)
def test_one_hundred_percent_arithmetic_agreement_with_the_deterministic_tool(
    case: str, parse_store: SourceParseStore, started: str, contracts: ContractRegistry
) -> None:
    """The exit criterion. Every figure the tool emits carries a derivation; the tie-out
    guard re-derives every one of them from the parse store, and the output validates
    against the contract. Not one figure is stated without the rows behind it."""
    inputs, proposal, _ = load_case(case)
    assert proposal is not None
    write_blocks(parse_store, started, inputs)
    sources, files = tool_inputs(inputs)
    out = timing_normalizer(proposal, sources, files, "claude-sonnet-5 @ effort=high")["output"]

    assert contracts.check("skills/timing-normalization@1.0.0", out) == ()
    figures = [v for item in out["normalized_historicals"]["line_items"] for v in item["values"]]
    assert figures
    assert all(f["derivation"]["op"] == "sum" and f["derivation"]["of"] for f in figures)
    result = TieoutGate(parse_store, recompute, 0.0).check(out, started)
    assert result.passed and result.checked == len(figures)
    for f in figures:
        rows = [parse_store.resolve(started, f["source_id"], loc) for loc in f["derivation"]["of"]]
        assert all(rows), f["derivation"]
        assert recompute("sum", [[r.value for r in rs] for rs in rows], f["value"]).matches


def test_a_period_gap_is_reported_and_never_interpolated() -> None:
    """The exit criterion. April is missing from the monthly file: it is in the report,
    and no line item has a figure for it - not zero, not an average, not March."""
    inputs, proposal, _ = load_case("monthly_gap")
    assert proposal is not None
    out = timing_normalizer(proposal, *tool_inputs(inputs), "pin")["output"]
    assert out["alignment_report"]["period_gaps"] == [
        {"period_label": "M2025-04", "why": "no block covers it"}
    ]
    ends = {p["end"] for p in out["normalized_historicals"]["periods"]}
    assert "2025-04-30" not in ends
    for item in out["normalized_historicals"]["line_items"]:
        assert len(item["values"]) == 5
        assert all(v["period"]["end"] != "2025-04-30" for v in item["values"])


def test_two_files_claiming_one_period_are_reported_not_chosen() -> None:
    inputs, proposal, _ = load_case("conflict")
    assert proposal is not None
    out = timing_normalizer(proposal, *tool_inputs(inputs), "pin")["output"]
    report = out["alignment_report"]
    assert {c["detail"].split(":")[0] for c in report["conflicts"]} == {"Revenue", "Gross profit"}
    assert all(
        len(c["source_ids"]) == 2 and "no figure taken" in c["detail"] for c in report["conflicts"]
    )
    by_label = {i["canonical_label"]: i for i in out["normalized_historicals"]["line_items"]}
    assert by_label["Revenue"]["values"] == [] and by_label["Gross profit"]["values"] == []
    (rent,) = by_label["Rent"]["values"]
    assert rent["value"] == 96000.0, "both files agree, so the figure is taken"
    assert len(rent["derivation"]["of"]) == 1, "and it cites its own source's row"
    trail = timing_normalizer(proposal, *tool_inputs(inputs), "pin")["rows"]
    rent_trail = next(t for t in trail if t["canonical_label"] == "Rent")
    assert len(rent_trail["rows"]) == 2, "the agreement is on the trail, both rows"


def test_every_unmatched_line_is_reported_including_the_ones_the_proposal_forgot() -> None:
    """The exit criterion. The proposal's own unmatched entry is on the report; a row
    the proposal simply omitted is on it too, saying so."""
    inputs, proposal, _ = load_case("annual_drift")
    assert proposal is not None
    forgetful = copy.deepcopy(proposal)
    dropped = forgetful["line_items"][3]["sources"].pop()  # one period of one line
    out = timing_normalizer(forgetful, *tool_inputs(inputs), "pin")["output"]
    unmatched = out["alignment_report"]["unmatched"]
    reasons = {u["source_label"]: u["reason"] for u in unmatched}
    assert reasons["Q3 special project"].startswith("no counterpart")
    assert reasons[dropped["label"]].startswith("not in the proposal")
    assert len(unmatched) == 2


def test_a_row_claimed_twice_is_refused() -> None:
    inputs, proposal, _ = load_case("annual_drift")
    assert proposal is not None
    doubled = copy.deepcopy(proposal)
    doubled["line_items"][1]["sources"].append(doubled["line_items"][0]["sources"][0])
    with pytest.raises(ValueError, match="claimed twice"):
        timing_normalizer(doubled, *tool_inputs(inputs), "pin")


def test_an_unsettled_scale_is_refused_not_defaulted() -> None:
    inputs, proposal, _ = load_case("annual_drift")
    assert proposal is not None
    sources, files = tool_inputs(inputs)
    files = {sid: {**meta, "scale": None} for sid, meta in files.items()}
    with pytest.raises(ValueError, match="no settled scale"):
        timing_normalizer(proposal, sources, files, "pin")


def test_the_period_cap_holds() -> None:
    inputs, proposal, _ = load_case("annual_drift")
    assert proposal is not None
    with pytest.raises(ValueError, match="cap"):
        timing_normalizer(proposal, *tool_inputs(inputs), "pin", caps={"max_periods": 2})


def test_the_trail_is_what_the_runtime_counts() -> None:
    inputs, proposal, expected = load_case("annual_drift")
    assert proposal is not None
    result = timing_normalizer(proposal, *tool_inputs(inputs), "pin")
    assert len(result["rows"]) == expected["matched"] * 3
    entry = result["rows"][0]
    assert set(entry) == {"canonical_label", "period_label", "op", "of", "rows", "value"}
    assert entry["value"] == sum(r["value"] for r in entry["rows"])


def test_the_tool_knows_nothing_about_models() -> None:
    import ast
    from pathlib import Path

    tree = ast.parse(
        (Path(__file__).resolve().parents[2] / "tools" / "normalize.py").read_text(encoding="utf-8")
    )
    imported = {
        (n.module or "") if isinstance(n, ast.ImportFrom) else n.names[0].name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
    }
    assert not any(
        m.startswith(("ports", "harness", "anthropic", "registries", "guards")) for m in imported
    )
