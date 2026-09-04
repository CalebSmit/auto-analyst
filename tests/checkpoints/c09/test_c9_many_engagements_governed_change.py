"""Checkpoint C9 - Many engagements, governed change.

Two halves of one evening, in order.

**A nightly sweep over several engagements completes.** Files arrive for three active
engagements and one paused one. One sweep plans, binds, fingerprints and launches; the
worker pool runs them, several at once, with the engagement lock still serialising within
each deal; every run ends with a manifest and a computed verdict, and the paused
engagement is never read.

**A skill ships through the full governance chain.** A rough draft with no frontmatter and
no fixtures is dropped, scanned, adapted, drafted in the sandbox, exercised, evaluated,
replayed, submitted, approved, shadowed against the runs that just happened, and only then
registered into the live tree. Remove any one of those and it does not ship - which is
proven one gate at a time in tests/p27; here the point is that the whole thing runs
together, on the same machine, in the same evening, over the same record.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

import ports
from evals.harness import EvalHarness
from evals.registration import SkillRegistration
from evals.world import EvalWorld
from governance import (
    AdaptationBench,
    ConformanceCheck,
    DropFolder,
    GovernanceChain,
    GovernanceRecord,
    Sandbox,
    SandboxTest,
    ShadowDeployment,
    SkillBoard,
    SkillRegistry,
)
from governance.adapt import GOVERNANCE_RUN, GOVERNANCE_SCOPE
from governance.candidate import STAGES, Stage
from harness.budget import BudgetGovernor
from harness.door import ModelDoor
from intake import Intake
from intake.config import ConfigStore
from intake.launch import RunLauncher
from intake.lock import EngagementLock
from intake.roster import ProjectRoster, RosterEntry, RosterState
from intake.store import IntakeStore
from ops.blobs import LocalContentStore
from ops.console import Console
from ops.cost import CostMeter
from ops.events import EventBus
from ops.manifest import close_out
from ops.models import Outcome, RunState
from ops.run_store import SqlRunStore, open_store
from privacy.payload_scan import PayloadScan
from privacy.vault import KEY_NAME
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from tests.p16.conftest import LAUNCH, Clock, Spy, config_document, drop
from tests.p27.conftest import (
    CASES,
    DROPPER,
    LAYER,
    OWNER,
    REVIEWER,
    ROUGH_DRAFT,
    SKILL,
    Dispatches,
    ScriptedPort,
    drop_draft,
)
from workers import WorkerPool

ACTIVE = (
    ("HEND-2026-04", "Henderson Manufacturing", "Henderson Manufacturing/2026 ESOP"),
    ("MERC-2026-02", "Mercer Foods", "Mercer Foods/2026 ESOP"),
    ("NOVK-2026-07", "Novak Industries", "Novak Industries/2026 ESOP"),
)
PAUSED = ("WSTF-2025-19", "Westfield Group", "Westfield Group/2025 ESOP")
WORKERS = 3


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    inbox = tmp_path / "inbox"
    (inbox / "Clients").mkdir(parents=True)
    (tmp_path / "outbox").mkdir()
    intake_root = tmp_path / "skills-intake"
    (intake_root / "_drop").mkdir(parents=True)
    monkeypatch.setenv("AA_INBOX_ROOT", str(inbox))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    monkeypatch.setenv("AA_SKILLS_INTAKE_ROOT", str(intake_root))
    monkeypatch.setenv("AA_MAX_PARALLELISM", str(WORKERS))
    monkeypatch.setenv("AA_QUEUE_ADAPTER", "in_process")
    monkeypatch.setenv(KEY_NAME, Fernet.generate_key().decode())
    ports.reset()

    contracts = ContractRegistry.load()
    constraints = ConstraintRegistry.load()
    store = open_store(f"sqlite:///{(tmp_path / 'c9.db').as_posix()}")
    bus = EventBus(store, contracts=contracts)
    clock = Clock()
    config = ConfigStore(store, contracts, environment="local")
    config.write(config_document(), who=OWNER, reason="C9")
    roster = ProjectRoster(store, config)
    for engagement_id, client, folder in ACTIVE:
        roster.register(_entry(engagement_id, client, folder, RosterState.ACTIVE),
                        who=OWNER, reason="engagement letter signed")
    roster.register(_entry(*PAUSED, RosterState.PAUSED), who=OWNER,
                    reason="client holding on the trial balance")

    intake_store = IntakeStore(store)
    port = Spy(ports.get_storage())
    lock = EngagementLock(store, bus, clock=clock)
    launcher = RunLauncher(store, bus, lock, intake_store, clock=clock)
    yield {
        "tmp": tmp_path,
        "inbox": inbox,
        "intake_root": intake_root,
        "store": store,
        "bus": bus,
        "clock": clock,
        "config": config,
        "roster": roster,
        "port": port,
        "lock": lock,
        "intake": Intake(port, roster, config, intake_store, launcher, clock=clock),
        "contracts": contracts,
        "constraints": constraints,
        "blobs": LocalContentStore(tmp_path / "blobs"),
    }
    store.close()


@pytest.fixture
def eval_world() -> Any:
    """The ephemeral world the eval harness scores in. Its own throwaway store, outside
    every engagement - the same one `gate eval` uses."""
    world = EvalWorld()
    yield world
    world.close()


def _entry(engagement_id: str, client: str, folder: str, state: RosterState) -> RosterEntry:
    return RosterEntry(
        engagement_id=engagement_id,
        client=client,
        scope_path="valuation/esop/repeat",
        watch_id="w-val",
        destination_id="d-local",
        state=state,
        folder=folder,
        template_pin="Chartwell_ESOP_Model_v9.xlsx@9.4",
        budget_usd=12.0,
    )


def test_a_nightly_sweep_completes_and_a_skill_ships_through_the_chain(
    world: dict[str, Any], eval_world: EvalWorld
) -> None:
    store: SqlRunStore = world["store"]
    bus: EventBus = world["bus"]
    clock: Clock = world["clock"]

    # ---- the sweep: files for three engagements, and one that is paused ----
    for _, _, folder in ACTIVE:
        drop(world["inbox"], f"Clients/{folder}/TB_FY25.xlsx", f"tb for {folder}")
        drop(world["inbox"], f"Clients/{folder}/income statement FY25.xlsx", f"is for {folder}")
    drop(world["inbox"], f"Clients/{PAUSED[2]}/TB_FY25.xlsx", "paused: never read")

    world["intake"].sweep(LAUNCH)
    clock.advance(minutes=31)
    launched = world["intake"].sweep(LAUNCH).launched
    assert {item.engagement_id for item in launched} == {e[0] for e in ACTIVE}
    assert all(item.sources == 2 for item in launched)
    assert not [p for p in world["port"].touched if PAUSED[1] in p], "paused: not read"

    # ---- the pool: several engagements at once, one run at a time within each ----
    passes: list[str] = []

    def one_pass(run_id: str) -> Any:
        passes.append(run_id)
        store.transition(run_id, RunState.RUNNING, reason="a worker holds it")
        store.record_step(run_id, "timing", "sha256:" + "11" * 32, "skill",
                          skill="timing-normalization@0.1.0")
        return _Report(run_id)

    pool = WorkerPool(store, bus, world["lock"], one_pass)
    assert pool.target.max_parallelism == WORKERS
    pool.submit_all([item.run_id for item in launched])
    pool.work()
    assert sorted(passes) == sorted(item.run_id for item in launched)

    delivery = ports.get_delivery()
    for item in launched:
        closed = close_out(store, item.run_id, RunState.HALTED, Outcome.BLOCKED, delivery, bus=bus)
        assert closed.manifest["scorecard"]["verdict"] == "blocked"
    assert len(store.runs()) == len(ACTIVE)
    console = Console(store, bus, queue=pool)
    assert all(row["state"] == "halted" for row in console.runs())
    assert pool.pressure().waiting == 0

    # ---- the chain: a rough draft, all eleven stages, into the live tree ----
    chain = _chain(world)
    dropped = chain.take(drop_draft(world["intake_root"], ROUGH_DRAFT), DROPPER)
    report = chain.scan(dropped, "skill_conformance")
    assert not report.conforms and report.for_a_person, "fixtures are a person's to supply"
    adapted = chain.adapt(report, OWNER)
    chain.draft(adapted, OWNER)
    transcript = chain.exercise(dropped.candidate_id, SKILL, CASES, OWNER)
    scorecard = chain.evaluate(dropped.candidate_id, SKILL, world=eval_world)
    assert scorecard.passed
    chain.replayed(dropped.candidate_id, changes=0, runs=len(launched), checked_by="replay")
    chain.submit(
        dropped.candidate_id,
        skill=SKILL,
        version=adapted.version,
        layer=LAYER,
        submitted_by=OWNER,
        transcript_ref=transcript.ref,
        scorecard_key=scorecard.key,
    )
    chain.decide(
        dropped.candidate_id,
        decision="approved",
        reviewer=REVIEWER,
        reason="the procedure is the one we follow by hand",
        layer=LAYER,
    )

    # Shadowed against the runs that just happened, and not one of them promotes it alone.
    for n, item in enumerate(launched):
        chain.shadow.observe(
            dropped.candidate_id,
            run_id=item.run_id,
            step_id="timing",
            skill=SKILL,
            version=adapted.version,
            registered_output={"periods": ["FY2024", "FY2025"]},
            candidate_output={"periods": ["FY2024", "FY2025"]},
        )
        if n < len(launched) - 1:
            assert not chain.shadow.promotion(dropped.candidate_id).sustained
    promotion = chain.promote(dropped.candidate_id, promoted_by=OWNER)
    assert promotion.promoted and promotion.runs == len(ACTIVE)

    published = chain.register(
        dropped.candidate_id,
        scorecard,
        definition=adapted.skill_md(),
        layer=LAYER,
        approved_by=OWNER,
    )

    # ---- and the whole evening is answerable from the two records ----
    assert published.path.is_file()
    assert chain.registry.unregistered() == ()
    assert {s.name for s in chain.registry.tree().all()} == {SKILL}

    names = {str(s) for s in STAGES}
    stages = [e.stage for e in chain.record.entries(dropped.candidate_id) if e.stage in names]
    assert stages == [str(s) for s in STAGES]
    chain.record.verify()
    assert chain.stage_of(dropped.candidate_id) is Stage.REGISTERED

    # The governance record and the run record are separate stores, and the skill that
    # shipped never saw a client file: the drafts live outside the repo, and the shadow
    # comparison read masked skill outputs by reference.
    assert chain.record.path.parent.parent == world["intake_root"]
    assert world["intake_root"] not in Path(__file__).resolve().parents
    assert store.runs(GOVERNANCE_SCOPE) == () or all(
        r.engagement_id == GOVERNANCE_SCOPE for r in store.runs(GOVERNANCE_SCOPE)
    )


class _Report:
    """What a pass hands back. C9 is about the evening, not about one step's arithmetic."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.executed = ["timing"]
        self.satisfied: list[str] = []
        self.quarantined: list[str] = []
        self.blocked_on = None
        self.finished = False

    def __str__(self) -> str:
        return f"{self.run_id}: 1 executed"


def _chain(world: dict[str, Any]) -> GovernanceChain:
    record = GovernanceRecord(world["intake_root"])
    store = world["store"]
    store.start_run(
        run_id=GOVERNANCE_RUN,
        engagement_id=GOVERNANCE_SCOPE,
        plan_hash="sha256:" + "7c" * 32,
        versions={
            "model_pin": "claude-opus-5 @ effort=high",
            "skills": [],
            "contracts": "1.0.0",
            "constraints": "1.0.0",
            "taxonomy": "coa-taxonomy@1.0.0",
        },
    )
    store.transition(GOVERNANCE_RUN, RunState.RUNNING, reason="a worker holds it")
    meter = CostMeter(store)
    door = ModelDoor(
        ScriptedPort(),
        PayloadScan(world["bus"]),
        BudgetGovernor(world["constraints"], meter, world["bus"], store),
        meter,
        world["bus"],
    )
    blobs = world["blobs"]
    return GovernanceChain(
        record=record,
        drop=DropFolder(record, world["intake_root"]),
        conformance=ConformanceCheck(record, world["contracts"], world["constraints"]),
        bench=AdaptationBench(record, door, blobs, world["constraints"]),
        sandbox=Sandbox(record, world["intake_root"]),
        sandbox_test=SandboxTest(record, blobs, Dispatches()),
        evals=EvalHarness(),
        board=SkillBoard(record, blobs),
        shadow=ShadowDeployment(record, blobs, threshold=0.08, required_runs=len(ACTIVE)),
        registry=SkillRegistry(
            record,
            SkillRegistration(world["tmp"] / "registered.yaml"),
            world["tmp"] / "skills",
        ),
    )


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
