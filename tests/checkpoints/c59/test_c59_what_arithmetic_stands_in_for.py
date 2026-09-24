"""C59 - what arithmetic is allowed to stand in for.

P99 produces evidence that `review/router.py` has read since P37 and nothing has ever set.
That is a particular kind of change: the risk is not in the addition - a total either
re-adds or it does not - but in what the evidence is then allowed to mean.

Three things this asks that P99 alone cannot.

1. **The acceptance rule did not get easier.** A figure nothing covers still goes to a
   person, and materiality, an always-review category and a raised review level still send
   a fully covered figure to one. An admin may raise a review requirement and never lower
   it, and arithmetic cover must not become the way round that.
2. **A statement that does not foot says so by name and by amount**, on the path a run
   takes, not only in a unit test's dataclass.
3. **Reading a folder still costs nothing it did not cost before**: no model, no OCR
   engine, no network, on any module P99 touched.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from intake.readers.footing import footings_in
from review.policy import CheckpointPolicy, Money
from review.router import ConfidenceRouter, Item, Route

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Row:
    label: str
    value: float | None
    ordinal: int = 0


def statement(*pairs: tuple[str, float | None]) -> list[Row]:
    return [Row(label, value, n) for n, (label, value) in enumerate(pairs)]


FOOTS = statement(("Cash", 100.0), ("Petty cash", 50.0), ("Total Cash", 150.0))
DOES_NOT = statement(("Cash", 100.0), ("Petty cash", 50.0), ("Total Cash", 200.0))


# ================================================ 1. the rule did not get easier


#: An engagement that auto-accepts a confident judgement, so that a figure being routed to
#: a person is about the figure rule rather than about nothing being auto-accepted at all.
POLICY = CheckpointPolicy(
    engagement_id="ENG-1",
    owner="the analyst",
    sla_hours=24,
    materiality=Money(amount=50_000, currency="USD"),
    auto_accept_confidence=0.9,
)


def a_figure(**kwargs: object) -> Item:
    """A figure read out of a client document, covered and locatable - the case that is
    allowed through, so that each test below removes exactly one thing."""
    base: dict[str, object] = {
        "item_id": "i1",
        "skill": "fs-normalization",
        "question": "is this the right cash balance?",
        "source_excerpt": "Total Cash 150.00",
        "proposal": {"value": 150.0},
        "extracted": True,
        "locator": "'FY23'!B4",
        "arithmetic_cover": ("Total Cash re-added from 2 rows",),
        "confidence": None,
    }
    base.update(kwargs)
    return Item(**base)  # type: ignore[arg-type]


def routing_for(item: Item) -> object:
    # Rank 0 on the review ladder: the skill declares no floor of its own, so what the
    # router does here is the acceptance rule and nothing else.
    return ConfidenceRouter(POLICY).route(item, "none")


def test_a_covered_figure_is_the_case_that_is_allowed_through() -> None:
    """The control. Without it the three tests below would pass against a router that sent
    everything to a person, which is the shape a broken acceptance rule actually takes."""
    assert routing_for(a_figure()).route is Route.AUTO_ACCEPT


def test_a_figure_no_arithmetic_covers_still_goes_to_a_person() -> None:
    """The rule P99 exists to feed, asked from the other side. Producing evidence must not
    have made the absence of evidence cheaper."""
    routed = routing_for(a_figure(arithmetic_cover=()))
    assert routed.route is not Route.AUTO_ACCEPT
    assert any("no arithmetic covers" in r for r in routed.reasons)


def test_a_covered_figure_with_no_locator_still_goes_to_a_person() -> None:
    """Both halves of the acceptance rule, not either. A figure that re-adds but cannot say
    which page and row it came from is a figure nobody can check."""
    routed = routing_for(a_figure(locator=""))
    assert routed.route is not Route.AUTO_ACCEPT
    assert any("locator" in r for r in routed.reasons)


def test_arithmetic_cover_stands_in_for_the_confidence_test_and_nothing_else() -> None:
    """Named in `review/router.py` and worth holding here, because this is the phase that
    makes the substitution reachable for the first time. Materiality, an always-review
    category and a raised level all still send a covered figure to a person."""
    source = (ROOT / "review" / "router.py").read_text(encoding="utf-8")
    assert "Evidence stands in for the confidence test and for nothing else" in source
    assert "never lower one" in source


# ================================================ 2. it reaches a person


def test_a_statement_that_does_not_foot_is_named_and_quantified_in_the_read() -> None:
    """Not "3 totals did not re-add", which sends somebody through a hundred rows. The
    total's own label and the amount it is out by."""
    from intake.readers import ReadReport

    report = ReadReport(source_id="s", filename="TB.xlsx", kind="spreadsheet")
    report.footing["'FY23'!B1:B3"] = footings_in(DOES_NOT)
    named = report.totals_that_did_not_foot
    assert named
    assert "Total Cash" in named[0]
    assert "-50.00" in named[0]
    assert "'FY23'!B1:B3" in named[0], "and which block, because a workbook has many"


def test_a_statement_that_foots_says_nothing_alarming() -> None:
    """A guard that only speaks when it fires is, on a quiet day, indistinguishable from one
    that never ran - so the count is recorded either way, and the *warning* is not."""
    from intake.readers import ReadReport

    report = ReadReport(source_id="s", filename="TB.xlsx", kind="spreadsheet")
    report.footing["'FY23'!B1:B3"] = footings_in(FOOTS)
    assert report.totals_that_did_not_foot == ()
    assert report.covered_rows == 2


def test_the_worst_miss_is_reported_first() -> None:
    """Three totals out by a cent and one out by nine thousand is one finding and three
    rounding differences, and a list in document order buries it."""
    from intake.readers import ReadReport

    report = ReadReport(source_id="s", filename="TB.xlsx", kind="spreadsheet")
    report.footing["a"] = footings_in(
        statement(("A", 1.0), ("Total A", 1.02))
    )
    report.footing["b"] = footings_in(
        statement(("B", 1.0), ("Total B", 9001.0))
    )
    assert "Total B" in report.totals_that_did_not_foot[0]


# ================================================ 3. it still costs nothing


@pytest.mark.parametrize(
    "module", ["intake/readers/footing.py", "intake/readers/periods.py", "review/router.py"]
)
def test_no_module_on_this_path_reaches_a_model_or_an_engine(module: str) -> None:
    tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
    named: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            named.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            named.add(node.module)
    for forbidden in ("ports.llm", "ports.ocr", "anthropic", "openai", "harness", "skills"):
        assert not any(n == forbidden or n.startswith(forbidden + ".") for n in named), module


def test_the_footing_reader_is_reached_by_something_a_run_does() -> None:
    """P68 shipped machinery unreached and it stayed that way for twenty-six phases. This
    is the join, asserted rather than assumed."""
    import sys

    sys.path.insert(0, str(ROOT))
    from tests.p82.test_nothing_a_run_cannot_reach import ALLOWED, unreachable

    assert "intake.readers.footing" not in unreachable()
    assert "intake.readers.footing" not in ALLOWED, "reached, and should not be excused"


def test_what_it_proves_is_written_down_where_somebody_will_read_it() -> None:
    """"Arithmetic cover" sounds like more than it is. The person relying on it is relying
    on the difference between addition and selection, and both modules that use the phrase
    say so."""
    footing = (ROOT / "intake" / "readers" / "footing.py").read_text(encoding="utf-8")
    tieout = (ROOT / "guards" / "tieout.py").read_text(encoding="utf-8")
    assert "proves addition" in footing and "not selection" in footing
    assert "proves arithmetic, not selection" in tieout
