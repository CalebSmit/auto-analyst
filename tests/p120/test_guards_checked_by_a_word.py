"""P120 - guards that were checked by looking for a word.

An audit found seven tests standing a substring in for a property, four of them the only
enforcement of a named non-negotiable. The worst was `tests/p45`: it asserted
`"proxy_headers=False"` appears in `tools/serve.py`, and the phrase occurs **twice** —
once as the keyword argument and once in the comment explaining it. Delete the argument
and the test stays green; uvicorn goes back to trusting `X-Forwarded-For`, which on a
loopback bind is every peer, which makes the one input the identity check has rewritable
by the request itself.

It was defeated by a *good comment*, and "keep the substring unique" is not a rule anyone
can follow. The same shape guarded OCR-is-local (`"urllib.request" not in source`, which
`from urllib import request` walks straight past), guards-are-not-configurable
(`"intake.config" not in source`, likewise), and the secrets port.

Beside them sat a one-line hole the substring tests had nothing to do with: `ui/who.py`
explicitly allowed `Origin: null`, which a sandboxed iframe on any website sends, and
several write routes take no body at all — so a cross-origin POST is a *simple* request,
no preflight, and the absent CORS headers do not stop it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.importing import imported_modules, reaches, reaches_any

ROOT = Path(__file__).resolve().parents[2]


# ============================================================ the helper itself


def test_a_dotted_import_is_seen() -> None:
    assert reaches("import intake.config", "intake.config")
    assert reaches("import intake.config as c", "intake.config")


def test_the_spelling_that_defeated_the_grep_is_seen() -> None:
    """`from intake import config` contains no "intake.config" and imports it exactly."""
    assert reaches("from intake import config", "intake.config")
    assert reaches("from urllib import request", "urllib")
    assert reaches("import http.client", "http")


def test_a_name_that_merely_contains_the_word_is_not() -> None:
    """The other half. A guard that fires on a correct change is one people learn to
    route around - `from registries.recipes import unbuilt_skills` imports no skill."""
    assert not reaches("from registries.recipes import unbuilt_skills", "skills")
    assert reaches_any("from registries.recipes import unbuilt_skills", ("skills",)) == ()


def test_a_relative_import_is_not_mistaken_for_an_absolute_one() -> None:
    """`from .config import x` inside a package is not an import of a top-level `config`,
    and counting it as one would fire a boundary guard on a module's own sibling."""
    assert not reaches("from . import config", "intake.config")
    assert not reaches("from .config import ConfigStore", "config")
    assert imported_modules("from .config import ConfigStore") == set()


def test_the_package_is_recorded_as_well_as_what_was_taken_from_it() -> None:
    """`from intake import config` imports `intake` *and* `intake.config`, and the
    boundary assertions ask about both - `"intake" not in names` is how a guard is kept
    from reaching the package by any route at all."""
    names = imported_modules("from intake import config")
    assert "intake" in names
    assert "intake.config" in names


def test_it_names_which_one_was_reached() -> None:
    """`assert reaches_any(...) == ()` fails with the offender in the message, which is
    what a boundary assertion wants to say."""
    assert reaches_any("import socket\nimport json", ("socket", "boto3")) == ("socket",)


def test_a_comment_cannot_satisfy_a_code_assertion() -> None:
    """The failure this whole phase is about, in the one place it is now a helper."""
    from tests.reading import page_code, python_code

    assert "proxy_headers" not in python_code("# proxy_headers=False is set below\nx = 1")
    assert "mature" not in page_code(
        "<script>/* mature-company was the default */\nlet a;</script>"
    )


# ============================================================ the peer address


def uvicorn_is_given(source: str) -> dict[str, Any]:
    """The keyword arguments of every `uvicorn.run(...)` in that source."""
    import ast

    given: dict[str, Any] = {}
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "uvicorn"
        ):
            given.update({kw.arg: kw.value for kw in node.keywords})
    return given


def test_the_peer_address_guard_reads_the_call() -> None:
    """Not a phrase near it. `tests/p45` asserts `proxy_headers` from the arguments
    `uvicorn.run` is actually given — and so does this, because the claim of this phase is
    that the rule now catches the thing, so the rule is run over the real file."""
    import ast

    said = (ROOT / "tests" / "p45" / "test_safe.py").read_text(encoding="utf-8")
    body = said[said.index("def test_the_peer_address") :]
    assert "ast.parse(source)" in body

    given = uvicorn_is_given((ROOT / "tools" / "serve.py").read_text(encoding="utf-8"))
    value = given.get("proxy_headers")
    assert isinstance(value, ast.Constant) and value.value is False, (
        "uvicorn is not told to distrust X-Forwarded-For"
    )


def test_deleting_the_argument_would_be_caught() -> None:
    """The proof, without touching the file: run the same rule over a call with the
    keyword removed, and over one that sets it the dangerous way."""
    import ast

    without = "import uvicorn\nuvicorn.run(app, host='h', port=1, log_level='warning')\n"
    assert "proxy_headers" not in uvicorn_is_given(without)
    trusting = "import uvicorn\nuvicorn.run(app, proxy_headers=True)\n"
    value = uvicorn_is_given(trusting)["proxy_headers"]
    assert isinstance(value, ast.Constant) and value.value is True, "and it reads the value"


# ============================================================ the boundaries


def test_no_guard_reaches_the_configuration_store() -> None:
    """*Guards are not configurable* — a blueprint non-negotiable whose only enforcement
    was a substring."""
    for folder in ("guards", "harness", "graph", "privacy"):
        for path in (ROOT / folder).rglob("*.py"):
            names = imported_modules(path.read_text(encoding="utf-8"))
            assert "intake.config" not in names, path
            assert "intake" not in names, path


@pytest.mark.parametrize(
    "path", sorted((ROOT / "ports" / "ocr").glob("*.py")), ids=lambda p: p.name
)
def test_no_ocr_adapter_reaches_the_network(path: Path) -> None:
    """*OCR is local, and that is not a preference* — the adapter sees the unmasked client
    scan before masking can happen. The old check looked at one literal spelling, in two
    of the three adapter files, and `rapidocr.py` — the one CLAUDE.md recommends for the
    work machine — was not among them."""
    reaching = reaches_any(
        path.read_text(encoding="utf-8"),
        ("requests", "httpx", "httpx2", "urllib", "http", "socket", "boto3", "ftplib"),
    )
    assert reaching == (), (path.name, reaching)


def test_the_recommended_adapter_is_one_of_the_files_checked() -> None:
    """The gap that mattered most: a parametrised test over a glob cannot leave one out,
    and the old one was a list of two names."""
    assert (ROOT / "ports" / "ocr" / "rapidocr.py").is_file()


def test_the_vault_key_is_not_read_from_the_environment() -> None:
    """The secrets port is the one door for credentials. The old check blocked exactly
    `os.environ.get(KEY_NAME` — `os.getenv(KEY_NAME)` and `os.environ[KEY_NAME]` both
    walked past it."""
    said = (ROOT / "tests" / "p12" / "test_mask_vault.py").read_text(encoding="utf-8")
    body = said[said.index("def test_the_key_comes_through_the_secrets_port") :]
    assert "ast.walk" in body
    assert "names_the_key" in body


def test_a_setting_may_still_come_from_the_environment() -> None:
    """The invariant is about credentials. `privacy/vault.py` reads its retention window
    from the environment and always has; a check that refused that would be refusing the
    wrong thing, and a guard that cries wolf gets routed around."""
    source = (ROOT / "privacy" / "vault.py").read_text(encoding="utf-8")
    assert "os.environ.get(RETENTION_VAR)" in source


# ============================================================ the waiver gate


def test_the_waiver_gate_is_asked_rather_than_read() -> None:
    """Inverting `==` to `!=` in `_waivers` satisfied every assertion the old test made,
    and would let a review item somebody *refused* waive the inputs they refused."""
    said = (ROOT / "tests" / "p112" / "test_the_waiver_the_message_promised.py").read_text(
        encoding="utf-8"
    )
    body = said[said.index("def test_the_driver_reads_acceptances") :]
    assert "driver._waivers(" in body
    assert "DecisionKind.REJECTED" in body, "and a rejection is one of the cases put to it"


def test_an_inverted_comparison_would_be_caught() -> None:
    """The proof, by asking the real function with all four decisions in front of it."""
    from ops.models import DecisionKind
    from workers.driver import RunDriver

    decided = [
        type("D", (), {"item_id": f"item:{kind.value}", "decision": kind})()
        for kind in DecisionKind
    ]
    driver = RunDriver.__new__(RunDriver)
    driver.wiring = type(  # type: ignore[attr-defined]
        "W", (), {"store": type("S", (), {"decisions": lambda self, r: decided})()}
    )()
    assert driver._waivers("r") == frozenset({"item:accepted"})  # noqa: SLF001


# ============================================================ the null origin


@pytest.fixture
def served(store: Any, bus: Any) -> Any:
    from fastapi.testclient import TestClient

    from ops.console.app import Console, create_app

    return TestClient(create_app(Console(store, bus)), base_url="http://127.0.0.1:8000")


def test_a_null_origin_is_refused(served: Any) -> None:
    """A page in a sandboxed iframe sends it, and so does a `file://` page - either of
    them on somebody else's website. It was the one value explicitly excused."""
    assert served.get("/api/runs", headers={"Origin": "null"}).status_code == 403


def test_an_origin_from_elsewhere_is_still_refused(served: Any) -> None:
    said = served.get("/api/runs", headers={"Origin": "https://example.invalid"})
    assert said.status_code == 403


def test_this_machine_s_own_page_is_not(served: Any) -> None:
    """The check has to keep letting the console through, or it is not a check, it is a
    closed door."""
    said = served.get("/api/runs", headers={"Origin": "http://127.0.0.1:8000"})
    assert said.status_code == 200


def test_a_request_with_no_origin_at_all_is_allowed(served: Any) -> None:
    """Same-origin navigations and curl send none. Refusing those would refuse the
    ordinary case to catch nothing - `Host` and the peer address are what cover it."""
    assert served.get("/api/runs").status_code == 200


def test_the_carve_out_is_gone_from_the_source() -> None:
    from tests.reading import python_code

    said = python_code((ROOT / "ui" / "who.py").read_text(encoding="utf-8"))
    assert 'origin != "null"' not in said
