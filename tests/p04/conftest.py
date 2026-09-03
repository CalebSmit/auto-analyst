"""Fixtures for P04.

The `store` fixture is parameterised over both backends, so every test that takes it is
part of the conformance suite by construction rather than by somebody remembering to add
it to a list. SQLite always runs. Postgres runs when `--postgres` is given, and when it
is not, the skip is counted and reported in words at the end of the session - see
`tests/conftest.py` for why a quiet skip was not good enough.

When `--postgres` *is* given and no server answers, the test fails. Asking for a backend
and being handed a green run that never touched it is the failure mode this whole
arrangement exists to prevent.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, text

import ports
from ops.models import Base
from ops.run_store import SqlRunStore, open_store
from registries.contracts import ContractRegistry
from tests.conftest import POSTGRES, postgres_url

BACKENDS = ("sqlite", "postgresql")

# One engine for the session, and one answer to "is there a server at all".
_PG: dict[str, Engine | None] = {}

ENGAGEMENT = "HEND-2026-04"
PLAN_HASH = "sha256:" + "7c" * 32
VERSIONS = {
    "model_pin": "claude-opus-5 @ effort=high",
    "skills": ["ddr-tagging@1.0.0", "qc-tieout@1.0.0"],
    "contracts": "1.0.0",
    "constraints": "1.0.0",
    "taxonomy": "1.0.0",
}


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    """Loaded once. Every event and the manifest are validated against it."""
    return ContractRegistry.load()


@pytest.fixture(params=BACKENDS)
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[SqlRunStore]:
    backend = request.param
    if backend == "sqlite":
        opened = open_store(f"sqlite:///{(tmp_path / 'run_store.db').as_posix()}")
        yield opened
        opened.close()
        return

    if not request.config.getoption("--postgres"):
        POSTGRES["not_run"] += 1
        pytest.skip("Postgres not requested; re-run with --postgres (reported in the summary)")

    engine = postgres_engine()
    if engine is None:
        pytest.fail(
            f"--postgres was given but no server answered at {POSTGRES['url']}: "
            f"{POSTGRES['error']}. This is a failure rather than a skip on purpose: "
            "a run that was asked for Postgres and quietly tested only SQLite is "
            "worse than a red one."
        )

    Base.metadata.drop_all(engine)
    opened = SqlRunStore(engine)
    POSTGRES["ran"] += 1
    yield opened
    Base.metadata.drop_all(engine)
    # The engine is shared for the session, so it is not disposed here.


def postgres_engine() -> Engine | None:
    """Connect once per session, or remember once per session that we could not.

    Probed once because an unreachable host costs several seconds per attempt, and sixty
    of those turn "tell me quickly that Postgres is not up" into a wait nobody sits
    through twice.
    """
    if "engine" not in _PG:
        url = postgres_url()
        POSTGRES["requested"] = True
        POSTGRES["url"] = url
        try:
            engine = create_engine(url, future=True, connect_args={"connect_timeout": 3})
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            _PG["engine"] = engine
        except Exception as unreachable:  # noqa: BLE001 - reported, not swallowed
            POSTGRES["error"] = str(unreachable).splitlines()[0]
            _PG["engine"] = None
    return _PG["engine"]


@pytest.fixture
def sqlite_store(tmp_path: Path) -> Iterator[SqlRunStore]:
    """For tests about something other than the backend. One run, not two."""
    opened = open_store(f"sqlite:///{(tmp_path / 'single.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def delivery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The real Delivery Port adapter, reached the way the pipeline reaches it."""
    root = tmp_path / "outbox"
    root.mkdir()
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(root))
    ports.reset()
    built = ports.get_delivery()
    yield built
    ports.reset()


def started(store: SqlRunStore, run_id: str = "run_p04", **overrides: Any) -> str:
    """A queued run with everything the manifest will need to name."""
    store.start_run(
        run_id=run_id,
        engagement_id=overrides.get("engagement_id", ENGAGEMENT),
        plan_hash=overrides.get("plan_hash", PLAN_HASH),
        versions=dict(overrides.get("versions", VERSIONS)),
        tieout_tolerance=overrides.get("tieout_tolerance", 1.0),
    )
    return run_id
