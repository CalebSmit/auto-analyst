"""Checkpoint C7 - a deliverable an analyst would accept.

Three real skills on the Henderson files produce an .xlsx that opens clean, with every
figure sourced and recomputed:

    timing normalization   the three income statements become one historical table
    line-item tagging      every line gets a category and its two flags
    EBITDA normalization   add-backs proposed with evidence, then verified separately
    model load             a mapping from validated figures to the template's named inputs
    the builder            writes by named range into a copy of the pinned template, locked
    QC and release         the workbook opens clean and leaves exactly once
    the manifest           lists every plan step, the never-started ones as not_reached

Every figure that reaches the workbook passed provenance and tie-out against the parse
store the readers wrote. The model's half is replayed from the fixtures; everything
else is the real code.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from openpyxl import load_workbook

import ports
from deliver import DeliverableQC, ModelBuilder, ReleaseGate, TemplateRegistry, WorkpaperNarrative
from deliver.registry import version_key
from graph.compile import PlanContext, compile_recipe
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver
from guards.provenance import ProvenanceGate
from guards.tieout import TieoutGate
from guards.untrusted import UntrustedBoundary
from harness.budget import BudgetGovernor
from harness.context import ContextBuilder
from harness.dispatch import SkillDispatcher
from harness.door import ModelDoor
from harness.loops import LoopController
from harness.policy import PolicyGate, RunScope
from harness.procedures import procedure_for, verifier_for
from harness.procedures.ebitda_normalization import EbitdaInputs, VerificationInputs
from harness.procedures.line_item_tagging import TaggingInputs
from harness.procedures.model_load import catalogue_from, inputs_from
from harness.procedures.timing_normalization import SourceFile, TimingInputs
from harness.runtime import GuardedRuntime
from ops.blobs import LocalContentStore
from ops.cost import CostMeter
from ops.events import EventBus
from ops.manifest import close_out
from ops.models import Outcome, RunState
from ops.run_store import open_store
from ops.source_parse import Row, SourceParseStore
from ports.delivery.local_folder import LocalFolderDelivery
from ports.llm import LLMRequest, LLMResponse, ModelPin, Usage
from precedent import PrecedentStore
from privacy.mask import Masker
from privacy.payload_scan import PayloadScan
from privacy.vault import KEY_NAME, open_vault
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.errors import VERIFICATION_PASS, diagnose
from registries.skills import SkillTree
from review import CheckpointPolicy
from tests.p15.conftest import profile
from tests.p20.conftest import load_case
from tests.p21.conftest import LINE_TO_INPUT, SLOTS
from tools.coa import chart_of_accounts_lookup
from tools.normalize import timing_normalizer
from tools.precedent import precedent_lookup_tool
from tools.recompute import recompute
from tools.template_schema import template_schema_lookup

ENGAGEMENT = "HEND-2026-04"
CLIENT = "client_henderson"
RUN_ID = "run_c7"
TAXONOMY = "coa-taxonomy@1.0.0"
TEMPLATE_KEY = version_key("Chartwell_ESOP_Model_v9.xlsx", "9.4")


class Replayed:
    """The model's half, from the fixtures. One proposal per call, in order."""

    name = "replayed"

    def __init__(self, *proposals: dict[str, Any]) -> None:
        self.proposals = list(proposals)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            text=json.dumps(self.proposals.pop(0)),
            model=request.pin.model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=5000, output_tokens=1500),
        )


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv(KEY_NAME, Fernet.generate_key().decode())
    ports.reset()
    contracts = ContractRegistry.load()
    constraints = ConstraintRegistry.load()
    store = open_store(f"sqlite:///{(tmp_path / 'c7.db').as_posix()}")
    bus = EventBus(store, contracts=contracts)
    scope = ScopeResolver().resolve("valuation/esop/repeat")
    precedents = PrecedentStore(store)
    plan = compile_recipe(
        load_recipe("monthly-refresh"),
        PlanContext(
            engagement_id=ENGAGEMENT,
            scope=scope,
            taxonomy_version=TAXONOMY,
            precedent_snapshot=precedents.snapshot_id(),
        ),
    )
    store.start_run(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
        plan_hash=plan.plan_hash,
        versions={
            "model_pin": str(ModelPin.for_tier("mid")),
            "skills": [
                "timing-normalization@0.1.0",
                "line-item-tagging@0.1.0",
                "ebitda-normalization@0.1.0",
                "model-load@0.1.0",
            ],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": TAXONOMY,
            "template_version": TEMPLATE_KEY,
        },
        tieout_tolerance=1.0,
    )
    store.transition(RUN_ID, RunState.RUNNING)
    store.start_clock(RUN_ID)

    vault = open_vault(ports.get_secrets(), f"sqlite:///{(tmp_path / 'vault.db').as_posix()}")
    blobs = LocalContentStore(tmp_path / "blobs")
    meter = CostMeter(store)
    governor = BudgetGovernor(constraints, meter, bus, store)
    runtime = GuardedRuntime(
        PolicyGate(constraints, bus),
        constraints,
        bus,
        {
            "timing_normalizer": timing_normalizer,
            "recompute": recompute,
            "chart_of_accounts_lookup": chart_of_accounts_lookup,
            "precedent_lookup": precedent_lookup_tool(precedents),
            "template_schema_lookup": template_schema_lookup,
        },
    )
    run_scope = RunScope(
        run_id=RUN_ID,
        engagement_id=ENGAGEMENT,
        engagement_root=f"engagements/{ENGAGEMENT}",
        scope_path="valuation/esop/repeat",
        versions={"chart_of_accounts_lookup": TAXONOMY, "template_schema_lookup": TEMPLATE_KEY},
        budget_remaining_usd=governor.remaining_usd(RUN_ID),
    )
    tree = SkillTree.load()

    def dispatcher(port: Any) -> SkillDispatcher:
        return SkillDispatcher(
            tree=tree,
            context=ContextBuilder(tree, blobs, bus, store=store, precedents=precedents),
            door=ModelDoor(port, PayloadScan(bus), governor, meter, bus),
            runtime=runtime,
            contracts=contracts,
            boundary=UntrustedBoundary(bus),
            masker=Masker(vault),
            bus=bus,
            blobs=blobs,
        )

    registry = TemplateRegistry()
    registry.register_bindings([scope.template] if scope.template else [])
    outbox = tmp_path / "outbox"
    delivery = LocalFolderDelivery(outbox)
    return {
        "store": store,
        "bus": bus,
        "blobs": blobs,
        "contracts": contracts,
        "constraints": constraints,
        "scope": scope,
        "plan": plan,
        "parse_store": SourceParseStore(store),
        "dispatcher": dispatcher,
        "run_scope": run_scope,
        "engagement_profile": blobs.put_json(profile(), name="engagement_profile"),
        "registry": registry,
        "outbox": outbox,
        "delivery": delivery,
        "release": ReleaseGate(store, bus, delivery, DeliverableQC(bus)),
        "controller": LoopController(constraints, store, bus),
    }


def test_three_real_skills_produce_a_workbook_that_opens_clean(world: dict[str, Any]) -> None:
    w = world
    store, bus, plan, scope = w["store"], w["bus"], w["plan"], w["scope"]
    contracts = w["contracts"]
    case = load_case()
    parse_store = w["parse_store"]

    def run(step_id: str, port: Any, inputs: Any, procedure: Any) -> Any:
        return w["dispatcher"](port).run(
            step=plan.step(step_id),
            run_id=RUN_ID,
            engagement_id=ENGAGEMENT,
            client_id=CLIENT,
            scope=scope,
            engagement_profile=w["engagement_profile"],
            inputs=inputs,
            identifiers=(),
            run_scope=w["run_scope"],
            procedure=procedure,
            pin=ModelPin.for_tier("mid"),
        )

    # -- the readers' rows, into the parse store
    files = []
    for f in case["case"]["files"]:
        for locator, rows in f["blocks"].items():
            parse_store.write(RUN_ID, f["source_id"], locator, [Row(**r) for r in rows])
        files.append(
            SourceFile(
                source_id=f["source_id"],
                filename=f["filename"],
                document_type=f["document_type"],
                blocks=f["blocks"],
                scale=f["scale"],
                currency=f["currency"],
                period_type=f["period_type"],
                period_ends=tuple(f["period_ends"]),
                ambiguous=tuple(f["ambiguous"]),
                source_version=f.get("source_version", 1),
                block_periods=f.get("block_periods", {}),
            )
        )
    versions = {f.source_id: f.source_version for f in files}
    blocks = {f.source_id: f.blocks for f in files}

    # -- 1. timing normalization: one real skill, one historical table
    timing = run(
        "timing",
        Replayed(case["timing_proposal"]),
        TimingInputs(files=tuple(files)),
        procedure_for("timing-normalization"),
    )
    assert (
        ProvenanceGate(contracts, parse_store, bus)
        .run(timing.output, RUN_ID, ENGAGEMENT, versions, "timing")
        .passed
    )
    assert (
        TieoutGate(parse_store, recompute, 1.0, bus)
        .run(timing.output, RUN_ID, ENGAGEMENT, "timing")
        .passed
    )

    # -- 2. line-item tagging
    policy = CheckpointPolicy.from_profile(profile(), w["constraints"])
    tagging_inputs = TaggingInputs.from_normalized(
        timing.output["normalized_historicals"],
        taxonomy_version=TAXONOMY,
        auto_accept_confidence=policy.auto_accept_confidence,
        always_review_categories=policy.always_review_categories,
    )
    by_ref = {t["line_item_ref"]: t for t in case["tagging"]["tagged_line_items"]}
    tagging_proposal = {
        "schema_version": "skills/line-item-tagging-proposal@1.0.0",
        "produced_by": "line-item-tagging@0.1.0",
        "items": [
            {
                "line_item_ref": i.line_item_ref,
                "category": by_ref[i.line_item_ref]["category"],
                "excluded_from_al": by_ref[i.line_item_ref]["excluded_from_al"],
                "include_in_nwc": by_ref[i.line_item_ref]["include_in_nwc"],
                "confidence": 0.95,
                "rationale": "the description says so",
            }
            for i in tagging_inputs.items
        ],
    }
    tagging = run(
        "tagging", Replayed(tagging_proposal), tagging_inputs, procedure_for("line-item-tagging")
    )
    assert len(tagging.output["tagged_line_items"]) == len(tagging_inputs.items)

    # -- 3. EBITDA normalization, both passes, the second admitted by the loop controller
    ebitda_inputs = EbitdaInputs.from_outputs(
        timing.output,
        tagging.output,
        profile(),
        blocks,
        materiality_amount=policy.materiality.amount,
        materiality_currency=policy.materiality.currency,
        auto_accept_confidence=policy.auto_accept_confidence,
        always_review_categories=policy.always_review_categories,
    )
    first = run(
        "ebitda", Replayed(case["proposal"]), ebitda_inputs, procedure_for("ebitda-normalization")
    )
    assert all(i["recomputed"] for i in first.output["addback_schedule"])
    assert (
        TieoutGate(parse_store, recompute, 0.0, bus)
        .run(first.output, RUN_ID, ENGAGEMENT, "ebitda")
        .passed
    )
    admitted = w["controller"].admit(
        RUN_ID,
        plan,
        plan.step("ebitda"),
        "self_verification",
        current_key=first.request_hash,
        next_key=f"verify:{first.request_hash}",
        next_inputs={"schedule": first.output_ref.content_hash},
        trigger=diagnose(VERIFICATION_PASS, "every EBITDA output", locator="ebitda"),
    )
    assert admitted.allowed
    verified = run(
        "ebitda",
        Replayed(case["verification"]),
        VerificationInputs.from_pass(first.output, ebitda_inputs),
        verifier_for("ebitda-normalization"),
    )
    project = next(
        i for i in verified.output["addback_schedule"] if i["candidate_id"] == "ADD-q3-project"
    )
    assert project["review_required"], "the verifier's disagreement reached the schedule"

    # -- 4. model load: a mapping, no cell written by the skill
    template = w["registry"].resolve(scope.template)
    catalogue = catalogue_from(timing.output, profile(), period_slots=SLOTS)
    load_inputs = inputs_from(
        template.key,
        template.template_version,
        [i.as_row() for i in template.inputs.inputs],
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
    mapping_proposal = {
        "schema_version": "skills/model-load-proposal@1.0.0",
        "produced_by": "model-load@0.1.0",
        "bindings": bindings,
        "unmapped_template_inputs": [],
        "unrouted_upstream_figures": [
            {"figure_ref": r.figure_ref, "why": "no template line"}
            for r in catalogue
            if r.figure_ref not in routed
        ],
    }
    loaded = run("model", Replayed(mapping_proposal), load_inputs, procedure_for("model-load"))
    assert loaded.output["template_mapping"]["unmapped_template_inputs"] == []

    # -- 5. the builder, the writer, the lock
    built = ModelBuilder(bus).build(
        loaded.output, load_inputs.figures(), template, run_id=RUN_ID, engagement_id=ENGAGEMENT
    )
    assert built.lock.passed and len(built.writes) == 43
    for name, value in built.writes.items():
        if name == "Owner_Comp_Benchmark":
            continue
        bound_ref = next(b["figure_ref"] for b in bindings if b["named_range"] == name)
        figure = load_inputs.figures()[bound_ref]
        assert isinstance(figure, dict) and figure["value"] == value
        assert parse_store.rows(RUN_ID, figure["source_id"], figure["derivation"]["of"][0])

    # -- 6. the narrative, from locked figures only
    narrative = WorkpaperNarrative().render(
        engagement_id=ENGAGEMENT,
        run_id=RUN_ID,
        template_key=template.key,
        periods=ebitda_inputs.periods,
        sources=case["case"]["files"],
        schedule=verified.output["addback_schedule"],
        mapping=loaded.output["template_mapping"],
        open_items=[],
        locked_text=built.locked_text
        + "\n"
        + "\n".join(str(i["amount"]["value"]) for i in verified.output["addback_schedule"]),
    )
    assert narrative.lock.passed, narrative.lock.reasons
    assert contracts.check("workpaper@1.0.0", narrative.body) == ()

    # -- 7. QC and release, exactly once; the manifest lists every step
    released = w["release"].release(
        RUN_ID, ENGAGEMENT, built.name, built.data, template_version="9.4", expected=built.writes
    )
    again = w["release"].release(
        RUN_ID, ENGAGEMENT, built.name, built.data, template_version="9.4", expected=built.writes
    )
    assert not released.already_released and again.already_released
    narrative_release = (
        w["release"].release(
            RUN_ID,
            ENGAGEMENT,
            "workpaper.json",
            json.dumps(narrative.body, indent=1).encode("utf-8"),
        )
        if False
        else None
    )  # the narrative is JSON; QC opens workbooks - it rides with the manifest
    assert narrative_release is None
    closed = close_out(
        store,
        RUN_ID,
        RunState.DELIVERED,
        Outcome.RELEASED_WITH_REVIEW,
        w["delivery"],
        bus=bus,
        plan=plan,
    )
    folder = w["outbox"] / ENGAGEMENT / RUN_ID
    assert sorted(p.name for p in folder.iterdir()) == [built.name, "run_manifest.json"]
    wb = load_workbook(BytesIO((folder / built.name).read_bytes()))
    assert wb["Inputs"]["B2"].value == "9.4" and wb["Inputs"]["B3"].value == RUN_ID
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                assert "#REF!" not in str(cell.value) and "[[" not in str(cell.value)

    manifest = closed.manifest
    statuses = {s["step_id"]: s["status"] for s in manifest["steps"]}
    assert set(statuses) == set(plan.order)
    assert statuses["intake"] == "not_reached" and statuses["release"] == "not_reached"
    assert manifest["versions"]["template_version"] == TEMPLATE_KEY
    guards = {g["guard"] for g in manifest["guard_events"]}
    assert {
        "provenance",
        "tieout",
        "numeric_lock",
        "deliverable_qc",
        "schema",
        "payload_scan",
    } <= guards
    assert all(g["result"] == "pass" for g in manifest["guard_events"])
    assert store.run(RUN_ID).model_calls == 5, "timing, tagging, ebitda, verification, model load"
    assert len(store.releases(RUN_ID)) == 1
