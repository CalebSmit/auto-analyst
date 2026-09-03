"""An overlay may only tighten.

The exit criterion names two dimensions - a lowered HITL requirement and a widened
privacy class - and both are here. So is a third, adding a tool, because "an overlay
takes powers away" is the same rule and leaving one door open would make the other two
decorative.

Every loosening is built in memory. That is not a shortcut: an overlay that loosens
cannot be committed to `skills/` without breaking the real tree, which is the point.
"""

from __future__ import annotations

import pytest

from graph.resolve import ScopeResolver
from registries.errors import RegistryError
from tests.p05.conftest import overlay, skill

ESOP = "valuation/esop/_segment"
SCOPE = "valuation/esop/repeat"


# ------------------------------------------------- what the real tree declares


def test_the_esop_overlay_raises_the_review_floor(resolver: ScopeResolver) -> None:
    """The blueprint's worked example. ESOP work carries DOL adequate-consideration
    obligations that non-ESOP work does not: the procedure is identical, the standard of
    review is not, and a second copy of the skill would mean the same add-back logic in
    two places."""
    esop = resolver.resolve("valuation/esop/repeat").skill("ebitda-normalization")
    plain = resolver.resolve("valuation/non-esop/repeat").skill("ebitda-normalization")

    assert plain.hitl == "material_addbacks_require_review"
    assert esop.hitl == "all_addbacks_require_review"
    assert esop.skill is plain.skill, "one skill, overlaid - not two copies"


def test_an_overlay_adds_references_without_removing_the_inherited_ones(
    resolver: ScopeResolver,
) -> None:
    esop = resolver.resolve("valuation/esop/repeat").skill("ebitda-normalization")
    assert esop.references[:3] == (
        "addback-taxonomy.md",
        "officer-comp-tests.md",
        "worked-examples.md",
    )
    assert "dol-adequate-consideration.md" in esop.references
    assert "repurchase-obligation.md" in esop.references


def test_an_overlay_can_add_to_what_a_skill_escalates(resolver: ScopeResolver) -> None:
    """The firm QC procedure holds unchanged; ESOP adds items to the checklist rather
    than replacing it."""
    qc = resolver.resolve("valuation/esop/repeat").skill("qc-tieout")
    assert len(qc.escalate_additions) == 1
    assert "repurchase obligation" in qc.escalate_additions[0]


def test_an_overlay_records_itself_on_the_skill_it_changed(resolver: ScopeResolver) -> None:
    resolved = resolver.resolve("valuation/esop/repeat")
    assert resolved.skill("ebitda-normalization").modified
    assert not resolved.skill("dcf-build").modified


def test_an_overlay_out_of_scope_does_nothing(resolver: ScopeResolver) -> None:
    """The ESOP overlays are declared at valuation/esop/_segment. A non-ESOP run never
    walks that layer, so it never sees them - and that is the control, not a filter
    somebody remembered to apply."""
    non_esop = resolver.resolve("valuation/non-esop/repeat")
    assert not any(o.layer == ESOP for o in non_esop.overlays)
    assert not non_esop.skill("ebitda-normalization").modified


def test_an_overlay_whose_target_did_not_resolve_is_simply_inert(synthetic: object) -> None:
    """Declared at a layer in force, targeting a skill this scope does not have. Not an
    error: there is nothing to change."""
    resolver = synthetic(  # type: ignore[operator]
        (skill("present", "_firm"),),
        (
            overlay(ESOP, "present", tightens={"hitl": "always_surfaces_to_reviewer"}),
            overlay(ESOP, "absent", tightens={"hitl": "always_surfaces_to_reviewer"}),
        ),
    )
    resolved = resolver.resolve(SCOPE)
    assert resolved.skill("present").hitl == "always_surfaces_to_reviewer"
    assert len(resolved) == 1


# --------------------------------------------------------------- loosenings


def test_an_overlay_that_lowers_a_review_requirement_raises(synthetic: object) -> None:
    """The exit criterion, first half. A review floor that was quietly lowered is
    indistinguishable from one nobody set."""
    resolver = synthetic(  # type: ignore[operator]
        (skill("a", "_firm", hitl="always_surfaces_to_reviewer"),),
        (overlay(ESOP, "a", tightens={"hitl": "low_confidence_fields_require_review"}),),
    )
    with pytest.raises(RegistryError) as raised:
        resolver.resolve(SCOPE)
    assert raised.value.diagnostic.code == "POLICY.OVERLAY_LOOSENS"
    assert "never lowers one" in str(raised.value)


def test_an_overlay_that_widens_a_privacy_class_raises(synthetic: object) -> None:
    """The exit criterion, second half. masked_only -> unmasked_ok is the widening."""
    resolver = synthetic(  # type: ignore[operator]
        (skill("a", "_firm", sensitivity="masked_only"),),
        (overlay(ESOP, "a", tightens={"data_sensitivity": "unmasked_ok"}),),
    )
    with pytest.raises(RegistryError) as raised:
        resolver.resolve(SCOPE)
    assert raised.value.diagnostic.code == "POLICY.OVERLAY_LOOSENS"
    assert "widens" in str(raised.value)


def test_an_overlay_that_grants_a_tool_raises(synthetic: object) -> None:
    """A skill that needs a new tool needs a review, not a deeper folder."""
    resolver = synthetic(  # type: ignore[operator]
        (skill("a", "_firm", tools=("recompute",)),),
        (overlay(ESOP, "a", tightens={"tools": ["recompute", "precedent_lookup"]}),),
    )
    with pytest.raises(RegistryError) as raised:
        resolver.resolve(SCOPE)
    assert raised.value.diagnostic.code == "POLICY.OVERLAY_LOOSENS"
    assert "precedent_lookup" in str(raised.value)


def test_an_overlay_that_restates_the_current_floor_raises(synthetic: object) -> None:
    """Setting a floor no higher is not raising it. An overlay whose whole content is a
    no-op is a change nobody can justify as a tightening, and it reads as one."""
    resolver = synthetic(  # type: ignore[operator]
        (skill("a", "_firm", hitl="material_addbacks_require_review"),),
        (overlay(ESOP, "a", tightens={"hitl": "material_addbacks_require_review"}),),
    )
    with pytest.raises(RegistryError, match="POLICY.OVERLAY_LOOSENS"):
        resolver.resolve(SCOPE)


def test_an_overlay_naming_an_unranked_review_value_raises(synthetic: object) -> None:
    """Not on the ladder means not comparable, and not comparable means not refusable.
    Better to fail than to let it through because nobody could tell."""
    resolver = synthetic(  # type: ignore[operator]
        (skill("a", "_firm"),),
        (overlay(ESOP, "a", tightens={"hitl": "seems_fine_require_review"}),),
    )
    with pytest.raises(RegistryError) as raised:
        resolver.resolve(SCOPE)
    assert raised.value.diagnostic.code == "SCOPE.UNKNOWN_REVIEW_LEVEL"


# --------------------------------------------------------- the vocabulary


def test_an_overlay_cannot_tighten_a_dimension_nobody_declared(synthetic: object) -> None:
    """An overlay vocabulary that quietly accepts new keys is one that quietly accepts
    new powers."""
    resolver = synthetic(  # type: ignore[operator]
        (skill("a", "_firm"),),
        (overlay(ESOP, "a", tightens={"timeout_s": 30}),),
    )
    with pytest.raises(RegistryError) as raised:
        resolver.resolve(SCOPE)
    assert raised.value.diagnostic.code == "SCOPE.SKILL_INVALID"
    assert "may tighten" in str(raised.value)


def test_an_overlay_cannot_add_something_that_is_not_addable(synthetic: object) -> None:
    resolver = synthetic(  # type: ignore[operator]
        (skill("a", "_firm"),),
        (overlay(ESOP, "a", adds={"tools": ["recompute"]}),),
    )
    with pytest.raises(RegistryError) as raised:
        resolver.resolve(SCOPE)
    assert raised.value.diagnostic.code == "SCOPE.SKILL_INVALID"


def test_an_overlay_cannot_invent_a_precedent_scope(synthetic: object) -> None:
    """Retrieval breadth is declared on a disposition. An overlay that could name its
    own would be a way to widen retrieval from a folder."""
    resolver = synthetic(  # type: ignore[operator]
        (skill("a", "_firm"),),
        (overlay(ESOP, "a", adds={"precedent_scope": "firm_wide"}),),
    )
    with pytest.raises(RegistryError) as raised:
        resolver.resolve(SCOPE)
    assert raised.value.diagnostic.code == "POLICY.OVERLAY_LOOSENS"


# ------------------------------------------------------- what is permitted


def test_an_overlay_may_raise_a_review_floor(synthetic: object) -> None:
    resolver = synthetic(  # type: ignore[operator]
        (skill("a", "_firm", hitl="material_addbacks_require_review"),),
        (overlay(ESOP, "a", tightens={"hitl": "always_surfaces_to_reviewer"}),),
    )
    assert resolver.resolve(SCOPE).skill("a").hitl == "always_surfaces_to_reviewer"


def test_an_overlay_may_narrow_a_privacy_class(synthetic: object) -> None:
    resolver = synthetic(  # type: ignore[operator]
        (skill("a", "_firm", sensitivity="unmasked_ok"),),
        (overlay(ESOP, "a", tightens={"data_sensitivity": "masked_only"}),),
    )
    assert resolver.resolve(SCOPE).skill("a").data_sensitivity == "masked_only"


def test_an_overlay_may_take_a_tool_away(synthetic: object) -> None:
    resolver = synthetic(  # type: ignore[operator]
        (skill("a", "_firm", tools=("recompute", "precedent_lookup")),),
        (overlay(ESOP, "a", tightens={"tools": ["recompute"]}),),
    )
    assert resolver.resolve(SCOPE).skill("a").tools == ("recompute",)


def test_a_tightening_changes_the_resolution_hash(synthetic: object) -> None:
    """Resolution is folded into the plan hash. If an overlay could change what runs
    without changing the hash, the hash would not be recording what ran."""
    skills = (skill("a", "_firm", hitl="material_addbacks_require_review"),)
    plain = synthetic(skills, ())  # type: ignore[operator]
    tightened = synthetic(  # type: ignore[operator]
        skills, (overlay(ESOP, "a", tightens={"hitl": "always_surfaces_to_reviewer"}),)
    )
    assert plain.resolve(SCOPE).resolution_hash != tightened.resolve(SCOPE).resolution_hash
