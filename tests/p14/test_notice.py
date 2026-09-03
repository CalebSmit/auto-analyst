"""The Fixed Notice: fixed strings, display names only, no model on the path."""

from __future__ import annotations

import json
import re

import pytest

from harness import notice as module
from harness.notice import DISPLAY_FIELDS, NOTICES, notice, notice_for
from registries.errors import LOOP_EXHAUSTED, UNKNOWN_CONTRACT, diagnose
from tests.p14.conftest import ROOT


def test_the_set_is_closed_and_covers_the_blueprints_situations() -> None:
    """Blocked release, unreachable source, missing template, not-in-dataset miss, the
    partial result a quarantine reports, and the config error preflight raises."""
    assert set(NOTICES) >= {
        "blocked_release",
        "unreachable_source",
        "missing_template",
        "not_in_dataset",
        "quarantined_partial",
        "config_error",
    }
    with pytest.raises(KeyError):
        notice("improvised", engagement="x")


def test_no_template_leaks_a_node_id_a_path_or_a_key() -> None:
    graph = json.loads((ROOT / "graph" / "architecture.json").read_text(encoding="utf-8"))
    node_ids = {n["id"] for n in graph["nodes"]}
    for kind, template in NOTICES.items():
        stripped = re.sub(r"\{[a-z_]+\}", "", template)
        for node_id in node_ids:
            assert node_id not in stripped, f"{kind} names the node {node_id}"
        assert "/" not in stripped and "sha256" not in stripped and ".py" not in stripped, kind


def test_every_placeholder_is_a_display_field() -> None:
    for kind, template in NOTICES.items():
        for name in re.findall(r"\{([a-z_]+)\}", template):
            assert name in DISPLAY_FIELDS, f"{kind} uses {name}"


def test_a_missing_value_is_refused_rather_than_defaulted() -> None:
    with pytest.raises(ValueError, match="no default text"):
        notice("missing_template", engagement="Henderson Manufacturing")


def test_braces_in_a_value_are_text_not_directives() -> None:
    made = notice(
        "not_in_dataset",
        term="{dataset}",
        dataset="the industry multiples table",
    )
    assert "'{dataset}' is not in the industry multiples table" in made.text


def test_the_quarantine_notice_reports_partial_progress_without_releasing_it() -> None:
    made = notice(
        "quarantined_partial",
        engagement="Henderson Manufacturing",
        step="EBITDA normalization",
        completed=4,
        total=8,
    )
    assert "4 of 8 steps finished" in made.text
    assert "nothing is released" in made.text
    assert "review item" in made.text


def test_a_diagnostic_becomes_the_message_a_person_sees() -> None:
    d = diagnose(LOOP_EXHAUSTED, "guard_repair on ebitda reached its ceiling of 2")
    made = notice_for(d, step="EBITDA normalization")
    assert made.text.startswith("EBITDA normalization did not complete.")
    assert "The skill owner" in made.text
    assert d.what_now in made.text
    assert "LOOP.EXHAUSTED" not in made.text and "ebitda" not in made.text.replace("EBITDA", "")


def test_a_config_error_names_the_administrator() -> None:
    d = diagnose(UNKNOWN_CONTRACT, "figure@9.9.9 is not in contracts/registry.yaml")
    made = notice_for(d, step="Preflight", engagement="Henderson Manufacturing")
    assert made.kind == "config_error"
    assert "The administrator owns the fix" in made.text
    assert "figure@9.9.9" not in made.text, "the detail stays in the record"


def test_no_model_anywhere_on_this_path() -> None:
    text = (ROOT / "harness" / "notice.py").read_text(encoding="utf-8")
    for forbidden in (
        "ports.llm",
        "anthropic",
        "ModelDoor",
        "harness.door",
        "str.format(",
        ".format(",
    ):
        assert forbidden not in text, forbidden
    assert not hasattr(module, "generate")
