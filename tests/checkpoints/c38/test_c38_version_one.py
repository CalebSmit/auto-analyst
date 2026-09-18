"""C38 - What version one gathers, and what it refuses to decide.

P67, P68 and P69 come from one interview session that redefined what version 1 is for: it
gathers and organises data into a workbook the analyst types from, and does not run the
model. Three pieces of that, built where the evidence reached and no further.

A checkpoint asks whether they agree with each other and with the rest of the build. What
they have in common is a discipline rather than a feature: each draws a line at what it
will not decide. The router will not accept a figure on a score. The request list will not
let a section stand in for an item. The roll-forward will not say whether a mismatch is the
client's change or the firm's own grouping. If any of those lines moves, the system starts
being confidently wrong in a way no downstream guard recovers - so they are asked together.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from intake.request_list import SECTIONS, Arrived, RequestList, Status
from registries.constraints import ConstraintRegistry
from registries.scopes import ScopeRegistry
from review import CheckpointPolicy, ConfidenceRouter, Item
from review.router import Route
from tests.p15.conftest import TAGGING, profile
from tools.rollforward import WINDOW, YearWindow, carry_line_items, roll_dates, roll_window

ROOT = Path(__file__).resolve().parents[3]
DECLARED = "low_confidence_fields_require_review"


@pytest.fixture
def router(constraints: ConstraintRegistry) -> ConfidenceRouter:
    policy = CheckpointPolicy.from_profile(profile(), constraints)
    return ConfidenceRouter(policy, ScopeRegistry.load())


def figure(item_id: str, value: float, **over: object) -> Item:
    body: dict[str, object] = {
        "item_id": item_id,
        "skill": f"{TAGGING}@0.1.0",
        "question": item_id,
        "source_excerpt": "",
        "proposal": {"value": value},
        "extracted": True,
        "locator": "p4/t1/r2",
        "arithmetic_cover": ("operating expenses re-added from 3 rows",),
    }
    body.update(over)
    return Item(**body)  # type: ignore[arg-type]


# ------------------------------------------------- one repeat year, walked through the three


def test_a_repeat_year_rolls_and_only_what_is_unproved_reaches_a_person(
    router: ConfidenceRouter,
) -> None:
    """The three pieces on one engagement: roll the window, carry the line items, route what
    comes out. What is covered goes through; what is not is seen."""
    rolled = roll_window(YearWindow(tuple(range(2016, 2026))), 2026)
    assert rolled.dropped == 2016
    assert len(rolled.window.years) == WINDOW

    carried = carry_line_items(
        ["Rent", "Insurance", "Repairs"], {"Rent": 120.0, "Insurance": 44.0, "Repairs": 9.0}
    )
    assert not carried.needs_a_person

    for label, value in carried.matched:
        routed = router.route(figure(f"is_{label.lower()}_2026", value), DECLARED)
        assert routed.route is Route.AUTO_ACCEPT, routed.reasons

    # The debt tab's fields are the ones no total re-adds, and every one is shown.
    rate = figure("debt_loan1_rate", 0.0725, arithmetic_cover=(), confidence=0.99)
    routed = router.route(rate, DECLARED)
    assert routed.route is Route.REVIEW
    assert any("no arithmetic covers" in r for r in routed.reasons)


def test_the_two_input_dates_and_the_window_agree_about_the_year() -> None:
    """The roll moves the window to 2026 and the dates to 2026. If these ever disagreed the
    workbook would carry a year of data under the wrong valuation date."""
    rolled = roll_window(YearWindow(tuple(range(2016, 2026))), 2026)
    valuation, fye = roll_dates(date(2025, 12, 31), date(2025, 12, 31))
    assert valuation.year == fye.year == rolled.window.newest


# ------------------------------------------------- each refuses what is not its to decide


def test_the_router_will_not_accept_an_unproved_figure_however_confident(
    router: ConfidenceRouter,
) -> None:
    unproved = figure("x", 1.0, arithmetic_cover=(), confidence=1.0)
    assert router.route(unproved, DECLARED).route is Route.REVIEW


def test_a_section_never_stands_in_for_an_item() -> None:
    wanted = RequestList.from_rows([("A.1", "Audited statements"), ("A.2", "Internal statements")])
    landed = Arrived.at("Clients/Acme/A. Financial Records/statements.pdf")
    assert landed.section == "A"
    assert all(c.status is Status.OUTSTANDING for c in wanted.coverage([landed]))


def test_a_mismatch_is_handed_over_rather_than_resolved() -> None:
    carried = carry_line_items(["Repairs"], {"Maintenance": 2.0})
    assert carried.needs_a_person
    assert "Did the client change their accounts" in carried.question


# ------------------------------------------------- and they agree with the rest of the build


def test_the_request_sections_are_not_a_second_document_type_vocabulary() -> None:
    """Section and document type are separate axes. If the sections leaked into the
    classifier's closed set, a file's type would depend on which folder it was dropped in."""
    from intake.readers.classify import CLASSES

    assert not set(SECTIONS) & set(CLASSES)


def test_the_router_still_routes_a_judgement_on_its_confidence(router: ConfidenceRouter) -> None:
    """P67 must not have swallowed the old rule for everything that is not an extracted
    figure - the EBITDA and tagging skills still propose judgements."""
    judgement = Item(
        item_id="j",
        skill=f"{TAGGING}@0.1.0",
        question="?",
        source_excerpt="",
        proposal={},
        confidence=0.10,
    )
    reasons = router.route(judgement, DECLARED).reasons
    assert any("below the bar" in r for r in reasons), reasons


def test_the_window_width_is_stated_in_one_place() -> None:
    """Ten is the model's shape. A second copy of it would drift from the first, and the
    one that drifted would be the one nobody was reading."""
    source = (ROOT / "tools" / "rollforward.py").read_text(encoding="utf-8")
    assert source.count("WINDOW = 10") == 1
    body = source.split('"""', 2)[2]
    assert "= 10" not in body.replace("WINDOW = 10", "", 1), "a second width is declared"


def test_the_acceptance_rule_has_no_producer_yet_and_that_is_recorded() -> None:
    """The honest state, held honest.

    `extracted` and `arithmetic_cover` are read by a tested rule and set by nothing, which
    is P55's "built, and wired to nothing". It is written down as B-040 rather than left to
    be rediscovered - and when something does start setting them, this test fails and tells
    whoever did to say so in the backlog.
    """
    sets_it = []
    for path in sorted(ROOT.rglob("*.py")):
        parts = path.parts
        if ".venv" in parts or "tests" in parts or "scratchpad" in parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg in ("extracted", "arithmetic_cover"):
                sets_it.append(str(path.relative_to(ROOT)))

    entry = (ROOT / "knowledge" / "backlog.md").read_text(encoding="utf-8")
    assert "## B-040" in entry, "the rule is inert and nothing records that"
    body = entry.split("## B-040", 1)[1].split("\n## ", 1)[0]
    if sets_it:
        assert "status: built" in body, (
            f"{sets_it} now sets the evidence, and B-040 still says nothing does"
        )
    else:
        assert "wired to nothing" in body
