"""Fixtures for P165: the real ebitda world from P20, and model-load driven the way C68
drives it. Re-exported rather than copied, for the reason P159 gives - two sets of these
would be two things that have to agree about what a run is."""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable, Mapping
from typing import Any

import pytest

from tests.p20.conftest import (  # noqa: F401 - re-exported as fixtures
    blobs,
    bus,
    case,
    constraints,
    contracts,
    ebitda_step,
    parse_store,
    plan,
    policy,
    precedents,
    scope,
    scopes,
    started,
    store,
    tree,
    world,
)


def model_load_apply(
    figures: Mapping[str, Mapping[str, Any] | float], bindings: Mapping[str, str]
) -> dict[str, Any]:
    """`ModelLoad.apply` over a one-cell template, with the catalogue given as figures by
    ref and the proposal as cell -> ref. The tools are C68's stand-in, which answers the
    schema call with the template's own rows."""
    from harness.procedures.model_load import FigureRef, ModelLoad, ModelLoadInputs, TemplateInput
    from tests.checkpoints.c68.test_c68_which_year_is_fy1 import tools_for

    loaded = ModelLoadInputs(
        template_key="Chartwell_Input_Help_v1@1.0",
        template_version="1.0",
        inputs=(TemplateInput(name="Revenue_FY1", line="Revenue", period="FY1", required=True),),
        catalogue=tuple(
            FigureRef(
                figure_ref=ref,
                source_output="timing",
                description=ref.split(":")[1],
                period="FY1",
                figure=figure,
            )
            for ref, figure in figures.items()
        ),
        periods=("FY1",),
        period_slots=(("FY2025", "FY1"),),
    )
    proposal = {
        "bindings": [{"named_range": name, "figure_ref": ref} for name, ref in bindings.items()],
        "unmapped_template_inputs": [
            {"named_range": i.name, "why": "not bound here"}
            for i in loaded.inputs
            if i.name not in bindings
        ],
        "unrouted_upstream_figures": [],
    }
    return ModelLoad().apply(proposal, tools_for(loaded), loaded, "pin")


@pytest.fixture
def ebitda_sites(
    world: dict[str, Any], case: dict[str, Any]  # noqa: F811 - the fixtures above, by name
) -> Callable[[Mapping[str, Any]], dict[str, Callable[[], Any]]]:
    """The three places the ebitda procedure turns a figure into a number, each as a
    callable over the real procedure, the real tools and the real case - with the first
    candidate's line carrying the figure given, in every period it has."""

    def make(figure: Mapping[str, Any]) -> dict[str, Callable[[], Any]]:
        procedure = world["procedure"]
        inputs = world["inputs"]
        proposal = copy.deepcopy(case["proposal"])
        first = proposal["candidates"][0]
        line = inputs.line(str(first["line_item_ref"]))
        assert line is not None
        swapped_line = dataclasses.replace(
            line,
            figures={period: {**line.figures[period], **figure} for period in line.figures},
        )
        swapped = dataclasses.replace(
            inputs, lines=tuple(swapped_line if ln is line else ln for ln in inputs.lines)
        )
        proposal["candidates"] = [first]

        def officer_total() -> Any:
            as_officer = copy.deepcopy(proposal)
            as_officer["candidates"][0]["officer_compensation"] = True
            return procedure.apply(as_officer, world["tools_for"](), swapped, "pin")

        def materiality() -> Any:
            plain = copy.deepcopy(proposal)
            plain["candidates"][0]["officer_compensation"] = False
            return procedure.apply(plain, world["tools_for"](), swapped, "pin")

        def review_items() -> Any:
            return procedure.review_items(
                {
                    "addback_schedule": [
                        {
                            "review_required": True,
                            "candidate_id": "c",
                            "amount": dict(figure),
                            "category": "non_recurring",
                            "line_item_ref": str(first["line_item_ref"]),
                        }
                    ]
                },
                {},
            )

        return {
            "review_items": review_items,
            "materiality": materiality,
            "officer_total": officer_total,
        }

    return make
