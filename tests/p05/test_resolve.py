"""Tier 0: one scope path in, exactly one skill set out.

The exit criterion says "all seven scope combinations". The declared taxonomy actually
admits eight - three practice groups, four segments between them, two dispositions - and
the seven in the blueprint's roster are those eight minus `consulting/tbd/non-repeat`,
which no engagement happens to use. These tests cover the cross product rather than the
roster, because a combination nobody has used yet is exactly the one that will be wrong
the first time somebody scopes an engagement into it.
"""

from __future__ import annotations

import pytest

from graph.resolve import ScopeResolver
from registries.scopes import ScopePath, ScopeRegistry

# The seven the blueprint's roster puts an engagement into. Kept alongside the cross
# product rather than instead of it: these are the ones that are live today.
ROSTER_SCOPES = (
    "valuation/esop/repeat",
    "valuation/esop/non-repeat",
    "valuation/non-esop/repeat",
    "valuation/non-esop/non-repeat",
    "consulting/tbd/repeat",
    "corporate-finance/tbd/repeat",
    "corporate-finance/tbd/non-repeat",
)


def test_the_taxonomy_admits_eight_combinations_and_the_roster_uses_seven(
    scopes: ScopeRegistry,
) -> None:
    combinations = {str(c) for c in scopes.combinations()}
    assert len(combinations) == 8
    assert set(ROSTER_SCOPES) < combinations
    assert combinations - set(ROSTER_SCOPES) == {"consulting/tbd/non-repeat"}


def test_every_combination_resolves_to_exactly_one_skill_set(
    resolver: ScopeResolver, scopes: ScopeRegistry
) -> None:
    """"Exactly one" is two claims: a skill set comes back, and no skill is in it twice.
    A name resolving from two layers at once would make "which procedure ran" a question
    with two answers."""
    for scope in scopes.combinations():
        resolved = resolver.resolve(scope)
        assert resolved.skills, f"{scope} resolved to nothing"
        assert len(set(resolved.names)) == len(resolved.names), f"{scope} has a duplicate"
        assert resolved.scope == scope


@pytest.mark.parametrize("path", ROSTER_SCOPES)
def test_every_roster_scope_resolves(resolver: ScopeResolver, path: str) -> None:
    assert len(resolver.resolve(path)) >= 4


def test_resolution_is_deterministic(resolver: ScopeResolver, scopes: ScopeRegistry) -> None:
    """Resolution is folded into the plan hash. If it were not stable, every plan hash
    over it would be noise."""
    for scope in scopes.combinations():
        first, second = resolver.resolve(scope), resolver.resolve(scope)
        assert first.resolution_hash == second.resolution_hash
        assert first.names == second.names


def test_different_scopes_hash_differently(resolver: ScopeResolver, scopes: ScopeRegistry) -> None:
    hashes = {resolver.resolve(s).resolution_hash for s in scopes.combinations()}
    assert len(hashes) == len(scopes.combinations())


def test_the_esop_repeat_resolution_is_the_one_the_blueprint_shows(
    resolver: ScopeResolver,
) -> None:
    """The blueprint's own run trace: `valuation/esop/repeat -> 12 skills from 5 layers
    · 3 overlays · precedent scope: this client first`."""
    resolved = resolver.resolve("valuation/esop/repeat")
    assert len(resolved) == 12
    assert len(resolved.layers) == 5
    assert len(resolved.overlays) == 3
    assert resolved.precedent_scope == "client_first"


# ---------------------------------------------------------------- shadowing


def test_a_deeper_layer_never_takes_a_firm_skill_away(
    resolver: ScopeResolver, scopes: ScopeRegistry
) -> None:
    """No run loses a firm skill by being specific. That is the whole reason a deeper
    layer adds rather than replaces."""
    firm = set(resolver.resolve("consulting/tbd/repeat").names)
    for scope in scopes.combinations():
        assert firm <= set(resolver.resolve(scope).names), f"{scope} lost a firm skill"


def test_a_shadowed_skill_records_where_it_came_from(synthetic: object) -> None:
    """Recorded rather than discarded: "which version of the procedure ran" should not
    be archaeology."""
    from tests.p05.conftest import skill

    resolver = synthetic(  # type: ignore[operator]
        (skill("qc-tieout", "_firm"), skill("qc-tieout", "valuation/_group")), ()
    )
    resolved = resolver.resolve("valuation/esop/repeat")
    assert len(resolved) == 1
    assert resolved.skill("qc-tieout").layer == "valuation/_group"
    assert resolved.skill("qc-tieout").shadowed == ("_firm",)


def test_the_deepest_declaration_wins(synthetic: object) -> None:
    from tests.p05.conftest import skill

    resolver = synthetic(  # type: ignore[operator]
        (
            skill("a", "_firm", hitl="none"),
            skill("a", "valuation/_group", hitl="assumptions_require_review"),
            skill("a", "valuation/esop/_segment", hitl="always_surfaces_to_reviewer"),
        ),
        (),
    )
    resolved = resolver.resolve("valuation/esop/repeat")
    assert resolved.skill("a").layer == "valuation/esop/_segment"
    assert resolved.skill("a").hitl == "always_surfaces_to_reviewer"


# ------------------------------------------------- consulting, said out loud


def test_consulting_resolves_to_the_firm_layer_only(resolver: ScopeResolver) -> None:
    resolved = resolver.resolve("consulting/tbd/repeat")
    assert resolved.firm_layer_only
    assert {r.layer for r in resolved.skills} == {"_firm"}
    assert not resolved.overlays


def test_the_resolver_says_so_explicitly(resolver: ScopeResolver) -> None:
    """The criterion is not that it happens - it is that the resolver says it. "Nothing
    is declared for Consulting yet" and "resolution went wrong" look identical from a
    count, and they are not the same situation."""
    explanation = "\n".join(resolver.resolve("consulting/tbd/repeat").explain)
    assert "firm layer only" in explanation
    assert "consulting/_group" in explanation
    assert "scaffolded" in explanation


def test_a_practice_with_skills_of_its_own_does_not_claim_to_be_firm_only(
    resolver: ScopeResolver,
) -> None:
    """The other half. A flag that is true for everything says nothing."""
    assert not resolver.resolve("valuation/esop/repeat").firm_layer_only
    assert not resolver.resolve("valuation/non-esop/non-repeat").firm_layer_only


def test_the_explanation_accounts_for_every_layer(
    resolver: ScopeResolver, scopes: ScopeRegistry
) -> None:
    for scope in scopes.combinations():
        resolved = resolver.resolve(scope)
        explanation = "\n".join(resolved.explain)
        for layer in resolved.layers:
            assert layer in explanation, f"{scope}: {layer} is not accounted for"


# ------------------------------------------------------- templates and scope


def test_the_deepest_bound_template_wins(resolver: ScopeResolver) -> None:
    """The same five-layer walk as the skills. One mechanism, two kinds of artifact."""
    esop = resolver.resolve("valuation/esop/repeat")
    assert esop.template is not None
    assert esop.template.file == "Chartwell_ESOP_Model_v9.xlsx"
    assert esop.template.layer == "valuation/esop/_segment"


def test_a_scope_with_no_binding_of_its_own_falls_back_to_the_firm() -> None:
    """The fall-through, asserted on a binding set this test owns.

    It used to name `valuation/non-esop/repeat` as the scope with nothing of its own, and
    P101 bound that segment to the input-help workbook - so a test of the *mechanism*
    started failing because the *configuration* changed under it. Which scopes happen to be
    unbound today is not a property worth pinning, and the firm's bindings will keep
    moving; that a layer with no row of its own inherits the one above it will not.
    """
    from graph.resolve import ScopeResolver as Resolver
    from graph.resolve import TemplateBinding

    bound = Resolver(
        bindings={
            "_firm": TemplateBinding(
                layer="_firm",
                file="Firm_Model.xlsx",
                template_version="1.0",
                why="the default",
            )
        }
    )
    for path in ("valuation/non-esop/repeat", "valuation/esop/repeat", "consulting/tbd/repeat"):
        resolved = bound.resolve(path)
        assert resolved.template is not None, path
        assert resolved.template.file == "Firm_Model.xlsx", path
        assert resolved.template.layer == "_firm", path


def test_a_layer_bound_to_nothing_falls_through_rather_than_binding_nothing(
    resolver: ScopeResolver,
) -> None:
    """Consulting declares a binding row with no file. That is not a binding - it falls
    through to the firm default, which is why the row is shown rather than hidden."""
    consulting = resolver.resolve("consulting/tbd/repeat")
    assert consulting.template is not None
    assert consulting.template.layer == "_firm"


def test_corporate_finance_binds_its_own_model(resolver: ScopeResolver) -> None:
    """"Corporate Finance uses a different model" is a row in a registry rather than a
    branch in the code."""
    cf = resolver.resolve("corporate-finance/tbd/non-repeat")
    assert cf.template is not None
    assert cf.template.file == "CF_LBO_Model_v3.xlsx"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("valuation/esop/repeat", "client_first"),
        ("valuation/esop/non-repeat", "scope_only"),
        ("corporate-finance/tbd/repeat", "client_first"),
    ],
)
def test_the_precedent_scope_comes_from_the_disposition(
    resolver: ScopeResolver, path: str, expected: str
) -> None:
    assert resolver.resolve(path).precedent_scope == expected


# ------------------------------------------------------------- the refusals


def test_an_undeclared_scope_does_not_resolve_to_an_empty_set(resolver: ScopeResolver) -> None:
    """The failure this whole registry exists to prevent: an unknown practice group
    quietly producing zero skills, which reads exactly like "nothing applies"."""
    from registries.errors import RegistryError

    with pytest.raises(RegistryError) as raised:
        resolver.resolve("tax/esop/repeat")
    assert raised.value.diagnostic.code == "SCOPE.UNKNOWN_PRACTICE"


def test_resolve_accepts_a_path_object_as_well_as_a_string(resolver: ScopeResolver) -> None:
    by_string = resolver.resolve("valuation/esop/repeat")
    by_object = resolver.resolve(ScopePath("valuation", "esop", "repeat"))
    assert by_string.resolution_hash == by_object.resolution_hash


def test_asking_for_a_skill_the_scope_did_not_get_is_a_key_error(
    resolver: ScopeResolver,
) -> None:
    with pytest.raises(KeyError):
        resolver.resolve("consulting/tbd/repeat").skill("dcf-build")
