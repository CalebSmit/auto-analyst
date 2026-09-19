"""C47 - Setting up a repeat client, with everything that needs saying.

P79 added the field the analyst asked for by name and nobody had built. A checkpoint asks
the part a unit test cannot: whether a person setting up a real repeat engagement is now
asked for everything the repeat path needs, and whether an older configuration - written
before the field existed - still means what it meant.

That second half is the one worth guarding. Versioned contracts are only worth their cost
if the old versions keep working, and the temptation when adding a field is to migrate
every document to the newest version because it is tidier. A first-year client's
configuration should never acquire a field about last year.
"""

from __future__ import annotations

import json
from pathlib import Path

from intake.config import CONTRACT, SUPPORTED

ROOT = Path(__file__).resolve().parents[3]


def test_the_newest_version_is_the_one_written_and_the_old_ones_still_load() -> None:
    assert SUPPORTED[0] == CONTRACT, "the newest is what a write produces"
    for version in SUPPORTED:
        name = version.split("@", 1)[1]
        schema = ROOT / "contracts" / f"config_document@{name}.schema.json"
        assert schema.is_file(), f"{version} is supported and its schema is gone"
        loaded = json.loads(schema.read_text(encoding="utf-8"))
        assert loaded["properties"]["schema_version"]["const"] == version


def test_no_version_was_edited_in_place() -> None:
    """The registry says it in its own note. Each older schema still describes what it
    described: 1.1.0 knows nothing of a recipe, 1.2.0 nothing of a prior model."""

    def keys(version: str) -> set[str]:
        path = ROOT / "contracts" / f"config_document@{version}.schema.json"
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return set(loaded["properties"]["engagements"]["additionalProperties"]["properties"])

    assert "recipe" not in keys("1.1.0")
    assert "prior_model" not in keys("1.2.0")
    assert "prior_model" in keys("1.3.0")
    assert keys("1.2.0") < keys("1.3.0"), "a version adds rather than replaces"


def test_an_engagement_naming_no_prior_model_is_not_upgraded(console, tmp_path: Path) -> None:
    """A first-year client's configuration should not acquire a field about last year just
    because somebody else's engagement did."""
    from intake.roster import RosterEntry, RosterState

    console.register_engagement(
        RosterEntry(
            engagement_id="FIRST-2026",
            client="First",
            scope_path="valuation/non-esop/non-repeat",
            watch_id="w1",
            destination_id="d1",
            state=RosterState.PAUSED,
            folder="First",
        ),
        profile=None,
        who="C. Smit",
        reason="test",
    )
    before = console.config.document().get("schema_version")
    console.set_review_level("FIRST-2026", "elevated", who="C. Smit", reason="test")
    assert console.config.document().get("schema_version") == before


def test_a_repeat_engagement_is_told_what_it_still_needs(console, tmp_path: Path) -> None:
    """The whole point of the field: the roster says so, where somebody looking at their
    engagements will see it rather than inside a dialog they have no reason to open."""
    from intake.roster import RosterEntry, RosterState

    console.register_engagement(
        RosterEntry(
            engagement_id="AGAIN-2026",
            client="Again",
            scope_path="valuation/non-esop/repeat",
            watch_id="w1",
            destination_id="d1",
            state=RosterState.PAUSED,
            folder="Again",
        ),
        profile=None,
        who="C. Smit",
        reason="test",
    )
    row = next(r for r in console.setup()["roster"] if r["engagement_id"] == "AGAIN-2026")
    assert row["is_repeat"] and not row["prior_model"]
    assert console.needs_a_prior_model("AGAIN-2026")

    book = tmp_path / "prior.xlsx"
    book.write_bytes(b"x")
    console.set_prior_model("AGAIN-2026", str(book), who="C. Smit", reason="setup")
    assert not console.needs_a_prior_model("AGAIN-2026")


def test_the_page_and_the_console_agree_about_which_engagements_are_repeat() -> None:
    """The page is handed `is_repeat` rather than splitting a scope path, so there is one
    place that knows which segment means repeat."""
    from admin.page import PAGE

    assert "r.is_repeat" in PAGE
    assert "scope_path.split" not in PAGE and "scope_path.rsplit" not in PAGE
