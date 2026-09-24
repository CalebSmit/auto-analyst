"""P117 - a workflow a run can finish, and a machine that has one.

The watch form pre-selected `mature-company-valuation` whenever it was in the list, and
every engagement under that watch inherited it. That recipe names `gpc-scrub`,
`cost-of-capital`, `dcf-build` and `qc-tieout`; four procedures exist, none of them those,
and `tests/p101` *asserts* the recipe still cannot finish.

So the default path was: setup goes green, files land, the run pays a real provider for
timing, tagging and EBITDA, and quarantines at a skill nobody wrote. Money spent, no
workbook — and the dropdown said nothing, because its labels distinguished approved from
not approved and never built from not built.

Two smaller ones sat beside it. Approving a workflow is required before an engagement can
activate, the register is not committed, and it was on no checklist — so the refusal
arrived at the last step. And `templates/*.xlsx` is generated and gitignored while nothing
on the start path built it, so a clean machine had no workbook to deliver into.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness.procedures import PROCEDURES
from registries.recipes import RECIPES_DIR, RecipeRegister, unbuilt_skills

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "admin" / "page.py"
CONSOLE = ROOT / "admin" / "console.py"
START = ROOT / "tools" / "start.ps1"


def script() -> str:
    """The page's JavaScript with the f-string doubling undone, as it ships."""
    text = PAGE.read_text(encoding="utf-8")
    return "\n".join(re.findall(r"<script>(.*?)</script>", text, re.S)).replace(
        "{{", "{"
    ).replace("}}", "}")


# ============================================================ derived, not listed


def test_whether_a_recipe_can_finish_comes_from_the_procedures_that_exist() -> None:
    """A list of what is not built yet is a list that is wrong the day somebody builds
    one. This reads `PROCEDURES`, which is the thing that decides."""
    for path in RECIPES_DIR.glob("*.yaml"):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        named = {
            str(s["skill"]).split("@", 1)[0]
            for s in (doc.get("steps") or [])
            if s.get("kind") == "skill"
        }
        expected = {s for s in named if s not in PROCEDURES}
        found = {s.split("@", 1)[0] for s in unbuilt_skills(path)}
        assert found == expected, path.name


def test_exactly_one_recipe_on_disk_can_finish_today() -> None:
    """Not a roll-call: the point is the shape of the answer, and that the one which can
    is version 1's. If somebody builds `qc-tieout` tomorrow this gets larger and stays
    true."""
    review = {r.name: r for r in RecipeRegister().review()}
    assert review["valuation-input-prep"].can_finish
    assert not review["mature-company-valuation"].can_finish
    assert "qc-tieout" in review["mature-company-valuation"].unbuilt


def test_an_unreadable_recipe_is_somebody_else_s_refusal(tmp_path: Path) -> None:
    """`load_recipe` already refuses a file that will not parse, in its own words. Two
    modules refusing one thing differently is how a person gets two answers."""
    broken = tmp_path / "broken.yaml"
    broken.write_text("steps: [ this is not\n", encoding="utf-8")
    assert unbuilt_skills(broken) == ()


def test_a_recipe_naming_only_built_skills_is_clean() -> None:
    assert unbuilt_skills(RECIPES_DIR / "valuation-input-prep.yaml") == ()


# ============================================================ what the form offers


def code() -> str:
    """The page's JavaScript with its comments removed.

    Written because the first version of the test below was defeated by the comment
    explaining the fix - the same way `tests/p45`'s `proxy_headers=False` check is
    satisfied by the comment above the line rather than the line. A substring assertion
    about code has to be asked of the code."""
    return re.sub(r"/\*.*?\*/", "", script(), flags=re.S)


def test_the_form_no_longer_prefers_a_workflow_that_cannot_finish() -> None:
    """The bug itself: a recipe named in the page's own code as the default."""
    assert "'mature-company-valuation'" not in code()


def test_the_default_is_chosen_by_whether_it_finishes() -> None:
    body = script()
    assert "const finishable = (r.recipes || []).filter(x => x.can_finish !== false" in body
    assert "value: preferred," in body


def test_each_one_that_cannot_finish_says_where_it_will_stop() -> None:
    """"Not approved" and "not built" are different problems and the label said only the
    first. Naming the step it stops at is what turns a dropdown into a warning."""
    body = script()
    assert "will stop at" in body
    assert "(x.unbuilt || []).join(', ')" in body


def test_the_console_tells_the_page_both_things() -> None:
    console = CONSOLE.read_text(encoding="utf-8")
    assert '"can_finish": found.can_finish,' in console
    assert '"unbuilt": list(found.unbuilt),' in console


# ============================================================ preflight says so


def preflight_over(recipe: str) -> Any:
    """`_recipes_and_budgets`'s unbuilt half, with a roster and a watch behind it."""
    from admin.preflight import Preflight
    from intake.roster import RosterEntry, RosterState

    entry = RosterEntry(
        engagement_id="KSPW-2026-01",
        client="Kestrel Precision Works",
        scope_path="valuation/non-esop/non-repeat",
        watch_id="w-clients",
        destination_id="d-out",
        folder="Kestrel Precision/2026 Valuation",
        state=RosterState.ACTIVE,
        recipe=recipe,
    )
    check = Preflight.__new__(Preflight)
    check.config = type(  # type: ignore[attr-defined]
        "C", (), {"watches": lambda self: (), "constraints": None}
    )()
    check.constraints = type("K", (), {"ceilings": {"per_run": {"usd_max": 40.0}}})()  # type: ignore[attr-defined]
    return check._recipes_and_budgets((entry,))  # noqa: SLF001


def test_preflight_names_the_skill_that_would_stop_the_run() -> None:
    found = preflight_over("monthly-refresh")
    said = " ".join(str(f.diagnostic) for f in found.failures)
    assert "qc-tieout" in said
    assert "pay for every step before and stop there" in said


def test_it_says_so_and_blocks_nothing() -> None:
    """Refusing would refuse three of the four workflows the firm has approved, which is
    the firm's decision and not this build's to take on its behalf. The protection that
    matters is at the other end - the form offers one that finishes and labels the rest."""
    found = preflight_over("monthly-refresh")
    unbuilt = [f for f in found.failures if "no procedure exists" in str(f.diagnostic)]
    assert unbuilt and all(f.severity == "warn" for f in unbuilt)
    assert not any(f.blocks_everything for f in unbuilt)


def test_saying_it_is_unbuilt_does_not_replace_compiling_it() -> None:
    """Two different questions about one recipe, and the first answer used to eat the
    second. `continue` after the warning meant a consulting engagement on a valuation
    workflow - which cannot compile, and blocks - activated with a warning instead. Found
    by tests/p29 after P117 closed."""
    from admin.preflight import Preflight
    from intake.roster import RosterEntry, RosterState

    # A consulting engagement on a valuation workflow: unbuilt *and* uncompilable. Both
    # have to be reported, and the blocking one is the compile.
    entry = RosterEntry(
        engagement_id="NOVK-2026-01",
        client="Novak Advisory",
        scope_path="consulting/tbd/repeat",
        watch_id="w-clients",
        destination_id="d-out",
        folder="Novak Advisory/2026",
        state=RosterState.ACTIVE,
        recipe="monthly-refresh",
    )
    check = Preflight.__new__(Preflight)
    check.config = type(  # type: ignore[attr-defined]
        "C", (), {"watches": lambda self: ()}
    )()
    check.constraints = type("K", (), {"ceilings": {"per_run": {"usd_max": 40.0}}})()  # type: ignore[attr-defined]
    check.resolver = None  # type: ignore[attr-defined]
    found = check._recipes_and_budgets((entry,))  # noqa: SLF001
    severities = {f.severity for f in found.failures}
    assert "warn" in severities, "it is unbuilt, and that is said"
    assert "fail" in severities, "and it cannot compile, and that still blocks"


def test_a_workflow_that_finishes_raises_nothing() -> None:
    found = preflight_over("valuation-input-prep")
    assert not [f for f in found.failures if "no procedure exists" in str(f.diagnostic)]


# ============================================================ a clean machine


def test_the_start_path_builds_the_workbooks_it_needs() -> None:
    """`templates/*.xlsx` is generated and gitignored, so a clone has the schemas and none
    of the files - and the refusal a person then meets tells them to bind a fallthrough at
    a higher layer, which a non-developer cannot act on and which is the wrong answer."""
    start = START.read_text(encoding="utf-8")
    assert "synthesize_templates.py" in start
    assert "Chartwell_Input_Help_v1.xlsx" in start
    assert start.index("Test-Path $anyTemplate") < start.index("synthesize_templates.py")


def test_it_only_builds_when_they_are_missing() -> None:
    """A start script that rewrote the pinned templates every time would be a start script
    that changed the thing whose hash is the contract."""
    start = START.read_text(encoding="utf-8")
    assert "if (-not (Test-Path $anyTemplate))" in start


# ============================================================ approving one


def test_approving_a_workflow_is_a_step_on_the_checklist() -> None:
    """It is required before activation and the register is not committed, so a clone has
    nothing approved - and the refusal used to arrive at the last step, for the want of a
    step nobody had been shown."""
    body = script()
    assert "t: 'Approve a workflow'" in body
    assert body.index("Approve a workflow") < body.index("Register an engagement")


def test_it_offers_the_approval_that_already_exists() -> None:
    """Rather than a second way to do it. The panel's button and the checklist's button
    are the same action, so they cannot disagree about what approving means."""
    body = script()
    step = body[body.index("t: 'Approve a workflow'") : body.index("t: 'Register an engagement'")]
    assert "'approveRecipe'" in step


def test_it_offers_one_that_can_finish_first() -> None:
    """Sorting the unbuildable ones last, so the button on the checklist is not an
    invitation to approve the workflow that stops."""
    body = script()
    step = body[body.index("t: 'Approve a workflow'") : body.index("t: 'Register an engagement'")]
    assert "(a.can_finish === false) - (b.can_finish === false)" in step


def test_the_count_beside_the_list_still_follows_it() -> None:
    """Adding a step is how the last three roll-call tests were found. This one is the
    relationship, so adding the eleventh will not be."""
    from tests.counting import in_words

    page = PAGE.read_text(encoding="utf-8")
    steps = page.count("{{done:")
    assert f"{in_words(steps)} steps, in order." in page


@pytest.mark.parametrize("name", ["full-ddr-intake", "mature-company-valuation", "monthly-refresh"])
def test_the_recipes_that_cannot_finish_are_not_deleted(name: str) -> None:
    """They are the firm's, approved by a board, and three of them become finishable the
    day somebody writes `qc-tieout`. Labelling is the fix; deleting is not."""
    assert (RECIPES_DIR / f"{name}.yaml").is_file()
