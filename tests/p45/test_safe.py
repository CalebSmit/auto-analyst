"""P45: the console can be left open on a machine that holds client work.

Three of these are about what a client's own file can do to the page that reads it, three
about what another website can do to a server bound to loopback, and the rest about what the
page does when something breaks - because a dashboard that looks calm while it is broken is
worse than one that says so.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import FRAME, Console, create_app
from ops.console.app import PAGE as ACTIVITY
from ops.console.help_page import PAGE as HELP
from ops.events import EventBus
from ops.run_store import SqlRunStore
from tests.p23.conftest import Clock, clean_run
from ui.theme import SHELL

PAGES = {"setup": SETUP, "activity": ACTIVITY, "analytics": ANALYTICS, "help": HELP}


def scripts(page: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", page, re.S))


@pytest.fixture
def client(store: SqlRunStore, bus: EventBus) -> TestClient:
    clean_run(store, bus)
    return TestClient(create_app(Console(store, bus, clock=Clock())))


# --------------------------------------------- what a client's file can do to the page


def test_a_quote_cannot_close_anything() -> None:
    """`esc` escaped `& < > "`. Every row wrote an id into a single-quoted JS string inside
    an onclick, so an apostrophe closed it: `Owner's draw` and `O'Brien` are ordinary in a
    trial balance, and a label is whatever the client typed."""
    (line,) = re.findall(r"const esc = .*?;", SHELL, re.S)
    for ch in ("&", "<", ">", '"', "'", "`"):
        assert ch in line, f"esc does not escape {ch!r}"


@pytest.mark.parametrize("name", PAGES)
def test_no_page_writes_a_handler_out_of_data(name: str) -> None:
    """Escaping the apostrophe would not have been enough: the browser decodes an entity in
    an attribute before the JavaScript is parsed, so the value is back to a bare quote by the
    time it matters. Values reach a handler as data instead."""
    body = PAGES[name]
    generated = re.findall(r'on\w+="[^"]*\$\{[^"]*"', body)
    assert generated == [], f"{name} builds script out of data: {generated[:2]}"


def listens_for(event: str) -> bool:
    """Whether the one dispatcher hears this kind of event.

    P146 derived the listeners from the `CLIMBS` table rather than writing one line per
    event, so that the list of events a handler may travel on is written down once. These
    two tests used to look for the `addEventListener` line itself, which is the spelling
    rather than the property.
    """
    table = re.search(r"const CLIMBS = \{([^}]*)\}", SHELL)
    assert table, "the dispatcher no longer says which events it carries"
    bound = re.search(
        r"for \(const kind of Object\.keys\(CLIMBS\)\) document\.addEventListener", SHELL
    )
    assert bound, "the table is written down and nothing binds it"
    return event in dict(re.findall(r"(\w+):\s*(true|false)", table.group(1)))



def test_a_row_carries_its_id_and_the_page_says_once_what_that_means() -> None:
    body = scripts(ACTIVITY)
    assert 'data-act="open" data-run=' in body
    assert "ACTIONS.open = d => open_(d.run);" in body
    assert "ACTIONS" in SHELL and listens_for("click"), "a press no longer reaches a row"


@pytest.mark.parametrize("name", ["setup", "activity"])
def test_a_row_can_be_reached_from_the_keyboard(name: str) -> None:
    """A row that only answers a mouse cannot be used at all by somebody working from the
    keyboard, and the runs list is how every other panel is reached."""
    assert 'role="button" tabindex="0"' in PAGES[name] or "data-act=" in PAGES[name]
    assert listens_for("keydown"), "a row cannot be reached from the keyboard"


def test_what_the_app_says_is_announced() -> None:
    """The toast is the only channel the app ever speaks on - every refusal, every reason a
    form was rejected - and it was said to nobody."""
    assert "role', kind === 'bad' ? 'alert' : 'status'" in SHELL
    assert "aria-live" in SHELL


# --------------------------------------------- what another website can do to the server


def test_a_page_at_another_name_cannot_drive_this_one(client: TestClient) -> None:
    """The identity port authenticates the socket's peer address, and a browser presents this
    machine's address whatever page asked it to: a hostname pointed at 127.0.0.1 is
    same-origin with the console. The Host it arrives under is not one this server answers to.
    """
    refused = client.get("/api/runs", headers={"host": "rebound.example.com"})
    assert refused.status_code == 403
    assert "host" in refused.text
    assert client.get("/api/runs", headers={"host": "127.0.0.1:8000"}).status_code == 200


def test_a_request_from_another_origin_is_refused(client: TestClient) -> None:
    refused = client.post(
        "/api/runs/run_clean/review/x/reveal",
        headers={"origin": "https://elsewhere.example"},
        json={},
    )
    assert refused.status_code == 403 and "origin" in refused.text


def test_the_ops_routes_carry_the_check_themselves(client: TestClient) -> None:
    """`create_app` is public. An entry point that served it alone would have served every
    run, every review excerpt and every released workbook with no check at all."""
    import inspect

    from ops.console import app as module

    assert "install_identity(app)" in inspect.getsource(module.create_app)


def test_the_peer_address_is_not_taken_from_a_header() -> None:
    """uvicorn trusts `X-Forwarded-For` from a trusted peer by default, and on a loopback
    bind every peer is trusted - so the one input the identity check has could be rewritten
    by the request itself.

    Read from the call's own arguments. This asserted `"proxy_headers=False" in source`,
    and the phrase occurs twice in `serve.py`: once as the keyword argument and once in
    the comment explaining why it is there. Deleting the argument left the test green -
    defeated by a good comment, which is not something anybody can be told to stop
    writing. tests/reading.py has the rule."""
    import ast
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "tools" / "serve.py").read_text(
        encoding="utf-8"
    )
    calls = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "uvicorn"
    ]
    assert calls, "tools/serve.py no longer starts uvicorn"
    for call in calls:
        given = {kw.arg: kw.value for kw in call.keywords}
        said = given.get("proxy_headers")
        assert isinstance(said, ast.Constant) and said.value is False, (
            "uvicorn is not told to distrust X-Forwarded-For"
        )


# --------------------------------------------- when something breaks


@pytest.mark.parametrize("name", ["setup", "activity", "analytics"])
def test_a_page_that_cannot_reach_the_server_says_so(name: str) -> None:
    """Every panel used to catch to an empty list, so a dead server rendered as "No runs yet"
    with a tutorial - the page's own legend says never ran and passed are the two answers it
    matters most not to confuse."""
    page = PAGES[name]
    assert '<div id="offline"></div>' in page, f"{name} has nowhere to say it"
    assert "offline(e)" in scripts(page), f"{name} does not say it"
    assert "function offline(err)" in SHELL and "function online()" in SHELL


def test_the_page_stops_asking_when_nobody_is_looking() -> None:
    """Three requests every five seconds, all day, into a background tab - and at full rate
    against a server that is not answering."""
    assert "function poll(fn, ms)" in SHELL
    assert "document.hidden" in SHELL
    assert "setInterval" not in SHELL + scripts(ACTIVITY) + scripts(ANALYTICS)


def test_the_layout_has_a_width_below_which_it_scrolls() -> None:
    """One screen with no scrolling is a good rule at a desk and a trap on a laptop: the
    columns get to about 310px, rows overflow, and the page cannot scroll to reach them.

    This used to check for `html,body{overflow:auto}` in the narrow block. P142 made the
    page scroll at *every* width, which is the stronger version of the same thing, and
    P146 took the declaration out once it was shown to be undoing nothing. So the property
    is asked of the base rules now, where it actually lives, plus the one thing the narrow
    block is still for.
    """
    import re

    from ui.theme import CSS

    for selector in ("html", "body"):
        rule = re.search(r"(?:^|\n)" + selector + r"\{([^}]*)\}", CSS)
        assert rule, f"{selector} has no rule"
        assert "overflow:hidden" not in rule.group(1), f"{selector} clips the page again"
    assert "@media (max-width:1100px)" in CSS, "there is no width below which the board folds"
    narrow = CSS[CSS.index("@media (max-width:1100px)") :]
    assert ".board{display:block!important}" in narrow[: narrow.index("\n}")], (
        "below a desk's width the board is still three columns of about 310px"
    )


# --------------------------------------------- dialogs, and the live feed


def test_a_dialog_reads_its_own_fields() -> None:
    """Two dialogs carry the same field ids, and getElementById answers with whichever came
    first in the document - so a second review item wired the visible dialog's buttons to the
    hidden one's fields."""
    body = scripts(ACTIVITY)
    assert "const mine = sel => box.querySelector(sel);" in body
    assert "$('rv-submit')" not in body and "$('rv-rationale')" not in body
    assert "const field = n => box.querySelector('#ask_' + n);" in SHELL


def test_a_decision_cannot_be_sent_twice() -> None:
    """The second send carries the version the first one just consumed, so the surface
    refuses it as stale - and the person is shown a red refusal for work that succeeded."""
    body = scripts(ACTIVITY)
    assert "if (sending) return;" in body
    assert "sending = true;" in body


def test_one_dialog_at_a_time_and_the_focus_comes_back() -> None:
    assert "function openModal(box)" in SHELL
    assert "document.querySelectorAll('.modal').forEach(m => m.remove());" in SHELL
    assert "came_from.focus()" in SHELL
    assert "document.removeEventListener('keydown', onKey)" in SHELL


def test_the_feed_cannot_drop_an_event_type_it_has_not_met(client: TestClient) -> None:
    """A browser delivers a named SSE frame only to a listener registered for that name, and
    the page cannot know every type the system will emit. One name; the type is in the body."""
    body = scripts(ACTIVITY)
    assert f"const FRAME = '{FRAME}';" in body, "the page and the server disagree on the name"
    assert "stream.addEventListener(FRAME, handler(stream))" in body
    assert "const known = [" not in body, "no hard-coded list of types is consulted"

    with client.stream("GET", "/api/runs/run_clean/stream?follow=false") as response:
        text = "".join(response.iter_text())
    names = {line[len("event: ") :] for line in text.splitlines() if line.startswith("event: ")}
    assert names == {FRAME}
    assert '"type": "step.started"' in text, "the type is in the body"


def test_a_dropped_connection_is_resumed_from_where_it_stopped() -> None:
    """It used to close for good on any error and say "the run ended, or the console lost the
    bus", which reads like the run ended - while the rest of the page kept refreshing."""
    body = scripts(ACTIVITY)
    assert "'/stream?since=' + through" in body
    assert "Lost the live feed" in body
    assert "attempts > 5" in body


def test_a_run_opened_twice_quickly_leaves_nothing_behind() -> None:
    """Two clicks: the second closed nothing, because the first had not assigned its stream
    yet - so one stream and one server-side subscriber were left for every race."""
    body = scripts(ACTIVITY)
    assert "const mine = ++OPENING;" in body
    assert "if (mine !== OPENING) return;" in body


def test_the_feed_does_not_grow_without_limit() -> None:
    assert "childElementCount > 300" in scripts(ACTIVITY)
