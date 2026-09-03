"""The figure envelope - the one contract every guard is really about.

Exit criteria 2 and 3:
  - a figure missing scale is rejected; scale is never inferred downstream
  - a figure citing 'derived', 'model' or 'analysis' is rejected as fabricated provenance
"""

from __future__ import annotations

from typing import Any

import pytest

from registries.contracts import ContractRegistry
from registries.errors import (
    FABRICATED_SOURCE,
    NO_PROVENANCE,
    SCHEMA_INVALID,
    ContractViolation,
)
from tests.p02.conftest import SHA, walk_schemas

FIGURE = "figure@1.0.0"


def codes(contracts: ContractRegistry, instance: object) -> set[str]:
    return {d.code for d in contracts.check(FIGURE, instance)}


def test_the_blueprints_worked_example_validates(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    assert contracts.check(FIGURE, figure) == ()


def test_a_read_figure_has_a_null_derivation(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    """Null, not absent. A figure that will not say whether it was read or computed
    cannot be tied out, so the field is required either way."""
    assert contracts.check(FIGURE, {**figure, "derivation": None}) == ()
    without = {k: v for k, v in figure.items() if k != "derivation"}
    assert codes(contracts, without) == {SCHEMA_INVALID}


# ------------------------------------------------------------------ scale


def test_a_figure_missing_scale_is_rejected(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    without = {k: v for k, v in figure.items() if k != "scale"}
    assert codes(contracts, without) == {SCHEMA_INVALID}


def test_scale_has_no_default_anywhere(contracts: ContractRegistry) -> None:
    """Scale is never inferred downstream.

    A default is inference with a friendly name: it is exactly how a trial balance in
    thousands gets read as units, which the blueprint lists as a halt-at-tie-out failure.
    """
    for key in contracts.ids():
        for subschema in walk_schemas(contracts.get(key)):
            properties = subschema.get("properties")
            if isinstance(properties, dict) and "scale" in properties:
                assert "default" not in properties["scale"], f"{key} defaults scale"


def test_only_declared_scales_are_accepted(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    for bad in (100, 0, 1_000_000_000, "1000", None):
        assert codes(contracts, {**figure, "scale": bad}) == {SCHEMA_INVALID}
    for good in (1, 1000, 1_000_000):
        assert contracts.check(FIGURE, {**figure, "scale": good}) == ()


# ------------------------------------------------------------------ provenance


@pytest.mark.parametrize("fabricated", ["derived", "model", "analysis"])
def test_fabricated_provenance_is_rejected_as_fabricated(
    contracts: ContractRegistry, figure: dict[str, Any], fabricated: str
) -> None:
    """Not merely as a malformed hash. The diagnostic has to say what happened, because
    'source_id does not match a pattern' sends somebody to fix the wrong thing."""
    with pytest.raises(ContractViolation) as raised:
        contracts.validate(FIGURE, {**figure, "source_id": fabricated})
    assert raised.value.diagnostic.code == FABRICATED_SOURCE
    assert raised.value.diagnostic.owner == "model"


@pytest.mark.parametrize(
    "fabricated",
    ["DERIVED", "Model", "sha256:derived", "estimate", "assumed", "calculated", "internal", "n/a"],
)
def test_the_obvious_variations_are_rejected_too(
    contracts: ContractRegistry, figure: dict[str, Any], fabricated: str
) -> None:
    assert FABRICATED_SOURCE in codes(contracts, {**figure, "source_id": fabricated})


@pytest.mark.parametrize("field", ["source_id", "locator", "source_version"])
def test_a_missing_provenance_field_reads_as_a_provenance_failure(
    contracts: ContractRegistry, figure: dict[str, Any], field: str
) -> None:
    without = {k: v for k, v in figure.items() if k != field}
    assert NO_PROVENANCE in codes(contracts, without)


def test_a_malformed_source_id_is_rejected(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    for bad in ("9f2c", "md5:" + "0" * 32, "sha256:NOTHEX" + "0" * 58, ""):
        assert codes(contracts, {**figure, "source_id": bad}) == {NO_PROVENANCE}


# ------------------------------------------------------------------ the rest


def test_a_currency_figure_must_name_its_currency(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    without = {k: v for k, v in figure.items() if k != "currency"}
    assert codes(contracts, without) == {SCHEMA_INVALID}


def test_a_non_currency_figure_may_not_carry_one(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    """A ratio with a currency code on it is a units error wearing a disguise."""
    assert codes(contracts, {**figure, "unit": "ratio"}) == {SCHEMA_INVALID}
    ratio = {**figure, "unit": "ratio"}
    del ratio["currency"]
    assert contracts.check(FIGURE, ratio) == ()


def test_confidence_is_bounded(contracts: ContractRegistry, figure: dict[str, Any]) -> None:
    for bad in (-0.1, 1.1, 83):
        assert codes(contracts, {**figure, "confidence": bad}) == {SCHEMA_INVALID}


def test_produced_by_is_a_pinned_skill_version(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    for bad in ("ebitda-normalization", "ebitda-normalization@latest", "@0.1.0"):
        assert codes(contracts, {**figure, "produced_by": bad}) == {SCHEMA_INVALID}


def test_a_figure_cannot_carry_an_undeclared_field(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    """Including one that sounds harmless. This is where a conclusion would arrive."""
    for smuggled in ("conclusion", "opinion_of_value", "note", "final"):
        assert codes(contracts, {**figure, smuggled: "x"}) == {SCHEMA_INVALID}


def test_the_period_is_typed(contracts: ContractRegistry, figure: dict[str, Any]) -> None:
    assert codes(contracts, {**figure, "period": {"end": "2023-12-31"}}) == {SCHEMA_INVALID}
    assert codes(contracts, {**figure, "period": "FY2023"}) == {SCHEMA_INVALID}
    assert codes(contracts, {**figure, "period": {"type": "TTM", "end": "2023-12-31"}}) == {
        SCHEMA_INVALID
    }


def test_a_derivation_names_its_operands(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    """The recompute engine re-derives from these. An empty list is a claim with nothing
    behind it, and tie-out would have nothing to check."""
    assert codes(contracts, {**figure, "derivation": {"op": "sum", "of": []}}) == {SCHEMA_INVALID}
    assert codes(contracts, {**figure, "derivation": {"op": "sum"}}) == {SCHEMA_INVALID}
    assert codes(contracts, {**figure, "derivation": {"op": "guess", "of": ["a"]}}) == {
        SCHEMA_INVALID
    }


def test_a_figure_leaves_a_skill_masked(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    """The schema permits false because deterministic code sets it after unmasking. What
    it does not permit is the field being absent, which is how a masked figure would be
    mistaken for an unmasked one."""
    without = {k: v for k, v in figure.items() if k != "masked"}
    assert codes(contracts, without) == {SCHEMA_INVALID}
    assert contracts.check(FIGURE, {**figure, "masked": False}) == ()


def test_the_sha_helper_matches_the_schema(contracts: ContractRegistry) -> None:
    assert len(SHA) == len("sha256:") + 64
