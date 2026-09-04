"""Swapping in_process for Redis changes no pipeline code, and the pool is as wide as
the Compute Target says and no wider."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

import ports
import workers.pool
from ops.models import RunState
from ops.run_store import SqlRunStore
from tests.p25.conftest import HEND, MERC, Stepper, events_of, plan_for, start


@pytest.mark.parametrize("adapter", ports.adapters("queue"))
def test_the_same_pool_runs_over_every_queue_adapter(
    store: SqlRunStore, blobs: Any, make_pool: Any, adapter: str
) -> None:
    runner = Stepper(blobs, delay=0.0)
    pool = make_pool(runner, workers=2, adapter=adapter)
    assert pool.queue.name == adapter
    hend = start(store, "run_hend", HEND)
    merc = start(store, "run_merc", MERC)
    placed = pool.submit_all([hend, merc])
    assert [p.position for p in placed] == [1, 2]
    pool.work()
    for run_id in (hend, merc):
        assert store.run(run_id).state is RunState.HALTED, adapter
        assert len(store.ledger(run_id)) == len(plan_for(HEND).order)
        (started,) = events_of(store, run_id, "worker.started")
        assert started.payload["adapter"] == adapter
    assert pool.pressure().adapter == adapter and pool.pressure().waiting == 0


def test_the_pool_names_no_adapter() -> None:
    """The exit criterion as a property of the source: `workers/` reaches the queue
    through `ports.get_queue()` and the Protocol, never an adapter module. The P03
    boundary test walks every package for the same thing; this is the pool's own copy."""
    imports = [
        line
        for line in inspect.getsource(workers.pool).splitlines()
        if line.startswith(("import ", "from "))
    ]
    assert not [
        line for line in imports if "ports.queue." in line or "redis" in line or "rq" in line
    ]
    assert any("from ports.queue import" in line for line in imports), "the Protocol, yes"


def test_the_pool_is_as_wide_as_the_compute_target_says(
    store: SqlRunStore, blobs: Any, make_pool: Any
) -> None:
    pool = make_pool(Stepper(blobs), workers=3)
    assert ports.get_compute().target().max_parallelism == 3
    assert pool.queue.workers == 3 and pool.pressure().capacity == 3
    assert pool.queue.depth().workers == 3
