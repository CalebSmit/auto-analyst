"""A skill below its gate cannot be registered; one at its gate is recorded, once."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml

from evals import EvalHarness, SkillRegistration
from evals.harness import Metric
from evals.registration import RegistrationRefused
from evals.world import EvalWorld


def test_a_skill_at_its_gate_registers_and_the_record_says_what_was_measured(
    harness: EvalHarness, eval_world: EvalWorld, tmp_path: Path
) -> None:
    card = harness.evaluate("timing-normalization", eval_world)
    registry = SkillRegistration(tmp_path / "registered.yaml")
    record = registry.register(card, approved_by="Caleb")
    assert record.key == "timing-normalization@0.1.0"
    assert record.scorecard_hash.startswith("sha256:")
    assert any("arithmetic_agreement" in g for g in record.gates)
    assert registry.is_registered("timing-normalization", "0.1.0")
    body = yaml.safe_load((tmp_path / "registered.yaml").read_text(encoding="utf-8"))
    assert body["registered"][0]["approved_by"] == "Caleb"


def test_a_skill_below_its_gate_cannot_be_registered(
    harness: EvalHarness, eval_world: EvalWorld, tmp_path: Path
) -> None:
    """The exit criterion. Same scorecard, one metric pushed under its threshold: the
    registration is refused with the code and the metric named, and nothing is written."""
    card = harness.evaluate("line-item-tagging", eval_world)
    metrics = tuple(
        dataclasses.replace(m, value=0.90, passed=False) if m.gate.metric == "top1_agreement" else m
        for m in card.metrics
    )
    below = dataclasses.replace(card, metrics=metrics)
    assert not below.passed
    registry = SkillRegistration(tmp_path / "registered.yaml")
    with pytest.raises(RegistrationRefused) as refused:
        registry.register(below, approved_by="Caleb")
    assert refused.value.diagnostic.code == "SKILL.BELOW_GATE"
    assert "top1_agreement" in refused.value.diagnostic.detail
    assert not (tmp_path / "registered.yaml").exists()
    assert not registry.is_registered("line-item-tagging", "0.1.0")


def test_an_owed_gate_is_recorded_as_owed_not_as_passed(
    harness: EvalHarness, eval_world: EvalWorld, tmp_path: Path
) -> None:
    card = harness.evaluate("line-item-tagging", eval_world)
    record = SkillRegistration(tmp_path / "registered.yaml").register(card, approved_by="Caleb")
    assert record.owed == ("shadow_disagreement (shadow_run)",)


def test_an_unshipped_skill_a_blank_approver_and_a_repeat_are_all_refused(
    harness: EvalHarness, eval_world: EvalWorld, tmp_path: Path
) -> None:
    registry = SkillRegistration(tmp_path / "registered.yaml")
    with pytest.raises(RegistrationRefused):
        registry.register(harness.evaluate("qc-tieout"), approved_by="Caleb")
    card = harness.evaluate("model-load", eval_world)
    with pytest.raises(ValueError):
        registry.register(card, approved_by="  ")
    registry.register(card, approved_by="Caleb")
    with pytest.raises(RegistrationRefused) as again:
        registry.register(card, approved_by="Caleb")
    assert "already registered" in again.value.diagnostic.detail
    assert len(registry.registered()) == 1


def test_registration_is_the_only_writer_of_the_record() -> None:
    """One module writes `skills/registered.yaml`, so there is one place a version can
    become live and one place to read to know how.

    Measured over code with the docstrings stripped out. Prose that names the file is
    describing it, not writing to it - a sibling register saying "append-only, like
    skills/registered.yaml" is documentation, and counting it as a writer would make this
    test a reason not to explain things.
    """
    import ast

    from tests.p22.conftest import ROOT

    def code_only(source: str) -> str:
        """The source with every docstring removed."""
        holds_a_docstring = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, holds_a_docstring):
                text = ast.get_docstring(node, clean=False)
                if text:
                    source = source.replace(text, "")
        return source

    writers = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".venv/", "tests/")):
            continue
        if "registered.yaml" in code_only(path.read_text(encoding="utf-8")):
            writers.append(rel)

    # One writer per register, not one writer overall. P33 added a second register - the
    # recipes approved to run on client work - and it owns its own file for exactly the
    # reason this test exists: a register with two writers is a register whose history
    # nobody can reconstruct.
    assert sorted(writers) == ["evals/registration.py", "registries/recipes.py"]

    from evals.registration import REGISTER_FILE as SKILLS
    from registries.recipes import REGISTERED_FILE as RECIPES

    assert SKILLS != RECIPES, "two registers, two files"
    assert SKILLS.parent.name == "skills" and RECIPES.parent.name == "recipes"
    metric = Metric  # the type registration reads; nothing else constructs a record
    assert metric is not None
