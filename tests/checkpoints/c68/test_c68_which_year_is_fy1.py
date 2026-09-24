"""C68 - which year is FY1.

P119 refused a binding whose figure is not from the period its cell asks for. P121 filled
the mapping that makes the question answerable: `RunFacts.period_slots` was declared, read
by `build_inputs`, and set by nothing, so the catalogue went to the model keyed on the
client's own years while the template asked for FY1, and nothing anywhere said which was
which.

They are one change seen twice. A guard that refuses a figure from the wrong year is only
possible once something states which year each cell is; and stating it is only worth doing
if something refuses when it is ignored. Between them they closed the gap where a figure
could land in the wrong cell and every check afterwards pass — the Numeric Integrity Lock
is a multiset, so two transposed years leave its difference empty and every total re-adds.

The question here is whether one run agrees with itself end to end: the years timing
settled, the slots derived from them, the payload that says what a slot means, the
catalogue keyed on them, and the check that refuses a binding that ignores all of it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness.inputs import slots_for
from harness.procedures.model_load import (
    ModelLoad,
    ProposalRefused,
    catalogue_from,
    inputs_from,
)

ROOT = Path(__file__).resolve().parents[3]
SLOTS = ("FY1", "FY2", "FY3")


def timing_output(*years: tuple[str, str]) -> dict[str, Any]:
    """A normalized table with one line item carrying a figure in each of those years."""
    return {
        "normalized_historicals": {
            "periods": [
                {"label": label, "type": "FY", "end": end, "source_id": "s", "block": "b"}
                for label, end in years
            ],
            "line_items": [
                {
                    "canonical_label": "Revenue",
                    "values": [
                        {
                            "value": float(n + 1),
                            "unit": "currency",
                            "currency": "USD",
                            "scale": 1000,
                            "period": {"type": "FY", "end": end},
                            "source_id": "sha256:" + "a" * 64,
                            "locator": f"IS!B{n + 4}",
                            "source_version": 1,
                            "derivation": None,
                            "masked": True,
                            "confidence": 0.9,
                            "produced_by": "timing-normalization@0.1.0",
                            "model_pin": "claude-sonnet-5 @ effort=high",
                        }
                        for n, (_, end) in enumerate(years)
                    ],
                }
            ],
        }
    }


def world(*years: tuple[str, str]) -> Any:
    """Everything model-load is handed for those client years, as a run assembles it."""
    timing = timing_output(*years)
    slots = slots_for(timing, SLOTS)
    catalogue = catalogue_from(timing, {}, period_slots=slots)
    return inputs_from(
        "Chartwell_Input_Help_v1@1.0",
        "1.0",
        [
            {"name": f"Revenue_{slot}", "line": "Revenue", "period": slot, "required": True}
            for slot in SLOTS
        ],
        catalogue,
        periods=SLOTS,
        period_slots=tuple(slots.items()),
    )


def tools_for(loaded: Any) -> Any:
    rows = [
        {"name": i.name, "line": i.line, "period": i.period, "required": i.required}
        for i in loaded.inputs
    ]
    return type(
        "T",
        (),
        {
            "engagement_id": "ENG-C68",
            "__getitem__": lambda self, n: (
                lambda **_: type("R", (), {"value": {"rows": rows}})()
            ),
        },
    )()


def apply(loaded: Any, bindings: list[dict[str, str]]) -> dict[str, Any]:
    proposal = {
        "bindings": bindings,
        "unmapped_template_inputs": [
            {"named_range": i.name, "why": "not bound here"}
            for i in loaded.inputs
            if i.name not in {b["named_range"] for b in bindings}
        ],
        "unrouted_upstream_figures": [],
    }
    return ModelLoad().apply(proposal, tools_for(loaded), loaded, "pin")


THREE = (("FY2023", "2023-12-31"), ("FY2024", "2024-12-31"), ("FY2025", "2025-12-31"))


# ============================================================ one run, agreeing


def test_the_catalogue_is_keyed_on_the_slots_the_template_asks_for() -> None:
    loaded = world(*THREE)
    assert {f.period for f in loaded.catalogue} == set(SLOTS)


def test_and_each_figure_still_says_which_year_it_is() -> None:
    """The ref is an identity in the client's own terms; the period is where it goes. Two
    fields, two jobs - the failure was never two spellings, it was nothing saying what a
    slot meant."""
    loaded = world(*THREE)
    assert {f.figure_ref for f in loaded.catalogue} == {
        "timing:Revenue:FY2023",
        "timing:Revenue:FY2024",
        "timing:Revenue:FY2025",
    }


def test_the_payload_says_what_each_slot_means() -> None:
    body = json.loads(ModelLoad().payload(world(*THREE)))
    assert body["period_slots"] == {"FY1": "FY2023", "FY2": "FY2024", "FY3": "FY2025"}


def test_a_binding_that_follows_the_payload_is_accepted() -> None:
    """The whole chain, agreeing. The payload says FY1 is FY2023, the catalogue keys that
    figure FY1, and the check lets it through."""
    loaded = world(*THREE)
    out = apply(
        loaded, [{"named_range": "Revenue_FY1", "figure_ref": "timing:Revenue:FY2023"}]
    )
    assert out["template_mapping"]["bindings"][0]["figure_ref"] == "timing:Revenue:FY2023"


def test_a_binding_that_ignores_it_is_refused() -> None:
    """And the other way. FY2025 into the FY1 cell is the failure the lock cannot see."""
    loaded = world(*THREE)
    with pytest.raises(ProposalRefused, match="wrong year"):
        apply(loaded, [{"named_range": "Revenue_FY1", "figure_ref": "timing:Revenue:FY2025"}])


# ============================================================ more and fewer years


def test_five_years_fill_the_three_most_recent_slots_and_say_so() -> None:
    """The real client folder's shape. Which three is a judgement (B-073); the default is
    the most recent three, and the payload names them so a different three is a correction
    rather than an excavation."""
    loaded = world(
        ("FY2019", "2019-12-31"),
        ("FY2020", "2020-12-31"),
        *THREE,
    )
    body = json.loads(ModelLoad().payload(loaded))
    assert body["period_slots"] == {"FY1": "FY2023", "FY2": "FY2024", "FY3": "FY2025"}


def test_the_older_years_are_still_in_the_catalogue_under_their_own_names() -> None:
    """Nothing is dropped. They have no cell in this template, and a figure with no slot
    keeps its own year so it stays identifiable."""
    loaded = world(("FY2019", "2019-12-31"), ("FY2020", "2020-12-31"), *THREE)
    refs = {f.figure_ref for f in loaded.catalogue}
    assert "timing:Revenue:FY2019" in refs
    assert {f.period for f in loaded.catalogue if f.figure_ref.endswith("FY2019")} == {"FY2019"}


def test_a_figure_with_no_slot_cannot_be_bound_to_a_cell() -> None:
    """Which is the point of leaving it unslotted rather than stretching. FY2019 has no
    cell in a three-slot template, and the check says so rather than the writer silently
    putting five years of revenue into three cells."""
    loaded = world(("FY2019", "2019-12-31"), ("FY2020", "2020-12-31"), *THREE)
    with pytest.raises(ProposalRefused, match="wrong year"):
        apply(loaded, [{"named_range": "Revenue_FY1", "figure_ref": "timing:Revenue:FY2019"}])


def test_two_years_leave_the_third_slot_empty_rather_than_repeating_one() -> None:
    loaded = world(("FY2024", "2024-12-31"), ("FY2025", "2025-12-31"))
    body = json.loads(ModelLoad().payload(loaded))
    assert body["period_slots"] == {"FY1": "FY2024", "FY2": "FY2025"}
    assert "FY3" not in body["period_slots"]


def test_and_the_empty_slot_ends_where_an_unfilled_input_always_ends() -> None:
    """With a person, and then `not found` in its own cell (P112, P115). Nothing invents a
    third year to fill it."""
    loaded = world(("FY2024", "2024-12-31"), ("FY2025", "2025-12-31"))
    out = apply(
        loaded,
        [
            {"named_range": "Revenue_FY1", "figure_ref": "timing:Revenue:FY2024"},
            {"named_range": "Revenue_FY2", "figure_ref": "timing:Revenue:FY2025"},
        ],
    )
    unmapped = {u["named_range"] for u in out["template_mapping"]["unmapped_template_inputs"]}
    assert "Revenue_FY3" in unmapped


# ============================================================ the rule, once


def test_the_rule_is_written_where_production_reads_it() -> None:
    """It was written down twice - in `evals` and in the stand-in - and in neither place
    could a run reach it."""
    said = (ROOT / "harness" / "inputs.py").read_text(encoding="utf-8")
    assert "FY1 is the earliest of the slots" in said


def test_the_stand_in_no_longer_keeps_its_own_version_of_it() -> None:
    """A second guess beside the derivation is a second answer to keep in step. With the
    catalogue speaking slots, the stand-in's sort was not merely redundant - it shifted
    every slot by one whenever a benchmark row was in the catalogue."""
    said = (ROOT / "ports" / "llm" / "scripted.py").read_text(encoding="utf-8")
    assert 'order = {f"FY{i + 1}": lab for i, lab in enumerate(labels)}' not in said
