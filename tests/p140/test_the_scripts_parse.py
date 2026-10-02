"""P140: nothing in this repo parsed the JavaScript the consoles are made of.

Written because I broke the Setup page while improving it. The comment explaining a change
went inside the template literal it was explaining:

    `<div class="r lede">
      <!-- ... What `passed` means is that nothing *blocks* a run ... -->

An HTML comment is a comment to a browser parsing HTML. Inside a template literal it is
text, and the two backticks in it ended the literal. The whole script failed to parse, every
panel on the page rendered as a grey bar, and **the suite was green** - because the three
consoles are Python strings, and `ruff` and `mypy` check the Python around them while
nothing at all looks at what is inside.

Found by opening the page. Which is how P135, P136, P137, P138 and P139 were found as well,
and the difference here is that this one did not have to be: a parser would have said so in
under a second.

So: every page this product serves has its script run through a real JavaScript parser. Node
is on the path on this machine and in CI; where it is not, the test skips loudly rather than
passing, because a check that quietly does nothing is this repo's named defect.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Every module that serves a page, found rather than listed - the same search P139 uses, and
# for the same reason: a list of three is what let a fourth surface drift.
PAGES = [
    path
    for path in [*sorted((ROOT / "ops" / "console").glob("*.py")), ROOT / "admin" / "page.py"]
    if re.search(r"^PAGE(: ?str)? = ", path.read_text(encoding="utf-8"), re.M)
]


def rendered(path: Path) -> str:
    """The page as it is actually served.

    Imported rather than read, because these are f-strings: `{{` is a brace in the source
    and a brace in the output, and checking the source would be checking something nobody
    ever runs.
    """
    import importlib

    module = importlib.import_module(
        str(path.relative_to(ROOT).with_suffix("")).replace("\\", ".").replace("/", ".")
    )
    return str(module.PAGE)


def scripts(page: str) -> list[str]:
    return re.findall(r"<script>(.*?)</script>", page, re.S)


def parses(source: str) -> tuple[bool, str]:
    """Through node's own parser, with nothing executed.

    `new Function(src)` compiles and does not run, which is what is wanted: these scripts
    call `fetch` and touch the DOM on load, and neither exists here. A parse is the whole
    question - what the script *does* is every other test in this suite.
    """
    node = shutil.which("node")
    assert node, "node is not on the path"
    probe = (
        "const fs=require('fs');"
        "const src=fs.readFileSync(process.argv[1],'utf8');"
        "try{new Function(src);console.log('OK');}"
        "catch(e){console.log('ERR '+e.message);}"
    )
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(source)
        name = f.name
    try:
        done = subprocess.run(
            [node, "-e", probe, name], capture_output=True, text=True, timeout=60, check=False
        )
    finally:
        Path(name).unlink(missing_ok=True)
    out = (done.stdout + done.stderr).strip()
    return out.startswith("OK"), out


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def test_the_pages_were_found() -> None:
    """Before anything else, because a check over an empty list passes."""
    assert len(PAGES) >= 4, f"only {[p.name for p in PAGES]} found; the search is wrong"


@needs_node
@pytest.mark.parametrize("path", PAGES, ids=lambda p: p.name)
def test_every_script_on_every_page_parses(path: Path) -> None:
    found = scripts(rendered(path))
    assert found, f"{path.name} serves a page with no script in it"
    for i, source in enumerate(found):
        ok, said = parses(source)
        assert ok, f"{path.name} script {i} does not parse: {said}"


@needs_node
def test_the_parser_is_actually_parsing() -> None:
    """A check that passes on broken input is the defect this repo names most often, and
    this one is a subprocess whose output is read as a string - exactly the shape that
    quietly stops working."""
    ok, _ = parses("const a = 1;")
    assert ok, "it refuses valid JavaScript"

    for broken, why in (
        ("const a = `unterminated;", "an unterminated template literal"),
        ("const a = `x` ` ;", "a stray backtick, which is how this was found"),
        ("function f( { }", "an unbalanced bracket"),
        ("const = 1;", "a missing name"),
    ):
        ok, said = parses(broken)
        assert not ok, f"it accepted {why}: {broken!r}"
        assert said.startswith("ERR"), said


@needs_node
def test_an_html_comment_with_a_backtick_in_a_literal_is_refused() -> None:
    """The exact shape of the mistake, asserted as a shape rather than as a string - the
    comment is harmless in HTML and fatal one line further in."""
    harmless = 'el.innerHTML = "<!-- `passed` means nothing blocks -->";'
    assert parses(harmless)[0], "a backtick inside a quoted string is fine"

    fatal = "el.innerHTML = `<div>\n  <!-- `passed` means nothing blocks -->\n</div>`;"
    assert not parses(fatal)[0], "the mistake that broke the Setup page parses"


@needs_node
def test_the_page_each_console_serves_is_the_one_that_is_parsed() -> None:
    """`PAGE` is built at import time from an f-string. Reading the source would check
    something nobody runs, so this asserts the rendered page has no doubled braces left in
    its script - which is what a source read would have been looking at."""
    for path in PAGES:
        for source in scripts(rendered(path)):
            assert "${{" not in source, f"{path.name} serves an unrendered f-string brace"


def test_node_is_written_down_as_something_this_needs() -> None:
    """A test that skips on a machine without node is a test that passes there. That is the
    right behaviour - node is not a dependency of the product - and it is only honest if
    somebody can find out that it skipped and why."""
    changing = (ROOT / "CHANGING.md").read_text(encoding="utf-8")
    assert "node" in changing.lower(), "nothing tells a reader this check needs node"


@needs_node
def test_what_the_parser_says_is_quotable() -> None:
    """A failure that says "does not parse" sends somebody to read 2,000 lines. The
    message carries node's own words, which name the line."""
    ok, said = parses("const a = `unterminated;")
    assert not ok
    assert len(said) > 4, f"the refusal says nothing: {said!r}"
    assert json.dumps(said), "it is not something a test message can carry"


# ------------------------------------------- and the page a browser shows is the page served


def test_every_page_is_served_as_not_to_be_stored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of the same morning.

    After fixing the script I restarted the server and the page was still the broken one -
    for three more restarts. The consoles send no cache headers at all, so a browser may
    reuse a response without asking, and these pages change only when the process does.
    On the machine this is moving to that reads as "I updated it and the fix is not there",
    with nothing on screen to say otherwise.
    """
    from fastapi.testclient import TestClient

    import ports
    from tools.serve import build

    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'cache.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "in"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "out"))
    ports.reset()
    system = build()
    try:
        client = TestClient(system.app)
        for path in ("/admin", "/", "/analytics", "/help"):
            answer = client.get(path)
            assert answer.status_code == 200, path
            assert answer.headers["content-type"].startswith("text/html"), path
            assert answer.headers.get("cache-control") == "no-store", (
                f"{path} may be kept by a browser across a restart"
            )

        # And not on the answers the scripts fetch. Those are asked for afresh every time
        # already, and a rule reaching them would be a rule about a non-problem.
        runs = client.get("/api/runs")
        assert runs.status_code == 200
        assert "cache-control" not in {k.lower() for k in runs.headers}
    finally:
        system.close()
        ports.reset()


def test_the_rule_is_written_once_rather_than_on_each_route() -> None:
    """Four pages today. A route added tomorrow would not know to do this, which is exactly
    how `/analytics` and `/help` would have been missed."""
    who = (ROOT / "ui" / "who.py").read_text(encoding="utf-8")
    assert re.search(r"^def _not_stored\(", who, re.M), "the one place is gone"
    assert "_not_stored(answer)" in who, "it is defined and nothing calls it"
    assert who.count("no-store") == 1, "more than one place decides this"
    for page in (ROOT / "ops" / "console" / "app.py", ROOT / "admin" / "app.py"):
        assert "no-store" not in page.read_text(encoding="utf-8"), f"{page.name} sets it too"
