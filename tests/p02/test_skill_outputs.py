"""One output schema per skill, referencing the envelope rather than restating it.

Also the structural half of "nothing concludes, signs or certifies": a schema with no
field a concluded value could be recorded in is a stronger guarantee than an instruction
in a prompt, because a later skill version cannot forget it.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from registries.contracts import ContractRegistry
from tests.p02.conftest import walk_schemas

ENVELOPE_REF = "https://chartwell.invalid/contracts/figure@1.0.0"

# Words that would make this system look as though it had reached a conclusion, signed
# something, or certified something. The appraiser signs, outside this system.
FORBIDDEN_FIELD_WORDS = (
    "conclusion",
    "concluded",
    "opinion",
    "certif",
    "signature",
    "signed_by",
    "attest",
    "approval",
    "approved",
    "fair_market_value",
    "final_value",
    "determination",
    "we_conclude",
    "is_adequate",
    "adequacy_",
)
# Never, in any enum: the system does not conclude, certify or sign.
FORBIDDEN_ENUM_VALUES = ("certified", "signed", "concluded", "adequate", "opinion")
# And a field that reports a state may not report approval either. "prior_year_approved"
# as the *basis* of a configured baseline is a record of what a person did last year;
# "approved" as a readiness or a result would be this system doing it.
STATE_FIELDS = frozenset({"status", "result", "readiness", "outcome", "decision", "verdict"})


def skill_keys(contracts: ContractRegistry) -> list[str]:
    """The skill *output* contracts. A proposal contract (P18 onwards) sits under the same
    prefix but is what the model returns, not what the skill emits - it declares no
    outputs and carries no figure, by design."""
    return [k for k in contracts.ids() if k.startswith("skills/") and "-proposal@" not in k]


def test_there_is_one_schema_per_blueprint_skill(
    contracts: ContractRegistry, blueprint_skills: dict[str, dict[str, tuple[str, ...]]]
) -> None:
    registered = {contracts.get(k)["x-skill"] for k in skill_keys(contracts)}
    assert registered == set(blueprint_skills)


def test_each_schema_requires_exactly_the_outputs_the_blueprint_declares(
    contracts: ContractRegistry, blueprint_skills: dict[str, dict[str, tuple[str, ...]]]
) -> None:
    """A skill declaring outputs the contract does not carry is a finding, not a
    preference - it means the frontmatter and the validator disagree about what the
    skill produces, and the validator is what actually runs."""
    for key in skill_keys(contracts):
        schema = contracts.get(key)
        skill = schema["x-skill"]
        declared = set(blueprint_skills[skill]["outputs"])
        required = set(schema["required"]) - {"schema_version", "produced_by"}
        assert required == declared, f"{skill}: contract says {required}, blueprint says {declared}"


def test_a_schema_references_the_envelope_exactly_when_it_emits_figures(
    contracts: ContractRegistry,
) -> None:
    """x-emits-figures is what the plan assertion in P07 reads when it checks that no
    generative step downstream of verification can originate a figure. It has to mean
    something, so it is checked against the schema's actual contents."""
    for key in skill_keys(contracts):
        schema = contracts.get(key)
        refs_envelope = ENVELOPE_REF in json.dumps(schema)
        assert schema["x-emits-figures"] is refs_envelope, (
            f"{key} claims emits_figures={schema['x-emits-figures']} but "
            f"{'does not reference' if refs_envelope is False else 'references'} the envelope"
        )


def test_no_schema_restates_the_envelope(contracts: ContractRegistry) -> None:
    """Defined once centrally, or it drifts per skill. A subschema carrying the
    envelope's own field names is a copy somebody made rather than a reference."""
    envelope_fields = {"value", "unit", "scale", "source_id", "locator", "source_version"}
    for key in skill_keys(contracts):
        for subschema in walk_schemas(contracts.get(key)):
            properties = subschema.get("properties")
            if isinstance(properties, dict):
                overlap = envelope_fields & set(properties)
                assert len(overlap) < 4, f"{key} restates the envelope: {sorted(overlap)}"


@pytest.mark.parametrize("word", FORBIDDEN_FIELD_WORDS)
def test_no_schema_has_a_field_a_conclusion_could_be_recorded_in(
    contracts: ContractRegistry, word: str
) -> None:
    for key in contracts.ids():
        for subschema in walk_schemas(contracts.get(key)):
            properties = subschema.get("properties")
            if isinstance(properties, dict):
                offenders = [p for p in properties if word in p.lower()]
                assert not offenders, f"{key} has {offenders}"


def test_no_enum_anywhere_concludes_or_certifies(contracts: ContractRegistry) -> None:
    for key in contracts.ids():
        for subschema in walk_schemas(contracts.get(key)):
            for value in subschema.get("enum", ()) or ():
                if isinstance(value, str):
                    lowered = value.lower()
                    for banned in FORBIDDEN_ENUM_VALUES:
                        assert banned not in lowered, f"{key} enum offers {value!r}"


def test_no_field_reporting_a_state_can_report_approval(contracts: ContractRegistry) -> None:
    """Approval is a person's act. A field that could record one here would make the
    system look as though it had performed it."""
    for key in contracts.ids():
        for subschema in walk_schemas(contracts.get(key)):
            properties = subschema.get("properties")
            if not isinstance(properties, dict):
                continue
            for name, spec in properties.items():
                if name.lower() not in STATE_FIELDS or not isinstance(spec, dict):
                    continue
                for value in spec.get("enum", ()) or ():
                    assert "approv" not in str(value).lower(), f"{key}.{name} offers {value!r}"


# ------------------------------------------------------ the specific promises


def test_qc_cannot_approve_anything(contracts: ContractRegistry) -> None:
    """The readiness field's permitted values, in full."""
    readiness = contracts.get("skills/qc-tieout@1.0.0")["properties"]["readiness"]
    assert set(readiness["enum"]) == {"items_outstanding", "no_automated_issues_found"}


def test_a_dcf_cannot_emit_a_point_value(contracts: ContractRegistry) -> None:
    """A single number would read as a conclusion. The schema requires two."""
    schema = contracts.get("skills/dcf-build@1.0.0")["properties"]["indicated_range"]
    assert schema["minItems"] == 2
    assert schema["maxItems"] == 2


def test_the_company_specific_premium_always_goes_to_review(
    contracts: ContractRegistry,
) -> None:
    """Not a threshold and not a confidence test - the field cannot hold false."""
    coc = contracts.get("skills/cost-of-capital@1.0.0")
    adjustment = coc["properties"]["cost_of_capital"]["properties"]["company_specific_adjustment"]
    assert adjustment["properties"]["review_required"] == {"const": True} | {
        "description": adjustment["properties"]["review_required"]["description"]
    }
    assert "review_required" in adjustment["required"]


def test_a_changed_prior_year_treatment_always_goes_to_review(
    contracts: ContractRegistry,
) -> None:
    report = contracts.get("skills/prior-year-rollforward@1.0.0")
    changed = report["properties"]["rollforward_report"]["properties"]["changed"]
    assert changed["items"]["properties"]["review_required"]["const"] is True


def test_a_binding_first_year_decision_always_goes_to_review(
    contracts: ContractRegistry,
) -> None:
    baseline = contracts.get("skills/first-year-baseline@1.0.0")
    decisions = baseline["properties"]["baseline_record"]["properties"]["binding_decisions"]
    assert decisions["items"]["properties"]["review_required"]["const"] is True


def test_the_adequate_consideration_record_cannot_state_adequacy(
    contracts: ContractRegistry,
) -> None:
    """It records what was done and what is unresolved. There is no field for the
    conclusion, because a field is an invitation."""
    record = contracts.get("skills/dol-adequate-consideration@1.0.0")
    fields = set(record["properties"]["adequate_consideration_record"]["properties"])
    assert fields == {
        "inputs_relied_on",
        "process_steps",
        "unresolved_items",
        "assumptions_requiring_confirmation",
        "independence_checklist",
        "related_party_indications",
    }
    assert record["x-emits-figures"] is False


BINDINGS = "skills/model-load@1.0.0"
NAMED_RANGE_CASES: list[tuple[str, bool]] = [
    ("Revenue_FY23", True),
    ("tbl_Historicals.EBITDA", True),
    ("_input_wacc", True),
    ("B44", False),
    ("AA7", False),
    ("b44", False),
    ("", False),
]


@pytest.mark.parametrize(("candidate", "valid"), NAMED_RANGE_CASES)
def test_a_template_binding_is_a_named_range_not_a_cell_address(
    contracts: ContractRegistry, candidate: str, valid: bool
) -> None:
    """B44 is not a contract. One inserted row shifts every mapping below it, and the
    deliverable is then plausibly wrong - which no reviewer catches by eye."""
    schema = contracts.get(BINDINGS)["properties"]["template_mapping"]
    pattern = schema["properties"]["bindings"]["items"]["properties"]["named_range"]["pattern"]
    assert bool(re.search(pattern, candidate)) is valid


def test_model_load_originates_nothing(contracts: ContractRegistry) -> None:
    """It routes validated figures to named ranges. The Template Writer does every write."""
    schema = contracts.get(BINDINGS)
    assert schema["x-emits-figures"] is False
    mapping = schema["properties"]["template_mapping"]["properties"]
    assert "unmapped_template_inputs" in mapping
    assert "unrouted_upstream_figures" in mapping


def test_every_skill_output_validates_a_worked_instance(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    """One end-to-end instance, so the schemas are known to be satisfiable at all.

    A schema nothing has ever validated against is a schema with an unnoticed
    contradiction in it.
    """
    instance = {
        "schema_version": "skills/ebitda-normalization@1.0.0",
        "produced_by": "ebitda-normalization@0.1.0",
        "addback_schedule": [
            {
                "candidate_id": "ADD-001",
                "line_item_ref": "IS/opex/officer_comp",
                "category": "owner_related",
                "amount": figure,
                "rationale": "Officer compensation above the survey median for the size band.",
                "evidence": [
                    {
                        "source_id": figure["source_id"],
                        "locator": "TB_FY23!B44:B51",
                        "excerpt": "Officer compensation 486,200",
                    }
                ],
                "recomputed": True,
                "above_materiality": True,
                "review_required": True,
                "officer_comp_benchmark": {
                    "basis": "survey_median",
                    "source": "RCReports 2024",
                    "as_of": "2024-06-30",
                },
                "recurs_in_all_periods": False,
            }
        ],
    }
    assert contracts.check("skills/ebitda-normalization@1.0.0", instance) == ()


def test_a_skill_output_carrying_a_fabricated_figure_is_rejected(
    contracts: ContractRegistry, figure: dict[str, Any]
) -> None:
    """The envelope's guarantees reach through the $ref. That is the point of the $ref."""
    instance = {
        "schema_version": "skills/repurchase-obligation@1.0.0",
        "produced_by": "repurchase-obligation@0.1.0",
        "repurchase_schedule": {
            "census_source_id": figure["source_id"],
            "projections": [
                {
                    "plan_year": 2026,
                    "participants_distributing": 12,
                    "distribution_amount": {**figure, "source_id": "derived"},
                }
            ],
            "range_sensitivity": {"basis": "stated separately", "effect": [figure]},
        },
    }
    codes = {d.code for d in contracts.check("skills/repurchase-obligation@1.0.0", instance)}
    assert "SKILL.FABRICATED_SOURCE" in codes
