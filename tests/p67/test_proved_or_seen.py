"""P67: proved by arithmetic, or seen.

`BUILD/OPEN.md` §2 has carried "set the auto-accept confidence bar" as an undecided
question belonging to a person since the start of this build. The fourth interview session
answered it, and answered it in a different shape than the build had assumed.

The analyst needs the data 100% accurate, and would otherwise re-check every figure against
the client's documents - which is the whole saving gone. Asked what would let him skip that:
a figure that carries the page and row it was read from, whose totals all re-add and whose
statements tie. *"Yes that would be enough."* And for figures no arithmetic covers: show
**every one**, not only those that changed since last year.

That is a rule about evidence, not about a score, and it is the right instrument for what is
coming. Most of what arrives is scanned PDF that has to be OCR'd, and the failure that matters
there is a misread the model is confident about. A probability cannot catch that. A total that
stops adding up can.

The load-bearing pair is `test_a_covered_figure_is_accepted_with_no_confidence_at_all` and
`test_materiality_still_sends_a_fully_covered_figure_to_a_person`. The first alone is satisfied
by ignoring every rule; the second alone by routing everything to review.
"""

from __future__ import annotations

import pytest

from registries.constraints import ConstraintRegistry
from registries.scopes import ScopeRegistry
from review import CheckpointPolicy, ConfidenceRouter, Item, Money
from review.router import Route
from tests.p15.conftest import TAGGING, profile

DECLARED = "low_confidence_fields_require_review"
COVER = ("total_operating_expenses re-added from 7 rows",)
LOCATOR = "p14/t2/r7"


@pytest.fixture
def router(constraints: ConstraintRegistry) -> ConfidenceRouter:
    policy = CheckpointPolicy.from_profile(profile(), constraints)
    return ConfidenceRouter(policy, ScopeRegistry.load())


def figure(**over: object) -> Item:
    """An extracted figure with the evidence the analyst named, unless a test removes it."""
    body: dict[str, object] = {
        "item_id": "is_opex_2025",
        "skill": f"{TAGGING}@0.1.0",
        "question": "Operating expenses, FY2025",
        "source_excerpt": "Total operating expenses ... 1,284",
        "proposal": {"value": 1284},
        "extracted": True,
        "locator": LOCATOR,
        "arithmetic_cover": COVER,
    }
    body.update(over)
    return Item(**body)  # type: ignore[arg-type]


def route(router: ConfidenceRouter, item: Item) -> tuple[Route, tuple[str, ...]]:
    routing = router.route(item, DECLARED)
    return routing.route, routing.reasons


# ------------------------------------------------------- evidence is enough, and is required


def test_a_covered_figure_is_accepted_with_no_confidence_at_all(router: ConfidenceRouter) -> None:
    """The point of the rule. `confidence` is None, which previously routed to review on
    its own - and for a figure read off a page a score was never the evidence anyway."""
    got, reasons = route(router, figure(confidence=None))
    assert got is Route.AUTO_ACCEPT, reasons


def test_a_covered_figure_is_accepted_even_below_the_confidence_bar(
    router: ConfidenceRouter,
) -> None:
    """The engagement's bar is 0.85. Evidence outranks it: a footed total is a fact, and a
    confident misread is exactly what the score cannot see."""
    got, reasons = route(router, figure(confidence=0.2))
    assert got is Route.AUTO_ACCEPT, reasons


def test_a_figure_with_no_locator_is_seen(router: ConfidenceRouter) -> None:
    got, reasons = route(router, figure(locator="", confidence=0.99))
    assert got is Route.REVIEW
    assert any("no source locator" in r for r in reasons), reasons


def test_a_figure_no_arithmetic_covers_is_seen(router: ConfidenceRouter) -> None:
    got, reasons = route(router, figure(arithmetic_cover=(), confidence=0.99))
    assert got is Route.REVIEW
    assert any("no arithmetic covers this figure" in r for r in reasons), reasons


def test_the_reason_names_which_evidence_is_missing(router: ConfidenceRouter) -> None:
    """A reviewer opening the item is told what to do about it. 'Low confidence' was never
    an instruction; 'nothing re-adds this' is."""
    _, both = route(router, figure(locator="", arithmetic_cover=(), confidence=0.99))
    assert any("no source locator" in r for r in both)
    assert any("no arithmetic covers" in r for r in both)


def test_every_uncovered_figure_is_seen_not_only_the_changed_ones(
    router: ConfidenceRouter,
) -> None:
    """Asked directly whether unchanged-since-last-year could be skipped: every one of them.
    That matters most on the repeat path, where almost nothing changes and the temptation to
    skip is strongest."""
    unchanged = figure(arithmetic_cover=(), changed_from_prior=False, confidence=0.99)
    got, _ = route(router, unchanged)
    assert got is Route.REVIEW


# ------------------------------------------------------- and never a way round a raised bar


def test_materiality_still_sends_a_fully_covered_figure_to_a_person(
    router: ConfidenceRouter,
) -> None:
    """Evidence substitutes for the score and for nothing else. The threshold is 20,000."""
    got, reasons = route(router, figure(amount=Money(90000, "USD")))
    assert got is Route.REVIEW
    assert any(r.startswith("material") for r in reasons), reasons


def test_an_always_review_category_still_sends_a_covered_figure_to_a_person(
    router: ConfidenceRouter,
) -> None:
    got, reasons = route(router, figure(category="owner_related"))
    assert got is Route.REVIEW
    assert any("always reviewed" in r for r in reasons), reasons


def test_review_required_still_sends_a_covered_figure_to_a_person(
    router: ConfidenceRouter,
) -> None:
    got, _ = route(router, figure(review_required=True))
    assert got is Route.REVIEW


def test_a_covered_figure_that_changed_from_prior_is_still_seen(
    router: ConfidenceRouter,
) -> None:
    got, reasons = route(router, figure(changed_from_prior=True))
    assert got is Route.REVIEW
    assert any("prior year" in r for r in reasons)


def test_a_raised_review_level_still_blocks_a_covered_figure(router: ConfidenceRouter) -> None:
    """The whole-output rung. Nothing about evidence may lower a level somebody raised."""
    routing = router.route(figure(), "always_surfaces_to_reviewer")
    assert routing.route is Route.BLOCK


# ------------------------------------------------------- a judgement is routed as before


def test_a_skill_judgement_is_unaffected_by_the_new_rule(router: ConfidenceRouter) -> None:
    """Not every item is a figure read off a page. For something a skill decided, a score is
    a reasonable gate and the old behaviour has to survive untouched."""
    judgement = Item(
        item_id="ebitda_addback_1",
        skill=f"{TAGGING}@0.1.0",
        question="Is the Q3 project cost non-recurring?",
        source_excerpt="Project costs ... 44",
        proposal={"category": "non_recurring"},
        confidence=0.95,
    )
    assert route(router, judgement)[0] is Route.AUTO_ACCEPT

    low = Item(**{**judgement.__dict__, "confidence": 0.10})
    got, reasons = route(router, low)
    assert got is Route.REVIEW
    assert any("below the bar" in r for r in reasons), reasons


def test_a_judgement_with_no_confidence_still_goes_to_review(router: ConfidenceRouter) -> None:
    """The old rule, which the new branch must not have swallowed: no score, no auto-accept.
    Only an *extracted* item is allowed to have no confidence and still pass."""
    judgement = Item(
        item_id="j2",
        skill=f"{TAGGING}@0.1.0",
        question="?",
        source_excerpt="",
        proposal={},
        confidence=None,
    )
    got, reasons = route(router, judgement)
    assert got is Route.REVIEW
    assert any("no confidence stated" in r for r in reasons), reasons


def test_an_extracted_figure_is_not_routed_on_its_score_at_all(router: ConfidenceRouter) -> None:
    """Both directions: a high score does not rescue missing evidence, and a low one does
    not spoil good evidence. Confidence is simply not the instrument here."""
    assert route(router, figure(confidence=0.99, arithmetic_cover=()))[0] is Route.REVIEW
    assert route(router, figure(confidence=0.01))[0] is Route.AUTO_ACCEPT
