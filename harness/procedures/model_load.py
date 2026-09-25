"""The mechanical half of model-load.

What the model sees is the template's declared inputs and a catalogue of figure refs -
names, lines, periods, never a value. What comes back is a routing. What this module
does with it is check every claim before it is a mapping: every destination is one the
pinned template declares (read through the gated `template_schema_lookup`, so the
version is the run's pin), every figure ref is one the catalogue holds, no input is
bound twice, **every binding's figure is from the period its cell asks for**, and every
required input is either bound or listed as unmapped. The Model Builder then resolves the
figures and the Template Writer performs every write; this skill writes no cell and
originates no figure.

**What is checked here, and what is not.** The period is arithmetic: the template says
`FY1` and the catalogue says `FY1`, and a mismatch is a figure from the wrong year, which
passes every check after this one - the Numeric Integrity Lock is a multiset, so two
transposed years leave its difference empty and every total still re-adds.

The **line is not checked, and cannot be**. The template says `Cost of sales`; this
client's own income statement says `Costs of Goods Sold`; the next one will say something
else again. Deciding that those are the same line is the work this skill exists to do, and
a string comparison would refuse every correct mapping it was ever given. So the line is
the model's judgement, unverified by anything deterministic - which is why an unfilled
input reaches a person (`unmapped_inputs_require_review`) and why the delivered workbook
prints the document and row each figure came from beside it (P115). A wrong line is meant
to be *seen*, and the Source column is where it is seen: on the first real client folder,
"Revenue" sourced from the Balance Sheet was obvious at a glance and would have been
invisible the day before.

Tying the line to something checkable is possible and is not built: the tagging step
already assigns every line a taxonomy category, a person reviews it, and model-load never
sees it (backlog).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from harness.procedures.payload import as_payload
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

SLOT_FOR_A_BENCHMARK = "as_of"
"""The period slot a figure carried over from the engagement profile sits in.

Not a fiscal year, and the template says so: `Owner_Comp_Benchmark` declares
`period: as_of`. Named here because the catalogue and the template have to agree about
it, and two spellings of one slot is how they would stop agreeing."""


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
    period_slots: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    """Which of the client's fiscal years fills each slot, as (label, slot) pairs.

    Stated to the model rather than left to be inferred. The catalogue is keyed on slots
    - `timing:Revenue:FY1` - and until P121 nothing said which year FY1 was, so the model
    was asked to route figures into cells whose meaning it had to guess. The same shape of
    omission as P110's fiscal calendar, and the same fix: say it."""

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
    years - and it maps the ref's own name too, so one row says one thing about its
    period. Which year each slot is is stated in the payload (P121); a year the template
    has no slot for keeps its own label and stays visible as itself."""
    table = timing_output["normalized_historicals"]
    by_end = {p["end"]: p["label"] for p in table["periods"]}
    slots = dict(period_slots or {})
    refs: list[FigureRef] = []
    for entry in table["line_items"]:
        label = str(entry["canonical_label"])
        for figure in entry.get("values", []):
            year = by_end.get(figure["period"]["end"], figure["period"]["end"])
            # The ref is named for the client's own year and `period` carries the slot the
            # template asks for. They are deliberately different things: the ref is an
            # identity - `timing:Revenue:FY2023` says which figure this is, in the
            # client's terms, wherever it ends up - and the period is where it goes. What
            # was missing was never a shared spelling but a statement of which year each
            # slot is, and that is in the payload now (P121).
            refs.append(
                FigureRef(
                    figure_ref=f"timing:{label}:{year}",
                    source_output="timing",
                    description=label,
                    period=slots.get(year, year),
                    figure=figure,
                )
            )
    baseline = (profile or {}).get("owner_compensation_baseline")
    if isinstance(baseline, Mapping) and baseline.get("amount") is not None:
        # The slot the template names, not the date the profile recorded. `period` is the
        # template's own vocabulary everywhere else in this catalogue - `period_slots`
        # turns FY2023 into FY1 for exactly that reason - and this one row carried a date
        # instead, so the two could not be compared. The date is not lost: it is the one
        # thing about this figure a reader wants, so it moves into the description, where
        # the model sees it and where it is not being asked to match anything.
        as_of = str(baseline.get("as_of") or "")
        refs.append(
            FigureRef(
                figure_ref="profile:owner_compensation_baseline",
                source_output="profile",
                description=(
                    f"Owner-compensation benchmark (as of {as_of})"
                    if as_of
                    else "Owner-compensation benchmark"
                ),
                period=SLOT_FOR_A_BENCHMARK,
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
        """Template inputs, the catalogue, and which year each slot is. Names, lines and
        periods; no values."""
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
            # Which of the client's own years each slot is. The catalogue below is keyed
            # on slots and the template asks for slots, and until this line existed
            # nothing said what a slot meant - so a figure could be routed into FY1
            # without anybody, model or reader, knowing which year that was.
            "period_slots": {slot: label for label, slot in inputs.period_slots},
            "catalogue": [f.as_row() for f in inputs.catalogue],
        }
        return as_payload(body)

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
            # The period the cell asks for against the period the figure carries. Both
            # were in the payload and neither was read, and downstream there is nothing
            # that could tell: the Numeric Integrity Lock is a multiset, so transposing
            # two fiscal years leaves its difference empty, every total re-adds and the
            # provenance is impeccable. Arithmetic, not judgement - so it is refused here
            # rather than raised as something for a person to weigh up.
            wanted, offered = str(declared[name]["period"]), str(refs[ref].period)
            if wanted != offered:
                raise ProposalRefused(
                    diagnose(
                        UNKNOWN_LINE_ITEM,
                        f"{name} is the {wanted} cell and {ref!r} is a {offered} figure; "
                        f"a figure from the wrong year passes every check after this one",
                        locator=name,
                        expected=wanted,
                        found=offered,
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
    period_slots: Iterable[tuple[str, str]] = (),
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
        period_slots=tuple(period_slots),
    )
