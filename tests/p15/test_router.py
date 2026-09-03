"""The Confidence Router: auto-accept, review or block - and it can only add review."""

from __future__ import annotations

import itertools

import pytest

from ops.run_store import SqlRunStore
from registries.constraints import ConstraintRegistry
from registries.scopes import ScopeRegistry
from review import CheckpointPolicy, ConfidenceRouter, Money, Route
from tests.p15.conftest import (
    DECLARED,
    EBITDA,
    ENGAGEMENT,
    OWNER,
    QC,
    TAGGING,
    events_of,
    item,
    profile,
)

STRICTNESS = {Route.AUTO_ACCEPT: 0, Route.REVIEW: 1, Route.BLOCK: 2}


def test_a_material_item_is_queued_regardless_of_confidence(
    router: ConfidenceRouter, started: str, store: SqlRunStore
) -> None:
    """The exit criterion. Confidence 0.99 does not matter at 50,000 against a 20,000
    threshold."""
    routing = router.route(
        item("ab_1", EBITDA, confidence=0.99, amount=Money(50000, "USD")),
        DECLARED[EBITDA],
        run_id=started,
        engagement_id=ENGAGEMENT,
    )
    assert routing.route is Route.REVIEW
    assert routing.reasons[0].startswith("material: 50,000 USD")
    assert routing.severity == "high"
    routed = events_of(store, started, "hitl.item.routed")
    assert len(routed) == 1 and routed[0].payload["route"] == "review"


def test_a_confident_immaterial_item_is_auto_accepted_and_recorded(
    router: ConfidenceRouter, started: str, store: SqlRunStore
) -> None:
    """Auto-accept is not silence: the record is what the Sampling Audit draws from."""
    routing = router.route(
        item(confidence=0.93, amount=Money(14200, "USD")),
        DECLARED[TAGGING],
        run_id=started,
        engagement_id=ENGAGEMENT,
    )
    assert routing.route is Route.AUTO_ACCEPT and routing.reasons == ()
    accepted = events_of(store, started, "hitl.item.auto_accepted")
    assert len(accepted) == 1 and accepted[0].payload["confidence"] == 0.93


def test_below_the_bar_goes_to_a_person(router: ConfidenceRouter) -> None:
    routing = router.route(item(confidence=0.61), DECLARED[TAGGING])
    assert routing.route is Route.REVIEW
    assert "below the bar of 0.85" in routing.reasons[0]


def test_no_confidence_goes_to_a_person(router: ConfidenceRouter) -> None:
    routing = router.route(item(confidence=None), DECLARED[TAGGING])
    assert routing.route is Route.REVIEW and "no confidence" in routing.reasons[0]


def test_no_bar_means_nothing_is_auto_accepted(
    constraints: ConstraintRegistry, scopes: ScopeRegistry
) -> None:
    policy = CheckpointPolicy.from_profile(
        profile(checkpoint_policy={"owner": OWNER, "sla_hours": 48}), constraints
    )
    routing = ConfidenceRouter(policy, scopes).route(item(confidence=0.99), DECLARED[TAGGING])
    assert routing.route is Route.REVIEW
    assert "no auto-accept bar" in routing.reasons[0]


def test_the_skills_own_review_required_is_never_lowered(router: ConfidenceRouter) -> None:
    routing = router.route(item(confidence=0.99, review_required=True), DECLARED[TAGGING])
    assert routing.route is Route.REVIEW
    assert "review_required" in routing.reasons[0]


@pytest.mark.parametrize(
    ("field", "phrase"),
    [
        ("category", "always reviewed"),
        ("changed_from_prior", "prior year"),
        ("binds_future_years", "future years"),
    ],
)
def test_the_constraint_registrys_forced_reviews(
    router: ConfidenceRouter, field: str, phrase: str
) -> None:
    value = "owner_related" if field == "category" else True
    routing = router.route(item(confidence=0.99, **{field: value}), DECLARED[TAGGING])
    assert routing.route is Route.REVIEW
    assert any(phrase in r for r in routing.reasons)


def test_a_skill_whose_whole_output_goes_to_a_person_blocks(router: ConfidenceRouter) -> None:
    """qc-tieout declares always_surfaces_to_reviewer: nothing downstream builds on an
    unseen result, so the run stops at that step."""
    routing = router.route(item("qc_1", QC, confidence=0.99), DECLARED[QC])
    assert routing.route is Route.BLOCK
    assert routing.effective_review == "always_surfaces_to_reviewer"


def test_a_policy_can_raise_a_skill_to_blocking(
    constraints: ConstraintRegistry, scopes: ScopeRegistry
) -> None:
    policy = CheckpointPolicy.from_profile(
        profile(
            checkpoint_policy={
                "owner": OWNER,
                "sla_hours": 48,
                "auto_accept_confidence": 0.85,
                "review_floors": {EBITDA: "all_addbacks_require_review"},
            }
        ),
        constraints,
    )
    routing = ConfidenceRouter(policy, scopes).route(
        item("ab_1", EBITDA, confidence=0.99, amount=Money(100, "USD")), DECLARED[EBITDA]
    )
    assert routing.route is Route.BLOCK


def test_a_policy_asking_for_less_changes_nothing(
    constraints: ConstraintRegistry, scopes: ScopeRegistry
) -> None:
    """Even a policy that got past validation cannot lower the effective level: the
    router takes the tighter of the two, always."""
    policy = CheckpointPolicy(
        ENGAGEMENT,
        OWNER,
        48,
        Money(20000, "USD"),
        auto_accept_confidence=0.85,
        review_floors={QC: "none"},
    )
    routing = ConfidenceRouter(policy, scopes).route(
        item("qc_1", QC, confidence=0.99), DECLARED[QC]
    )
    assert routing.route is Route.BLOCK


def test_a_foreign_currency_amount_is_treated_as_material(router: ConfidenceRouter) -> None:
    routing = router.route(item(confidence=0.99, amount=Money(1, "EUR")), DECLARED[TAGGING])
    assert routing.route is Route.REVIEW


def test_the_router_can_add_review_and_never_remove_it(
    constraints: ConstraintRegistry, scopes: ScopeRegistry
) -> None:
    """A tighter policy routes every item at least as strictly as a looser one, over a
    grid of items."""
    loose = CheckpointPolicy(ENGAGEMENT, OWNER, 48, Money(25000, "USD"), auto_accept_confidence=0.6)
    tight = CheckpointPolicy(
        ENGAGEMENT,
        OWNER,
        48,
        Money(5000, "USD"),
        auto_accept_confidence=0.95,
        always_review_categories=frozenset({"owner_related"}),
        review_floors={TAGGING: "material_addbacks_require_review"},
    )
    a, b = ConfidenceRouter(loose, scopes), ConfidenceRouter(tight, scopes)
    grid = itertools.product(
        [None, 0.5, 0.7, 0.9, 0.99],
        [None, Money(1000, "USD"), Money(10000, "USD"), Money(30000, "USD")],
        [None, "owner_related", "rent"],
        [False, True],
    )
    for confidence, amount, category, required in grid:
        it = item(confidence=confidence, amount=amount, category=category, review_required=required)
        assert (
            STRICTNESS[b.route(it, DECLARED[TAGGING]).route]
            >= STRICTNESS[a.route(it, DECLARED[TAGGING]).route]
        )


def test_the_router_never_reads_the_excerpt() -> None:
    """The excerpt is for the person. Routing is on confidence, materiality and the
    declarations - never on what the text says."""
    from pathlib import Path

    from tests.p15.conftest import ROOT

    text = (Path(ROOT) / "review" / "router.py").read_text(encoding="utf-8")
    assert (
        "item.source_excerpt" not in text
        and "source_excerpt" not in text.split("class ConfidenceRouter")[1]
    )
