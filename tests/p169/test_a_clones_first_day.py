"""P169 - a clone's first day.

The fresh-clone rehearsal was run to the end for the first time on 2026-10-06: clone,
`uv sync`, `--check`, both rehearsals against the clone's own server. Both rehearsals
failed at setup, on a machine that had never run the test suite. Each test here is one of
the four things that found, and each was proved by reverting its fix and watching it fail.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import ports
from admin import AdminConsole, Preflight
from admin.app import create_admin_app
from deliver.registry import TemplateRegistry
from graph.recipes import load_recipe
from intake.config import ConfigStore
from intake.roster import ProjectRoster
from intake.store import IntakeStore
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.errors import RegistryError
from registries.methodology import MethodologyRegister
from registries.recipes import RECIPES_DIR, RecipeRegister, digest_of_recipe
from tests.p24.conftest import HEND, WHO, Clock, entry, profile_for

ROOT = Path(__file__).resolve().parents[2]


def _preflight(
    config: ConfigStore,
    roster: ProjectRoster,
    templates: TemplateRegistry,
    store: Any,
    constraints: ConstraintRegistry,
    clock: Clock,
    *,
    recipes: RecipeRegister,
    methodology: MethodologyRegister | None = None,
) -> Preflight:
    """P24's preflight, with the recipe register pointed at a temporary file - the state a
    fresh clone is in, and one the machine's own register must never be confused with."""
    return Preflight(
        config,
        roster,
        storage=ports.get_storage(),
        delivery=ports.get_delivery(),
        secrets=ports.get_secrets(),
        templates=templates,
        intake_store=IntakeStore(store),
        constraints=constraints,
        methodology=methodology,
        recipes=lambda name: load_recipe(name, register=recipes),
        clock=clock,
    )


def test_a_recipe_nobody_approved_reaches_preflight_as_unregistered(
    tmp_path: Path,
    environment: dict[str, Path],
    config: ConfigStore,
    roster: ProjectRoster,
    templates: TemplateRegistry,
    store: Any,
    constraints: ConstraintRegistry,
    clock: Clock,
) -> None:
    """An empty register refuses the workflow as SCOPE.RECIPE_UNREGISTERED, whose next
    action is to take it through the board. Preflight used to catch that and re-issue it as
    RECIPE_INVALID - "a step naming something that does not exist" - which on a clone was
    the first sentence anybody read about every engagement they tried to activate."""
    register = RecipeRegister(tmp_path / "registered.yaml")
    preflight = _preflight(config, roster, templates, store, constraints, clock, recipes=register)
    console = AdminConsole(config, roster, preflight, constraints=constraints)
    console.register_engagement(entry(), profile=profile_for(HEND), who=WHO, reason="setup")

    report = console.check(HEND)
    check = next(c for c in report.checks if c.id == "recipes_and_budgets")
    assert check.failures, "an empty register refuses the workflow"
    codes = {f.diagnostic.code for f in check.failures}
    assert codes == {"SCOPE.RECIPE_UNREGISTERED"}, codes
    for failure in check.failures:
        assert "has never been approved for client work" in failure.diagnostic.detail
        assert "does not compile" not in failure.diagnostic.what_now
        assert "board" in failure.diagnostic.what_now
    assert report.blocking(HEND), "and it still blocks activation"

    # The compile refusal is untouched: a group that cannot run the workflow at all is
    # still told so in compilation's words, once the recipe is approved.
    from governance.board import Decision, SkillBoard
    from governance.record import GovernanceRecord
    from ops.blobs import LocalContentStore

    board = SkillBoard(GovernanceRecord(tmp_path / "governance"), LocalContentStore(tmp_path / "b"))
    board.register_recipe(
        RECIPES_DIR / "valuation-input-prep.yaml",
        version=1,
        decision=Decision(
            candidate_id="recipe:valuation-input-prep",
            decision="approved",
            reviewer=WHO,
            reason="test",
            routed_to="",
        ),
        register=register,
    )
    console.register_engagement(
        entry(
            "CONS-2026-01",
            client="Someone",
            scope_path="consulting/tbd/repeat",
            folder="Someone/2026 Consulting",
        ),
        profile=profile_for("CONS-2026-01", "consulting/tbd/repeat"),
        who=WHO,
        reason="setup",
    )
    report = console.check("CONS-2026-01")
    mine = [f for f in report.blocking("CONS-2026-01") if f.check == "recipes_and_budgets"]
    assert {f.diagnostic.code for f in mine} == {"SCOPE.RECIPE_INVALID"}, mine


class _Api:
    """The rehearsal's `Api` over a TestClient: the same (status, body) pairs."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    @staticmethod
    def _body(response: Any) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text

    def get(self, path: str) -> tuple[int, Any]:
        r = self.client.get(path)
        return r.status_code, self._body(r)

    def post(self, path: str, body: dict[str, Any]) -> tuple[int, Any]:
        r = self.client.post(path, json=body)
        return r.status_code, self._body(r)


def test_the_rehearsal_approves_the_workflow_it_runs_the_way_the_page_does(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, Path],
    store: Any,
    contracts: ContractRegistry,
    templates: TemplateRegistry,
    constraints: ConstraintRegistry,
    clock: Clock,
) -> None:
    """`simulate_firm.set_up` against a machine that has nothing: no configuration, no
    register, nothing cleared. It approves the workflow through the approval route before
    it registers an engagement, so every activation that should pass passes - which is what
    it could not do on a fresh clone, where it had been relying on the register the test
    suite writes."""
    from governance.board import SkillBoard
    from governance.record import GovernanceRecord
    from ops.blobs import LocalContentStore
    from tools import simulate_firm as sim

    register = RecipeRegister(tmp_path / "registered.yaml")
    assert not register.registered(), "a clone starts here"
    config = ConfigStore(store, contracts, environment="local")
    roster = ProjectRoster(store, config)
    cleared = MethodologyRegister(tmp_path / "cleared.yaml")
    preflight = _preflight(
        config, roster, templates, store, constraints, clock, recipes=register, methodology=cleared
    )
    console = AdminConsole(config, roster, preflight, constraints=constraints)

    # The approval route builds the real register and the real governance chain. Both are
    # redirected here so the test proves the rehearsal's behaviour without writing a
    # "dress rehearsal" approval into this machine's own records.
    original = AdminConsole.approve_recipe
    board = SkillBoard(GovernanceRecord(tmp_path / "governance"), LocalContentStore(tmp_path / "b"))

    def redirected(self: AdminConsole, name: str, *, who: str, reason: str, **_: Any) -> Any:
        return original(self, name, who=who, reason=reason, register=register, board=board)

    monkeypatch.setattr(AdminConsole, "approve_recipe", redirected)

    api = _Api(TestClient(create_admin_app(console)))
    out = sim.Report()
    sim.set_up(api, out)

    assert out.findings == [], out.findings
    for name in sim.RECIPES_USED:
        assert register.is_registered(digest_of_recipe(RECIPES_DIR / f"{name}.yaml")), name
    assert all(r.approved_by for r in register.registered())
    machine = ROOT / "recipes" / "registered.yaml"
    if machine.is_file():
        assert "dress rehearsal" not in machine.read_text(encoding="utf-8")


def test_a_missing_template_names_the_command_that_writes_it(tmp_path: Path) -> None:
    """templates/*.xlsx is not in git. The refusal used to name the absence and nothing
    else, so a fresh clone read every practice group as having no model and the runbook's
    install step did not say which command produces the files."""
    registry = TemplateRegistry(templates_dir=tmp_path)
    with pytest.raises(RegistryError) as refused:
        registry.register("Chartwell_Input_Help_v1.xlsx", "1.0")
    diagnostic = refused.value.diagnostic
    assert diagnostic.code == "DELIVER.TEMPLATE_MISSING"
    assert "tools/synthesize_templates.py" in diagnostic.detail
    assert "start.cmd" in diagnostic.detail

    runbook = (ROOT / "docs" / "WORK-LAPTOP.md").read_text(encoding="utf-8")
    install = runbook.index("python -m uv sync")
    first_check = runbook.index("tools/serve.py --check")
    assert (
        "python -m uv run python tools/synthesize_templates.py" in runbook[install:first_check]
    ), "the synthesizer belongs in the install step, before the first --check"


def test_the_files_rehearsal_names_what_blocked_an_engagement() -> None:
    """A case that launched nothing is reported with preflight's blocking failures for that
    engagement - its own and the environment's - rather than "nothing said why" when
    something had."""
    from tools.simulate_files import blocked

    report = {
        "checks": [
            {
                "id": "recipes_and_budgets",
                "failures": [
                    {
                        "severity": "fail",
                        "engagement_ids": ["BAT-X"],
                        "code": "SCOPE.RECIPE_UNREGISTERED",
                        "detail": "monthly-refresh has never been approved for client work",
                    },
                    {
                        "severity": "warn",
                        "engagement_ids": ["BAT-X"],
                        "code": "SCOPE.RECIPE_INVALID",
                        "detail": "names qc-tieout - no procedure exists for it",
                    },
                    {
                        "severity": "fail",
                        "engagement_ids": ["BAT-Y"],
                        "code": "CONFIG.BUDGET_ABOVE_CEILING",
                        "detail": "someone else's",
                    },
                ],
            },
            {
                "id": "paths_readable",
                "failures": [
                    {
                        "severity": "fail",
                        "engagement_ids": [],
                        "code": "CONFIG.PATH_UNREADABLE",
                        "detail": "watch w-clients: Clients is gone",
                    }
                ],
            },
        ]
    }
    assert blocked(report, "BAT-X") == [
        "SCOPE.RECIPE_UNREGISTERED: monthly-refresh has never been approved for client work",
        "CONFIG.PATH_UNREADABLE: watch w-clients: Clients is gone",
    ]
    assert blocked(report, "BAT-Z") == ["CONFIG.PATH_UNREADABLE: watch w-clients: Clients is gone"]
    assert blocked({}, "BAT-X") == []
    assert blocked(None, "BAT-X") == []
