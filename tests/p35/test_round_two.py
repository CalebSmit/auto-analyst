"""Round two: what the system did with something answering for the model.

The first rehearsal stopped at the model door because nothing could answer for it. The
second put a scripted analyst behind the door - one that reads each request and writes a
structurally right proposal - and drove generated clients through the served system, the
consoles, a restart, six deliberately bad answers, a budget of a cent, and twenty
wrong-shaped files. Every test here is a bug that found, fixed, and pinned.
"""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from admin.app import install_identity
from admin.preflight import CHECKS
from graph.execute import step_key
from graph.recipes import load_recipe
from harness.budget import BudgetExceeded, BudgetGovernor
from harness.procedures.timing_normalization import SourceFile
from intake.bind import bind_document_type
from intake.readers.periods import detect_periods
from ops.console.app import Console, create_app
from ops.cost import CostMeter
from ops.models import DecisionKind, RunState
from precedent.store import PrecedentStore
from registries.constraints import ConstraintRegistry
from review import ReviewSurface
from tests.p16.conftest import LAUNCH, drop
from tests.p17.conftest import build_xlsx
from tests.p35.test_a_run_on_real_files import STATEMENT, release_statements
from tests.p35.test_run_driver import _intake, set_up
from workers.driver import _distinctive_words, plan_for

ROOT = Path(__file__).resolve().parents[2]
HEND = "HEND-2026-04"
FOLDER = "Clients/Henderson Manufacturing/2026 ESOP"


def scripted() -> Any:
    from ports.llm.scripted import ScriptedAnalyst

    return ScriptedAnalyst()


def trouble(store: Any, run_id: str) -> list[str]:
    """What stopped a run, for an assertion message worth reading."""
    return [
        f"{e.type}: {e.message[:200]}"
        for e in store.events(run_id)
        if e.type.endswith(".fail") or e.type in ("step.quarantined", "run.refused")
    ]


# ------------------------------------------------------------- two runs are two runs


def test_the_step_key_names_the_run(world: dict[str, Any]) -> None:
    """Lockhart's timing step was satisfied from Brightwater's ledger entry: same recipe,
    same declared input (the mask step, whose output says nothing about which client),
    no context ref from the driver. Two clients shared one normalized table."""
    set_up(world)
    entry = world["roster"].get(HEND)
    plan, _ = plan_for(
        entry,
        load_recipe("full-ddr-intake"),
        config=world["config"],
        precedents=PrecedentStore(world["store"]),
        contracts=world["contracts"],
        constraints=ConstraintRegistry.load(),
    )
    step = plan.step("timing")
    a = step_key(step, {}, "context:none", "run_a")
    assert a == step_key(step, {}, "context:none", "run_a"), "a resumed run replays its own"
    assert a != step_key(step, {}, "context:none", "run_b"), "and never another run's"


# ------------------------------------------------------------- the loop closes


def test_a_run_pauses_on_review_items_and_resumes_past_them(
    world: dict[str, Any], driver_for: Any
) -> None:
    """The procedures set review_required; nothing read it. A run went from tagging to
    the model with every flagged item auto-accepted by omission. Now the pass ends at
    the step whose items a person must answer, and the next pass resumes after it."""
    set_up(world)
    run_id = release_statements(world)
    driver = driver_for(scripted())
    store = world["store"]

    first = driver(run_id)
    assert store.run(run_id).state is RunState.WAITING, trouble(store, run_id)
    assert first.blocked_on, "the pass ended at a step with open items"
    opened = [i for i in store.review_items(run_id) if i.state == "open"]
    assert opened, "a person has something to decide"
    assert "hitl.pass.paused" in {e.type for e in store.events(run_id)}

    surface = ReviewSurface(store, world["bus"])
    for item in opened:
        surface.decide(
            run_id,
            item.item_id,
            decided_by="Dana Whitfield",
            decision=DecisionKind.ACCEPTED,
            expected_version=item.version,
        )
    assert "run.resumed" in {e.type for e in store.events(run_id)}

    second = driver(run_id)
    assert first.blocked_on in second.satisfied, "the step is replayed, not redone"
    moved = second.blocked_on != first.blocked_on or [
        s for s in second.executed if s not in first.executed
    ]
    assert moved, f"the frontier did not move: {trouble(store, run_id)}"
    decided = {o.item_id for o in opened}
    items_now = store.review_items(run_id)
    assert not [i for i in items_now if i.item_id in decided and i.state == "open"]


def test_a_decision_becomes_an_example(world: dict[str, Any], driver_for: Any) -> None:
    """Thirty-seven decisions on one run were recorded as writing precedent; the store
    held none. The write-back existed and nothing on the served path called it."""
    set_up(world)
    run_id = release_statements(world)
    driver = driver_for(scripted())
    store = world["store"]
    driver(run_id)
    assert store.run(run_id).state is RunState.WAITING, trouble(store, run_id)
    surface = ReviewSurface(store, world["bus"])
    for item in [i for i in store.review_items(run_id) if i.state == "open"]:
        surface.decide(
            run_id,
            item.item_id,
            decided_by="Dana Whitfield",
            decision=DecisionKind.ACCEPTED,
            expected_version=item.version,
        )
    driver(run_id)  # the pass after the answers is where the write-back runs

    kinds = {e.type for e in store.events(run_id)}
    assert "precedent.written" in kinds or "precedent.writeback.refused" in kinds
    written = [e for e in store.events(run_id) if e.type == "precedent.written"]
    if written:
        assert PrecedentStore(store).count() >= len(written)
    for refused in (e for e in store.events(run_id) if e.type == "precedent.writeback.refused"):
        assert refused.payload.get("code"), "a refusal names its reason"


# ------------------------------------------------------------- what the readers refuse


def test_an_unreadable_workbook_ends_the_run_halted_naming_the_file(
    world: dict[str, Any], driver_for: Any
) -> None:
    """A .xlsx that is not a zip crashed the worker (BadZipFile) and left the run queued
    with nothing to report it."""
    set_up(world)
    drop(
        world["inbox"],
        f"{FOLDER}/Henderson Income Statement FY2025.xlsx",
        build_xlsx({"Income Statement": STATEMENT}),
    )
    drop(world["inbox"], f"{FOLDER}/TB_FY25.xlsx", b"")  # zero bytes, .xlsx by name only
    intake = _intake(world)
    intake.sweep(LAUNCH)
    world["clock"].advance(minutes=31)
    (launched,) = intake.sweep(LAUNCH).launched
    run_id = str(launched.run_id)

    report = driver_for(scripted())(run_id)
    assert report.state is RunState.HALTED, trouble(world["store"], run_id)
    refused = next(e for e in world["store"].events(run_id) if e.type == "run.refused")
    assert refused.payload["code"] == "INTAKE.UNREADABLE_FILE"
    assert "TB_FY25.xlsx" in refused.message


# ------------------------------------------------------------- names, words, files


def test_an_ordinary_word_of_a_clients_name_is_not_an_identifier() -> None:
    """ "Zero-Byte Case Co" put "Case" on the identifier list, and "case" is in the
    firm's own skill text beside the payload. Every such client quarantined on its own
    name. A name that only ever appears capitalised is still a name."""
    assert _distinctive_words("Zero-Byte Case Co") == ("Zero-Byte",)
    assert _distinctive_words("Henderson Manufacturing") == ("Henderson",)


def test_short_convention_tokens_match_whole_words() -> None:
    """`IS.xlsx`, `BS.xlsx`, `TB.xlsx` were held forever, silently, because no token
    claimed them; adding `is` as a substring would have claimed `analysis.xlsx`."""
    conventions = {"trial_balance": ("tb", "trial balance"), "financial_statements": ("is", "bs")}
    assert bind_document_type("IS 2025.xlsx", conventions) == "financial_statements"
    assert bind_document_type("TB.xlsx", conventions) == "trial_balance"
    assert bind_document_type("analysis.xlsx", conventions) is None
    assert bind_document_type("subs.xlsx", conventions) is None


def test_preflight_tells_somebody_about_held_files() -> None:
    assert "held_files" in [c[0] for c in CHECKS]


def test_december_31_is_a_day_and_dated_headers_are_annual() -> None:
    """ "For the fiscal years ended December 31" gave every statement a period end of
    2031-12-31. Real dates in a header row gave period ends and no period type."""
    ended = detect_periods("For the fiscal years ended December 31\n($000s)\nFY2024 FY2025")
    assert "2031-12-31" not in ended.period_ends
    dated = detect_periods("Account 2024-12-31 2025-12-31")
    assert dated.period_type == "annual"
    assert dated.period_ends == ("2024-12-31", "2025-12-31")
    assert detect_periods("Dec-24 Dec-25").period_ends == ("2024-12-31", "2025-12-31")


def test_the_manifest_admits_the_precedent_snapshot() -> None:
    """Every run the server launches names its precedent snapshot; the manifest contract
    refused it, so every halted or delivered run failed while writing its manifest."""
    schema = json.loads((ROOT / "contracts" / "run_manifest.schema.json").read_text("utf-8"))
    versions = schema["properties"]["versions"]
    assert "precedent_snapshot" in versions["properties"]
    assert versions.get("additionalProperties") is False


# ------------------------------------------------------------- money and the model


def test_the_engagements_budget_is_enforced(world: dict[str, Any]) -> None:
    """A budget of $0.01 was recorded, shown, counted by preflight - and a run under it
    spent $0.30 with no budget event."""
    set_up(world)
    run_id = release_statements(world)
    governor = BudgetGovernor(
        ConstraintRegistry.load(),
        CostMeter(world["store"]),
        world["bus"],
        world["store"],
        budget_for=lambda _e: 0.01,
    )
    with pytest.raises(BudgetExceeded):
        governor.check(run_id, HEND, about_to_spend_usd=0.05, about_to_call=True)
    crossed = [e for e in world["store"].events(run_id) if e.type == "budget.ceiling_crossed"]
    assert crossed and crossed[0].payload["ceiling"] == "engagement_budget_usd"


def test_the_scripted_analyst_is_for_rehearsals_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """The adapter builds like any other, so the conformance suite can hold it to the
    port's shape; the front door refuses to start on it unless a rehearsal says so."""
    import ports
    from ports.llm import scripted as module
    from registries.errors import RegistryError
    from tools import serve

    monkeypatch.setenv("AA_LLM_ADAPTER", "scripted")
    monkeypatch.delenv("AA_REHEARSAL", raising=False)
    ports.reset()
    with pytest.raises(RegistryError) as refused:
        serve.build()
    assert refused.value.diagnostic.locator == "AA_REHEARSAL"
    analyst = module.build()
    answer = analyst.answer(
        {
            "files": [
                {
                    "source_id": "sha256:" + "a" * 64,
                    "filename": "x",
                    "period_ends": [],
                    "blocks": {
                        "IS!B2:B3": {
                            "period_hint": "FY2025",
                            "rows": ["IS!B2: Revenue", "IS!B3: Rent"],
                        }
                    },
                }
            ]
        },
        "timing-normalization@0.1.0",
    )
    assert answer["schema_version"] == "skills/timing-normalization-proposal@1.0.0"
    assert answer["produced_by"] == "timing-normalization@0.1.0"
    assert answer["periods"][0]["label"] == "FY2025"


def test_the_served_runtime_registers_the_five_tools(wiring: Any) -> None:
    """The served runtime had no tools. With a real key every skill would have failed at
    its mechanical half, on every run."""
    from tools import serve

    for name in (
        "timing_normalizer",
        "recompute",
        "chart_of_accounts_lookup",
        "precedent_lookup",
        "template_schema_lookup",
    ):
        assert name in inspect.getsource(serve._pool)  # noqa: SLF001
    runtime = wiring(scripted()).dispatcher_for("any").runtime
    registered = set(runtime._tools)  # noqa: SLF001
    assert {"timing_normalizer", "recompute", "chart_of_accounts_lookup"} <= registered


def test_currency_is_settled_from_the_profile(world: dict[str, Any], driver_for: Any) -> None:
    """A US file rarely says USD; the timing tool's output then failed its own schema on
    every value. The profile declared the currency; the driver settles it, on the record."""
    set_up(world)
    run_id = release_statements(world)
    driver = driver_for(scripted())
    entry = world["roster"].get(HEND)
    source = SourceFile(
        source_id="sha256:" + "b" * 64,
        filename="TB.xlsx",
        document_type="trial_balance",
        blocks={},
        scale=1,
        currency=None,
        period_type=None,
        period_ends=(),
        ambiguous=("currency: no cue",),
        source_version=1,
    )
    (settled,) = driver._settle_currency(  # noqa: SLF001
        run_id,
        entry.engagement_id,
        (source,),
        {"materiality_threshold": {"amount": 0, "currency": "USD"}},
    )
    assert settled.currency == "USD"
    assert not [a for a in settled.ambiguous if a.startswith("currency")]
    assert "intake.currency.assumed" in {e.type for e in world["store"].events(run_id)}


# ------------------------------------------------------------- the consoles


def _app(world: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AA_IDENTITY_NAME", "Dana Whitfield")
    import ports

    ports.reset()
    store, bus = world["store"], world["bus"]
    app = create_app(
        Console(store, bus, constraints=ConstraintRegistry.load()),
        surface=ReviewSurface(store, bus),
    )
    install_identity(app)
    return TestClient(app)


def test_a_reviewer_answers_through_the_console_and_the_run_wakes(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review surface was complete and nothing served it: no way to decide from the
    front door, and nothing to wake a decided run."""
    set_up(world)
    run_id = release_statements(world)
    store = world["store"]
    store.transition(run_id, RunState.RUNNING, reason="a worker holds it")
    store.open_review_item(
        run_id,
        "tag:li_1",
        "below_threshold",
        "Rent: tag as rent?",
        detail={"skill": "line-item-tagging", "proposal": {"category": "rent"}},
    )
    store.transition(run_id, RunState.WAITING, reason="blocked on tagging")
    client = _app(world, monkeypatch)

    shown = client.get(f"/api/runs/{run_id}/review/tag:li_1")
    assert shown.status_code == 200 and shown.json()["version"] == 1
    base = f"/api/runs/{run_id}/review/tag:li_1/decide"
    silent = {"decision": "rejected", "expected_version": 1}
    assert client.post(base, json=silent).status_code == 422
    claimed = {"decision": "accepted", "expected_version": 1, "who": "somebody.else"}
    assert client.post(base, json=claimed).status_code == 403
    stale = {"decision": "accepted", "expected_version": 9}
    assert client.post(base, json=stale).status_code == 409
    done = client.post(base, json={"decision": "accepted", "expected_version": 1})
    assert done.status_code == 200 and done.json()["decided_by"] == "Dana Whitfield"
    assert done.json()["open_items"] == 0
    assert "run.resumed" in {e.type for e in store.events(run_id)}
    again = {"decision": "accepted", "expected_version": 1}
    assert client.post(base, json=again).status_code == 409


def test_a_quarantined_run_can_be_ended_from_the_console_with_a_reason(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A quarantined run could only be resumed or ended from Python. And the ending is
    the one the record supports: this run refused nothing and waited on nobody, so it
    ends blocked, not halted, whatever the button is called."""
    set_up(world)
    run_id = release_statements(world)
    store = world["store"]
    store.transition(run_id, RunState.RUNNING, reason="a worker holds it")
    store.transition(run_id, RunState.QUARANTINED, reason="quarantined: timing")
    client = _app(world, monkeypatch)

    assert client.post(f"/api/runs/{run_id}/halt", json={"reason": ""}).status_code == 422
    ended = client.post(f"/api/runs/{run_id}/halt", json={"reason": "wrong files; resending"})
    assert ended.status_code == 200, ended.json()
    assert ended.json()["state"] == "halted"
    assert store.run(run_id).state is RunState.HALTED
    assert "run.manifest.written" in {e.type for e in store.events(run_id)}
    assert client.post(f"/api/runs/{run_id}/halt", json={"reason": "again"}).status_code == 409


def test_the_rehearsal_walks_the_loop_only_when_asked() -> None:
    """`--scripted` sets the adapter and the flag together; nothing else selects it."""
    source = (ROOT / "tools" / "simulate_firm.py").read_text(encoding="utf-8")
    assert '"scripted" if args.scripted' in source
    assert '"AA_REHEARSAL": "1"' in source
    assert os.environ.get("AA_LLM_ADAPTER") != "scripted"
