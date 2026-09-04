"""Fixtures for P22. The eval harness runs over the committed fixtures on its own world;
the replay tests borrow P19's world, which dispatches a real skill and so leaves the
three blobs per step that replay reads."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from evals import EvalHarness
from evals.world import EvalWorld
from tests.p19.conftest import (  # noqa: F401 - fixtures, registered by import
    blobs,
    bus,
    constraints,
    contracts,
    plan,
    policy,
    precedents,
    queue,
    router,
    scope,
    scopes,
    started,
    store,
    surface,
    tagging_step,
    tree,
    world,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def harness() -> EvalHarness:
    return EvalHarness()


@pytest.fixture
def eval_world(tmp_path: Path) -> Iterator[EvalWorld]:
    w = EvalWorld(tmp_path / "eval")
    yield w
    w.close()
