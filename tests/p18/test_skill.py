"""The skill through the dispatcher: one call, a mapping back, the tool does the sums."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from graph.compile import Step
from graph.execute import Blocked
from graph.resolve import ResolvedScope
from guards import GuardFailed
from guards.provenance import ProvenanceGate
from guards.tieout import TieoutGate
from guards.untrusted import BEGIN, SENTINEL_RULE
from ops.run_store import SqlRunStore
from ops.source_parse import SourceParseStore
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.skills import SkillTree
from tests.p18.conftest import (
    CASES,
    ROOT,
    ProposalPort,
    dispatch,
    events_of,
    load_case,
    tool_inputs,
    write_blocks,
)
from tools.normalize import timing_normalizer
from tools.recompute import recompute


def test_the_skill_runs_end_to_end_through_the_dispatcher(
    world: dict[str, Any], timing_step: Step, scope: ResolvedScope, store: SqlRunStore
) -> None:
    inputs, proposal, expected = load_case("annual_drift")
    assert proposal is not None
    port = ProposalPort(proposal)
    done = dispatch(world, timing_step, scope, port, inputs)

    assert done.skill == "timing-normalization@0.1.0"
    assert len(done.output["alignment_report"]["matched"]) == expected["matched"]
    assert done.proposal == proposal
    assert len(port.requests) == 1 and done.model_calls == 1
    assert store.run(world["run_id"]).model_calls == 1
    kinds = {e.type for e in store.events(world["run_id"])}
    assert {
        "skill.dispatched",
        "context.assembled",
        "guard.untrusted_boundary.pass",
        "model.called",
        "model.answered",
        "guard.schema.pass",
        "tool.called",
        "skill.completed",
    } <= kinds, sorted(kinds)
    assert len(events_of(store, world["run_id"], "guard.schema.pass")) == 2, "proposal and output"


def test_the_model_sees_labels_and_locators_never_values(
    world: dict[str, Any], timing_step: Step, scope: ResolvedScope
) -> None:
    inputs, proposal, _ = load_case("annual_drift")
    assert proposal is not None
    port = ProposalPort(proposal)
    dispatch(world, timing_step, scope, port, inputs)
    (request,) = port.requests
    user = request.messages[0].content
    assert user.startswith(BEGIN)
    assert "IS!B4: Officer salary" in user or "IS!B5: Officer salary" in user
    for value in ("4,020,000", "4020000", "4,401,900", "4401900", "235,000", "235000"):
        assert value not in user, f"a value reached the model: {value}"
    assert SENTINEL_RULE in request.system
    assert "never a number" in request.system.lower()
    assert "line-item matching" in request.system.lower()


def test_the_proposal_contract_has_no_numeric_field_anywhere(contracts: ContractRegistry) -> None:
    """The exit criterion for the proposal schema: a mapping, never a number."""
    schema = contracts.get("skills/timing-normalization-proposal@1.0.0")

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            assert node.get("type") not in ("number", "integer"), node
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)


def test_a_proposal_carrying_a_number_is_refused_before_any_tool_runs(
    world: dict[str, Any], timing_step: Step, scope: ResolvedScope, store: SqlRunStore
) -> None:
    inputs, proposal, _ = load_case("annual_drift")
    assert proposal is not None
    numeric = copy.deepcopy(proposal)
    numeric["line_items"][0]["value"] = 4020000
    with pytest.raises(GuardFailed) as refused:
        dispatch(world, timing_step, scope, ProposalPort(numeric), inputs)
    assert refused.value.diagnostic.code == "SKILL.SCHEMA_INVALID"
    assert events_of(store, world["run_id"], "tool.called") == []


def test_the_fixture_set_matches_at_least_98_percent_and_reports_every_unmatched_line() -> None:
    """The exit criterion, over the whole golden set: rows placed under a canonical label
    over all rows, with every remaining row on the report by name."""
    matched_rows = total_rows = 0
    for case in ("annual_drift", "monthly_gap", "conflict"):
        inputs, proposal, expected = load_case(case)
        assert proposal is not None
        out = timing_normalizer(proposal, *tool_inputs(inputs), "pin")["output"]
        placed = sum(len(i["sources"]) for i in proposal["line_items"])
        rows = sum(
            len([r for r in rows if r.get("value") is not None])
            for f in inputs.files
            for rows in f.blocks.values()
        )
        assert rows == expected["rows"] and placed == expected["matched_rows"]
        assert len(out["alignment_report"]["unmatched"]) == rows - placed
        matched_rows += placed
        total_rows += rows
    assert matched_rows / total_rows >= 0.98, f"{matched_rows}/{total_rows}"


def test_the_output_passes_provenance_and_tie_out_over_the_parse_store(
    world: dict[str, Any],
    timing_step: Step,
    scope: ResolvedScope,
    parse_store: SourceParseStore,
    contracts: ContractRegistry,
) -> None:
    inputs, proposal, _ = load_case("annual_drift")
    assert proposal is not None
    write_blocks(parse_store, world["run_id"], inputs)
    done = dispatch(world, timing_step, scope, ProposalPort(proposal), inputs)
    versions = {f.source_id: f.source_version for f in inputs.files}
    provenance = ProvenanceGate(contracts, parse_store).check(
        done.output, world["run_id"], versions
    )
    assert provenance.passed and provenance.checked == 57
    tieout = TieoutGate(parse_store, recompute, 0.0).check(done.output, world["run_id"])
    assert tieout.passed and tieout.checked == 57


def test_an_ambiguous_file_escalates_before_the_skill_proceeds(
    world: dict[str, Any], timing_step: Step, scope: ResolvedScope, store: SqlRunStore
) -> None:
    """The exit criterion. No payload is masked, no context is built, no model is
    called: the run blocks on a person with the detector's own words."""
    inputs, _, expected = load_case("ambiguous")
    assert expected["escalates"]
    port = ProposalPort({})
    with pytest.raises(Blocked) as blocked:
        dispatch(world, timing_step, scope, port, inputs)
    assert "ambiguous" in blocked.value.subject and "scale" in blocked.value.subject
    assert blocked.value.kind == "ambiguous_periods_require_review"
    assert port.requests == []
    kinds = {e.type for e in store.events(world["run_id"])}
    assert "skill.escalated" in kinds
    assert not kinds & {"model.called", "context.assembled", "tool.called"}


def test_the_skill_may_only_call_the_tool_it_declared(
    world: dict[str, Any], constraints: ConstraintRegistry
) -> None:
    from harness.policy import PolicyDenied

    tools = world["runtime"].bound(world["run_scope"], "timing-normalization@0.1.0", "timing")
    assert tools.names() == ("timing_normalizer",)
    with pytest.raises(PolicyDenied):
        tools["recompute"](
            engagement_id=world["run_scope"].engagement_id, op="sum", operands=[[1.0]], stated=1.0
        )


# ------------------------------------------------------------- the skill file


def test_the_skill_file_is_written_and_says_a_mapping_never_a_number(tree: SkillTree) -> None:
    skill = next(s for s in tree.all() if s.name == "timing-normalization")
    assert skill.status == "draft"
    body = tree.body(skill)
    for heading in ("## When to use", "## When not to use", "## Procedure", "## Escalate when"):
        assert heading in body
    assert "never a number" in body.lower()
    assert "Skeleton" not in body
    for ref in ("period-conventions.md", "line-item-matching.md"):
        text = tree.reference(skill, ref)
        assert "Placeholder" not in text and len(text.splitlines()) > 20


def test_the_references_teach_the_four_kinds_and_the_gap_rule(tree: SkillTree) -> None:
    skill = next(s for s in tree.all() if s.name == "timing-normalization")
    matching = tree.reference(skill, "line-item-matching.md")
    for kind in ("exact", "rename", "split", "merge"):
        assert f"| {kind}" in matching
    conventions = tree.reference(skill, "period-conventions.md")
    assert "never filled" in conventions.lower() or "never interpolated" in conventions.lower()


def test_no_python_under_the_skill_tree_still_holds() -> None:
    assert not list((ROOT / "skills").rglob("*.py"))
    assert (ROOT / "harness" / "procedures" / "timing_normalization.py").is_file()


def test_the_golden_cases_are_synthetic_and_complete() -> None:
    for case in ("annual_drift", "monthly_gap", "conflict", "ambiguous"):
        body = json.loads((CASES / case / "case.json").read_text(encoding="utf-8"))
        for f in body["files"]:
            assert f["source_id"].startswith("sha256:")
            assert "Henderson" not in json.dumps(f["blocks"]), "no client-looking names in the rows"
