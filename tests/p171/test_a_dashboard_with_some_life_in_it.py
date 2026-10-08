"""P171 - a dashboard with some life in it, one skill one row, and a place for the model-setup
skill to land.

Every motion the phase added is held to two things: it is declared once, and the one
reduced-motion rule stops it. Every colour it added is a mix of tokens. The Analytics board
is held to grouping by skill rather than by (skill, group). And the runbook's section on the
model-setup skill is held to paths and front-matter names that exist, because a runbook that
names a folder nobody made is a runbook that teaches a wrong move.
"""

from __future__ import annotations

import re
from pathlib import Path

from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.map_view import MAP_STYLE
from registries.skills import REQUIRED_FRONTMATTER
from tests.conftest import needs_a_checkout
from ui.theme import CSS

ROOT = Path(__file__).resolve().parents[2]
SHEET = CSS + MAP_STYLE

ADDED = ("aurora", "breathe", "shimmer", "arrive", "march")
"""The animations P171 added, by keyframe name."""


def test_every_motion_added_is_declared_once_and_used() -> None:
    for name in ADDED:
        assert SHEET.count(f"@keyframes {name}{{") == 1, name
        assert re.search(rf"animation:{name} ", SHEET), f"{name} is declared and worn by nothing"


def test_one_rule_stops_all_of_it() -> None:
    """`prefers-reduced-motion` already covered every animation with a universal selector; a
    new animation that escaped it would be the first the product could not switch off."""
    block = re.search(r"@media \(prefers-reduced-motion:reduce\)\{(.*?)\n\}", CSS, re.S)
    assert block, "the reduced-motion rule is gone"
    assert block.group(1).lstrip().startswith("*,*::before,*::after{"), block.group(1)[:80]
    assert "animation-iteration-count:1!important" in block.group(1)


def test_the_masthead_has_weather_and_the_paper_is_lit() -> None:
    top = re.search(r"\.top::before\{([^}]*)\}", CSS).group(1)
    assert "animation:aurora" in top and top.count("radial-gradient(") == 3
    body = re.search(r"\nbody\{([^}]*)\}", CSS).group(1)
    assert body.count("radial-gradient(") == 2 and "background-attachment:fixed" in body
    # The masthead clips its own lights: they are drawn beyond its edges so the drift
    # never shows an edge, and `overflow:hidden` is what keeps them under the chrome.
    assert "overflow:hidden" in re.search(r"\n\.top\{([^}]*)\}", CSS).group(1)


def test_every_colour_the_phase_mixed_is_a_token() -> None:
    """A `color-mix` names two colours; each is a token, white, black or transparent."""
    for mix in re.findall(r"color-mix\(in srgb,([^)]*)\)", SHEET):
        for part in mix.split(","):
            part = part.strip().split(" ")[0]
            assert part.startswith("var(--") or part in (
                "white",
                "black",
                "transparent",
                "currentColor",
            ), mix


def test_the_board_arrives_in_order() -> None:
    rule = re.search(r"\.board>\.card\{animation:rise[^}]*\}", CSS).group(0)
    assert "var(--i,0)" in rule
    for n in range(2, 9):
        assert f".board>.card:nth-child({n}){{--i:{n - 1}}}" in CSS, n
    assert ".board>.card:nth-child(n+9){--i:8}" in CSS, "the ninth and later share a beat"


def test_a_panel_wears_one_signature() -> None:
    assert CSS.count(".card::before{") == 1
    sig = re.search(r"\.card::before\{([^}]*)\}", CSS).group(1)
    assert "height:2px" in sig and "var(--brand-p2)" in sig


def test_the_runs_trail_marches_the_way_the_run_went() -> None:
    path = re.search(r"#dmap #dmap-path path\{([^}]*)\}", MAP_STYLE).group(1)
    assert "stroke-dasharray:1 7" in path and "animation:march" in path
    assert "@keyframes march{to{stroke-dashoffset:-16}}" in MAP_STYLE, "two periods of the dash"


def test_one_skill_is_one_row_with_its_groups_under_it() -> None:
    js = ANALYTICS[ANALYTICS.index("function skills(rows)") :]
    js = js[: js.index("ACTIONS.setPeriod")]
    assert "by.get(k.skill)" in js, "grouped by skill"
    assert "k.override_rate * (k.decided || 0)" in js, "weighted by what each group decided"
    assert "practice group" in js, "and the groups are named under it"
    assert js.count('<div class="r">') == 1, "one row template, not one per group"


def test_the_server_carries_the_denominator_the_page_weights_by() -> None:
    import inspect

    from ops.analytics import Analytics

    source = inspect.getsource(Analytics._skills)
    assert '"decided": row["decided"]' in source


def test_the_runbook_names_a_landing_place_that_exists() -> None:
    needs_a_checkout("the knowledge folder the runbook points at")
    runbook = (ROOT / "docs" / "WORK-LAPTOP.md").read_text(encoding="utf-8")
    section = runbook[runbook.index("## 8. Bringing the model-setup skill") :]
    assert "skills/valuation/_group/model-setup/SKILL.md" in section
    for key in REQUIRED_FRONTMATTER:
        assert f"`{key}`" in section, key
    for path in (
        "skills/README.md",
        "skills/valuation/_group/model-load/SKILL.md",
        "skills/valuation/_repeat",
        "knowledge/model-setup",
        "templates/inputs",
        "tools/read_template.py",
        "tools/interview.py",
    ):
        assert path in section, path
        assert (ROOT / path).exists(), path
    assert (
        ROOT / "skills" / "valuation" / "_repeat" / "prior-year-rollforward" / "SKILL.md"
    ).is_file()
    assert "status: draft" in section, "a skill on its first day here is dispatched by nothing"


def test_the_private_half_has_its_three_sections_and_names_nobody() -> None:
    needs_a_checkout("the knowledge folder the runbook points at")
    private = (ROOT / "knowledge" / "model-setup" / "README.md").read_text(encoding="utf-8")
    for heading in (
        "## What goes here",
        "## What the skill does with it",
        "## What is still unknown",
    ):
        assert heading in private, heading
    assert "identifiers.txt" in private
    assert "knowledge/README.md" and "model-setup/" in (ROOT / "knowledge" / "README.md").read_text(
        encoding="utf-8"
    )


def test_a_workflow_with_an_unbuilt_step_gets_its_own_sentence() -> None:
    """The Setup page was printing RECIPE_INVALID's next action - "The recipe does not
    compile" - under a warning about a workflow that compiles and stops partway. A finding
    that is not that one does not get to borrow its sentence."""
    import inspect

    from admin.preflight import Preflight
    from registries.diagnostics import DiagnosticsRegistry
    from registries.errors import RECIPE_INVALID, RECIPE_UNBUILT

    registry = DiagnosticsRegistry.load()
    assert RECIPE_UNBUILT in registry
    what_now = registry.get(RECIPE_UNBUILT).what_now
    assert "compiles" in what_now and "stop" in what_now and "does not compile" not in what_now
    assert registry.get(RECIPE_UNBUILT).owner == registry.get(RECIPE_INVALID).owner == "config"

    source = inspect.getsource(Preflight._recipes_and_budgets)
    unbuilt = source[source.index("unbuilt_skills(RECIPES_DIR") : source.index("self._compile_for")]
    assert "RECIPE_UNBUILT," in unbuilt and "RECIPE_INVALID," not in unbuilt
    assert 'severity="warn"' in unbuilt, "and it still blocks nothing"

    blueprint = (ROOT / "docs" / "architecture.html").read_text(encoding="utf-8")
    assert blueprint.count("RECIPE_UNBUILT") == 1, "named once, in its SCOPE.* row"
