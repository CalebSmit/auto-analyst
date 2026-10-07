"""Checkpoint C97 - the board as the server hands it over.

P172 changed two boards' layouts, capped a panel, moved a renderer, put a key on the shared
shell and made a directory on somebody's disk. Each of those was proved against the string a
module holds. What a checkpoint can ask is whether it is true of what the server actually
serves, and whether the halves that live in different files still meet.

Three joins, and each one is a place this build has been wrong before.

* **The layout and the bound are one claim.** A board laid out in bands is only bounded if
  every panel in it is, and a capped panel only has an effect if nothing spans a row around
  it. The two were changed in two files by two tests, and the page the browser gets is where
  they have to agree.
* **The reason and the payload.** `whyItStopped` finds a diagnostic by matching it to the
  step a run stopped on. That is a claim about the page *and* about `/api/runs/{id}`, and
  nothing in either file can see the other.
* **The folder and the route.** `AdminConsole._make_folder` makes a directory; the Setup
  page shows a path from `engagement_files`. Those are the same directory or the page sends
  somebody to an empty window in Explorer.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from tools.serve import build

SURFACES = ("/", "/admin", "/analytics", "/help")
BOARDS = ("/", "/admin", "/analytics")


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c97.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("AA_NO_ENV_FILE", "1")
    (tmp_path / "inbox").mkdir()
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    system = build()
    yield TestClient(system.app)
    system.close()
    ports.reset()


def bands_of(page: str) -> list[list[list[str]]]:
    """Every `grid-template-areas` the page carries, as bands of area names."""
    out = []
    for declaration in re.findall(r"grid-template-areas:([^;}]*)", page):
        rows = [row.split() for row in re.findall(r'"([^"]*)"', declaration)]
        if rows:
            out.append(rows)
    return out


# ------------------------------------------------ the layout and the bound, as one claim


@pytest.mark.parametrize("path", BOARDS)
def test_no_board_the_server_serves_puts_a_panel_in_two_bands(
    served: TestClient, path: str
) -> None:
    """The property, asked of the bytes rather than of the module. A panel spanning two rows
    has its height shared across rows nothing else is in, so the panels beside it are
    stretched to a height nothing in their band asked for - which with an unbounded run
    detail was 2,794px of Runs panel around 259px of content."""
    page = served.get(path).text
    layouts = bands_of(page)
    assert layouts, f"{path} serves a board that names no areas"
    for layout in layouts:
        rows_of: dict[str, set[int]] = {}
        for n, row in enumerate(layout):
            for area in row:
                if area != ".":
                    rows_of.setdefault(area, set()).add(n)
        spanning = {a: sorted(r) for a, r in rows_of.items() if len(r) > 1}
        assert spanning == {}, f"{path} serves a panel in more than one band: {spanning}"


@pytest.mark.parametrize("path", BOARDS)
def test_every_panel_the_server_serves_is_capped_or_fixed_by_this_build(
    served: TestClient, path: str
) -> None:
    """C82's property, re-asked where the two halves meet. The classification lives in
    `tests/p149` and the `stream` class lives in three page modules; this reads the markup
    the server sends and holds it to the table, so a panel added to a board without being
    asked whose length it is fails here as well as there."""
    from tests.p149.test_the_panels_whose_length_is_not_ours import WHOSE

    page = served.get(path).text
    panels = {
        m.group(2): bool(m.group(1))
        for m in re.finditer(r'<section class="card( stream)?" style="grid-area:(\w+)">', page)
    }
    assert panels, f"{path} serves no board panels"
    for area, capped in panels.items():
        assert area in WHOSE, f"{path} serves {area!r} and nobody has said whose length it is"
        whose = WHOSE[area][0]
        if whose == "firm":
            assert capped, f"{path}/{area} grows with the firm and is served uncapped"
        if whose == "ours":
            assert not capped, f"{path}/{area} is this build's to size and scrolls anyway"


def test_the_bands_a_board_declares_are_the_bands_it_lays_out(served: TestClient) -> None:
    """A board declaring six rows and laying out three has three rows of nothing in it, and
    a panel dropped into one of them later sits in a band by itself."""
    for path in BOARDS:
        page = served.get(path).text
        declared = re.search(r"grid-template-rows:\s*repeat\((\d+),\s*min-content\)", page)
        assert declared, f"{path} does not size its bands to what is in them"
        for layout in bands_of(page):
            assert len(layout) == int(declared.group(1)), (
                f"{path} declares {declared.group(1)} bands and lays out {len(layout)}"
            )


def test_the_panel_bound_is_still_one_number_and_every_board_is_served_it(
    served: TestClient,
) -> None:
    """Ten panels rely on it. Served three times, it would be a page height kept in step in
    three files."""
    for path in BOARDS:
        page = served.get(path).text
        assert page.count(".card.stream>.body{max-height:26rem;overflow:auto") == 1, path
        assert len(re.findall(r"max-height:\s*[\d.]+rem", page)) <= 3, (
            f"{path} serves a maximum height beside the one the panels share"
        )


# --------------------------------------------------------- the reason, and the payload


def test_the_page_and_the_payload_agree_about_where_a_stopped_run_says_why(
    served: TestClient,
) -> None:
    """The join. The page finds a diagnostic by matching `step_id` to the step a run stopped
    on; the API decides what a diagnostic carries. Neither file can see the other, and the
    failure if they disagree is silent - an empty rule beside the state, and a reader back
    to `quarantined: qc`."""
    page = served.get("/").text
    assert "function whyItStopped(" in page, "the run detail no longer says why it stopped"
    assert "d.step_id === step" in page, "it no longer matches a diagnostic to a step"
    assert page.count('<div class="d-row">') == 1 + page.count(
        '<div class="diag"><div class="d-row">'
    ), "the console draws a diagnostic in more than one way"

    # And the shape the page matches on is the shape the reducer emits, read off the code
    # that builds it rather than off a fixture that could agree with neither.
    import inspect

    from ops.console.app import Console

    source = inspect.getsource(Console.run)
    assert "trace" in source, "the run payload no longer carries its trace"
    from ops.console.trace import TraceReducer

    fields = inspect.getsource(TraceReducer)
    assert "step_id" in fields and "diagnostics" in fields, (
        "a diagnostic no longer names the step it belongs to, so the run detail cannot "
        "find the one that stopped it"
    )


def test_one_key_reaches_a_find_box_on_every_page_that_has_one(served: TestClient) -> None:
    """Served to all four, declared once, and harmless on the one with no box - a shortcut
    that throws on a page without a filter would be worse than none."""
    for path in SURFACES:
        page = served.get(path).text
        assert page.count("e.key !== '/'") == 1, f"{path} is served the shortcut more than once"
        # Read out of the shortcut's own block. Asked of the whole page, `if (!box) return;`
        # is in five other handlers on the Activity console and the assertion passed with
        # the guard deleted - which the revert harness caught and is the exact defect this
        # repo keeps finding.
        rule = page[page.index("e.key !== '/'") :]
        rule = rule[: rule.index("box.select();")]
        assert "document.querySelector('.filter input')" in rule, path
        assert "if (!box) return;" in rule, f"{path} would throw on a page with no find box"
    assert '<div class="filter">' in served.get("/").text
    assert '<div class="filter">' in served.get("/help").text
    assert '<div class="filter">' not in served.get("/analytics").text, (
        "a page without a find box is the case the guard above is for"
    )


# ----------------------------------------------------- the folder, and the route to it


def test_registering_an_engagement_over_http_makes_the_folder_the_page_then_shows(
    served: TestClient, tmp_path: Path
) -> None:
    """The second join, and the one with a person on the other end of it. The console makes
    a directory; the Setup page's **files** dialog prints a path. If those are not the same
    directory, the page sends somebody to a window in Explorer that is not there."""
    # The name every change is recorded against is the system's answer, not a guess: the
    # console refuses a change attributed to anybody else, which is exactly the guard P36
    # built and is not what this test is about.
    me = served.get("/api/admin/whoami").json()["name"]
    # Set up the way the Setup page sets up - initialise, a watch, a destination - so
    # what is being tested is a state the product can actually get into.
    for route, body in (
        ("/api/admin/initialise", {}),
        (
            "/api/admin/watches",
            {
                "id": "w1",
                "kind": "pattern",
                "name": "Clients",
                "root": "Clients",
                "recipe": "valuation-input-prep",
                "depth": 2,
            },
        ),
        (
            "/api/admin/destinations",
            {"id": "d1", "name": "Out", "path": "out", "adapter": "local_folder"},
        ),
    ):
        answer = served.post(route, json={"who": me, "reason": "C97 setup", **body})
        assert answer.status_code == 200, f"{route}: {answer.text}"

    made = served.post(
        "/api/admin/engagements",
        json={
            "who": me,
            "reason": "C97: somewhere to put the files",
            "engagement_id": "C97-2026-01",
            "client": "Checkpoint Co",
            "scope_path": "valuation/non-esop/non-repeat",
            "watch_id": "w1",
            "destination_id": "d1",
            "folder": "Checkpoint Co/2026 Valuation",
        },
    )
    assert made.status_code == 200, made.text

    files = served.get("/api/admin/engagements/C97-2026-01/files").json()
    shown = Path(files["absolute"])
    assert shown.is_dir(), (
        f"the files dialog shows {shown}, and registering the engagement did not make it"
    )
    assert shown == tmp_path / "inbox" / "Clients" / "Checkpoint Co" / "2026 Valuation"
    assert files["files"] == [], "making the folder put something in it"
