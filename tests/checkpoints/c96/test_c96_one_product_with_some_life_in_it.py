"""Checkpoint C96 - one product with some life in it.

P171 put motion and atmosphere into the shared sheet and a hero band onto one page. The
question a checkpoint asks is about the four pages together: each is served with the one
theme, once; each carries the one reduced-motion rule that stops every animation the phase
added; the hero band is worn by the page that asked for it and no other; and the map's
trail, the skill table and the runbook's landing place are in the pages as the browser
gets them, not only in the Python strings the phase's own tests read.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.help_page import PAGE as HELP
from tests.conftest import needs_a_checkout
from tests.p171.test_a_dashboard_with_some_life_in_it import ADDED

PAGES = ((SETUP, "Setup"), (ACTIVITY, "Activity"), (ANALYTICS, "Analytics"), (HELP, "Help"))
ROOT = Path(__file__).resolve().parents[3]


def test_every_page_is_served_the_one_theme_once_with_the_one_switch_that_stops_it() -> None:
    for page, name in PAGES:
        assert page.count("@keyframes aurora{") == 1, name
        assert page.count("@media (prefers-reduced-motion:reduce)") == 1, name
        assert page.count("--shadow:") == 1, (name, "the elevation token is declared once")
        for motion in ADDED:
            if motion == "march":
                continue  # the map's, and only the Activity page carries the map
            assert f"@keyframes {motion}{{" in page, (name, motion)
    assert "@keyframes march{" in ACTIVITY
    assert all("@keyframes march{" not in page for page, name in PAGES if name != "Activity")


def test_the_hero_band_is_worn_by_the_page_that_asked_for_it_and_no_other() -> None:
    assert ANALYTICS.count('class="metrics hero"') == 1
    for page, name in PAGES:
        if name != "Analytics":
            assert "metrics hero" not in page, name
    assert ".metrics.hero{" in ANALYTICS, "and the rule it wears is in the sheet it is served with"


def test_the_activity_page_serves_the_trail_and_the_analytics_page_serves_one_row_per_skill(
    tmp_path: Path,
) -> None:
    from ops.console import Console
    from ops.console.app import create_app
    from ops.events import EventBus
    from ops.run_store import open_store
    from registries.contracts import ContractRegistry

    store = open_store(f"sqlite:///{(tmp_path / 'c96.db').as_posix()}")
    try:
        bus = EventBus(store, contracts=ContractRegistry.load())
        api = TestClient(create_app(Console(store, bus)))
        activity = api.get("/").text
        analytics = api.get("/analytics").text
    finally:
        store.close()
    assert "animation:march 1.4s linear infinite" in activity
    assert "by.get(k.skill)" in analytics and "k.override_rate * (k.decided || 0)" in analytics
    assert re.search(r"radial-gradient\([^)]*var\(--brand-p4\)", activity), "lit paper"


def test_the_runbooks_landing_place_is_a_folder_the_tree_would_read() -> None:
    """Section 8 says the skill goes in the valuation group's layer. That layer exists, the
    tree reads it, and its sibling skills carry the front matter the section lists."""
    needs_a_checkout("the knowledge folder the runbook points at")
    from registries.skills import REQUIRED_FRONTMATTER, SkillTree

    layer = ROOT / "skills" / "valuation" / "_group"
    assert layer.is_dir()
    assert any(s.name == "model-load" for s in SkillTree.load().at("valuation/_group")), (
        "the layer is read"
    )
    sibling = (layer / "model-load" / "SKILL.md").read_text(encoding="utf-8")
    for key in REQUIRED_FRONTMATTER:
        assert re.search(rf"^{key}:", sibling, re.M), key
    private = ROOT / "knowledge" / "model-setup" / "README.md"
    assert private.is_file()
    assert not (layer / "model-setup").exists(), "the slot is described, not pre-filled"
