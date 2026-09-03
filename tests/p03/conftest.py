"""Fixtures for P03.

Every adapter is built through `ports.get_port` rather than constructed directly, so the
conformance suite exercises the same path the pipeline uses. Configuration is set through
the environment, because that is how an adapter is chosen in a real run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ports

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def clean_ports() -> None:
    """Adapters are cached per (port, adapter). Tests change configuration, so the cache
    is dropped around each one."""
    ports.reset()
    yield
    ports.reset()


@pytest.fixture
def inbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "inbox"
    root.mkdir()
    monkeypatch.setenv("AA_INBOX_ROOT", str(root))
    return root


@pytest.fixture
def outbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "outbox"
    root.mkdir()
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(root))
    return root
