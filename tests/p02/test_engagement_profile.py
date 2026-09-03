"""engagement_profile and participant_census - finding F1, closed as a contract.

Exit criterion 4 - engagement_profile round-trips, and a profile missing the
owner-compensation baseline fails validation.

Three skills declared engagement_profile as a required input and nothing produced it;
Repurchase Obligation declared participant_census, likewise. Invariant 23 had already
decided the answer - configuration writes the engagement record - so what was missing
was a contract, not a design.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from registries.contracts import ContractRegistry
from registries.errors import ContractViolation
from tests.p02.conftest import SHA

PROFILE = "engagement_profile@1.0.0"
CENSUS = "participant_census@1.0.0"

DECLARERS = ("ebitda-normalization", "gpc-scrub", "cost-of-capital")


@pytest.fixture
def profile() -> dict[str, Any]:
    return {
        "schema_version": "engagement_profile@1.0.0",
        "engagement_id": "HEND-2026-04",
        "practice": "valuation",
        "segment": "esop",
        "disposition": "repeat",
        "industry_classification": {
            "system": "NAICS",
            "code": "332710",
            "description": "Machine shops",
        },
        "size_band": {"metric": "revenue", "band": "25-100m", "as_of": "2025-12-31"},
        "fiscal_calendar": {"basis": "calendar", "year_end_month": 12, "year_end_day": 31},
        "scale_convention": 1000,
        "owner_compensation_baseline": {
            "amount": 385000,
            "currency": "USD",
            "basis": "survey_median",
            "source": "RCReports 2025, machine shops, 25-100m revenue",
            "as_of": "2025-06-30",
        },
        "recorded_by": "caleb.smit",
        "recorded_at": "2026-01-14T16:20:00Z",
    }


def test_the_contract_that_finding_f1_asked_for_exists(contracts: ContractRegistry) -> None:
    assert contracts.entry(PROFILE).kind == "configuration"


def test_the_three_skills_that_declared_it_really_do(
    blueprint_skills: dict[str, dict[str, tuple[str, ...]]],
) -> None:
    """If this ever fails, F1 has changed shape and the fix needs revisiting rather
    than assuming."""
    declaring = {
        skill for skill, fields in blueprint_skills.items()
        if "engagement_profile" in fields.get("inputs", ())
    }
    assert declaring == set(DECLARERS)


def test_a_profile_round_trips(contracts: ContractRegistry, profile: dict[str, Any]) -> None:
    assert contracts.check(PROFILE, profile) == ()
    round_tripped = json.loads(json.dumps(profile))
    assert round_tripped == profile
    assert contracts.check(PROFILE, round_tripped) == ()


def test_a_profile_without_an_owner_compensation_baseline_fails(
    contracts: ContractRegistry, profile: dict[str, Any]
) -> None:
    """EBITDA Normalization escalates when there is no benchmark. A profile that omits
    it silently is exactly how that escalation gets skipped."""
    without = {k: v for k, v in profile.items() if k != "owner_compensation_baseline"}
    with pytest.raises(ContractViolation):
        contracts.validate(PROFILE, without)


@pytest.mark.parametrize("field", ["amount", "currency", "basis", "source", "as_of"])
def test_a_baseline_without_its_basis_is_not_a_baseline(
    contracts: ContractRegistry, profile: dict[str, Any], field: str
) -> None:
    """An amount with no source and no date is a number somebody remembered."""
    baseline = {k: v for k, v in profile["owner_compensation_baseline"].items() if k != field}
    assert contracts.check(PROFILE, {**profile, "owner_compensation_baseline": baseline})


@pytest.mark.parametrize(
    "field",
    ["industry_classification", "size_band", "fiscal_calendar", "scale_convention", "disposition"],
)
def test_every_declared_element_of_the_engagement_record_is_required(
    contracts: ContractRegistry, profile: dict[str, Any], field: str
) -> None:
    without = {k: v for k, v in profile.items() if k != field}
    assert contracts.check(PROFILE, without)


def test_scale_convention_is_a_convention_not_a_default(contracts: ContractRegistry) -> None:
    """It says how this engagement's working papers are kept. It is never the value a
    figure gets when nobody read one - see the figure envelope, where scale is required
    and undefaulted."""
    schema = contracts.get(PROFILE)["properties"]["scale_convention"]
    assert "default" not in schema
    assert schema["enum"] == [1, 1000, 1000000]


def test_a_profile_cannot_carry_a_conclusion(
    contracts: ContractRegistry, profile: dict[str, Any]
) -> None:
    assert contracts.check(PROFILE, {**profile, "indicated_value": 12_000_000})


# ------------------------------------------------------------------ census


def test_a_census_validates_and_is_masked(contracts: ContractRegistry) -> None:
    census = {
        "document_type": "participant_census",
        "source_id": SHA,
        "as_of": "2025-12-31",
        "plan_year": 2025,
        "masked": True,
        "headcount": 2,
        "participants": [
            {
                "participant_token": "PERSON_7f31",
                "status": "active",
                "age_band": "45-49",
                "service_years": 12.5,
                "vested_percent": 100,
                "account_balance": {
                    "value": 84200.0,
                    "unit": "currency",
                    "currency": "USD",
                    "scale": 1,
                    "period": {"type": "POINT", "end": "2025-12-31"},
                    "source_id": SHA,
                    "locator": "census!D14",
                    "source_version": 1,
                    "derivation": None,
                    "masked": True,
                    "confidence": 1.0,
                    "produced_by": "intake-reader@0.1.0",
                    "model_pin": "none - deterministic reader",
                },
            }
        ],
        "coverage_gaps": ["No vesting schedule supplied for terminated participants."],
    }
    assert contracts.check(CENSUS, census) == ()

    unmasked = {**census, "masked": False}
    assert contracts.check(CENSUS, unmasked), "masked=false must not be expressible"

    named = json.loads(json.dumps(census))
    named["participants"][0]["participant_token"] = "Jane Henderson"
    assert contracts.check(CENSUS, named), "a name must not pass as a token"
