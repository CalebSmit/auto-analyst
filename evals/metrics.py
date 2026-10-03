"""The metrics behind the gates, one function per shipped skill.

Each runs the skill's own mechanical half over the skill's golden fixtures - the same
procedures, tools and guards a run uses, through the gated runtime - and returns the
named numbers `gates.yaml` compares. The model's half is the fixture's replayed
proposal, so the numbers say what the code does with a proposal, and the fixture's
README says where the proposal came from.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from deliver.registry import TemplateInputs
from evals.world import TEMPLATE_KEY, EvalWorld
from guards.provenance import ProvenanceGate
from guards.tieout import TieoutGate
from harness.procedures.ebitda_normalization import EbitdaInputs, EbitdaNormalization
from harness.procedures.line_item_tagging import LineItem, LineItemTagging, TaggingInputs
from harness.procedures.model_load import (
    PRODUCED_BY as MODEL_LOAD_PRODUCED_BY,
)
from harness.procedures.model_load import (
    PROPOSAL_CONTRACT as MODEL_LOAD_PROPOSAL,
)
from harness.procedures.model_load import (
    ModelLoad,
    catalogue_from,
    inputs_from,
)
from harness.restate import amount_of
from review import CheckpointPolicy, ConfidenceRouter, Item, Money, Route
from tools.normalize import timing_normalizer
from tools.recompute import recompute

__all__ = ["METRICS", "FIXTURES_ROOT", "MetricFn"]

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "skills"
MetricFn = Callable[[EvalWorld], dict[str, float]]

# The historical table's lines against the ESOP template's inputs, for model-load's
# fixture. Officer bonus and the one-off lines have no template line and are unrouted.
LINE_TO_INPUT = {
    "Revenue": "Revenue",
    "Cost of sales": "COGS",
    "Officer salary": "Officer_Comp",
    "Wages": "Wages",
    "Payroll taxes": "Payroll_Taxes",
    "Rent - facilities": "Rent",
    "Repairs and maintenance": "Repairs",
    "Utilities": "Utilities",
    "Insurance": "Insurance",
    "Professional fees": "Professional_Fees",
    "Depreciation": "Depreciation",
    "Travel": "Travel",
    "Office supplies": "Office",
    "Charitable contributions": "Other_Opex",
}
SLOTS = {"FY2023": "FY1", "FY2024": "FY2", "FY2025": "FY3"}


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------ timing-normalization


def timing_metrics(world: EvalWorld) -> dict[str, float]:
    cases = FIXTURES_ROOT / "timing-normalization" / "cases"
    figures = tied = placed = rows = unmatched_ok = cases_n = 0
    for folder in sorted(cases.iterdir()):
        proposal_path = folder / "proposal.json"
        if not proposal_path.is_file():
            continue  # the ambiguous case escalates before any tool runs
        case = _json(folder / "case.json")
        proposal = _json(proposal_path)
        sources = {f["source_id"]: f["blocks"] for f in case["files"]}
        files = {
            f["source_id"]: {
                "scale": f["scale"],
                "currency": f["currency"],
                "source_version": f.get("source_version", 1),
            }
            for f in case["files"]
        }
        run = world.write_blocks(case["files"], run_id=f"eval_timing_{folder.name}")
        out = timing_normalizer(proposal, sources, files, "eval")["output"]
        result = TieoutGate(world.parse_store, recompute, 0.0).check(out, run)
        figures += result.checked
        tied += result.checked - result.failed
        total_rows = sum(
            len([r for r in block if r.get("value") is not None])
            for f in case["files"]
            for block in f["blocks"].values()
        )
        placed_here = sum(len(i["sources"]) for i in proposal["line_items"])
        rows += total_rows
        placed += placed_here
        unmatched_ok += int(len(out["alignment_report"]["unmatched"]) == total_rows - placed_here)
        cases_n += 1
    return {
        "arithmetic_agreement": tied / figures if figures else 0.0,
        "line_item_match_rate": placed / rows if rows else 0.0,
        "unmatched_reported": unmatched_ok / cases_n if cases_n else 0.0,
        "cases": float(cases_n),
    }


# ------------------------------------------------------------ line-item-tagging


def tagging_metrics(world: EvalWorld) -> dict[str, float]:
    root = FIXTURES_ROOT / "line-item-tagging"
    items = [
        LineItem(
            line_item_ref=i["line_item_ref"],
            description=i["description"],
            source_labels=tuple(i["source_labels"]),
            statement_hint=i["statement_hint"],
            periods=tuple(i["periods"]),
        )
        for i in _json(root / "items.json")
    ]
    gold = _json(root / "gold.json")
    batches = _json(root / "proposals.json")
    procedure = LineItemTagging()
    tagged: list[dict[str, Any]] = []
    given = {i.line_item_ref: i.description for i in items}
    for n, batch in enumerate(batches):
        chunk = items[n * 20 : (n + 1) * 20]
        inputs = TaggingInputs(
            items=tuple(chunk),
            taxonomy_version="coa-taxonomy@1.0.0",
            auto_accept_confidence=0.85,
        )
        out = procedure.apply(
            batch, world.tools_for("line-item-tagging@0.1.0", f"tagging:{n}"), inputs, "eval"
        )
        tagged.extend(out["tagged_line_items"])
    agree = sum(1 for t in tagged if t["category"] == gold[t["line_item_ref"]]["category"])
    provenance_failures = sum(
        1
        for t in tagged
        if given.get(t["line_item_ref"]) != t["description"] or t["precedent_ref"] is not None
    )
    flags = sum(
        1
        for t in tagged
        if t["category"] == gold[t["line_item_ref"]]["category"]
        and t["excluded_from_al"] == gold[t["line_item_ref"]]["excluded_from_al"]
        and t["include_in_nwc"] == gold[t["line_item_ref"]]["include_in_nwc"]
    )
    return {
        "top1_agreement": agree / len(items),
        "provenance_failures": float(provenance_failures),
        "flags_agreement": flags / len(items),
        "items": float(len(items)),
    }


# ------------------------------------------------------------ ebitda-normalization


def _henderson(
    world: EvalWorld,
) -> tuple[dict[str, Any], dict[str, Any], EbitdaInputs, CheckpointPolicy]:
    folder = FIXTURES_ROOT / "ebitda-normalization" / "cases" / "henderson"
    case = {p.stem: _json(p) for p in folder.glob("*.json")}
    profile = case["profile"]
    policy = CheckpointPolicy.from_profile(profile, world.constraints)
    sources = {f["source_id"]: f["blocks"] for f in case["case"]["files"]}
    files = {
        f["source_id"]: {
            "scale": f["scale"],
            "currency": f["currency"],
            "source_version": f.get("source_version", 1),
        }
        for f in case["case"]["files"]
    }
    world.write_blocks(case["case"]["files"], run_id="eval_henderson")
    timing = timing_normalizer(case["timing_proposal"], sources, files, "eval")["output"]
    inputs = EbitdaInputs.from_outputs(
        timing,
        case["tagging"],
        profile,
        sources,
        materiality_amount=policy.materiality.amount,
        materiality_currency=policy.materiality.currency,
        auto_accept_confidence=policy.auto_accept_confidence,
        always_review_categories=policy.always_review_categories,
    )
    return case, timing, inputs, policy


def ebitda_metrics(world: EvalWorld) -> dict[str, float]:
    from harness.procedures.line_item_tagging import line_item_ref
    from registries.scopes import ScopeRegistry

    case, _, inputs, policy = _henderson(world)
    out = EbitdaNormalization().apply(
        case["proposal"], world.tools_for("ebitda-normalization@0.1.0", "ebitda"), inputs, "eval"
    )
    schedule = out["addback_schedule"]
    tieout = TieoutGate(world.parse_store, recompute, 0.0).check(out, "eval_henderson")
    tied = sum(1 for i in schedule if i["recomputed"]) if tieout.passed else 0
    proposed = {
        (i["line_item_ref"], i["amount"]["period"]["end"][:4], i["category"])
        for i in schedule
        if not (i["recurs_in_all_periods"] and i["category"] == "non_recurring")
    }
    gold = {(line_item_ref(g["label"]), g["period"][2:], g["category"]) for g in case["gold"]}
    router = ConfidenceRouter(policy, ScopeRegistry.load())
    auto_accepted = 0
    for i in schedule:
        if not i["above_materiality"]:
            continue
        figure = i["amount"]
        item = Item(
            item_id=i["candidate_id"],
            skill="ebitda-normalization@0.1.0",
            question="eval",
            source_excerpt="eval",
            proposal=i,
            confidence=0.99,
            amount=Money(
                amount_of(figure, i["candidate_id"], unit="currency").number, figure["currency"]
            ),
            category=i["category"],
            review_required=False,
        )
        if router.route(item, "material_addbacks_require_review").route is Route.AUTO_ACCEPT:
            auto_accepted += 1
    traps = [i for i in schedule if i["recurs_in_all_periods"] and i["category"] == "non_recurring"]
    # Every figure this skill emits carries a locator, so provenance has something to say
    # about all of them - and until P86 it was never asked. `sources` is the case's own
    # intake manifest, which is what a run would give the gate.
    return {
        "tie_rate": tied / len(schedule) if schedule else 0.0,
        "recall": len(gold & proposed) / len(gold) if gold else 0.0,
        "material_auto_accepted": float(auto_accepted),
        "recurring_flagged": (
            sum(1 for t in traps if t["review_required"]) / len(traps) if traps else 1.0
        ),
        "items": float(len(schedule)),
        **kinds_of_wrong(
            world,
            out,
            {f["source_id"]: f.get("source_version", 1) for f in case["case"]["files"]},
            "eval_henderson",
            sent_to_a_person=sum(1 for i in schedule if i["review_required"]),
            items=len(schedule),
        ),
    }


# ------------------------------------------------------------ model-load


def model_load_metrics(world: EvalWorld) -> dict[str, float]:
    case, timing, _, _ = _henderson(world)
    schema = TemplateInputs.load(TEMPLATE_KEY)
    catalogue = catalogue_from(timing, case["profile"], period_slots=SLOTS)
    inputs = inputs_from(
        TEMPLATE_KEY,
        schema.template_version,
        [i.as_row() for i in schema.inputs],
        catalogue,
        periods=("FY1", "FY2", "FY3"),
    )
    bindings, routed = [], set()
    for ref in catalogue:
        if ref.source_output == "profile":
            bindings.append({"named_range": "Owner_Comp_Benchmark", "figure_ref": ref.figure_ref})
        elif ref.description in LINE_TO_INPUT:
            bindings.append(
                {
                    "named_range": f"{LINE_TO_INPUT[ref.description]}_{ref.period}",
                    "figure_ref": ref.figure_ref,
                }
            )
        else:
            continue
        routed.add(ref.figure_ref)
    proposal = {
        "schema_version": MODEL_LOAD_PROPOSAL,
        "produced_by": MODEL_LOAD_PRODUCED_BY,
        "bindings": bindings,
        "unmapped_template_inputs": [],
        "unrouted_upstream_figures": [
            {"figure_ref": r.figure_ref, "why": "no template line"}
            for r in catalogue
            if r.figure_ref not in routed
        ],
    }
    out = ModelLoad().apply(proposal, world.tools_for("model-load@0.1.0", "model"), inputs, "eval")
    mapping = out["template_mapping"]
    bound = {b["named_range"] for b in mapping["bindings"]}
    reported = {u["named_range"] for u in mapping["unmapped_template_inputs"]}
    accounted = sum(1 for n in schema.required if n in bound or n in reported)
    outside = sum(1 for n in bound if n not in schema.declared)
    return {
        "inputs_mapped_or_reported": accounted / len(schema.required),
        "writes_outside_schema": float(outside),
        "unmapped": float(len(reported)),
    }


METRICS: dict[str, MetricFn] = {
    "timing-normalization": timing_metrics,
    "line-item-tagging": tagging_metrics,
    "ebitda-normalization": ebitda_metrics,
    "model-load": model_load_metrics,
}


def provenance_of(
    world: EvalWorld,
    output: dict[str, Any],
    versions: dict[str, int],
    run_id: str | None = None,
) -> int:
    """Figures in an output the provenance gate faults.

    The real gate, on the real parse store, rather than a second opinion written beside
    it. Until P86 this was exposed and called by nothing - the one entry on P82's
    allowlist that was a defect and not a decision - so a candidate skill could promote
    while faulting provenance, which is the gate that decides whether a figure is really
    in the document it cites.
    """
    result = ProvenanceGate(world.contracts, world.parse_store).check(
        output, run_id or world.run_id, versions
    )
    return result.failed


def kinds_of_wrong(
    world: EvalWorld,
    output: dict[str, Any],
    versions: dict[str, int],
    run_id: str,
    *,
    sent_to_a_person: int,
    items: int,
) -> dict[str, float]:
    """The three ways an output can be wrong, told apart by the guards that decide them.

    An agreement rate says how often a skill was right and nothing about how it was wrong,
    and the two failures below are repaired in different places: a locator that does not
    resolve is an extraction problem, and a total that does not re-add is an arithmetic
    one. LAVA (arXiv 2608.16763) separates the same two on financial documents and reports
    the second near zero by having the model produce a formula and a deterministic engine
    execute it - which is what this build already does, and had never measured.

    * `fabricated_evidence` - the Provenance Gate's verdict: a cited source or locator
      that is not there, or a value that is not at it.
    * `numeric_infidelity` - the Tie-Out Gate's: evidence that resolves and arithmetic
      that does not re-add. Counted from the gate's mismatches rather than from its pass
      flag, which said only that something somewhere disagreed.
    * `sent_to_a_person` - what neither settled. Not a failure and not free: it is the
      work the analyst still does, and a skill that routes everything is a skill that
      agrees with the gold set by not answering.

    The first two are gated at zero in `gates.yaml`, which is not a threshold somebody
    should be asked to set: a figure whose locator does not resolve is not a worse figure,
    it is not a figure, and a recompute either falls inside the practice's tolerance or
    does not. The third is reported and deliberately not gated - on the Henderson fixture
    it is 0.61, eleven of eighteen add-backs, and whether that is a good number is the
    pilot's question. It is owed in BUILD/OPEN.md rather than defaulted here.
    """
    tieout = TieoutGate(world.parse_store, recompute, 0.0).check(output, run_id)
    fabricated = provenance_of(world, output, versions, run_id=run_id)
    return {
        "fabricated_evidence": float(fabricated),
        "numeric_infidelity": float(tieout.failed),
        "sent_to_a_person": float(sent_to_a_person),
        "fabricated_evidence_rate": fabricated / items if items else 0.0,
        "numeric_infidelity_rate": tieout.failed / items if items else 0.0,
        "sent_to_a_person_rate": sent_to_a_person / items if items else 0.0,
    }
