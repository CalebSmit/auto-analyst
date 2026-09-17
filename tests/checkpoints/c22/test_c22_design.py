"""Checkpoint C22 - the design language, on the pages that are served.

Proves, against the running server rather than against the strings: every page carries the
one stylesheet, every page's ink is the measured palette, no page carries a colour or a type
size of its own, and the states a keyboard and a reduced-motion preference depend on are
served with it.

P46 rewrote the stylesheet every surface is built on, and touched two pages' markup. Each was
tested alone; this is the whole of it, delivered over HTTP.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from tests.p46.test_design import TOKENS, body_of, contrast
from tools.serve import build

PATHS = ("/", "/admin", "/analytics", "/help")


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c22.db').as_posix()}")
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


def test_every_page_is_served_with_the_one_stylesheet(served: TestClient) -> None:
    for path in PATHS:
        page = served.get(path).text
        assert "--s4:" in page and "--t-display:" in page, f"{path} is missing the scales"
        assert f"--ink-3:{TOKENS['ink-3']}" in page.replace(" ", ""), f"{path} has other ink"


def test_no_served_page_carries_a_colour_or_a_size_of_its_own(served: TestClient) -> None:
    for path in PATHS:
        body = body_of(served.get(path).text)
        assert re.findall(r"#[0-9a-fA-F]{6}\b", body) == [], path
        assert re.findall(r"font-size:\s*[\d.]+px", body) == [], path


def test_the_served_ink_is_legible_on_the_served_paper(served: TestClient) -> None:
    """The measurement that matters is of what a browser is actually sent."""
    page = served.get("/").text.replace(" ", "")
    for token, floor in (("ink", 10.0), ("ink-2", 6.0), ("ink-3", 4.5)):
        assert f"--{token}:{TOKENS[token]}" in page
        assert contrast(TOKENS[token], TOKENS["bg"]) >= floor


def test_the_keyboard_and_a_reduced_motion_preference_are_served(served: TestClient) -> None:
    for path in PATHS:
        page = served.get(path).text
        assert ":focus-visible{outline:2px solid var(--accent)" in page, path
        assert "@media (prefers-reduced-motion:reduce)" in page, path
