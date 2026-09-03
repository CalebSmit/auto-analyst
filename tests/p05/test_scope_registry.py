"""The Scope Registry: the declared taxonomy, and the two ladders.

The registry exists so that an engagement scoped to a practice group nobody declared
fails at the start of a run rather than resolving to an empty skill set that looks like
a considered answer. Most of these tests are about that refusal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from registries.errors import RegistryError
from registries.scopes import ScopePath, ScopeRegistry


def test_the_taxonomy_is_the_blueprints(scopes: ScopeRegistry) -> None:
    assert [p.id for p in scopes.practices] == ["valuation", "consulting", "corporate-finance"]
    assert [s.id for s in scopes.practice("valuation").segments] == ["esop", "non-esop"]
    assert [d.id for d in scopes.dispositions] == ["repeat", "non-repeat"]


def test_a_scaffolded_practice_says_it_is_scaffolded(scopes: ScopeRegistry) -> None:
    """`defined: false` is a fact about the firm, not about the file. Consulting exists
    and has named no segments; that is different from Consulting not existing."""
    assert scopes.practice("valuation").defined
    assert not scopes.practice("consulting").defined
    assert not scopes.practice("consulting").segments[0].defined
    assert scopes.practice("consulting").note


def test_the_layer_order_matches_the_blueprint(
    scopes: ScopeRegistry, blueprint_layer_order: tuple[str, ...]
) -> None:
    """Declared as data in both places, so this is a real comparison rather than a
    restatement. A five-layer walk written twice is one that will disagree with itself.
    """
    assert scopes.layer_order == blueprint_layer_order


def test_the_layers_expand_in_order(scopes: ScopeRegistry) -> None:
    assert scopes.layers_for(ScopePath("valuation", "esop", "repeat")) == (
        "_firm",
        "valuation/_group",
        "valuation/_repeat",
        "valuation/esop/_segment",
        "valuation/esop/repeat",
    )


def test_there_are_five_layers_and_the_first_is_the_firm(scopes: ScopeRegistry) -> None:
    assert len(scopes.layer_order) == 5
    assert scopes.layer_order[0] == "_firm"


# ------------------------------------------------------------- the refusals


def test_an_undeclared_practice_group_is_refused(scopes: ScopeRegistry) -> None:
    with pytest.raises(RegistryError) as raised:
        scopes.validate(ScopePath("tax", "esop", "repeat"))
    assert raised.value.diagnostic.code == "SCOPE.UNKNOWN_PRACTICE"
    assert "two-line change" in raised.value.diagnostic.what_now


def test_a_segment_of_another_practice_is_refused(scopes: ScopeRegistry) -> None:
    """Segments are per practice. `valuation/tbd` would otherwise resolve to a layer
    nothing is declared at, which reads as "no skills apply" rather than "wrong scope"."""
    with pytest.raises(RegistryError) as raised:
        scopes.validate(ScopePath("valuation", "tbd", "repeat"))
    assert raised.value.diagnostic.code == "SCOPE.UNKNOWN_SEGMENT"


def test_an_undeclared_disposition_is_refused(scopes: ScopeRegistry) -> None:
    with pytest.raises(RegistryError) as raised:
        scopes.validate(ScopePath("valuation", "esop", "prospect"))
    assert raised.value.diagnostic.code == "SCOPE.UNKNOWN_DISPOSITION"


@pytest.mark.parametrize("path", ["valuation/esop", "valuation//repeat", "", "a/b/c/d"])
def test_a_malformed_scope_path_is_refused(path: str) -> None:
    with pytest.raises(RegistryError) as raised:
        ScopePath.parse(path)
    assert raised.value.diagnostic.code == "SCOPE.UNRESOLVED"


def test_a_scope_path_round_trips() -> None:
    assert str(ScopePath.parse("valuation/esop/repeat")) == "valuation/esop/repeat"


# ---------------------------------------------------------------- the ladders


def test_every_review_value_the_tree_uses_is_ranked(scopes: ScopeRegistry, tree: object) -> None:
    """An unranked review level cannot be compared, and an overlay that cannot be
    compared cannot be refused. So every value in use has to be placed deliberately."""
    for skill in tree.all():  # type: ignore[attr-defined]
        assert scopes.review_rank(skill.hitl) >= 0
        assert scopes.sensitivity_rank(skill.data_sensitivity) >= 0


def test_the_ladders_actually_rank(scopes: ScopeRegistry) -> None:
    assert scopes.review_rank("always_surfaces_to_reviewer") > scopes.review_rank(
        "all_addbacks_require_review"
    ) > scopes.review_rank("material_addbacks_require_review") > scopes.review_rank(
        "low_confidence_fields_require_review"
    ) > scopes.review_rank("none")
    assert scopes.sensitivity_rank("masked_only") > scopes.sensitivity_rank("unmasked_ok")


def test_an_unranked_review_value_is_refused_rather_than_guessed(scopes: ScopeRegistry) -> None:
    with pytest.raises(RegistryError) as raised:
        scopes.review_rank("looks_important_require_review")
    assert raised.value.diagnostic.code == "SCOPE.UNKNOWN_REVIEW_LEVEL"
    assert "deliberately" in str(raised.value)


def test_the_declared_sensitivity_values_are_the_blueprints(scopes: ScopeRegistry) -> None:
    """The blueprint types it as Literal["masked_only", "unmasked_ok"]."""
    assert set(scopes.sensitivity_ranks) == {"masked_only", "unmasked_ok"}


def test_a_ladder_with_one_rung_is_refused_at_load(tmp_path: Path) -> None:
    """A ladder that cannot rank anything passes every tighten-only check that ever
    runs, which is worse than no check at all: it reads as enforcement."""
    broken = tmp_path / "scopes.yaml"
    broken.write_text(
        "version: 1.0.0\n"
        "layer_order: ['_firm', '{practice}/_group', '{practice}/{segment}/{disposition}']\n"
        "practices: [{id: valuation, name: Valuation, defined: true,"
        " segments: [{id: esop, name: ESOP}]}]\n"
        "dispositions: [{id: repeat, name: Repeat, precedent_scope: client_first}]\n"
        "review_ladder: [{value: none, rank: 0}]\n"
        "sensitivity_ladder: [{value: masked_only, rank: 10}]\n",
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="tighten"):
        ScopeRegistry.load(broken)


def test_a_layer_order_that_does_not_start_at_the_firm_is_refused(tmp_path: Path) -> None:
    """The firm layer is the floor. Starting deeper would mean a run could be scoped out
    of the standards every skill is meant to inherit."""
    broken = tmp_path / "scopes.yaml"
    broken.write_text(
        "version: 1.0.0\n"
        "layer_order: ['{practice}/_group', '{practice}/{segment}/{disposition}']\n"
        "practices: [{id: valuation, name: Valuation, defined: true,"
        " segments: [{id: esop, name: ESOP}]}]\n"
        "dispositions: [{id: repeat, name: Repeat, precedent_scope: client_first}]\n"
        "review_ladder: [{value: none, rank: 0}, {value: a, rank: 1}]\n"
        "sensitivity_ladder: [{value: unmasked_ok, rank: 0}, {value: masked_only, rank: 10}]\n",
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="_firm"):
        ScopeRegistry.load(broken)
