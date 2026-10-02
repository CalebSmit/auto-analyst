"""P42: the three consoles, made easier to use - and two bugs the reworking found.

What is tested is what a person relies on without looking: runs and review items name the
client; a review item shows its source before its proposal; nothing asks through a browser
pop-up; a finished run's live feed does not replay itself forever; and no page ships a script
that fails before it runs - which is how the Analytics page would have broken silently when a
shared helper took a name it already used.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.app import Console, create_app
from ops.events import EventBus
from ops.run_store import SqlRunStore
from tests.p23.conftest import ENGAGEMENT, Clock, clean_run, reviewed_run

PAGES = {"setup": SETUP, "activity": ACTIVITY, "analytics": ANALYTICS}


def scripts(page: str) -> str:
    return "\n;\n".join(re.findall(r"<script>(.*?)</script>", page, re.S))


# ------------------------------------------------------------------ every page


@pytest.mark.parametrize("name", PAGES)
def test_nothing_asks_through_a_browser_pop_up(name: str) -> None:
    """A pop-up cannot explain itself, cannot require a reason in context, and blocks the
    whole page. Every question is asked in the page instead."""
    body = scripts(PAGES[name])
    for call in ("prompt(", "confirm(", "alert("):
        assert not re.search(rf"(?<![\w.]){re.escape(call)}", body), f"{name} uses {call}"


@pytest.mark.parametrize("name", PAGES)
def test_no_page_declares_the_same_name_twice(name: str) -> None:
    """Two top-level declarations of one name are a syntax error, and a syntax error stops
    every script on the page. The shared shell and a page's own script are one namespace."""
    declared = re.findall(
        r"^(?:const|let|var|function|async function)\s+([A-Za-z_$][\w$]*)",
        scripts(PAGES[name]),
        re.M,
    )
    doubled = sorted({n for n in declared if declared.count(n) > 1})
    assert doubled == [], f"{name} declares {doubled} more than once"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed here")
@pytest.mark.parametrize("name", PAGES)
def test_every_page_script_parses(name: str, tmp_path: Path) -> None:
    target = tmp_path / f"{name}.js"
    target.write_text(scripts(PAGES[name]), encoding="utf-8")
    checked = subprocess.run(["node", "--check", str(target)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr


def test_the_activity_tab_says_what_is_waiting_on_every_page() -> None:
    for name, page in PAGES.items():
        assert "async function waiting()" in page, name
        assert 'rel="icon"' in page, name


# ------------------------------------------------------------------ activity


def test_a_review_item_shows_the_source_before_the_proposal() -> None:
    """The review surface's order: the question and the source, then - on request, and on
    the record - the proposal. Accepting or correcting is not offered until it is shown."""
    assert "/review/${itemId}/reveal" in ACTIVITY
    assert '<button data-d="accepted" disabled title="Show the proposal first">' in ACTIVITY
    assert '<button data-d="corrected" disabled title="Show the proposal first">' in ACTIVITY
    reveal_at = ACTIVITY.index("What the source says")
    proposal_at = ACTIVITY.index("What the system proposes")
    assert reveal_at < proposal_at


def test_a_finished_runs_stream_is_closed_rather_than_replayed_forever() -> None:
    """A closed EventSource reconnects on its own and replays the run's whole history into
    the feed again. So the page closes the stream itself once a run that has ended has
    finished replaying, and it never shows one event twice.

    Written as what the page must do rather than as the lines it did it in: P45 rewrote this
    block so a *live* run reconnects after a dropped connection, which is a different thing
    from replaying a finished one - and a test should not confuse the two either.
    """
    body = scripts(ACTIVITY)
    assert "if (ended() && source) source.close();" in body, "a finished run closes its own"
    assert "seen.has(ev.event_id || ev.seq)" in body, "an event already shown is not shown twice"
    assert "stream.onerror" in body, "and a dropped connection is noticed"


def test_a_refused_action_is_said_not_swallowed() -> None:
    """The old handler passed a caught error to a function that expects a response, so a
    refused resume, halt or decision failed without a word."""
    assert "catch (e) { refusal(e); }" not in ACTIVITY
    assert "catch (e) { say(e.text || String(e), 'bad', e.code); }" in ACTIVITY


def test_links_open_a_run_a_review_item_and_a_profile() -> None:
    """The property, not the spelling. P143 put Setup's prefixes in one table and made the
    router read it, because the page was handing out `#settings=` that the router did not
    know - so asserting the literal `startsWith('profile=')` here would now require the bug
    back. Activity still tests its prefixes directly; it has two and they are routed where
    they are written."""
    assert "wanted.startsWith('review=')" in ACTIVITY
    assert "'profile=': editProfile" in SETUP, "Setup no longer routes a profile link"
    assert 'href="#profile=' in SETUP, "and nothing links to one"


@pytest.fixture
def labelled(store: SqlRunStore, bus: EventBus) -> TestClient:
    clean_run(store, bus)
    reviewed_run(store, bus, run_id="run_open")
    store.open_review_item("run_open", "li_99", kind="tagging", subject="Which category?")
    names = {
        ENGAGEMENT: {"client": "Henderson Manufacturing", "scope_path": "valuation/non-esop/repeat"}
    }
    console = Console(store, bus, clock=Clock(), label_of=names.get)
    return TestClient(create_app(console))


def test_runs_and_review_items_name_the_client(labelled: TestClient) -> None:
    runs = labelled.get("/api/runs").json()
    assert {r["client"] for r in runs} == {"Henderson Manufacturing"}
    assert {r["scope_path"] for r in runs} == {"valuation/non-esop/repeat"}
    (item,) = [i for i in labelled.get("/api/review").json() if i["item_id"] == "li_99"]
    assert item["client"] == "Henderson Manufacturing"
    assert item["engagement_id"] == ENGAGEMENT


def test_without_a_roster_the_console_still_answers(store: SqlRunStore, bus: EventBus) -> None:
    clean_run(store, bus)
    runs = TestClient(create_app(Console(store, bus, clock=Clock()))).get("/api/runs").json()
    assert runs[0]["client"] == "" and runs[0]["engagement_id"] == ENGAGEMENT


# ------------------------------------------------------------------ setup


def test_the_profile_is_a_form_with_the_json_one_click_away() -> None:
    assert "function profileForm(profile)" in SETUP
    assert "Edit as JSON instead" in SETUP
    assert "readProfileForm" in SETUP
