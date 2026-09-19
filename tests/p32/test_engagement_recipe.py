"""P32: what order the work happens in belongs to the engagement.

The recipe was a property of the watched folder. Two engagements found under one watch ran
the same recipe because they arrived through the same tree - a fact about filing, not about
the work - and the only way around it was a second watch over the same folder, which the
overlap check refuses, correctly.

Three claims:

1. Two engagements under one watch run different recipes.
2. An engagement naming no recipe behaves exactly as it did before this phase.
3. A recipe that does not load is refused at setup, naming the engagement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from admin.console import AdminConsole, AdminRefused
from intake.config import CONTRACT, SUPPORTED, ConfigStore
from intake.roster import ProjectRoster
from intake.sweep import SweepPlanner
from tests.p29.conftest import HEND, NOVK, WHO

ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------- the engagement's own


def test_two_engagements_under_one_watch_run_different_recipes(
    console: AdminConsole, roster: ProjectRoster, both: tuple[str, str]
) -> None:
    """The first exit criterion, and the whole point of the phase."""
    console.set_recipe(HEND, "monthly-refresh", who=WHO, reason="a returning client")
    console.set_recipe(NOVK, "full-ddr-intake", who=WHO, reason="first year, full intake")

    assert roster.get(HEND).recipe == "monthly-refresh"
    assert roster.get(NOVK).recipe == "full-ddr-intake"
    assert {e.watch_id for e in roster.entries()} == {"w-val"}, "one watch, two answers"


def test_the_sweep_plans_each_engagement_with_its_own_recipe(
    console: AdminConsole,
    roster: ProjectRoster,
    config: ConfigStore,
    environment: dict[str, Path],
    both: tuple[str, str],
) -> None:
    """Not just recorded - carried. The planner is what turns a folder into a run, and it
    is where a recipe stops being a setting and starts deciding what happens."""
    for engagement in both:
        console.activate(engagement, who=WHO, reason="ready")
    console.set_recipe(NOVK, "full-ddr-intake", who=WHO, reason="first year")

    import ports
    from intake.store import IntakeStore

    # A folder the sweeper can see is a folder with something in it.
    novak = environment["inbox"] / "Clients" / "Novak Industrial" / "2026 ESOP"
    novak.mkdir(parents=True)
    henderson_folder = environment["inbox"] / "Clients" / "Henderson Manufacturing"
    for folder in (novak, henderson_folder / "2026 ESOP"):
        (folder / "trial balance FY25.csv").write_text("account,amount\n", encoding="utf-8")

    planner = SweepPlanner(
        roster,
        config,
        ports.get_storage(),
        IntakeStore(console.config._store),  # noqa: SLF001
    )
    by_engagement = {t.engagement_id: t.recipe for t in planner.plan().targets}

    assert by_engagement[HEND] == "monthly-refresh", "inherited from the watch"
    assert by_engagement[NOVK] == "full-ddr-intake", "its own"


# ------------------------------------------------------------- naming none


def test_an_engagement_naming_no_recipe_is_unchanged(
    roster: ProjectRoster, config: ConfigStore, henderson: Any
) -> None:
    """The second exit criterion. Every engagement that existed before this phase named
    no recipe, and inherit has to mean exactly what it always did - not "the watch's, via
    a new mechanism that might one day differ"."""
    entry = roster.get(HEND)
    assert entry.recipe == "", "empty, not the watch's name"
    assert config.recipe(HEND) == ""

    watch = next(w for w in config.watches() if w.id == entry.watch_id)
    assert watch.recipe == "monthly-refresh"
    assert (entry.recipe or watch.recipe) == "monthly-refresh"


def test_clearing_a_recipe_puts_it_back_to_inheriting(
    console: AdminConsole, roster: ProjectRoster, henderson: Any
) -> None:
    """Undo has to exist, and it has to be the same word as never having chosen."""
    console.set_recipe(HEND, "full-ddr-intake", who=WHO, reason="trying it")
    assert roster.get(HEND).recipe == "full-ddr-intake"

    console.set_recipe(HEND, "", who=WHO, reason="back to the watch's")
    assert roster.get(HEND).recipe == ""
    assert "recipe" not in console.config.engagement(HEND), "removed, not blanked"


def test_choosing_a_recipe_is_logged_like_every_other_change(
    console: AdminConsole, henderson: Any
) -> None:
    """A configuration change nobody can attribute is a configuration change nobody can
    argue with later."""
    before = len(console.changes())
    console.set_recipe(HEND, "full-ddr-intake", who="R. Partner", reason="first year work")
    after = console.changes()

    assert len(after) > before
    latest = [
        c for c in after
        if "recipe" in json.dumps(c.__dict__ if hasattr(c, "__dict__") else c)
    ]
    assert latest, "the change log names the field"


# ------------------------------------------------------------- refusing


def test_a_recipe_that_does_not_load_is_refused_when_it_is_chosen(
    console: AdminConsole, henderson: Any
) -> None:
    """The third exit criterion. Refused where the person choosing it is still reading,
    rather than on the run it would have broken."""
    with pytest.raises(AdminRefused) as refused:
        console.set_recipe(HEND, "not-a-recipe", who=WHO, reason="a typo")

    diagnostic = refused.value.diagnostics[0]
    assert diagnostic.code == "SCOPE.RECIPE_INVALID"
    assert HEND in diagnostic.detail and "not-a-recipe" in diagnostic.detail
    assert diagnostic.what_now
    assert console.config.recipe(HEND) == "", "nothing was written"


def test_preflight_names_the_engagement_whose_recipe_will_not_load(
    console: AdminConsole, config: ConfigStore, henderson: Any
) -> None:
    """The surface refuses, and preflight is the belt: a document edited outside the
    console, or a recipe deleted after it was chosen, still gets caught before a run."""
    console.activate(HEND, who=WHO, reason="ready")
    document = config.document()
    document["schema_version"] = CONTRACT
    document["engagements"] = {
        **(document.get("engagements") or {}),
        HEND: {**(document.get("engagements") or {}).get(HEND, {}), "recipe": "went-away"},
    }
    config.write(document, who=WHO, reason="a recipe that was removed from the repo")

    check = next(c for c in console.check().checks if c.id == "recipes_and_budgets")
    assert check.status == "fail"
    assert [f.diagnostic.locator for f in check.failures] == [f"engagements/{HEND}/recipe"]
    assert check.failures[0].engagement_ids == (HEND,)
    assert "engagement(s) with their own" in check.detail


def test_an_unknown_engagement_cannot_be_given_a_recipe(console: AdminConsole) -> None:
    with pytest.raises(KeyError):
        console.set_recipe("NOPE-2026-01", "monthly-refresh", who=WHO, reason="typo")


# ------------------------------------------------------------- the contract


def test_the_document_is_checked_against_the_version_it_declares(
    config: ConfigStore, henderson: Any
) -> None:
    """1.1.0 stays listed and stays readable. Checking every document against the newest
    version would make each new version retroactively invalidate every document already
    written, which is the opposite of leaving the old one listed."""
    # 1.3.0 joined at P79 (where last year's model is). Every older version stays, and
    # the newest is first - which is the order `write` picks from.
    assert SUPPORTED == (
        "config_document@1.3.0",
        "config_document@1.2.0",
        "config_document@1.1.0",
    )

    document = config.document()
    assert document["schema_version"] == "config_document@1.1.0", "written by the fixture"
    config.write(document, who=WHO, reason="rewritten as it stands")  # still valid

    document["schema_version"] = "config_document@0.9.0"
    with pytest.raises(ValueError, match="not a configuration version"):
        config.write(document, who=WHO, reason="a version that does not exist")


def test_writing_a_recipe_upgrades_the_document_and_nothing_else_does(
    console: AdminConsole, config: ConfigStore, henderson: Any
) -> None:
    """1.1.0 has no field for a recipe, so a document that gains one becomes 1.2.0. A
    document that does not stays what it was - a version bump nobody needed is a change
    to a record for no reason."""
    assert config.document()["schema_version"] == "config_document@1.1.0"

    console.set_budget(HEND, 15.0, who=WHO, reason="unrelated change")
    assert config.document()["schema_version"] == "config_document@1.1.0", "unchanged"

    console.set_recipe(HEND, "full-ddr-intake", who=WHO, reason="first year")
    assert config.document()["schema_version"] == CONTRACT


def test_both_versions_are_registered_and_1_1_0_is_still_there() -> None:
    """A version is never edited in place. A document already written is still a document
    that has to be readable."""
    import yaml

    registry = yaml.safe_load((ROOT / "contracts" / "registry.yaml").read_text(encoding="utf-8"))
    versions = [
        row["version"] for row in registry["contracts"] if row["id"] == "config_document"
    ]
    assert versions == ["1.0.0", "1.1.0", "1.2.0", "1.3.0"]

    for version in ("1.1.0", "1.2.0", "1.3.0"):
        schema = json.loads(
            (ROOT / "contracts" / f"config_document@{version}.schema.json").read_text(
                encoding="utf-8"
            )
        )
        assert schema["properties"]["schema_version"]["const"] == f"config_document@{version}"

    latest = json.loads(
        (ROOT / "contracts" / "config_document@1.2.0.schema.json").read_text(encoding="utf-8")
    )
    recipe = latest["properties"]["engagements"]["additionalProperties"]["properties"]["recipe"]
    assert recipe["type"] == "string" and recipe["minLength"] == 1
    assert "inherits the watch" in recipe["description"]


def test_the_surface_offers_it_over_http(console: AdminConsole, henderson: Any) -> None:
    from fastapi.testclient import TestClient

    from admin.app import create_admin_app

    client = TestClient(create_admin_app(console))
    ok = client.post(
        f"/api/admin/engagements/{HEND}/recipe",
        json={"who": WHO, "reason": "first year", "recipe": "full-ddr-intake"},
    )
    assert ok.status_code == 200 and ok.json()["version"] > 0

    refused = client.post(
        f"/api/admin/engagements/{HEND}/recipe",
        json={"who": WHO, "reason": "a typo", "recipe": "not-a-recipe"},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["refused"][0]["code"] == "SCOPE.RECIPE_INVALID"

    row = next(r for r in console.setup()["roster"] if r["engagement_id"] == HEND)
    assert row["recipe"] == "full-ddr-intake", "the surface shows what it runs"
