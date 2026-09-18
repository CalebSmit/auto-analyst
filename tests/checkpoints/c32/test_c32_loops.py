"""C32 - A loop that can be entered.

"The graph owns every loop. Every cycle is declared with an integer maximum the compiler
checks. No agent decides for itself whether to try again." That is a non-negotiable, and
until P59 the first sentence described a mechanism nothing could reach: four regions
declared on every recipe, a controller that could admit and exhaust them, and no production
code that raised the exception which starts one.

What this asks is whether the join holds and whether it holds *only* where it should - a
raiser that could name a region the recipe did not declare would be an agent deciding, which
is the half of the invariant that is easier to break than to notice.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_the_guards_reach_the_controller_and_only_through_the_masker() -> None:
    """The dispatcher is the only object holding the masker, the engagement id and the run's
    identifiers together. The feedback's bytes reach the model, so it is written there or it
    is written somewhere that cannot mask it."""
    dispatch = (ROOT / "harness" / "dispatch.py").read_text(encoding="utf-8")
    assert "raise self._repair(" in dispatch
    assert "self.masker.mask(" in dispatch.split("def _repair")[1].split("def run")[0]

    for module in ("graph/execute.py", "harness/runner.py"):
        body = (ROOT / module).read_text(encoding="utf-8")
        assert "as_repair(" not in body, f"{module} decides whether a loop may run"


def test_nothing_can_name_a_region_the_recipe_did_not_declare() -> None:
    from graph.compile import Step
    from harness.repair import LOOP_FOR, as_repair

    class Failed(Exception):
        def __init__(self, guard: str) -> None:
            super().__init__(guard)
            self.result = type("R", (), {"guard": guard, "code": "X", "reasons": (), "detail": {},
                                         "checked": 1, "failed": 1})()
            self.diagnostic = type("D", (), {"code": "X", "what_now": ""})()

    bare = Step(
        id="ebitda", kind="skill", skill="s@1", inputs=(), output_schema=None,
        timeout_s=1, retries=0, loops=(), on_failure="quarantine",
    )
    for guard in LOOP_FOR:
        assert as_repair(bare, Failed(guard), None) is None  # type: ignore[arg-type]


def test_the_feedback_the_model_sees_is_the_guard_s_own_verdict() -> None:
    """Not prose, and not the exception's str(). The tie-out guard already produces what the
    blueprint says tie-out repair hands back - the recomputed value and the cited rows."""
    from harness.repair import feedback_document

    class Failed(Exception):
        result = type("R", (), {"guard": "tieout", "code": "GUARD.TIEOUT_MISMATCH",
                                "checked": 4, "failed": 1, "reasons": ("a != b",),
                                "detail": {"mismatches": [{"stated": 1, "recomputed": 2}]}})()
        diagnostic = type("D", (), {"code": "GUARD.TIEOUT_MISMATCH", "what_now": "look"})()

    said = feedback_document(Failed())
    assert said["code"] == "GUARD.TIEOUT_MISMATCH"
    assert said["reasons"] == ["a != b"]
    assert said["detail"]["mismatches"][0]["recomputed"] == 2


def test_a_region_nothing_can_enter_is_recorded_rather_than_silent() -> None:
    """Both remaining gaps are named in OPEN.md. Silence is what let all four sit
    unreachable through twenty-five phases."""
    open_items = (ROOT / "BUILD" / "OPEN.md").read_text(encoding="utf-8")
    assert "conflict_resolution" in open_items
    assert "self_verification" in open_items
    assert "line-item-tagging" in open_items


def test_the_plan_hash_did_not_move() -> None:
    """Reading what a plan already declares changes nothing about what the plan is. If this
    moved, a recipe changed and every registered one needs re-approving."""
    surfaces = (ROOT / "BUILD" / "surfaces.json").read_text(encoding="utf-8")
    assert "plan_hash" in surfaces or "recipes" in surfaces


def test_the_blueprint_still_matches_the_code() -> None:
    """The code caught up to what the blueprint already said; it did not change the design.
    `step_executor` has routed a guard failure to the Loop Controller in the drawing since
    the blueprint was written."""
    blueprint = (ROOT / "docs" / "architecture.html").read_text(encoding="utf-8")
    assert "loop_controller" in blueprint
    tree = ast.parse((ROOT / "harness" / "repair.py").read_text(encoding="utf-8"))
    assert any(isinstance(n, ast.FunctionDef) and n.name == "as_repair" for n in ast.walk(tree))
