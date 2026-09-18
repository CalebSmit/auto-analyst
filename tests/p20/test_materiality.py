"""Materiality routing: above the threshold goes to a person regardless of confidence,
and the requirement itself is not switchable."""

from __future__ import annotations

from typing import Any

from graph.compile import Step
from graph.resolve import ResolvedScope
from registries.constraints import ConstraintRegistry
from registries.skills import SkillTree
from review import CheckpointPolicy, ConfidenceRouter, Item, Money, Route
from tests.p15.conftest import profile
from tests.p20.conftest import HITL, SKILL, first_pass


def as_item(schedule_item: dict[str, Any], **overrides: Any) -> Item:
    figure = schedule_item["amount"]
    fields: dict[str, Any] = {
        "item_id": schedule_item["candidate_id"],
        "skill": SKILL,
        "question": f"{schedule_item['candidate_id']}: {schedule_item['category']}?",
        "source_excerpt": schedule_item["evidence"][0]["excerpt"],
        "proposal": schedule_item,
        "confidence": figure["confidence"],
        "amount": Money(float(figure["value"]) * int(figure["scale"]), figure["currency"]),
        "category": schedule_item["category"],
        "review_required": schedule_item["review_required"],
    }
    fields.update(overrides)
    return Item(**fields)


def test_every_item_above_the_threshold_is_marked_for_review_by_the_procedure(
    world: dict[str, Any], ebitda_step: Step, scope: ResolvedScope, case: dict[str, Any]
) -> None:
    done = first_pass(world, ebitda_step, scope, case)
    threshold = world["policy"].materiality
    assert threshold.amount == case["expected"]["material_threshold"]
    material = [i for i in done.output["addback_schedule"] if i["above_materiality"]]
    assert material, "the case has material items"
    for item in material:
        # Magnitude on both sides, because that is what materiality means. Comparing the
        # signed amount let a large negative add-back score below the threshold.
        absolute = abs(float(item["amount"]["value"]) * int(item["amount"]["scale"]))
        assert absolute >= threshold.amount
        assert item["review_required"]
    below = [i for i in done.output["addback_schedule"] if not i["above_materiality"]]
    for item in below:
        size = abs(float(item["amount"]["value"]) * int(item["amount"]["scale"]))
        assert size < threshold.amount


def test_a_material_add_back_is_material_whichever_sign_it_carries(
    world: dict[str, Any], ebitda_step: Step, scope: ResolvedScope, case: dict[str, Any]
) -> None:
    """A statement is read as presented, so a material line can arrive negative: an
    interest-income reversal, a credit-balance expense, a contra account. The procedure
    compared the *signed* amount, so -$500,000 scored below a $250,000 threshold and
    materiality - the one trigger that is meant to be sign-blind - stopped firing. With no
    other trigger the item auto-accepted and no person ever saw it.

    Driven through a real dispatch, with one material line's figures negated, because the
    thing that has to hold is what the procedure decides and not what arithmetic does.
    """
    import dataclasses

    before = first_pass(world, ebitda_step, scope, case)
    material = [i for i in before.output["addback_schedule"] if i["above_materiality"]]
    assert material, "the case has a material item to flip"
    ref = material[0]["line_item_ref"]

    # The same run, with that line's figures the other way round.
    inputs = world["inputs"]
    flipped = []
    for line in inputs.lines:
        if line.line_item_ref != ref:
            flipped.append(line)
            continue
        figures = {
            period: {**figure, "value": -float(figure["value"])}
            for period, figure in line.figures.items()
        }
        flipped.append(dataclasses.replace(line, figures=figures))
    world["inputs"] = dataclasses.replace(inputs, lines=tuple(flipped))

    after = first_pass(world, ebitda_step, scope, case)
    negated = [i for i in after.output["addback_schedule"] if i["line_item_ref"] == ref]
    assert negated, "the line is still in the schedule"
    for item in negated:
        assert float(item["amount"]["value"]) < 0, "the figure really is negative now"
        assert item["above_materiality"], (
            "a material line does not stop being material by arriving negative"
        )
        assert item["review_required"], "and a material add-back always reaches a person"


def test_the_router_never_auto_accepts_a_material_add_back_whatever_the_confidence(
    world: dict[str, Any],
    ebitda_step: Step,
    scope: ResolvedScope,
    case: dict[str, Any],
    router: ConfidenceRouter,
) -> None:
    """The exit criterion, from the router's side: hand it every material item with a
    confidence of 0.99 and the review flag cleared, as a skill that wanted to slip one
    through would, and it still goes to a person."""
    done = first_pass(world, ebitda_step, scope, case)
    material = [i for i in done.output["addback_schedule"] if i["above_materiality"]]
    for schedule_item in material:
        routing = router.route(
            as_item(schedule_item, confidence=0.99, review_required=False),
            HITL,
            run_id=world["run_id"],
            engagement_id="HEND-2026-04",
            step_id="ebitda",
        )
        assert routing.route is not Route.AUTO_ACCEPT, schedule_item["candidate_id"]
        assert any("material" in r for r in routing.reasons)


def test_an_immaterial_confident_item_can_auto_accept_until_verification_says_otherwise(
    world: dict[str, Any],
    ebitda_step: Step,
    scope: ResolvedScope,
    case: dict[str, Any],
    router: ConfidenceRouter,
) -> None:
    """The special project: below the threshold, confidence above the bar, no reason to
    review - so the router auto-accepts it. That is what the verification pass is for
    (test_verification.py), and why the sampling audit exists at all."""
    done = first_pass(world, ebitda_step, scope, case)
    project = next(
        i
        for i in done.output["addback_schedule"]
        if i["candidate_id"] == case["expected"]["verifier_disagrees"]
    )
    assert not project["above_materiality"] and not project["review_required"]
    routing = router.route(as_item(project), HITL, run_id=world["run_id"], engagement_id="X")
    assert routing.route is Route.AUTO_ACCEPT


def test_the_threshold_is_the_engagements_and_never_above_the_firm_floor(
    constraints: ConstraintRegistry, policy: CheckpointPolicy
) -> None:
    floor_amount, floor_currency = constraints.materiality_floor()
    assert policy.materiality.amount <= float(floor_amount)
    assert policy.materiality.currency == floor_currency
    assert policy.materiality.amount == profile()["materiality_threshold"]["amount"]


def test_the_requirement_is_declared_by_the_skill_and_listed_by_the_constraints(
    tree: SkillTree, constraints: ConstraintRegistry
) -> None:
    """`hitl: material_addbacks_require_review` in the frontmatter, and the constraint
    registry's forces-review list names the add-back case. Neither is a setting."""
    skill = next(s for s in tree.all() if s.name == "ebitda-normalization")
    assert skill.hitl == HITL
    forced = constraints._raw["materiality"]["forces_review_regardless_of_confidence"]  # noqa: SLF001
    assert any("addback above the engagement materiality threshold" in f for f in forced)
