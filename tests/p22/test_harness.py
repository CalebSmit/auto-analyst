"""The Evaluation Harness: every shipped skill has fixtures and a named numeric gate,
the gates are the blueprint's, and coverage says what is not covered."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from evals import EvalHarness
from evals.harness import GATES_FILE
from evals.world import EvalWorld
from registries.skills import SkillTree
from tests.p22.conftest import ROOT

SHIPPED = ("timing-normalization", "line-item-tagging", "ebitda-normalization", "model-load")


def test_every_shipped_skill_has_fixtures_and_a_named_numeric_gate(
    harness: EvalHarness, tree: SkillTree
) -> None:
    """The exit criterion. Shipped means the tree says draft - a procedure exists - and
    for each such skill the gates file names fixtures on disk and at least one gate
    with a metric name, an operator and a number."""
    drafted = {s.name for s in tree.all() if s.status == "draft"}
    assert drafted == set(SHIPPED) == set(harness.shipped())
    for skill in SHIPPED:
        entry = harness.spec["skills"][skill]
        assert (ROOT / entry["fixtures"]).is_dir(), skill
        gates = harness.gates_for(skill)
        assert gates, skill
        for gate in gates:
            assert re.match(r"^[a-z][a-z0-9_]+$", gate.metric)
            assert gate.op in (">=", "<=", ">", "<", "==")
            assert isinstance(gate.threshold, float)
            assert gate.blueprint, f"{skill}.{gate.metric} has no blueprint sentence"


def test_the_gates_are_the_blueprints_gate_table() -> None:
    """Every skill row in the blueprint's GATES table has an entry - shipped with
    numbers, or listed as not shipped with the blueprint's sentence."""
    html = (ROOT / "docs" / "architecture.html").read_text(encoding="utf-8")
    start = html.index("const GATES = [")
    block = html[start : html.index("];", start)]
    rows = re.findall(r"\['([a-z /-]+)','", block)
    spec = yaml.safe_load(GATES_FILE.read_text(encoding="utf-8"))["skills"]
    for row in rows:
        for skill in (s.strip() for s in row.split("/")):
            assert skill in spec, f"{skill} is in the blueprint's gate table and not in gates.yaml"


@pytest.mark.parametrize("skill", SHIPPED)
def test_each_shipped_skill_clears_its_gates(
    harness: EvalHarness, eval_world: EvalWorld, skill: str
) -> None:
    card = harness.evaluate(skill, eval_world)
    assert card.status == "shipped" and card.passed, card.report()
    measured = [m for m in card.metrics if m.value is not None]
    assert measured and all(m.passed for m in measured)
    assert card.key.endswith("@0.1.0")


def test_the_numbers_are_the_phases_own(harness: EvalHarness, eval_world: EvalWorld) -> None:
    """The harness computes what P18-P21 asserted, through the same code: not a second
    opinion, the same one made into a number."""
    timing = harness.evaluate("timing-normalization", eval_world)
    values = {m.gate.metric: m.value for m in timing.metrics}
    assert values["arithmetic_agreement"] == 1.0 and values["unmatched_reported"] == 1.0
    assert values["line_item_match_rate"] is not None and values["line_item_match_rate"] >= 0.98

    tagging = harness.evaluate("line-item-tagging", eval_world)
    values = {m.gate.metric: m.value for m in tagging.metrics}
    assert values["top1_agreement"] == pytest.approx(383 / 400)
    assert values["provenance_failures"] == 0
    owed = [m for m in tagging.metrics if m.value is None]
    assert [m.gate.metric for m in owed] == ["shadow_disagreement"]
    assert owed[0].gate.measured_by == "shadow_run"

    ebitda = harness.evaluate("ebitda-normalization", eval_world)
    values = {m.gate.metric: m.value for m in ebitda.metrics}
    assert values["tie_rate"] == 1.0 and values["material_auto_accepted"] == 0
    assert values["recall"] == pytest.approx(17 / 18) and values["recurring_flagged"] == 1.0

    model = harness.evaluate("model-load", eval_world)
    values = {m.gate.metric: m.value for m in model.metrics}
    assert values == {"inputs_mapped_or_reported": 1.0, "writes_outside_schema": 0.0}


def test_a_gate_that_cannot_be_measured_offline_is_owed_not_passed(
    harness: EvalHarness, eval_world: EvalWorld
) -> None:
    card = harness.evaluate("line-item-tagging", eval_world)
    assert card.passed, "an owed gate does not fail the skill here"
    assert [g.metric for g in card.owed] == ["shadow_disagreement"]
    assert "owed to shadow_run" in card.report()


def test_an_unshipped_skill_scores_nothing_and_says_so(harness: EvalHarness) -> None:
    card = harness.evaluate("ddr-tagging")
    assert card.status == "not_shipped" and not card.passed and card.metrics == ()
    with pytest.raises(KeyError):
        harness.evaluate("no-such-skill")


def test_coverage_reports_what_is_covered_and_what_is_not(harness: EvalHarness) -> None:
    """The exit criterion. Nine skeleton skills without fixtures, four guard nodes
    without an adversarial fixture, one gate owed - named, not summarised."""
    coverage = harness.coverage()
    assert set(coverage.skills_covered) == set(SHIPPED)
    assert len(coverage.skills_not_covered) == 9
    assert "ddr-tagging" in coverage.skills_not_covered
    assert len(coverage.guards_covered) == 10
    assert set(coverage.guards_not_covered) == {
        "index_gate",
        "policy_gate",
        "reconcile",
        "release_gate",
        "schema_gate",
        "skill_conformance",
    }
    assert coverage.gates_owed == ("line-item-tagging: shadow_disagreement (shadow_run)",)
    report = coverage.report()
    assert "skills NOT covered (9)" in report and "guards NOT covered (6)" in report


def test_the_eval_world_leaves_nothing_behind(tmp_path: Path) -> None:
    world = EvalWorld()
    root = world.root
    assert root.is_dir()
    world.close()
    assert not root.exists()
