"""C5 - Every guard fires on its own fixture.

Proves: every adversarial fixture whose guard is built fires that guard and only that
guard, every loop is bounded, and every failure carries code, owner and what_now.

Three claims, and the chain they hang on, from P13 to P15 in one run:

    a guard rejects an output       -> GuardFailed, with code, owner, what_now, both values
    the plan declares a repair loop -> the controller admits a changed input, refuses an
                                       unchanged one, and stops at the ceiling
    the loop exhausts               -> a quarantine record and a review item, both positions
    a person decides                -> the decision log, append-only, names them

The fixture table names ten guards. Seven are built by P15 (payload scan, unmask verify,
tie-out, numeric lock, provenance, budget governor, loop controller); the untrusted
boundary, the engagement lock and the deliverable QC are built by P17, P16 and P21 and
their fixtures are reported, not skipped silently. The checkpoint's claim is amended to
say so; this file will not need to change when the last three land - the pending list
just empties.

Written at the end of P15 rather than at the checkpoint, per the phase file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from graph.compile import CompiledGraph, PlanContext, compile_recipe
from graph.execute import StepExecutor
from graph.plan_assertions import assert_all_loops_bounded
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver
from harness.loops import LoopController
from ops.blobs import LocalContentStore
from ops.events import EventBus
from ops.models import DecisionKind, RunState
from ops.run_store import SqlRunStore
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.diagnostics import DiagnosticsRegistry
from registries.errors import DiagnosticError, diagnose
from review import DecisionLog, ReviewSurface
from tests.conftest import PENDING_FIXTURES
from tests.p13.conftest import ENGAGEMENT
from tests.p13.test_fixtures import BUILT, _fire
from tests.p14.conftest import Repairer

ROOT = Path(__file__).resolve().parents[3]


# ------------------------------------------------ 1. every fixture, its guard


@pytest.mark.parametrize("row_index", range(10))
def test_every_built_guard_fires_on_its_own_fixture_and_only_that_guard(
    row_index: int,
    fixture_table: dict[str, Any],
    store: SqlRunStore,
    bus: EventBus,
    contracts: ContractRegistry,
    started: str,
    parsed: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = fixture_table["fixtures"][row_index]
    if row["guard"] not in BUILT:
        PENDING_FIXTURES.append((row["id"], row["guard"], row["built_by"]))
        pytest.skip(f"{row['id']}: {row['guard']} is built by {row['built_by']} (reported)")
    fired = _fire(row, store, bus, contracts, started, parsed, monkeypatch)
    assert fired[row["guard"]] == row["fires"]
    assert not {g: c for g, c in fired.items() if g != row["guard"] and c is not None}


def test_every_guard_fixture_has_its_guard(fixture_table: dict[str, Any]) -> None:
    """Nine after P17; the tenth, the Deliverable QC Gate, landed with P21."""
    built = [r for r in fixture_table["fixtures"] if r["guard"] in BUILT]
    owed = {r["guard"]: r["built_by"] for r in fixture_table["fixtures"] if r["guard"] not in BUILT}
    assert len(built) == 10
    assert owed == {}


# ------------------------------------------------------ 2. every loop bounded


def _plans() -> tuple[CompiledGraph, ...]:
    scope = ScopeResolver().resolve("valuation/esop/repeat")
    return tuple(
        compile_recipe(
            load_recipe(name),
            PlanContext(
                engagement_id=ENGAGEMENT,
                scope=scope,
                taxonomy_version="coa-taxonomy@1.0.0",
                precedent_snapshot="precedent_snapshot_2026_09_01",
            ),
        )
        for name in ("monthly-refresh", "full-ddr-intake")
    )


def test_every_loop_in_every_recipe_is_bounded_by_an_integer_the_registry_allows() -> None:
    constraints = ConstraintRegistry.load()
    declared = {s.name: s.max_iterations for s in constraints.in_run_loops()}
    assert all(isinstance(m, int) and m >= 1 for m in declared.values())
    for plan in _plans():
        assert_all_loops_bounded(plan)
        for region in plan.loops:
            assert region.scope == "in_run"
            assert 1 <= region.max_iterations <= declared[region.loop]
            assert region.max_iterations <= constraints.loop_ceiling()


def test_the_controller_holds_every_ceiling_and_the_run_ceiling(
    store: SqlRunStore, bus: EventBus, started: str
) -> None:
    constraints = ConstraintRegistry.load()
    controller = LoopController(constraints, store, bus)
    plan = _plans()[0]
    trigger = diagnose("SKILL.SCHEMA_INVALID", "c5")
    for region in plan.loops:
        step = plan.step(region.head)
        keys = ["sha256:" + f"{n:064x}" for n in range(region.max_iterations + 2)]
        current = keys[0]
        for n in range(1, region.max_iterations + 1):
            admitted = controller.admit(
                started, plan, step, region.loop, current, keys[n], {}, trigger
            )
            assert admitted.allowed, f"{region.id} iteration {n}"
            current = keys[n]
        refused = controller.admit(started, plan, step, region.loop, current, keys[-1], {}, trigger)
        assert not refused.allowed and refused.code == "LOOP.EXHAUSTED"
    assert controller.iterations_so_far(started) == sum(r.max_iterations for r in plan.loops)
    assert controller.iterations_so_far(started) <= constraints.loop_ceiling() * len(plan.loops)


# --------------------------------------- 3. every failure: code, owner, what_now


def test_every_declared_code_has_an_owner_and_a_what_now() -> None:
    registry = DiagnosticsRegistry.load()
    assert registry.self_check() == []
    for code in registry.codes():
        entry = registry.get(code)
        assert entry.owner and len(entry.what_now.split()) >= 12, code


def test_no_failure_path_raises_a_bare_exception() -> None:
    """Every deliberate failure is a DiagnosticError carrying a diagnostic. A bare
    RuntimeError or Exception on a failure path would be a message nobody can act on."""
    bare = re.compile(r"^\s*raise (RuntimeError|Exception)\(", re.M)
    offenders = []
    for folder in ("guards", "harness", "graph", "privacy", "registries", "review", "ops"):
        for path in (ROOT / folder).rglob("*.py"):
            if bare.search(path.read_text(encoding="utf-8")):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_the_chain_from_guard_to_decision(
    store: SqlRunStore, bus: EventBus, started: str, tmp_path: Path
) -> None:
    """One run: a tie-out failure, two admitted repairs, exhaustion, a quarantine record
    with both values, a review item with both positions, and a named person's decision
    in an append-only log. Every failure along the way carries a code and an owner."""
    plan = _plans()[0]
    blobs = LocalContentStore(tmp_path / "blobs")
    inputs = {
        ref.name: blobs.put_json({"run_input": ref.name}, name=ref.name)
        for step in plan.steps
        for ref in step.inputs
        if ref.from_run
    }
    runner = Repairer(blobs, "ebitda", "guard_repair", feedback=lambda n: {"attempt": n})
    report = StepExecutor(store, bus, runner, blobs=blobs).execute(
        plan, started, inputs, "context:c5"
    )

    assert report.quarantined == ["ebitda"] and report.state is RunState.QUARANTINED
    (held,) = store.quarantines(started)
    assert held.code == "LOOP.EXHAUSTED" and held.owner == "model" and held.diagnostic["what_now"]
    assert held.guard_output["diagnostic"]["code"] == "GUARD.TIEOUT_MISMATCH"
    assert held.guard_output["diagnostic"]["expected"] == "331000.0"
    assert held.guard_output["diagnostic"]["found"] == "332324.0"

    (item,) = [i for i in store.review_items(started) if i.kind == "loop_exhausted"]
    assert set(item.detail["positions"]) == {"proposed", "recomputed"}

    surface = ReviewSurface(store, bus)
    record = surface.decide(
        started,
        item.item_id,
        decided_by="Dana Whitfield",
        decision=DecisionKind.ESCALATED,
        expected_version=item.version,
        rationale="Client schedule does not foot; asked for a corrected TB.",
    )
    assert record.decided_by == "Dana Whitfield" and not record.writes_precedent
    assert DecisionLog(store).entries(started) == (record,)

    failures = [e for e in store.events(started) if e.level == "error"]
    assert failures, "the run failed and said so"
    for e in failures:
        assert e.diagnostic_code, f"{e.type} carries no code"
        assert e.payload.get("owner") or e.payload.get("diagnostic_code"), e.type


def test_every_error_raised_in_the_chain_is_a_diagnostic_error() -> None:
    """The base class is what makes an operator-facing error surface possible."""
    from guards import GuardFailed
    from harness.budget import BudgetExceeded
    from ops.models import RunStoreError
    from review import PolicyRefused, ReviewRefused, StaleDecision

    for cls in (
        GuardFailed,
        BudgetExceeded,
        RunStoreError,
        PolicyRefused,
        ReviewRefused,
        StaleDecision,
    ):
        assert issubclass(cls, DiagnosticError), cls
