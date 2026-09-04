"""The chart-of-accounts taxonomy: versioned data, a gated lookup, an honest answer."""

from __future__ import annotations

import json
from typing import Any

import pytest

from harness.policy import PolicyDenied
from registries.errors import RegistryError
from registries.skills import SkillTree
from registries.taxonomy import TAXONOMY_DIR, UNMAPPED, load_taxonomy, taxonomy_versions
from tests.p19.conftest import TAXONOMY, inputs_for, load_fixture


def test_the_taxonomy_is_versioned_on_disk_and_loads_at_exactly_that_version() -> None:
    assert taxonomy_versions() == (TAXONOMY,)
    taxonomy = load_taxonomy(TAXONOMY)
    assert taxonomy.version == TAXONOMY
    assert (TAXONOMY_DIR / f"{TAXONOMY}.yaml").is_file()
    assert len(taxonomy.categories) >= 50


def test_every_category_has_a_statement_a_section_and_both_flags() -> None:
    taxonomy = load_taxonomy(TAXONOMY)
    for c in taxonomy.categories.values():
        assert c.statement in ("IS", "BS", "NA"), c.id
        assert c.section and c.label, c.id
        if c.statement == "IS":
            assert not c.excluded_from_al and not c.include_in_nwc, f"{c.id} has a BS flag"
        if c.include_in_nwc:
            assert not c.excluded_from_al, f"{c.id}: excluded from A/L and in NWC at once"


def test_the_honest_answer_exists_and_carries_no_flags() -> None:
    unmapped = load_taxonomy(TAXONOMY).categories[UNMAPPED]
    assert unmapped.statement == "NA"
    assert not unmapped.excluded_from_al and not unmapped.include_in_nwc
    assert "person" in unmapped.label.lower()
    assert "reviewed" in unmapped.note.lower()


@pytest.mark.parametrize("version", ["coa-taxonomy@9.9.9", "latest", "coa-taxonomy", ""])
def test_there_is_no_latest_only_a_pinned_version(version: str) -> None:
    with pytest.raises(RegistryError) as refused:
        load_taxonomy(version)
    assert refused.value.diagnostic.code == "SCOPE.UNKNOWN_TAXONOMY"
    assert refused.value.diagnostic.owner == "config"


def test_the_lookup_is_a_gated_read_at_the_pinned_version(world: dict[str, Any]) -> None:
    """The run pinned coa-taxonomy@1.0.0. Asking for it works; asking for anything else
    is refused by the gate before the tool runs, which is how a run can say which
    taxonomy it tagged against."""
    tools = world["tools_for"]()
    result = tools["chart_of_accounts_lookup"](
        engagement_id=tools.engagement_id, version=tools.pinned("chart_of_accounts_lookup")
    )
    assert result.value["version"] == TAXONOMY
    assert result.rows == len(load_taxonomy(TAXONOMY).categories)
    assert result.decision.allowed

    with pytest.raises(PolicyDenied) as denied:
        tools["chart_of_accounts_lookup"](
            engagement_id=tools.engagement_id, version="coa-taxonomy@1.1.0"
        )
    assert denied.value.decision.predicate == "pinned_versions_only"


def test_the_lookup_can_answer_for_specific_ids_and_respects_the_cap(
    world: dict[str, Any],
) -> None:
    tools = world["tools_for"]()
    result = tools["chart_of_accounts_lookup"](
        engagement_id=tools.engagement_id, version=TAXONOMY, ids=["cash", "nope", "equity"]
    )
    assert [r["id"] for r in result.value["rows"]] == ["cash", "equity"]
    capped = tools["chart_of_accounts_lookup"](
        engagement_id=tools.engagement_id, version=TAXONOMY, limit=3
    )
    assert capped.rows == 3


def test_the_payload_carries_the_pinned_list_and_the_reference_does_not_restate_it(
    world: dict[str, Any], tree: SkillTree
) -> None:
    """One source of truth for the categories: the data file, at the run's version. The
    reference explains the shape; a copy of the list in prose would drift."""
    items, _, _ = load_fixture()
    payload = json.loads(world["procedure"].payload(inputs_for(items[:5])))
    ids = {c["id"] for c in payload["taxonomy"]["categories"]}
    assert ids == set(load_taxonomy(TAXONOMY).categories)
    assert payload["taxonomy"]["version"] == TAXONOMY
    assert "value" not in json.dumps(payload["items"])

    skill = next(s for s in tree.all() if s.name == "line-item-tagging")
    reference = tree.reference(skill, "firm-taxonomy.md")
    assert "not in this file" in reference
    assert "excluded_from_al: " not in reference
