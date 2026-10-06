"""Checkpoint C94 - day one, after the set-up the page walks.

C93 proved what a fresh clone says before anyone has done anything. This is the hour after:
a machine with no configuration, no approved recipe and nothing cleared is set up the way the
Setup page does it - the rehearsal's `set_up` is that sequence over the real routes - and at
the end of it the sixteen checks of P168 read the way a person would want them to. P166 to
P169 meet here: the model-adapter warning stands beside a green recipe check, the approval
went through the board, and the one consulting engagement is refused in compilation's words
while the two valuation engagements are active.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from admin import AdminConsole
from admin.app import create_admin_app
from deliver.registry import TemplateRegistry
from intake.config import ConfigStore
from intake.roster import ProjectRoster, RosterState
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.methodology import MethodologyRegister
from registries.recipes import RECIPES_DIR, RecipeRegister, digest_of_recipe
from tests.p24.conftest import Clock
from tests.p169.test_a_clones_first_day import _Api, _preflight


def test_a_machine_with_nothing_is_set_up_through_the_routes_and_the_sixteen_checks_agree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, Path],
    store: Any,
    contracts: ContractRegistry,
    templates: TemplateRegistry,
    constraints: ConstraintRegistry,
    clock: Clock,
) -> None:
    from governance.board import SkillBoard
    from governance.record import GovernanceRecord
    from ops.blobs import LocalContentStore
    from tools import simulate_firm as sim

    register = RecipeRegister(tmp_path / "registered.yaml")
    cleared = MethodologyRegister(tmp_path / "cleared.yaml")
    config = ConfigStore(store, contracts, environment="local")
    roster = ProjectRoster(store, config)
    preflight = _preflight(
        config, roster, templates, store, constraints, clock, recipes=register, methodology=cleared
    )
    console = AdminConsole(config, roster, preflight, constraints=constraints)

    original = AdminConsole.approve_recipe
    board = SkillBoard(GovernanceRecord(tmp_path / "governance"), LocalContentStore(tmp_path / "b"))

    def redirected(self: AdminConsole, name: str, *, who: str, reason: str, **_: Any) -> Any:
        return original(self, name, who=who, reason=reason, register=register, board=board)

    monkeypatch.setattr(AdminConsole, "approve_recipe", redirected)

    api = _Api(TestClient(create_admin_app(console)))
    out = sim.Report()
    sim.set_up(api, out)
    assert out.findings == [], out.findings

    # The approval is on the register and in the chain, under a name.
    (approved,) = [
        r
        for r in register.registered()
        if r.digest == digest_of_recipe(RECIPES_DIR / "monthly-refresh.yaml")
    ]
    assert approved.approved_by and approved.decision_ref
    assert board.record.entries(), "the governance chain saw it"

    # Sixteen checks, nothing failing; the two warnings are the two a developer's machine
    # is allowed - the fixture adapter (P168) and a workflow with an unbuilt step (P117) -
    # and the recipe check does not say "unregistered" or "does not compile" about anything.
    code, report = api.get("/api/admin/preflight")
    assert code == 200 and report["passed"], report
    checks = {c["id"]: c for c in report["checks"]}
    assert len(checks) == 16
    assert not [c["id"] for c in checks.values() if c["status"] == "fail"]
    assert checks["model_answers"]["status"] == "warn"
    recipes = checks["recipes_and_budgets"]
    assert all(f["severity"] == "warn" for f in recipes["failures"]), recipes
    assert all("RECIPE_UNREGISTERED" not in f["code"] for f in recipes["failures"])

    # The roster ends the way the page would show it.
    states = {e.engagement_id: e.state for e in roster.entries()}
    assert states["BRWF-2026-03"] is RosterState.ACTIVE
    assert states["NGDP-2026-07"] is RosterState.ACTIVE
    assert states["HALG-2026-09"] is RosterState.PAUSED, "consulting cannot compile the workflow"
    halg = console.check("HALG-2026-09").blocking("HALG-2026-09")
    assert {f.diagnostic.code for f in halg} == {"SCOPE.RECIPE_INVALID"}
    assert all("did not resolve into consulting" in f.diagnostic.detail for f in halg), halg

    # And nothing was written into this machine's own records.
    root = Path(__file__).resolve().parents[3]
    machine = root / "recipes" / "registered.yaml"
    if machine.is_file():
        assert "dress rehearsal" not in machine.read_text(encoding="utf-8")
    assert not (root / "foundations" / "cleared.yaml").exists() or (
        "rehearsal" not in (root / "foundations" / "cleared.yaml").read_text(encoding="utf-8")
    )
