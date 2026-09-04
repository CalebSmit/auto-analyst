"""Fixtures for P03.

Every adapter is built through `ports.get_port` rather than constructed directly, so the
conformance suite exercises the same path the pipeline uses. Configuration is set through
the environment, because that is how an adapter is chosen in a real run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ports
from tests.conftest import REDIS, redis_url

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


@pytest.fixture(autouse=True)
def redis_backend(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """The redis_rq adapter runs over an in-memory fake unless --redis asks for a server.
    Either way the session summary says which one it was, in words, with a count."""
    if "redis_rq" not in str(getattr(request, "param", "")) and "redis_rq" not in request.node.name:
        return
    if not request.config.getoption("--redis"):
        REDIS["fake"] += 1
        monkeypatch.setenv("AA_REDIS_URL", f"fakeredis://{request.node.nodeid}")
        return
    url = redis_url()
    REDIS["requested"] = True
    REDIS["url"] = url
    try:
        import redis

        redis.Redis.from_url(url, socket_connect_timeout=3).ping()
    except Exception as unreachable:  # noqa: BLE001 - reported, not swallowed
        REDIS["error"] = str(unreachable).splitlines()[0]
        pytest.fail(f"--redis was given but no server answered at {url}: {unreachable}")
    REDIS["real"] += 1
    monkeypatch.setenv("AA_REDIS_URL", url)
