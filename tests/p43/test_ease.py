"""P43: the tool made easy to start and use - and the bug the deep dive found.

What is tested is what a person relies on without looking: a deliverable downloads as exactly
what was released, or not at all; Help is one click from every page; a setting written in .env
reaches the system when it is started locally (it did not: only secrets were read from the file,
so `AA_LLM_ADAPTER=anthropic_messages` there changed nothing, silently); and the one-click start
exists and parses.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import ports
from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.app import Console, create_app
from ops.console.help_page import PAGE as HELP
from ops.events import EventBus
from ops.run_store import SqlRunStore
from tests.p23.conftest import ENGAGEMENT, Clock, clean_run
from tests.p23.conftest import delivery as delivery  # noqa: PLC0414 - the fixture, reused

ROOT = Path(__file__).resolve().parents[2]
PAGES = {"setup": SETUP, "activity": ACTIVITY, "analytics": ANALYTICS, "help": HELP}


# ------------------------------------------------------------------ deliverables


@pytest.fixture
def delivered(store: SqlRunStore, bus: EventBus, delivery: Any) -> tuple[TestClient, Path]:
    clean_run(store, bus)
    root = Path(delivery.root)
    placed = root / ENGAGEMENT / "run_clean" / "model.xlsx"
    placed.parent.mkdir(parents=True)
    placed.write_bytes(b"the released model")
    digest = "sha256:" + hashlib.sha256(b"the released model").hexdigest()
    store.record_artifact(
        "run_clean", "model.xlsx", digest, path=f"{ENGAGEMENT}/run_clean/model.xlsx"
    )
    store.record_artifact("run_clean", "escape.xlsx", digest, path="../outside.xlsx")
    return TestClient(create_app(Console(store, bus, clock=Clock()))), placed


def test_a_deliverable_downloads_as_released(delivered: tuple[TestClient, Path]) -> None:
    client, _ = delivered
    got = client.get("/api/runs/run_clean/artifacts/model.xlsx/download")
    assert got.status_code == 200
    assert got.content == b"the released model"
    assert 'filename="model.xlsx"' in got.headers["content-disposition"]


def test_a_file_changed_since_release_is_not_offered_as_the_deliverable(
    delivered: tuple[TestClient, Path],
) -> None:
    client, placed = delivered
    placed.write_bytes(b"edited afterwards")
    got = client.get("/api/runs/run_clean/artifacts/model.xlsx/download")
    assert got.status_code == 409 and "changed since it was released" in got.text


def test_nothing_outside_the_delivery_folder_or_unrecorded_downloads(
    delivered: tuple[TestClient, Path],
) -> None:
    client, _ = delivered
    assert client.get("/api/runs/run_clean/artifacts/escape.xlsx/download").status_code == 404
    assert client.get("/api/runs/run_clean/artifacts/nothing.xlsx/download").status_code == 404


def test_the_run_detail_lists_deliverables_with_a_download() -> None:
    assert "async function deliverables(id)" in ACTIVITY
    assert "/download" in ACTIVITY


def test_an_empty_activity_page_says_how_a_run_starts() -> None:
    assert "No runs yet - here is how one starts" in ACTIVITY


# ------------------------------------------------------------------ help


def test_help_is_served_and_linked_from_every_page(store: SqlRunStore, bus: EventBus) -> None:
    client = TestClient(create_app(Console(store, bus, clock=Clock())))
    page = client.get("/help")
    assert page.status_code == 200 and "Putting an engagement through" in page.text
    for name, body in PAGES.items():
        assert 'href="/help"' in body, f"{name} has no link to Help"


def test_every_word_help_defines_is_one_the_pages_use() -> None:
    """A glossary of words nobody sees is noise; each term is on a page a person uses."""
    from ops.console.help_page import GLOSSARY

    shown = (SETUP + ACTIVITY + ANALYTICS).lower()
    # A guard's name reaches the page from the run record (the trace, the alerts), not markup.
    from_the_record = {"provenance"}
    for term, _ in GLOSSARY:
        if term.lower() in from_the_record:
            continue
        word = term.split(" (")[0].lower()
        assert word in shown, f"Help defines {term!r}, which no page shows"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed here")
def test_the_help_page_script_parses(tmp_path: Path) -> None:
    target = tmp_path / "help.js"
    target.write_text(
        "\n;\n".join(re.findall(r"<script>(.*?)</script>", HELP, re.S)), encoding="utf-8"
    )
    checked = subprocess.run(["node", "--check", str(target)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr


def test_no_page_module_carries_an_invalid_escape() -> None:
    """Pages are Python strings holding JavaScript; a `\\s` written once is a warning today and
    a syntax error in a later Python. Compiled with warnings as errors, none may warn."""
    modules = [
        "admin/page.py",
        "ops/console/app.py",
        "ops/console/analytics_page.py",
        "ops/console/help_page.py",
        "ui/theme.py",
    ]
    checked = subprocess.run(
        [
            sys.executable,
            "-W",
            "error",
            "-c",
            "import sys\nfor p in sys.argv[1:]:"
            " compile(open(p, encoding='utf-8').read(), p, 'exec')",
            *modules,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0, checked.stderr


# ------------------------------------------------------------------ .env


def test_settings_in_env_reach_the_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text(
        '# a comment\nAA_P43_ADAPTER=anthropic_messages\nAA_P43_QUOTED="with spaces"\n'
        "AA_P43_EMPTY=\nAA_P43_SHELL=from-file\n",
        encoding="utf-8",
    )
    for name in ("AA_P43_ADAPTER", "AA_P43_QUOTED", "AA_P43_EMPTY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AA_P43_SHELL", "from-shell")

    applied = ports.load_env_file(env)
    assert os.environ["AA_P43_ADAPTER"] == "anthropic_messages"
    assert os.environ["AA_P43_QUOTED"] == "with spaces"
    assert "AA_P43_EMPTY" not in os.environ, "a blank line in .env does not blank a setting"
    assert os.environ["AA_P43_SHELL"] == "from-shell", "the real environment wins"
    assert set(applied) == {"AA_P43_ADAPTER", "AA_P43_QUOTED"}
    monkeypatch.delenv("AA_P43_ADAPTER")
    monkeypatch.delenv("AA_P43_QUOTED")


def test_a_missing_env_file_is_not_an_error(tmp_path: Path) -> None:
    assert ports.load_env_file(tmp_path / "absent.env") == ()


def test_the_secrets_adapter_and_the_start_read_env_the_same_way() -> None:
    from ports.secrets.dotenv import _parse

    text = "A=1\n B = '2' \n#C=3\nD\n"
    assert _parse(text) == ports.env_file_values(text) == {"A": "1", "B": "2"}


def test_serve_loads_env_unless_told_not_to() -> None:
    source = (ROOT / "tools" / "serve.py").read_text(encoding="utf-8")
    assert "ports.load_env_file()" in source
    assert 'os.environ.get("AA_NO_ENV_FILE") != "1"' in source
    rehearsal = (ROOT / "tools" / "simulate_firm.py").read_text(encoding="utf-8")
    assert '"AA_NO_ENV_FILE": "1"' in rehearsal, "a developer's .env stays out of the rehearsal"


# ------------------------------------------------------------------ one-click start


def test_start_cmd_runs_the_start_script() -> None:
    cmd = (ROOT / "start.cmd").read_text(encoding="utf-8")
    assert r"tools\start.ps1" in cmd
    script = (ROOT / "tools" / "start.ps1").read_text(encoding="utf-8")
    assert "-AsSecureString" in script, "the key is typed without being shown"
    assert "UTF8Encoding $false" in script, ".env is written without a byte-order mark"
    assert "Invoke-WebRequest" not in script.split("# 5. start")[0], "setup downloads nothing"


@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell is not installed here")
def test_the_start_script_parses() -> None:
    check = (
        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{ROOT / 'tools' / 'start.ps1'}', [ref]$null, [ref]$e) | Out-Null; "
        "if ($e.Count) { $e | ForEach-Object { $_.Message }; exit 1 }"
    )
    parsed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", check], capture_output=True, text=True
    )
    assert parsed.returncode == 0, parsed.stdout + parsed.stderr
