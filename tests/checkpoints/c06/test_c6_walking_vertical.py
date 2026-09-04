"""C6 - The walking vertical.

Proves: watched folder to masked payload to one real skill to guards to review to local
output, on one real engagement.

One engagement, one sweep, one run, one skill, one manifest on disk:

    watched folder   two income statements and a trial balance land in the inbox
    intake           the roster admits the engagement; the window releases one run
    readers          every file into the Source Parse Store, classified and timed
    masked payload   a person's name in a row label leaves as a token, never as text
    one real skill   timing-normalization proposes the alignment; the tool does the sums
    guards           schema (in the dispatcher), provenance and tie-out over the parse
                     store, the numeric lock over the table as written
    review           the unmatched line is a review item; a named person decides it
    local output     the table and the manifest land in the outbox through the port

Everything from P01 to P18 together. The model's half is replayed from a proposal built
in this test from the rows the readers actually wrote; the tool's half is real. Written
at the end of P18 rather than at the checkpoint, per the phase file.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

import ports
from graph.compile import PlanContext, compile_recipe
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver
from guards.numeric_lock import NumericLock, as_text
from guards.provenance import ProvenanceGate
from guards.tieout import TieoutGate
from guards.untrusted import UntrustedBoundary
from harness.budget import BudgetGovernor
from harness.context import ContextBuilder
from harness.dispatch import SkillDispatcher
from harness.door import ModelDoor
from harness.policy import PolicyGate, RunScope
from harness.procedures.timing_normalization import SourceFile, TimingInputs, TimingNormalization
from harness.runtime import GuardedRuntime
from intake import Intake
from intake.config import ConfigStore
from intake.launch import RunLauncher
from intake.lock import EngagementLock
from intake.readers import read_source
from intake.roster import ProjectRoster, RosterState
from intake.store import IntakeStore
from ops.blobs import LocalContentStore
from ops.cost import CostMeter
from ops.events import EventBus
from ops.manifest import close_out, manifest_path
from ops.models import DecisionKind, Outcome, RunState
from ops.run_store import open_store
from ops.source_parse import SourceParseStore
from ports.llm import LLMRequest, LLMResponse, ModelPin, Usage
from privacy.mask import Identifier, Masker
from privacy.payload_scan import PayloadScan
from privacy.vault import KEY_NAME, open_vault
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.skills import SkillTree
from review import CheckpointPolicy, ConfidenceRouter, Item, ReviewQueue, ReviewSurface
from tests.p15.conftest import profile
from tests.p16.conftest import HEND, HEND_FOLDER, WHO, Clock, config_document, drop, entry
from tests.p17.conftest import build_xlsx
from tools.normalize import timing_normalizer
from tools.recompute import recompute

ENGAGEMENT = HEND
CLIENT = "client_henderson"
OFFICER = "Robert Henderson"
PIN = ModelPin.for_tier("mid")

FY24 = [
    ["Henderson Manufacturing - Income Statement ($ in thousands) FY2024", None],
    ["Line", "FY2024"],
    ["Revenue", 4_401_900],
    ["Cost of sales", 2_688_400],
    ["Gross profit", 1_713_500],
    [f"Officer salary - {OFFICER}", 235_000],
    ["Rent", 96_000],
    ["Repairs & Maint.", 41_000],
    ["Net income", 1_341_500],
]
FY25 = [
    ["Henderson Manufacturing - Income Statement ($ in thousands) FY2025", None],
    ["Line", "FY2025"],
    ["Revenue", 4_812_300],
    ["Cost of sales", 2_905_100],
    ["Gross profit", 1_907_200],
    [f"Officer salary - {OFFICER}", 240_000],
    ["Rent", 96_000],
    ["Repairs and Maintenance", 44_100],
    ["Q3 special project", 14_200],
    ["Net income", 1_512_900],
]
TB = [
    ["Henderson Manufacturing - Trial Balance ($ in thousands) FY2025", None, None],
    ["Account", "Debit", "Credit"],
    ["Cash", 412_000, None],
    ["Revenue", None, 4_812_300],
]

STAGES = {
    "intake": {"intake_window", "engagement_lock"},
    "readers": {"source_parse"},
    "masked payload": {"payload_scan"},
    "one real skill": {"dispatcher", "context_builder", "llm_port", "guarded_runtime"},
    "guards": {
        "schema_gate",
        "provenance_gate",
        "tieout_gate",
        "numeric_lock",
        "untrusted_boundary",
    },
    "review": {"review_queue", "decision_log"},
    "local output": {"run_manifest"},
}


class ReplayedAnalyst:
    """The model's half, replayed: an alignment built from the rows the readers wrote."""

    name = "replayed"

    def __init__(self, proposal: dict[str, Any]) -> None:
        self.proposal = proposal
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            text=json.dumps(self.proposal),
            model=request.pin.model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=3000, output_tokens=700),
        )


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    inbox = tmp_path / "inbox"
    outbox = tmp_path / "outbox"
    inbox.mkdir()
    monkeypatch.setenv("AA_INBOX_ROOT", str(inbox))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(outbox))
    monkeypatch.setenv(KEY_NAME, Fernet.generate_key().decode())
    ports.reset()
    contracts = ContractRegistry.load()
    constraints = ConstraintRegistry.load()
    store = open_store(f"sqlite:///{(tmp_path / 'c6.db').as_posix()}")
    bus = EventBus(store, contracts=contracts)
    clock = Clock()
    config = ConfigStore(store, contracts, environment="local")
    config.write(config_document(), who=WHO, reason="C6")
    roster = ProjectRoster(store, config)
    roster.register(
        entry(HEND, HEND_FOLDER, RosterState.ACTIVE, "Henderson Manufacturing"),
        who=WHO,
        reason="C6",
    )
    intake_store = IntakeStore(store)
    lock = EngagementLock(store, bus, timeout=timedelta(hours=6), clock=clock)
    launcher = RunLauncher(store, bus, lock, intake_store, clock=clock)
    scope = ScopeResolver().resolve("valuation/esop/repeat")
    plan = compile_recipe(
        load_recipe("monthly-refresh"),
        PlanContext(
            engagement_id=ENGAGEMENT,
            scope=scope,
            taxonomy_version="coa-taxonomy@1.0.0",
            precedent_snapshot="precedent_snapshot_2026_09_01",
        ),
    )
    return {
        "inbox": inbox,
        "outbox": outbox,
        "store": store,
        "bus": bus,
        "clock": clock,
        "contracts": contracts,
        "constraints": constraints,
        "config": config,
        "roster": roster,
        "intake_store": intake_store,
        "lock": lock,
        "launcher": launcher,
        "scope": scope,
        "plan": plan,
        "intake": Intake(ports.get_storage(), roster, config, intake_store, launcher, clock=clock),
        "vault": open_vault(ports.get_secrets(), f"sqlite:///{(tmp_path / 'vault.db').as_posix()}"),
        "blobs": LocalContentStore(tmp_path / "blobs"),
        "tmp": tmp_path,
    }


def test_the_walking_vertical(world: dict[str, Any]) -> None:
    w = world
    store, bus, clock, plan, scope = w["store"], w["bus"], w["clock"], w["plan"], w["scope"]
    contracts, constraints, blobs = w["contracts"], w["constraints"], w["blobs"]

    # -- watched folder -> intake: three files land; the window releases one run
    folder = f"Clients/{HEND_FOLDER}"
    drop(w["inbox"], f"{folder}/Henderson income statement FY24.xlsx", build_xlsx({"IS": FY24}))
    drop(w["inbox"], f"{folder}/Henderson income statement FY25.xlsx", build_xlsx({"IS": FY25}))
    drop(w["inbox"], f"{folder}/TB_FY25.xlsx", build_xlsx({"TB": TB}))
    launch = {
        "plan_hash": plan.plan_hash,
        "versions": {
            "model_pin": str(PIN),
            "skills": ["timing-normalization@0.1.0"],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": "coa-taxonomy@1.0.0",
        },
    }
    first = w["intake"].sweep(launch)
    assert first.runs == [] and len(first.arrived) == 3
    clock.advance(minutes=31)
    (launched,) = w["intake"].sweep(launch).launched
    run_id = launched.run_id
    assert launched.lock.acquired and launched.sources == 3 and launched.gaps == ()
    assert store.run(run_id).state is RunState.QUEUED, "the lock grants; nothing is allocated yet"
    store.transition(run_id, RunState.RUNNING, reason="a worker holds it")  # this test is one

    # -- readers: every file into the parse store, classified and timed
    parse_store = SourceParseStore(store)
    boundary = UntrustedBoundary(bus)
    reports = {}
    for row in w["intake_store"].files(ENGAGEMENT):
        data = ports.get_storage().read(
            __import__("ports.storage", fromlist=["FileRef"]).FileRef(row.path)
        )
        reports[row.filename] = read_source(
            run_id,
            ENGAGEMENT,
            row,
            data,
            store=store,
            parse_store=parse_store,
            boundary=boundary,
            bus=bus,
        )
    statements = {
        n: r for n, r in reports.items() if r.classification.document_type == "financial_statements"
    }
    assert len(statements) == 2 and all(r.periods.scale == 1000 for r in statements.values())
    assert reports["TB_FY25.xlsx"].classification.document_type == "trial_balance"

    # -- the skill's inputs, from what the readers wrote
    files = []
    for name, report in sorted(statements.items()):
        blocks = {
            loc: [r.__dict__ for r in parse_store.block(run_id, report.source_id, loc)]
            for loc in report.locators
        }
        (block,) = blocks
        label = "FY2024" if "FY24" in name else "FY2025"
        files.append(
            SourceFile(
                source_id=report.source_id,
                filename=name,
                document_type="financial_statements",
                blocks=blocks,
                scale=1000,
                currency="USD",
                period_type="annual",
                period_ends=(f"{label[2:]}-12-31",),
                block_periods={block: label},
            )
        )
    inputs = TimingInputs(files=tuple(files))

    # -- the analyst's alignment, replayed: labels and locators, never a number
    def rows_of(f: SourceFile) -> tuple[str, list[dict[str, Any]]]:
        (block,) = f.blocks
        return block, f.blocks[block]

    def loc(block: str, ordinal: int) -> str:
        sheet, span = block.split("!")
        return f"{sheet}!{span[0]}{ordinal}"

    f24, f25 = files
    b24, r24 = rows_of(f24)
    b25, r25 = rows_of(f25)
    canon = {
        "Revenue": ("Revenue", "Revenue", "exact"),
        "Cost of sales": ("Cost of sales", "Cost of sales", "exact"),
        "Gross profit": ("Gross profit", "Gross profit", "exact"),
        "Officer salary": (r24[3]["label"], r25[3]["label"], "exact"),
        "Rent": ("Rent", "Rent", "exact"),
        "Repairs and Maintenance": ("Repairs & Maint.", "Repairs and Maintenance", "rename"),
        "Net income": ("Net income", "Net income", "exact"),
    }

    def source(f: SourceFile, rows: list[dict[str, Any]], block: str, label: str) -> dict[str, str]:
        r = next(x for x in rows if x["label"] == label)
        return {"source_id": f.source_id, "locator": loc(block, r["ordinal"]), "label": label}

    proposal = {
        "schema_version": "skills/timing-normalization-proposal@1.0.0",
        "produced_by": "timing-normalization@0.1.0",
        "periods": [
            {
                "label": "FY2024",
                "type": "FY",
                "end": "2024-12-31",
                "source_id": f24.source_id,
                "block": b24,
            },
            {
                "label": "FY2025",
                "type": "FY",
                "end": "2025-12-31",
                "source_id": f25.source_id,
                "block": b25,
            },
        ],
        "line_items": [
            {
                "canonical_label": c,
                "kind": kind,
                "sources": [source(f24, r24, b24, l24), source(f25, r25, b25, l25)],
            }
            for c, (l24, l25, kind) in canon.items()
        ],
        "unmatched": [
            {
                "source_id": f25.source_id,
                "locator": loc(
                    b25, next(x for x in r25 if x["label"] == "Q3 special project")["ordinal"]
                ),
                "label": "Q3 special project",
                "reason": "no counterpart in FY2024; a one-off project line",
            }
        ],
    }

    # -- masked payload -> one real skill, through the whole harness
    meter = CostMeter(store)
    governor = BudgetGovernor(constraints, meter, bus, store)
    runtime = GuardedRuntime(
        PolicyGate(constraints, bus), constraints, bus, {"timing_normalizer": timing_normalizer}
    )
    analyst = ReplayedAnalyst(proposal)
    dispatcher = SkillDispatcher(
        tree=SkillTree.load(),
        context=ContextBuilder(SkillTree.load(), blobs, bus, store=store),
        door=ModelDoor(analyst, PayloadScan(bus), governor, meter, bus),
        runtime=runtime,
        contracts=contracts,
        boundary=boundary,
        masker=Masker(w["vault"]),
        bus=bus,
        blobs=blobs,
    )
    run_scope = RunScope(
        run_id=run_id,
        engagement_id=ENGAGEMENT,
        engagement_root=f"engagements/{ENGAGEMENT}",
        scope_path="valuation/esop/repeat",
        versions={},
        budget_remaining_usd=governor.remaining_usd(run_id),
    )
    done = dispatcher.run(
        step=plan.step("timing"),
        run_id=run_id,
        engagement_id=ENGAGEMENT,
        client_id=CLIENT,
        scope=scope,
        engagement_profile=blobs.put_json(profile(), name="engagement_profile"),
        inputs=inputs,
        identifiers=(Identifier("PERSON", OFFICER),),
        run_scope=run_scope,
        procedure=TimingNormalization(),
        pin=PIN,
    )
    (request,) = analyst.requests
    assert OFFICER not in request.messages[0].content and OFFICER not in request.system
    assert "[[PERSON_" in request.messages[0].content, "the name left as a token"
    output = done.output
    assert len(output["alignment_report"]["matched"]) == 7
    assert [u["source_label"] for u in output["alignment_report"]["unmatched"]] == [
        "Q3 special project"
    ]

    # -- guards over the parse store the readers wrote
    versions = {f.source_id: 1 for f in files}
    assert (
        ProvenanceGate(contracts, parse_store, bus)
        .run(output, run_id, ENGAGEMENT, versions, "timing")
        .passed
    )
    assert (
        TieoutGate(parse_store, recompute, 1.0, bus)
        .run(output, run_id, ENGAGEMENT, "timing")
        .passed
    )
    table_text = as_text(output["normalized_historicals"])
    assert NumericLock(bus).run(table_text, table_text, run_id, ENGAGEMENT, "release").passed

    # -- review: the unmatched line reaches a person, and a person decides
    policy = CheckpointPolicy.from_profile(profile(), constraints)
    router = ConfidenceRouter(policy, bus=bus)
    item = Item(
        item_id="unmatched:q3",
        skill="timing-normalization",
        question="Q3 special project (FY2025) has no counterpart in FY2024. New line or a rename?",
        source_excerpt="IS!A9 Q3 special project  14,200",
        proposal={"treatment": "unmatched"},
        confidence=None,
        review_required=True,
        locator=proposal["unmatched"][0]["locator"],
    )
    routing = router.route(
        item,
        "ambiguous_periods_require_review",
        run_id=run_id,
        engagement_id=ENGAGEMENT,
        step_id="timing",
    )
    assert routing.needs_a_person
    ReviewQueue(store, bus, policy_for=lambda e: policy, clock=clock).enqueue(
        run_id, ENGAGEMENT, item, routing, step_id="timing"
    )
    surface = ReviewSurface(store, bus)
    assert surface.show(run_id, "unmatched:q3").question.startswith("Q3 special project")
    decision = surface.decide(
        run_id,
        "unmatched:q3",
        decided_by="Dana Whitfield",
        decision=DecisionKind.ACCEPTED,
        expected_version=1,
    )
    assert decision.writes_precedent

    # -- local output: the table and the manifest, through the delivery port
    delivery = ports.get_delivery()
    table = delivery.put(
        f"{ENGAGEMENT}/{run_id}/normalized_historicals.json",
        json.dumps(output, indent=1).encode("utf-8"),
    )
    store.record_artifact(
        run_id, "normalized_historicals.json", table.content_hash, path=table.path
    )
    w["lock"].release(ENGAGEMENT, run_id)
    closed = close_out(
        store, run_id, RunState.DELIVERED, Outcome.RELEASED_WITH_REVIEW, delivery, bus=bus
    )
    assert (w["outbox"] / manifest_path(ENGAGEMENT, run_id)).is_file()
    assert (w["outbox"] / table.path).is_file()
    manifest = closed.manifest
    assert {s["document_type"] for s in manifest["sources"]} == {
        "financial_statements",
        "trial_balance",
    }
    assert manifest["human_decisions"][0]["decided_by"] == "Dana Whitfield"
    assert manifest["outcome"] == "released_with_review"

    # -- every stage said so, on the record
    nodes = {e.node_id for e in store.events(run_id)}
    for stage, expected in STAGES.items():
        missing = expected - nodes
        assert not missing, f"stage {stage!r} did not emit from {sorted(missing)}"
    w["vault"].close()
    store.close()
