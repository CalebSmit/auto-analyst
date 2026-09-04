"""The registry itself: it loads, it self-validates, and it refuses.

Exit criterion 1 - every schema loads, self-validates, and carries a version in its id.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from registries.contracts import ContractRegistry
from registries.errors import UNKNOWN_CONTRACT, RegistryError
from tests.p02.conftest import ROOT, walk_schemas

VERSIONED_ID = re.compile(
    r"^https://chartwell[.]invalid/contracts/[a-z_/-]+@[0-9]+[.][0-9]+[.][0-9]+$"
)


def test_every_registered_schema_is_itself_a_valid_schema(contracts: ContractRegistry) -> None:
    # config_document (P16), timing proposal (P18), tagging proposal (P19), the EBITDA
    # proposal and its verification proposal (P20), the model-load proposal and the
    # workpaper narrative (P21)
    assert len(contracts.self_check()) == 25


def test_every_id_carries_a_version(contracts: ContractRegistry) -> None:
    for key in contracts.ids():
        schema_id = contracts.get(key)["$id"]
        assert VERSIONED_ID.match(schema_id), f"{key} has an unversioned or malformed $id"
        assert schema_id.endswith(key), f"{key} and its $id disagree"


def test_an_unpinned_id_is_refused(contracts: ContractRegistry) -> None:
    """'figure' is not a contract. 'figure@1.0.0' is."""
    with pytest.raises(RegistryError) as raised:
        contracts.get("figure")
    assert raised.value.diagnostic.code == UNKNOWN_CONTRACT
    assert raised.value.diagnostic.owner == "config"
    assert raised.value.diagnostic.what_now


def test_an_unknown_version_is_refused_rather_than_approximated(
    contracts: ContractRegistry,
) -> None:
    for key in ("figure@9.9.9", "figure@1.0", "invented@1.0.0", "skills/no-such-skill@1.0.0"):
        with pytest.raises(RegistryError):
            contracts.get(key)


def test_the_index_and_the_disk_agree(contracts: ContractRegistry) -> None:
    """A schema file the index does not list is not a contract - it is a second copy."""
    on_disk = {
        p.relative_to(ROOT / "contracts").as_posix()
        for p in (ROOT / "contracts").rglob("*.schema.json")
    }
    listed = {entry.file for entry in contracts.entries()}
    assert on_disk == listed


def test_an_unlisted_schema_file_fails_the_load(tmp_path: Path) -> None:
    staged = tmp_path / "contracts"
    staged.mkdir()
    for path in (ROOT / "contracts").rglob("*"):
        target = staged / path.relative_to(ROOT / "contracts")
        if path.is_dir():
            target.mkdir(exist_ok=True)
        else:
            target.write_bytes(path.read_bytes())
    (staged / "stowaway.schema.json").write_text(
        json.dumps({"$id": "https://chartwell.invalid/contracts/stowaway@1.0.0"}), encoding="utf-8"
    )
    with pytest.raises(RegistryError) as raised:
        ContractRegistry.load(staged / "registry.yaml")
    assert "not in the index" in raised.value.diagnostic.detail


def test_every_contract_explains_what_it_is(contracts: ContractRegistry) -> None:
    for key in contracts.ids():
        schema = contracts.get(key)
        assert schema["title"], f"{key} has no title"
        assert len(schema["description"]) > 40, f"{key} does not explain itself"


def test_forbidden_fields_are_structural_everywhere(contracts: ContractRegistry) -> None:
    """Every object closes itself.

    "The skill wrote a conclusion into a field that should not exist" is caught by the
    schema or it is not caught at all - the Output Schema Validator has no other way to
    know a field was not meant to be there.
    """
    for key in contracts.ids():
        for subschema in walk_schemas(contracts.get(key)):
            if subschema.get("type") != "object":
                continue
            if subschema.get("x-open-by-design"):
                # An exception has to be declared and give its reason, so that it is a
                # decision somebody made rather than a field somebody forgot to close.
                assert len(subschema["x-open-by-design"]) > 20
                continue
            assert subschema.get("additionalProperties") is False, (
                f"{key} has an open object: {subschema.get('title') or subschema.get('required')}"
            )


def test_participant_census_is_a_declared_intake_document_type(
    contracts: ContractRegistry,
) -> None:
    """The other half of finding F1.

    Repurchase Obligation declared participant_census as an input and nothing produced
    it - because nothing should. It is a client document, and the fix was to declare the
    type rather than to invent a producer for it.
    """
    census = contracts.intake_document_type("participant_census")
    assert census.contract == "participant_census@1.0.0"
    assert "repurchase-obligation" in census.required_by
    assert census.privacy_class == "masked_only"


def test_every_intake_type_with_a_contract_names_a_registered_one(
    contracts: ContractRegistry,
) -> None:
    for doc_type in contracts.intake_document_types():
        if doc_type.contract is not None:
            assert contracts.get(doc_type.contract)
