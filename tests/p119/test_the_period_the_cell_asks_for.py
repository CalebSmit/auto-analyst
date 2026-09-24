"""P119 - the period a figure carries and the period the cell asks for.

`ModelLoad.apply` refused a named range the template does not declare, a `figure_ref` not
in the catalogue, and a double binding. It never compared the period the input asks for
with the period the figure carries — and both were sitting in the payload it was handed.

The only guard downstream is the Numeric Integrity Lock, and the lock is a **multiset**.
Bind FY3's revenue to `Revenue_FY1`, transpose two years, and the lock's difference is
empty, every total re-adds, the provenance is impeccable, and the workbook is wrong in a
way nothing else in this build can see.

Every other invariant here is a guard a model cannot relax. The one cross-check that was
free was left to the model's judgement.

The line is a different matter and is deliberately *not* checked: the template says
`Cost of sales`, this client's income statement says `Costs of Goods Sold`, and deciding
those are the same line is the work the skill exists to do. A string comparison would
refuse every correct mapping it was ever given.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from harness.procedures.model_load import (
    SLOT_FOR_A_BENCHMARK,
    FigureRef,
    ModelLoad,
    ModelLoadInputs,
    ProposalRefused,
    TemplateInput,
    catalogue_from,
)

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "harness" / "procedures" / "model_load.py"
KEY = "Chartwell_Input_Help_v1@1.0"


def figure(ref: str, period: str, description: str = "Revenue") -> FigureRef:
    return FigureRef(
        figure_ref=ref,
        source_output="timing",
        description=description,
        period=period,
        figure={"value": 1.0, "scale": 1000, "unit": "currency", "currency": "USD"},
    )


def inputs(*rows: tuple[str, str, str]) -> ModelLoadInputs:
    return ModelLoadInputs(
        template_key=KEY,
        template_version="1.0",
        inputs=tuple(TemplateInput(n, line, period, required=True) for n, line, period in rows),
        catalogue=(),
    )


class Tools:
    """The gated schema lookup, answering with exactly the rows it was given."""

    engagement_id = "ENG-P119"

    def __init__(self, loaded: ModelLoadInputs) -> None:
        self.loaded = loaded

    def __getitem__(self, name: str) -> Any:
        rows = [
            {"name": i.name, "line": i.line, "period": i.period, "required": i.required}
            for i in self.loaded.inputs
        ]
        return lambda **_: type("R", (), {"value": {"rows": rows}})()


def applied(loaded: ModelLoadInputs, bindings: list[dict[str, str]]) -> dict[str, Any]:
    proposal = {
        "bindings": bindings,
        "unmapped_template_inputs": [
            {"named_range": i.name, "why": "not bound by this test"}
            for i in loaded.inputs
            if i.name not in {b["named_range"] for b in bindings}
        ],
        "unrouted_upstream_figures": [],
    }
    return ModelLoad().apply(proposal, Tools(loaded), loaded, "pin")


# ============================================================ the wrong year


def test_a_figure_from_another_year_is_refused() -> None:
    """The failure the lock cannot see. Two years transposed, an empty difference, every
    total re-adding, and a valuation built on the wrong revenue."""
    loaded = inputs(("Revenue_FY1", "Revenue", "FY1"))
    loaded = ModelLoadInputs(
        loaded.template_key,
        loaded.template_version,
        loaded.inputs,
        catalogue=(figure("timing:Revenue:FY3", "FY3"),),
    )
    with pytest.raises(ProposalRefused) as refused:
        applied(loaded, [{"named_range": "Revenue_FY1", "figure_ref": "timing:Revenue:FY3"}])
    said = str(refused.value)
    assert "Revenue_FY1" in said, "the input"
    assert "FY1" in said and "FY3" in said, "both periods"
    assert "passes every check after this one" in said


def test_the_right_year_is_written() -> None:
    loaded = inputs(("Revenue_FY1", "Revenue", "FY1"))
    loaded = ModelLoadInputs(
        loaded.template_key,
        loaded.template_version,
        loaded.inputs,
        catalogue=(figure("timing:Revenue:FY1", "FY1"),),
    )
    out = applied(loaded, [{"named_range": "Revenue_FY1", "figure_ref": "timing:Revenue:FY1"}])
    assert out["template_mapping"]["bindings"][0]["figure_ref"] == "timing:Revenue:FY1"


def test_the_refusal_carries_both_periods_where_a_console_reads_them() -> None:
    """`expected` and `found` are the fields a diagnostic is rendered from; a message that
    said it in prose alone would be findable by reading and not by looking."""
    loaded = inputs(("Revenue_FY1", "Revenue", "FY1"))
    loaded = ModelLoadInputs(
        loaded.template_key,
        loaded.template_version,
        loaded.inputs,
        catalogue=(figure("timing:Revenue:FY2", "FY2"),),
    )
    with pytest.raises(ProposalRefused) as refused:
        applied(loaded, [{"named_range": "Revenue_FY1", "figure_ref": "timing:Revenue:FY2"}])
    assert refused.value.diagnostic.expected == "FY1"
    assert refused.value.diagnostic.found == "FY2"
    assert refused.value.diagnostic.locator == "Revenue_FY1"


def test_it_is_a_refusal_rather_than_a_question_for_a_person() -> None:
    """An unfilled input is a judgement and reaches a review queue. A figure in the wrong
    year is arithmetic, and asking somebody to weigh it up would be asking them to
    ratify a mistake."""
    loaded = inputs(("Revenue_FY1", "Revenue", "FY1"))
    loaded = ModelLoadInputs(
        loaded.template_key,
        loaded.template_version,
        loaded.inputs,
        catalogue=(figure("timing:Revenue:FY3", "FY3"),),
    )
    with pytest.raises(ProposalRefused):
        applied(loaded, [{"named_range": "Revenue_FY1", "figure_ref": "timing:Revenue:FY3"}])


# ============================================================ the benchmark's slot


def test_the_profile_benchmark_speaks_the_template_s_vocabulary() -> None:
    """It carried the profile's `as_of` *date* in the field every other row uses for the
    template's slot, so the one row that is not a fiscal year could not be compared with
    anything. `period_slots` turns FY2023 into FY1 for the same reason."""
    catalogue = catalogue_from(
        {"normalized_historicals": {"periods": [], "line_items": []}},
        {
            "owner_compensation_baseline": {
                "amount": 265000.0,
                "currency": "USD",
                "as_of": "2025-06-30",
            }
        },
    )
    benchmark = next(f for f in catalogue if f.source_output == "profile")
    assert benchmark.period == SLOT_FOR_A_BENCHMARK == "as_of"


def test_the_date_is_not_lost_it_moves_to_where_it_is_read() -> None:
    """It is the one thing about this figure anybody wants to know, and in the description
    it is shown to the model rather than being asked to match something."""
    catalogue = catalogue_from(
        {"normalized_historicals": {"periods": [], "line_items": []}},
        {
            "owner_compensation_baseline": {
                "amount": 265000.0,
                "currency": "USD",
                "as_of": "2025-06-30",
            }
        },
    )
    benchmark = next(f for f in catalogue if f.source_output == "profile")
    assert "2025-06-30" in benchmark.description


def test_a_benchmark_with_no_date_still_has_a_slot() -> None:
    catalogue = catalogue_from(
        {"normalized_historicals": {"periods": [], "line_items": []}},
        {"owner_compensation_baseline": {"amount": 1.0, "currency": "USD"}},
    )
    benchmark = next(f for f in catalogue if f.source_output == "profile")
    assert benchmark.period == SLOT_FOR_A_BENCHMARK
    assert benchmark.description == "Owner-compensation benchmark"


def test_the_template_declares_that_same_slot() -> None:
    """The two have to agree and neither owns the other, so this is the assertion that
    they do. If the template ever renames it, this is where that is found."""
    from deliver.registry import TemplateInputs

    schema = TemplateInputs.load(KEY)
    benchmark = schema.get("Owner_Comp_Benchmark")
    assert benchmark is not None
    assert benchmark.period == SLOT_FOR_A_BENCHMARK


# ============================================================ what is not checked


def test_the_line_is_not_compared() -> None:
    """Deliberately. The template says `Cost of sales`, this client says `Costs of Goods
    Sold`, and the next client will say something else - deciding those are the same line
    is the work the skill exists to do."""
    loaded = inputs(("COGS_FY1", "Cost of sales", "FY1"))
    loaded = ModelLoadInputs(
        loaded.template_key,
        loaded.template_version,
        loaded.inputs,
        catalogue=(figure("timing:cogs:FY1", "FY1", description="Costs of Goods Sold"),),
    )
    out = applied(loaded, [{"named_range": "COGS_FY1", "figure_ref": "timing:cogs:FY1"}])
    assert out["template_mapping"]["bindings"][0]["figure_ref"] == "timing:cogs:FY1"


def test_the_module_says_the_line_is_unchecked() -> None:
    """Where a reader of the skill will find it. An invariant somebody assumes is there
    is worse than one they know is not."""
    said = MODULE.read_text(encoding="utf-8")
    assert "line is not checked, and cannot be" in said
    assert "Cost of sales" in said and "Costs of Goods Sold" in said


def test_it_says_where_a_wrong_line_is_meant_to_be_seen_instead() -> None:
    """Naming a gap without naming the thing that covers it is half an answer. The Source
    column is the other half, and it is why P115 mattered."""
    said = MODULE.read_text(encoding="utf-8")
    assert "Source column" in said
    assert "unmapped_inputs_require_review" in said


def test_the_older_refusals_are_all_still_there() -> None:
    """Adding a check must not have replaced one. An unknown destination, a ref that is
    not in the catalogue and a double binding each still stop the step."""
    loaded = inputs(("Revenue_FY1", "Revenue", "FY1"))
    loaded = ModelLoadInputs(
        loaded.template_key,
        loaded.template_version,
        loaded.inputs,
        catalogue=(figure("timing:Revenue:FY1", "FY1"),),
    )
    with pytest.raises(ProposalRefused, match="not a declared input"):
        applied(loaded, [{"named_range": "Nonesuch", "figure_ref": "timing:Revenue:FY1"}])
    with pytest.raises(ProposalRefused, match="not in the catalogue"):
        applied(loaded, [{"named_range": "Revenue_FY1", "figure_ref": "timing:nope:FY1"}])
    with pytest.raises(ProposalRefused, match="bound twice"):
        applied(
            loaded,
            [
                {"named_range": "Revenue_FY1", "figure_ref": "timing:Revenue:FY1"},
                {"named_range": "Revenue_FY1", "figure_ref": "timing:Revenue:FY1"},
            ],
        )
