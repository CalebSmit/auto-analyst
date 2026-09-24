"""P121 - which year is FY1.

P119 refused a binding whose figure is not from the period its cell asks for, and
immediately exposed why nothing had been able to check it: `RunFacts.period_slots` was
declared, read by `build_inputs`, and populated by nothing. Only `evals` set it.

So on a real run the catalogue's periods were the client's own labels — FY2023, FY2024 —
and the template asked for FY1, FY2, FY3, with no statement anywhere of which year was
which. The model was left to guess; the scripted stand-in guessed by sorting; and the two
guesses agreeing was the only thing holding it together.

The convention was already written down twice — `evals.metrics.SLOTS` maps FY2023 to FY1
and FY2025 to FY3, and the stand-in sorts and zips — and written down nowhere production
could read. **FY1 is the earliest of the slots; the newest year takes the last.**
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from harness.inputs import slots_for
from harness.procedures.model_load import ModelLoad, ModelLoadInputs, inputs_from

SLOTS = ("FY1", "FY2", "FY3")


def timing(*years: tuple[str, str]) -> dict[str, Any]:
    """A timing output carrying those (label, end) periods, one block each."""
    return {
        "normalized_historicals": {
            "periods": [
                {"label": label, "type": "FY", "end": end, "source_id": "s", "block": "b"}
                for label, end in years
            ],
            "line_items": [],
        }
    }


# ============================================================ the rule


def test_the_earliest_year_is_fy1() -> None:
    """The convention `evals` and the stand-in both already assumed, now written where
    production reads it."""
    found = slots_for(
        timing(("FY2023", "2023-12-31"), ("FY2024", "2024-12-31"), ("FY2025", "2025-12-31")),
        SLOTS,
    )
    assert found == {"FY2023": "FY1", "FY2024": "FY2", "FY2025": "FY3"}


def test_it_agrees_with_what_evals_already_assumed() -> None:
    """Two places had the rule and neither was reachable from a run. If they ever
    disagree, this is where it is found."""
    from evals.metrics import SLOTS as WRITTEN_DOWN

    derived = slots_for(
        timing(*[(label, f"{label[2:]}-12-31") for label in WRITTEN_DOWN]), SLOTS
    )
    assert derived == WRITTEN_DOWN


def test_it_orders_by_the_date_rather_than_the_label() -> None:
    """A label is whatever the client wrote on the tab. The end is a date the timing step
    settled, and sorting text puts `FY10` before `FY9`.

    The labels here are chosen so the two orders disagree: sorted as text they come out
    reversed, so a fixture whose names happen to sort the right way would prove nothing."""
    found = slots_for(
        timing(("FY9", "2023-06-30"), ("FY10", "2024-06-30"), ("FY11", "2025-06-30")),
        SLOTS,
    )
    assert sorted(["FY9", "FY10", "FY11"]) == ["FY10", "FY11", "FY9"], "text order differs"
    assert found == {"FY9": "FY1", "FY10": "FY2", "FY11": "FY3"}


# ============================================================ more years than slots


def test_five_years_against_three_slots_takes_the_most_recent() -> None:
    """The ordinary case on a real folder: the client sent five and the template has
    three. Choosing among them is a judgement (B-073); the most recent three is the
    default an analyst would take, and it is stated so that taking a different three is a
    correction rather than an excavation."""
    found = slots_for(
        timing(
            ("FY2019", "2019-12-31"),
            ("FY2020", "2020-12-31"),
            ("FY2021", "2021-12-31"),
            ("FY2022", "2022-12-31"),
            ("FY2023", "2023-12-31"),
        ),
        SLOTS,
    )
    assert found == {"FY2021": "FY1", "FY2022": "FY2", "FY2023": "FY3"}
    assert "FY2019" not in found and "FY2020" not in found


def test_the_two_that_were_dropped_are_simply_not_slotted() -> None:
    """They are still in the catalogue and still have their own labels; they have no cell
    in this template. Nothing is deleted and nothing is renamed."""
    found = slots_for(
        timing(("FY2019", "2019-12-31"), ("FY2023", "2023-12-31")), ("FY1",)
    )
    assert found == {"FY2023": "FY1"}


# ============================================================ fewer years than slots


def test_two_years_against_three_slots_leaves_one_empty() -> None:
    """Stretching two years over three cells, or repeating one, would be inventing a
    period. An unfilled input already has somewhere to go: a person, and then `not found`
    in its own cell."""
    found = slots_for(timing(("FY2022", "2022-12-31"), ("FY2023", "2023-12-31")), SLOTS)
    assert found == {"FY2022": "FY1", "FY2023": "FY2"}
    assert "FY3" not in set(found.values())


def test_no_periods_at_all_slots_nothing() -> None:
    assert slots_for(timing(), SLOTS) == {}
    assert slots_for({}, SLOTS) == {}


def test_a_template_with_no_slots_asks_for_nothing() -> None:
    assert slots_for(timing(("FY2023", "2023-12-31")), ()) == {}


def test_a_period_repeated_across_blocks_is_one_year() -> None:
    """Timing emits one period row per block, so a year read from four sheets arrives four
    times. Counting it four times would push three real years out of the slots."""
    found = slots_for(
        timing(
            ("FY2023", "2023-12-31"),
            ("FY2023", "2023-12-31"),
            ("FY2024", "2024-12-31"),
            ("FY2024", "2024-12-31"),
        ),
        SLOTS,
    )
    assert found == {"FY2023": "FY1", "FY2024": "FY2"}


# ============================================================ said to the model


def loaded(mapping: dict[str, str]) -> ModelLoadInputs:
    return inputs_from(
        "Chartwell_Input_Help_v1@1.0",
        "1.0",
        [{"name": "Revenue_FY1", "line": "Revenue", "period": "FY1", "required": True}],
        (),
        periods=SLOTS,
        period_slots=tuple(mapping.items()),
    )


def test_the_payload_says_which_year_each_slot_is() -> None:
    """The point of the whole phase. The catalogue is keyed on slots and the template asks
    for slots, and nothing said what a slot meant - so a figure could be routed into FY1
    without anybody, model or reader, knowing which year that was."""
    body = json.loads(ModelLoad().payload(loaded({"FY2023": "FY1", "FY2024": "FY2"})))
    assert body["period_slots"] == {"FY1": "FY2023", "FY2": "FY2024"}


def test_it_is_keyed_the_way_a_reader_asks_the_question() -> None:
    """"What is FY1" rather than "where did FY2023 go". The template's vocabulary is what
    somebody is holding when they ask."""
    body = json.loads(ModelLoad().payload(loaded({"FY2023": "FY1"})))
    assert list(body["period_slots"]) == ["FY1"]


def test_the_rest_of_the_payload_is_unchanged() -> None:
    body = json.loads(ModelLoad().payload(loaded({"FY2023": "FY1"})))
    assert body["template"]["inputs"][0]["name"] == "Revenue_FY1"
    assert body["periods"] == list(SLOTS)
    assert body["catalogue"] == []


# ============================================================ and used by the run


def test_build_inputs_derives_them_when_nothing_else_has() -> None:
    """`facts.period_slots` was the override and was doing the whole job, which is to say
    none of it: nothing set it."""
    from harness.inputs import RunFacts, build_inputs
    from ops.blobs import ContentRef

    class Blobs:
        def get(self, ref: Any) -> bytes:
            return json.dumps(
                timing(("FY2023", "2023-12-31"), ("FY2024", "2024-12-31"))
            ).encode("utf-8")

    facts = RunFacts(
        profile={},
        policy=None,
        taxonomy_version="coa-taxonomy@1.0.0",
        sources=(),
        blocks={},
        template=type(
            "T",
            (),
            {
                "key": "K",
                "template_version": "1.0",
                "inputs": type("I", (), {"inputs": ()})(),
            },
        )(),
        periods=SLOTS,
    )
    built = build_inputs(
        "model-load@0.1.0",
        "model",
        {"timing": ContentRef("sha256:" + "a" * 64, 1, "application/json")},
        facts,
        Blobs(),  # type: ignore[arg-type]
    )
    assert dict(built.period_slots) == {"FY2023": "FY1", "FY2024": "FY2"}


def test_a_caller_that_has_decided_differently_still_wins() -> None:
    """The override is kept because the decision is a person's: `evals` pins one, and an
    engagement that wants a different three years than the most recent three has to be
    able to say so."""
    from harness.inputs import RunFacts, build_inputs
    from ops.blobs import ContentRef

    class Blobs:
        def get(self, ref: Any) -> bytes:
            return json.dumps(
                timing(("FY2019", "2019-12-31"), ("FY2023", "2023-12-31"))
            ).encode("utf-8")

    facts = RunFacts(
        profile={},
        policy=None,
        taxonomy_version="coa-taxonomy@1.0.0",
        sources=(),
        blocks={},
        template=type(
            "T",
            (),
            {
                "key": "K",
                "template_version": "1.0",
                "inputs": type("I", (), {"inputs": ()})(),
            },
        )(),
        periods=SLOTS,
        period_slots={"FY2019": "FY1"},
    )
    built = build_inputs(
        "model-load@0.1.0",
        "model",
        {"timing": ContentRef("sha256:" + "a" * 64, 1, "application/json")},
        facts,
        Blobs(),  # type: ignore[arg-type]
    )
    assert dict(built.period_slots) == {"FY2019": "FY1"}


@pytest.mark.parametrize("years", [1, 2, 3, 4, 5, 6])
def test_every_slot_that_is_filled_is_filled_once(years: int) -> None:
    """However many years arrive, no year takes two slots and no slot takes two years -
    which is the property the period check downstream depends on."""
    found = slots_for(
        timing(*[(f"FY20{19 + n}", f"20{19 + n}-12-31") for n in range(years)]), SLOTS
    )
    assert len(set(found.values())) == len(found)
    assert len(set(found)) == len(found)
    assert len(found) == min(years, len(SLOTS))
