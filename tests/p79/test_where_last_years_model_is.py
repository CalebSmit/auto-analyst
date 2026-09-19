"""P79: where last year's model is.

The analyst asked for this field by name. Asked in the fourth interview how the system
should get hold of last year's model for a repeat client, he said: *"In the set up, I would
point it to the right box file location."* It did not exist - not on the engagement, not in
the profile, nowhere - and 75% of engagements are repeat clients whose work begins by
opening last year's workbook: historicals copied forward, years shifted, WS line items
carried across as this year's schema. Everything in B-036 waited behind a path nobody could
type.

`test_a_path_that_is_not_there_is_refused_immediately` is the one that matters. The failure
this surface keeps producing is not an error - it is an engagement that registers cleanly,
looks right, and never does anything, because a path was wrong and nothing looked at it
until a run needed it, by which time whoever typed it is somewhere else.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from admin.console import AdminRefused
from intake.roster import RosterEntry, RosterState

REPEAT = "valuation/non-esop/repeat"
NEW = "valuation/non-esop/non-repeat"


@pytest.fixture
def registered(console, tmp_path: Path):
    """Two engagements: one a repeat client, one a first-year client."""

    def put(engagement_id: str, scope: str) -> None:
        console.register_engagement(
            RosterEntry(
                engagement_id=engagement_id,
                client=engagement_id,
                scope_path=scope,
                watch_id="w1",
                destination_id="d1",
                state=RosterState.PAUSED,
                folder=engagement_id,
            ),
            profile=None,
            who="C. Smit",
            reason="test",
        )

    put("REPEAT-2026", REPEAT)
    put("FIRST-2026", NEW)
    return console


def workbook(tmp_path: Path, name: str = "last year.xlsx") -> Path:
    path = tmp_path / name
    path.write_bytes(b"not really a workbook, but really a file")
    return path


# ------------------------------------------------------------------ it can be set


def test_a_repeat_engagement_can_be_pointed_at_last_years_workbook(
    registered, tmp_path: Path
) -> None:
    where = workbook(tmp_path)
    registered.set_prior_model("REPEAT-2026", str(where), who="C. Smit", reason="setup")
    assert registered.prior_model("REPEAT-2026") == str(where.resolve())


def test_the_setting_survives_being_read_back_from_the_configuration(
    registered, tmp_path: Path
) -> None:
    """Stored in the configuration document like the recipe, not held in memory."""
    where = workbook(tmp_path)
    registered.set_prior_model("REPEAT-2026", str(where), who="C. Smit", reason="setup")
    doc = registered.config.document()
    assert doc["engagements"]["REPEAT-2026"]["prior_model"] == str(where.resolve())


def test_the_path_is_normalised_rather_than_stored_as_typed(
    registered, tmp_path: Path
) -> None:
    """A path that works today and means something else tomorrow.

    Asserting only that the stored value is absolute proved nothing - a path typed from a
    file picker already is, so the assertion held whether or not anything normalised it.
    This gives it one that needs resolving: the same file, reached through a redundant
    segment, as a copied path or a drag-and-drop often is.
    """
    where = workbook(tmp_path)
    awkward = tmp_path / "sub" / ".." / where.name
    (tmp_path / "sub").mkdir()

    registered.set_prior_model("REPEAT-2026", str(awkward), who="C. Smit", reason="setup")
    stored = registered.prior_model("REPEAT-2026")
    assert stored == str(where.resolve())
    assert ".." not in stored, "stored as typed rather than resolved"


def test_a_pasted_path_in_quotes_is_accepted(registered, tmp_path: Path) -> None:
    """Windows' "copy as path" wraps the path in quotes, and somebody pasting one should
    not have to know that."""
    where = workbook(tmp_path)
    registered.set_prior_model("REPEAT-2026", f'"{where}"', who="C. Smit", reason="setup")
    assert registered.prior_model("REPEAT-2026") == str(where.resolve())


def test_clearing_it_is_how_a_mistake_is_undone(registered, tmp_path: Path) -> None:
    where = workbook(tmp_path)
    registered.set_prior_model("REPEAT-2026", str(where), who="C. Smit", reason="setup")
    registered.set_prior_model("REPEAT-2026", "", who="C. Smit", reason="wrong file")
    assert registered.prior_model("REPEAT-2026") == ""


# ------------------------------------------------------------------ and it is checked


def test_a_path_that_is_not_there_is_refused_immediately(registered, tmp_path: Path) -> None:
    """The failure this prevents does not look like a failure: the engagement registers,
    everything reads correctly, and no run ever finds the file."""
    missing = tmp_path / "not here.xlsx"
    with pytest.raises(AdminRefused) as refused:
        registered.set_prior_model("REPEAT-2026", str(missing), who="C. Smit", reason="setup")
    said = str(refused.value)
    assert "not here.xlsx" in said, "the refusal must name what was not found"
    assert registered.prior_model("REPEAT-2026") == "", "nothing was written"


def test_a_folder_is_not_a_workbook(registered, tmp_path: Path) -> None:
    """Pointing at the client's folder rather than the file in it is the obvious slip."""
    with pytest.raises(AdminRefused):
        registered.set_prior_model("REPEAT-2026", str(tmp_path), who="C. Smit", reason="setup")


def test_the_refusal_says_a_synced_path_rather_than_a_link(registered, tmp_path: Path) -> None:
    """Somebody will paste a Box web link. Saying so is the difference between one more
    attempt and a support question."""
    with pytest.raises(AdminRefused) as refused:
        registered.set_prior_model(
            "REPEAT-2026", "https://app.box.com/file/12345", who="C. Smit", reason="setup"
        )
    assert "not a web link" in str(refused.value)


def test_an_unknown_engagement_is_a_clean_refusal(registered, tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        registered.set_prior_model("NOBODY-2026", str(workbook(tmp_path)), who="x", reason="y")


# ------------------------------------------------------------------ who is asked


def test_a_repeat_engagement_without_one_is_reported_as_incomplete(registered) -> None:
    assert registered.needs_a_prior_model("REPEAT-2026")


def test_a_first_year_client_is_never_asked(registered) -> None:
    """A new client has no last year. A checklist that demanded one would be asking for a
    file that does not exist, which is how somebody learns to ignore the checklist."""
    assert not registered.needs_a_prior_model("FIRST-2026")


def test_once_set_it_stops_being_reported(registered, tmp_path: Path) -> None:
    registered.set_prior_model(
        "REPEAT-2026", str(workbook(tmp_path)), who="C. Smit", reason="setup"
    )
    assert not registered.needs_a_prior_model("REPEAT-2026")


def test_the_roster_row_carries_it_so_the_page_need_not_parse_a_scope_path(
    registered, tmp_path: Path
) -> None:
    """Which segment of the scope path means repeat is this module's business. A page
    splitting the string would be a second place to be wrong about it."""
    registered.set_prior_model(
        "REPEAT-2026", str(workbook(tmp_path)), who="C. Smit", reason="setup"
    )
    rows = {r["engagement_id"]: r for r in registered.setup()["roster"]}
    assert rows["REPEAT-2026"]["is_repeat"] is True
    assert rows["REPEAT-2026"]["prior_model"].endswith("last year.xlsx")
    assert rows["FIRST-2026"]["is_repeat"] is False
    assert rows["FIRST-2026"]["prior_model"] == ""


# ------------------------------------------------------------------ and it is on the page


def test_the_page_offers_it_only_for_a_repeat_engagement() -> None:
    from admin.page import PAGE

    assert "row.is_repeat ? [{name: 'prior'" in PAGE.replace("{{", "{").replace("}}", "}")
    assert "Last year" in PAGE


def test_the_page_says_when_a_repeat_engagement_has_not_been_pointed_anywhere() -> None:
    """On the roster, where somebody looking at their engagements will see it - not only
    inside a settings dialog they have no reason to open."""
    from admin.page import PAGE

    assert "last year&rsquo;s model: not set" in PAGE
    assert "nothing to roll forward from" in PAGE
