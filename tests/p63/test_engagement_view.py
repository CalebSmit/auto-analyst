"""P63: an engagement view, and a way to find one client.

Everything on Activity was indexed by run, which is the system's unit and not the work's.
An analyst thinks in clients, and a repeat client has several runs behind one engagement,
so "where does Northgate stand" meant reading every row and noticing the ids repeating.
`/api/runs?engagement_id=` had existed unused since P23.

What is tested here is the fold and the find box: that an engagement line is folded from
the same rows the runs panel reads rather than from a second source, that it counts what
is open across every run behind it, that the page groups rather than lists, and that
narrowing is a redraw of what the browser already has. The last two tests are the ones
that matter for this repo's usual defect: each fails if the page stops doing the thing,
rather than passing on the mere presence of a word.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from ops.console.app import NEEDS_ATTENTION, Console, create_app
from ops.console.app import PAGE as ACTIVITY
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore
from tests.p23.conftest import ENGAGEMENT, OTHER_ENGAGEMENT, Clock, clean_run, reviewed_run

LABELS = {
    ENGAGEMENT: {"client": "Henderson Manufacturing", "scope_path": "valuation/non-esop"},
    OTHER_ENGAGEMENT: {"client": "Mercer Dental", "scope_path": "esop/annual"},
}


@pytest.fixture
def console(store: SqlRunStore, bus: EventBus) -> Console:
    return Console(store, bus, clock=Clock(), label_of=LABELS.get)


@pytest.fixture
def client(console: Console) -> TestClient:
    return TestClient(create_app(console))


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))


# ------------------------------------------------------------------ the fold


def test_a_repeat_client_is_one_line_not_three(
    console: Console, store: SqlRunStore, bus: EventBus
) -> None:
    """The whole point. Three runs on one engagement and one on another is two
    engagements, not four rows."""
    clean_run(store, bus, run_id="run_a1", engagement=ENGAGEMENT)
    clean_run(store, bus, run_id="run_a2", engagement=ENGAGEMENT)
    reviewed_run(store, bus, run_id="run_a3", engagement=ENGAGEMENT)
    clean_run(store, bus, run_id="run_b1", engagement=OTHER_ENGAGEMENT)

    lines = console.engagements()
    assert len(lines) == 2, "a repeat client read as several engagements"
    by_id = {line["engagement_id"]: line for line in lines}
    assert by_id[ENGAGEMENT]["runs"] == 3
    assert by_id[OTHER_ENGAGEMENT]["runs"] == 1
    assert set(by_id[ENGAGEMENT]["run_ids"]) == {"run_a1", "run_a2", "run_a3"}


def test_the_line_carries_the_client_name_a_person_would_search_for(
    console: Console, store: SqlRunStore, bus: EventBus
) -> None:
    clean_run(store, bus, run_id="run_a1", engagement=ENGAGEMENT)
    line = console.engagements()[0]
    assert line["client"] == "Henderson Manufacturing"
    assert line["scope_path"] == "valuation/non-esop"


def test_what_is_open_is_counted_across_every_run_behind_the_engagement(
    console: Console, store: SqlRunStore, bus: EventBus
) -> None:
    """A review item sits on a run; the question "what is open on Henderson" is about the
    engagement. Counting only the newest run's would under-report the client."""
    for run_id in ("run_a1", "run_a2"):
        script_ = reviewed_run(store, bus, run_id=run_id, engagement=ENGAGEMENT)
        script_.review(f"{run_id}_open", "line-item-tagging@0.1.0", confidence=0.42)

    line = console.engagements()[0]
    assert line["open_review_items"] == 2, "open items were counted on one run, not the engagement"


def test_needs_attention_is_counted_from_the_one_list_the_page_also_uses(
    console: Console, store: SqlRunStore, bus: EventBus
) -> None:
    """Two lists of the states that want a person would drift, and the one that drifted
    would be the one nobody was reading."""
    clean_run(store, bus, run_id="run_a1", engagement=ENGAGEMENT)
    reviewed_run(store, bus, run_id="run_a2", engagement=ENGAGEMENT)
    store.transition("run_a2", RunState.WAITING, reason="blocked on a person")

    line = console.engagements()[0]
    assert line["needs_attention"] == 1
    assert "waiting" in NEEDS_ATTENTION


def test_engagements_sort_by_what_moved_last(
    console: Console, store: SqlRunStore, bus: EventBus
) -> None:
    clean_run(store, bus, run_id="run_b1", engagement=OTHER_ENGAGEMENT)
    clean_run(store, bus, run_id="run_a1", engagement=ENGAGEMENT)

    lines = console.engagements()
    assert lines[0]["engagement_id"] == ENGAGEMENT, "the engagement that moved last is not first"


def test_the_fold_reads_the_same_rows_the_runs_panel_reads(
    console: Console, store: SqlRunStore, bus: EventBus
) -> None:
    """No second source. If these two could disagree, one of the screens would be wrong
    and there would be no way to tell which."""
    clean_run(store, bus, run_id="run_a1", engagement=ENGAGEMENT)
    reviewed_run(store, bus, run_id="run_a2", engagement=ENGAGEMENT)
    clean_run(store, bus, run_id="run_b1", engagement=OTHER_ENGAGEMENT)

    from_runs: dict[str, int] = {}
    for row in console.runs():
        from_runs[row["engagement_id"]] = from_runs.get(row["engagement_id"], 0) + 1
    from_fold = {line["engagement_id"]: line["runs"] for line in console.engagements()}
    assert from_runs == from_fold


def test_no_engagement_line_carries_a_valuation_date(
    console: Console, store: SqlRunStore, bus: EventBus
) -> None:
    """B-026 asked for one. The engagement profile has no such field - its two `as_of`
    dates belong to size_band and fiscal_calendar - so a valuation date here would be a
    number invented for the screen. Recorded in BUILD/OPEN.md instead; this test is what
    stops it being added quietly later."""
    clean_run(store, bus, run_id="run_a1", engagement=ENGAGEMENT)
    line = console.engagements()[0]
    assert not [k for k in line if "valuation" in k or k == "as_of"]


# ------------------------------------------------------------------ the route


def test_the_route_answers(client: TestClient, store: SqlRunStore, bus: EventBus) -> None:
    clean_run(store, bus, run_id="run_a1", engagement=ENGAGEMENT)
    response = client.get("/api/engagements")
    assert response.status_code == 200
    assert response.json()[0]["engagement_id"] == ENGAGEMENT


def test_the_route_that_existed_unused_still_narrows_to_one_engagement(
    client: TestClient, store: SqlRunStore, bus: EventBus
) -> None:
    """`/api/runs?engagement_id=` has been there since P23 with no caller. It is the
    server half of the same question, and it still answers."""
    clean_run(store, bus, run_id="run_a1", engagement=ENGAGEMENT)
    clean_run(store, bus, run_id="run_b1", engagement=OTHER_ENGAGEMENT)
    rows = client.get("/api/runs", params={"engagement_id": ENGAGEMENT}).json()
    assert [r["run_id"] for r in rows] == ["run_a1"]


# ------------------------------------------------------------------ the page


def test_the_page_groups_runs_rather_than_listing_them() -> None:
    """The panel builds a group per engagement and puts the runs inside it. Asserted on
    the structure it emits, not on the word "engagement" appearing somewhere."""
    body = script()
    assert "function paintRuns()" in body
    group = re.search(r"function paintRuns\(\)\s*\{(.*?)\n\}", body, re.S)
    assert group, "the page has no paintRuns"
    inner = group.group(1)
    assert "grp-head" in inner and "grp-runs" in inner, "runs are not nested under a group"
    assert "rs.map(runRow)" in inner, "a group does not render its own runs"


def test_the_find_box_exists_and_narrows_without_asking_the_server() -> None:
    """Narrowing is a redraw of what the page already has. A fetch here would make a
    person wait to be told something the browser knew."""
    assert 'id="q"' in ACTIVITY and 'type="search"' in ACTIVITY
    body = script()
    filtering = re.search(r"function matching\(\)\s*\{(.*?)\n\}", body, re.S)
    assert filtering, "the page has no filter"
    assert "RUNS.filter" in filtering.group(1)
    assert "get(" not in filtering.group(1), "the filter asks the server"
    assert "/api/" not in filtering.group(1)


def test_the_filter_matches_the_words_a_person_would_type() -> None:
    body = script()
    hay = re.search(r"function haystack\(r\)\s*\{(.*?)\n\}", body, re.S)
    assert hay, "the page says nothing about what it matches on"
    for field in ("client", "engagement_id", "scope_path", "run_id"):
        assert f"r.{field}" in hay.group(1), f"{field} is not searchable"
    assert "r.state" not in hay.group(1), "matching the state would hide runs behind a pill"


def test_clearing_the_filter_is_an_action_by_name_not_a_handler_in_the_markup() -> None:
    """`ui/who.py`'s rule: a page builds no handler out of data. The button carries a
    name and the table holds the behaviour."""
    assert 'data-act="clearFilter"' in ACTIVITY
    assert "ACTIONS.clearFilter" in script()


def test_the_page_and_the_server_agree_on_which_states_want_a_person() -> None:
    """The same pinning P45 does for FRAME. The page counts these for its chrome and
    `engagements()` counts them per engagement."""
    body = script()
    declared = re.search(r"const NEEDS_ATTENTION = new Set\(\[(.*?)\]\);", body, re.S)
    assert declared, "the page names no attention states"
    named = tuple(re.findall(r"'([a-z_]+)'", declared.group(1)))
    assert named == NEEDS_ATTENTION, "the page and the server disagree on what wants a person"


def test_a_filter_that_matches_nothing_says_so_rather_than_reading_as_no_work() -> None:
    """An empty panel is a claim that there is nothing to do. When a filter is what
    emptied it, the panel has to say that instead."""
    body = script()
    empty = re.search(r"No run matches(.*?)</div>", body, re.S)
    assert empty, "a filter that matches nothing falls through to the no-runs-yet panel"
    assert "Clear the box" in empty.group(1)
