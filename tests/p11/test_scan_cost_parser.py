"""The scan on its own, the meter on its own, and the parser that owes nothing to a SDK."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ops.cost import CostMeter, price
from ports.llm import RATES_USD_PER_MTOK, TIER_MODELS, ModelPin, Usage
from privacy.payload_scan import IdentifierList, PayloadScan
from registries.errors import RegistryError
from registries.skills import parse_skill_file
from tests.p11.conftest import ENGAGEMENT, NAMES, TOKENS

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- the scan


def test_a_clean_masked_payload_passes(identifiers: IdentifierList) -> None:
    result = PayloadScan().check("[[CLIENT_1]] [[PERSON_1]] [[ACCOUNT_17]] 48,231", identifiers)
    assert result.passed
    assert result.checked == len(NAMES) + len(TOKENS)
    assert result.tokens_seen == 3


def test_an_identifier_is_caught_regardless_of_case(identifiers: IdentifierList) -> None:
    text = "[[CLIENT_1]] [[PERSON_1]] [[ACCOUNT_17]] bob henderson"
    result = PayloadScan().check(text, identifiers)
    assert not result.passed
    assert result.hits == ("Bob Henderson",)


def test_a_missed_substitution_is_caught(identifiers: IdentifierList) -> None:
    """The masker said it wrote three tokens. Two are there. The third was skipped, and
    whatever stood where it should be is still in the text."""
    result = PayloadScan().check("[[CLIENT_1]] [[PERSON_1]] something else", identifiers)
    assert not result.passed
    assert result.missing_tokens == ("[[ACCOUNT_17]]",)
    assert result.hits == ()


def test_the_scan_is_deterministic_code() -> None:
    """No model performs re-identification, and none checks it either."""
    source = (ROOT / "privacy" / "payload_scan.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        (n.module or "") if isinstance(n, ast.ImportFrom) else n.names[0].name
        for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom)
    }
    assert not any(i.startswith(("ports.llm", "anthropic", "harness.door")) for i in imported)


def test_an_empty_identifier_list_is_a_pass_over_nothing_and_says_so() -> None:
    """checked=0 in the event. Not asserted as a refusal here - an engagement with no
    identifiers yet is real - but visible, so a manifest showing a pass over zero
    checks reads as what it is."""
    result = PayloadScan().check("anything", IdentifierList.of(ENGAGEMENT, []))
    assert result.passed and result.checked == 0


# --------------------------------------------------------------- the meter


@pytest.mark.parametrize(("tier", "rate"), [("low", (1, 5)), ("mid", (2, 10)), ("high", (5, 25))])
def test_the_rate_table_is_the_blueprints(tier: str, rate: tuple[int, int]) -> None:
    """RATE = {low:[1,5], mid:[2,10], high:[5,25]}, per MTok in and out."""
    assert RATES_USD_PER_MTOK[TIER_MODELS[tier]] == rate


def test_a_charge_is_arithmetic_over_reported_usage() -> None:
    charge = price("claude-opus-5", Usage(input_tokens=100_000, output_tokens=10_000))
    assert charge.usd == pytest.approx(0.5 + 0.25)
    assert charge.tokens == 110_000


def test_cache_reads_and_writes_are_priced() -> None:
    charge = price("claude-sonnet-5", Usage(
        input_tokens=0, output_tokens=0,
        cache_read_input_tokens=1_000_000, cache_creation_input_tokens=1_000_000,
    ))
    assert charge.usd == pytest.approx(2.0 * 0.1 + 2.0 * 1.25)


def test_an_unpriced_model_cannot_be_metered() -> None:
    """A run that cannot say what it spent cannot be budgeted."""
    with pytest.raises(RegistryError) as raised:
        price("claude-3-opus-20240229", Usage(input_tokens=1))
    assert raised.value.diagnostic.code == "SCOPE.MODEL_PIN_UNAVAILABLE"


def test_spend_accumulates_across_calls(meter: CostMeter, started: str) -> None:
    meter.record(started, ModelPin.for_tier("low"), Usage(input_tokens=1_000_000))
    meter.record(started, ModelPin.for_tier("high"), Usage(output_tokens=100_000))
    spend = meter.spend(started)
    assert spend.usd == pytest.approx(1.0 + 2.5)
    assert spend.model_calls == 2
    assert spend.tokens == 1_100_000


def test_the_three_tiers_resolve_to_the_three_models() -> None:
    assert ModelPin.for_tier("low").model == "claude-haiku-4-5"
    assert ModelPin.for_tier("mid").model == "claude-sonnet-5"
    assert ModelPin.for_tier("high").model == "claude-opus-5"
    assert str(ModelPin.for_tier("high", "max")) == "claude-opus-5 @ effort=max"


# -------------------------------------------------------------- the parser


def test_the_parser_reads_frontmatter_body_and_references() -> None:
    parsed = parse_skill_file(ROOT / "skills/valuation/_group/ebitda-normalization/SKILL.md")
    assert parsed.frontmatter["name"] == "ebitda-normalization"
    assert parsed.references == (
        "addback-taxonomy.md", "officer-comp-tests.md", "worked-examples.md"
    )
    assert parsed.body.startswith("# EBITDA Normalization")
    assert "## Procedure" in parsed.body


def test_the_parser_owes_nothing_to_any_sdk() -> None:
    """Finding F4. SKILL.md is a file format we parse, not a framework dependency."""
    tree = ast.parse((ROOT / "registries" / "skills.py").read_text(encoding="utf-8"))
    imported = {
        (n.module or "") if isinstance(n, ast.ImportFrom) else n.names[0].name
        for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom)
    }
    for forbidden in ("anthropic", "claude_agent_sdk", "claude", "langchain", "openai"):
        assert not any(i == forbidden or i.startswith(forbidden + ".") for i in imported)


def test_the_parser_reads_every_skill_in_the_tree() -> None:
    files = sorted((ROOT / "skills").rglob("SKILL.md"))
    assert len(files) == 13
    for path in files:
        parsed = parse_skill_file(path)
        assert parsed.frontmatter["name"] == path.parent.name
        assert parsed.body
