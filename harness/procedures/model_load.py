"""The mechanical half of model-load.

What the model sees is the template's declared inputs and a catalogue of figure refs -
names, lines, periods, never a value. What comes back is a routing. What this module
does with it is check every claim before it is a mapping: every destination is one the
pinned template declares (read through the gated `template_schema_lookup`, so the
version is the run's pin), every figure ref is one the catalogue holds, no input is
bound twice, and every required input is either bound or listed as unmapped. The
Model Builder then resolves the figures and the Template Writer performs every write;
this skill writes no cell and originates no figure.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from harness.runtime import BoundTools
from registries.errors import UNKNOWN_LINE_ITEM, DiagnosticError, diagnose
from review.router import Item

__all__ = [
    "CONTRACT",
    "FigureRef",
    "ModelLoad",
    "ModelLoadInputs",
    "PROPOSAL_CONTRACT",
    "PRODUCED_BY",
    "ProposalRefused",
    "TemplateInput",
    "catalogue_from",
]

CONTRACT = "skills/model-load@1.0.0"
PROPOSAL_CONTRACT = "skills/model-load-proposal@1.0.0"
PRODUCED_BY = "model-load@0.1.0"
SCHEMA_TOOL = "template_schema_lookup"


class ProposalRefused(DiagnosticError):
    """The proposal routes something the step was not given, or routes it twice."""


@dataclass(frozen=True)
class TemplateInput:
    name: str
    line: str
    period: str
    required: bool


@dataclass(frozen=True)
class FigureRef:
    """One routable figure: its ref, where it came from, what it is - and, kept out of
    the payload, the figure itself for the builder."""

    figure_ref: str
    source_output: str
    description: str
    period: str
    figure: Mapping[str, Any] | float

    def as_row(self) -> dict[str, Any]:
        return {
            "figure_ref": self.figure_ref,
            "source_output": self.source_output,
            "description": self.description,
            "period": self.period,
        }


@dataclass(frozen=True)
class ModelLoadInputs:
    template_key: str
    template_version: str
    inputs: tuple[TemplateInput, ...]
    catalogue: tuple[FigureRef, ...]
    periods: tuple[str, ...] = field(default_factory=tuple)

    @property
    def required(self) -> tuple[str, ...]:
        return tuple(i.name for i in self.inputs if i.required)

    @property
    def declared(self) -> frozenset[str]:
        return frozenset(i.name for i in self.inputs)

    def figures(self) -> dict[str, Mapping[str, Any] | float]:
        return {f.figure_ref: f.figure for f in self.catalogue}


def catalogue_from(
    timing_output: Mapping[str, Any],
    profile: Mapping[str, Any] | None = None,
    *,
    period_slots: Mapping[str, str] | None = None,
) -> tuple[FigureRef, ...]:
    """Every figure the historical table carries, as `timing:<line>:<period>`, plus the
    profile's benchmark as `profile:owner_compensation_baseline`. `period_slots` maps a
    period label to the template's slot (FY2023 -> FY1) so the model reads slots, not
    years."""
    table = timing_output["normalized_historicals"]
    by_end = {p["end"]: p["label"] for p in table["periods"]}
    slots = dict(period_slots or {})
    refs: list[FigureRef] = []
    for entry in table["line_items"]:
        label = str(entry["canonical_label"])
        for figure in entry.get("values", []):
            period = by_end.get(figure["period"]["end"], figure["period"]["end"])
            refs.append(
                FigureRef(
                    figure_ref=f"timing:{label}:{period}",
                    source_output="timing",
                    description=label,
                    period=slots.get(period, period),
                    figure=figure,
                )
            )
    baseline = (profile or {}).get("owner_compensation_baseline")
    if isinstance(baseline, Mapping) and baseline.get("amount") is not None:
        refs.append(
            FigureRef(
                figure_ref="profile:owner_compensation_baseline",
                source_output="profile",
                description="Owner-compensation benchmark",
                period=str(baseline.get("as_of", "as_of")),
                figure=float(baseline["amount"]),
            )
        )
    return tuple(refs)


class ModelLoad:
    name = "model-load"
    proposal_contract = PROPOSAL_CONTRACT

    def escalate(self, inputs: ModelLoadInputs) -> str | None:
        if not inputs.inputs:
            raise ValueError("model-load was given a template with no declared inputs")
        if not inputs.catalogue:
            return "there are no validated figures to route; nothing upstream produced a table"
        return None

    def terms(self, inputs: ModelLoadInputs) -> tuple[str, ...]:
        return ()

    def review_items(self, output: dict[str, Any], inputs: dict[str, Any]) -> list[Item]:
        """A required template input with nothing bound to it. The workbook is not built
        around a hole a person has not seen."""
        mapping = output.get("template_mapping") or {}
        required = {str(n) for n in (inputs.get("required") or ())}
        items: list[Item] = []
        for u in mapping.get("unmapped_template_inputs", ()):
            name = str(u.get("named_range") or "")
            if required and name not in required:
                continue
            items.append(
                Item(
                    item_id=f"unmapped:{name}",
                    skill=self.name,
                    question=(
                        f"Template input {name} has no upstream figure: {u.get('why') or ''}. "
                        f"Leave it empty, or name the figure?"
                    ),
                    source_excerpt=name,
                    proposal={"named_range": name, "why": u.get("why")},
                    confidence=None,
                    review_required=True,
                    locator=name,
                )
            )
        return items

    def payload(self, inputs: ModelLoadInputs) -> str:
        """Template inputs and the catalogue. Names, lines, periods; no values."""
        body = {
            "template": {
                "key": inputs.template_key,
                "template_version": inputs.template_version,
                "inputs": [
                    {"name": i.name, "line": i.line, "period": i.period, "required": i.required}
                    for i in inputs.inputs
                ],
            },
            "periods": list(inputs.periods),
            "catalogue": [f.as_row() for f in inputs.catalogue],
        }
        return json.dumps(body, indent=1)

    def parse(self, text: str) -> dict[str, Any]:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("the model returned no JSON object")
        body = json.loads(text[start : end + 1])
        if not isinstance(body, dict):
            raise ValueError("the proposal is not an object")
        return body

    def apply(
        self, proposal: dict[str, Any], tools: BoundTools, inputs: ModelLoadInputs, pin: str
    ) -> dict[str, Any]:
        # The template's inputs, through the gate: the version is the run's pin or the
        # call is refused. What the model was told and what the run pinned must agree.
        schema = tools[SCHEMA_TOOL](
            engagement_id=tools.engagement_id, version=inputs.template_key
        ).value
        declared = {row["name"]: row for row in schema["rows"]}
        if set(declared) != inputs.declared:
            raise ProposalRefused(
                diagnose(
                    UNKNOWN_LINE_ITEM,
                    f"the pinned template {inputs.template_key} declares "
                    f"{sorted(set(declared) ^ inputs.declared)} differently from the payload; "
                    f"the template changed under the step",
                    locator=inputs.template_key,
                    skill=PRODUCED_BY,
                )
            )
        refs = {f.figure_ref: f for f in inputs.catalogue}

        bound: dict[str, str] = {}
        bindings = []
        for b in proposal["bindings"]:
            name, ref = str(b["named_range"]), str(b["figure_ref"])
            if name not in declared:
                raise ProposalRefused(
                    diagnose(
                        UNKNOWN_LINE_ITEM,
                        f"{name!r} is not a declared input of {inputs.template_key}",
                        locator=name,
                        skill=PRODUCED_BY,
                    )
                )
            if ref not in refs:
                raise ProposalRefused(
                    diagnose(
                        UNKNOWN_LINE_ITEM,
                        f"{ref!r} is bound to {name} and is not in the catalogue",
                        locator=name,
                        skill=PRODUCED_BY,
                    )
                )
            if name in bound:
                raise ProposalRefused(
                    diagnose(
                        UNKNOWN_LINE_ITEM,
                        f"{name} is bound twice ({bound[name]} and {ref}); one input, one figure",
                        locator=name,
                        skill=PRODUCED_BY,
                    )
                )
            bound[name] = ref
            bindings.append(
                {"named_range": name, "source_output": refs[ref].source_output, "figure_ref": ref}
            )

        unmapped = [
            {"named_range": str(u["named_range"]), "why": str(u["why"])}
            for u in proposal["unmapped_template_inputs"]
            if str(u["named_range"]) not in bound
        ]
        listed = {u["named_range"] for u in unmapped}
        for name in inputs.required:
            if name not in bound and name not in listed:
                unmapped.append({"named_range": name, "why": "not in the proposal"})

        routed = set(bound.values())
        unrouted = [
            {"figure_ref": str(u["figure_ref"]), "why": str(u["why"])}
            for u in proposal["unrouted_upstream_figures"]
            if str(u["figure_ref"]) not in routed
        ]
        named = {u["figure_ref"] for u in unrouted}
        for ref in refs:
            if ref not in routed and ref not in named:
                unrouted.append({"figure_ref": ref, "why": "not in the proposal"})

        return {
            "schema_version": CONTRACT,
            "produced_by": PRODUCED_BY,
            "template_mapping": {
                "template_version": inputs.template_version,
                "bindings": bindings,
                "unmapped_template_inputs": unmapped,
                "unrouted_upstream_figures": unrouted,
            },
        }


def inputs_from(
    template_key: str,
    template_version: str,
    schema_rows: Iterable[Mapping[str, Any]],
    catalogue: Iterable[FigureRef],
    periods: Iterable[str] = (),
) -> ModelLoadInputs:
    return ModelLoadInputs(
        template_key=template_key,
        template_version=template_version,
        inputs=tuple(
            TemplateInput(str(r["name"]), str(r["line"]), str(r["period"]), bool(r["required"]))
            for r in schema_rows
        ),
        catalogue=tuple(catalogue),
        periods=tuple(periods),
    )
