"""Checkpoint C25 - the map as something to work with, on the system that serves it.

Proves against the assembled server: the page carries the map's controls and its one script
namespace; the order a run went through the design can be derived from what the console
serves, which is what the numbering is; and a node's neighbours come from the served edges,
which is what the panel's links are.

P49 is a browser view, so most of it is held by tests/p49 over the strings. What belongs
here is the part that depends on the console actually serving the right shape.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from tools.serve import build


def _names(declaration: str) -> list[str]:
    """The names a `const`/`let`/`var` statement binds, and nothing else.

    Only what sits at bracket depth zero counts: the keys of an object literal spanning
    several lines, and a default inside an arrow function's parameters, are commas and
    identifiers too, and reading them as bindings is how this check reports a collision
    that is not there.
    """
    found: list[str] = []
    depth, expecting = 0, True
    for token in re.finditer(r"[()\[\]{}]|=>|[=,;]|[A-Za-z_$][\w$]*", declaration):
        text = token.group()
        if text in "([{":
            depth += 1
        elif text in ")]}":
            depth -= 1
        elif depth > 0:
            continue
        elif text == ",":
            expecting = True
        elif text in ("=", "=>", ";"):
            expecting = False
        elif expecting:
            found.append(text)
            expecting = False
    return found


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c25.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("AA_NO_ENV_FILE", "1")
    (tmp_path / "inbox").mkdir()
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    system = build()
    client = TestClient(system.app)
    system.store.start_run("run_c25", "PILOT-2026-01", "sha256:c25", {})
    for node, kind in (("intake_window", "run.launched"), ("source_parse", "intake.read")):
        system.ops.bus.emit(
            run_id="run_c25",
            engagement_id="PILOT-2026-01",
            node_id=node,
            type=kind,
            message=f"{node}: {kind}",
        )
    # Through the guard's own emitter: the bus refuses a guard event that does not say how
    # many things it checked, which is an invariant worth meeting rather than working round.
    system.ops.bus.emit_guard(
        run_id="run_c25",
        engagement_id="PILOT-2026-01",
        node_id="untrusted_boundary",
        guard="untrusted_boundary",
        passed=False,
        checked=1,
        failed=1,
    )
    yield system, client
    system.close()
    ports.reset()


def test_the_order_a_run_went_in_is_derivable_from_what_is_served(served: Any) -> None:
    """The numbering is the first event recorded against each node, so the console has to
    serve events with their node and their time, in the order they happened."""
    _, client = served
    events = client.get("/api/runs/run_c25/events").json()
    first: dict[str, str] = {}
    for e in events:
        assert e["node_id"] and e["ts"], "an event with no node or no time cannot be ordered"
        first.setdefault(e["node_id"], e["ts"])
    order = sorted(first, key=lambda node: first[node])
    assert order[:3] == ["intake_window", "source_parse", "untrusted_boundary"]


def test_a_nodes_neighbours_come_from_the_served_edges(served: Any) -> None:
    """The panel's "what feeds this" and "what it feeds" are the blueprint's own edges."""
    _, client = served
    edges = client.get("/api/graph").json()["edges"]
    into = {e["from"] for e in edges if e["to"] == "untrusted_boundary"}
    out_of = {e["to"] for e in edges if e["from"] == "untrusted_boundary"}
    assert into and out_of, "the guard the run failed at is joined to something both ways"
    assert all("kind" in e for e in edges)


def test_the_page_serves_the_controls_and_one_script_namespace(served: Any) -> None:
    _, client = served
    page = client.get("/").text
    for control in ('id="dmap-find"', 'data-act="mapStep"', 'data-act="mapFilter"'):
        assert control in page, control
    body = "\n".join(re.findall(r"<script>(.*?)</script>", page, re.S))
    # P50: every name, not only the first on a declaration. `let A = 1, B = 2;` used to
    # hide B from this check - and a duplicate `let` across the page's two classic scripts
    # is an early SyntaxError, so the second script never runs and the whole map vanishes
    # with nothing but a console message. tests/p50 keeps the declarations one per line;
    # this reads the rest of the names anyway, so the two are not relying on each other.
    declared: list[str] = []
    for statement in re.findall(r"^(?:const|let|var)\s+[\s\S]*?;$", body, re.M):
        declared += _names(statement.split(None, 1)[1])
    declared += re.findall(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", body, re.M)
    doubled = sorted({n for n in declared if declared.count(n) > 1})
    assert doubled == [], f"the served page declares {doubled} twice"
