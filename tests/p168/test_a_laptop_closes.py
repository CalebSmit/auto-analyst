"""P168: a laptop closes.

A server runs until somebody stops it; a laptop closes at six. The queue is in-process and
memory-only, so when the process ends the job of any run that was mid-pass is gone - while
the record still says the run is running and a step is open. Before this phase that run
was invisible to everything that could have helped it: `stranded()` looked only for a job
the queue reported as *failed*, and a job the queue had never heard of was skipped; the
console refused both Resume and Halt with `RUN.HELD` because the run was "running under a
worker"; nothing at start picked it up; and the engagement lock stayed held, so every later
run on that client queued behind it for good. The ops node audit proved it with a probe
against the real pool and store.

Two more things a work laptop meets on day one. The fake model adapter passed all fifteen
preflight checks and activation, and the first real run quarantined at its first skill step
with a sentence written for a developer. And everything the tool knows is one gitignored
SQLite file under `runs/` that no document named.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import ports
from ops.console import Console, create_app
from ops.models import RunState
from review.surface import ReviewSurface
from tests.p25.conftest import Stepper, start
from workers.pool import WAITING_ON_WORKER

ROOT = Path(__file__).resolve().parents[2]
ENG = "HEND-2026-04"
RUN = "run_mid_pass"


def left_mid_pass(store: Any, bus: Any, lock: Any, make_pool: Any, blobs: Any) -> Any:
    """Process one: the run is enqueued, the lock taken, a worker takes it up, a step is
    opened - and then the process ends. Nothing in the queue survives that; the record
    does."""
    stepper = Stepper(blobs)
    pool_one = make_pool(stepper, workers=1)
    start(store, RUN, ENG)
    placed = pool_one.submit(RUN)
    assert placed.waiting_on == WAITING_ON_WORKER
    store.transition(RUN, RunState.RUNNING, "a worker took it up")
    store.ensure_step(RUN, "intake", "key-intake", "io")
    store.begin_attempt(RUN, "intake")
    assert lock.holder(ENG) is not None and lock.holder(ENG).run_id == RUN
    del pool_one
    return stepper


def test_a_run_whose_job_the_queue_has_forgotten_is_stranded_and_picked_up(
    store, bus, lock, make_pool, blobs
) -> None:
    stepper = left_mid_pass(store, bus, lock, make_pool, blobs)

    # Process two: the same store, a fresh in-process queue that has never heard of the
    # job. Before P168 this listed nothing.
    ports.reset()
    pool_two = make_pool(stepper, workers=1)
    (lost,) = pool_two.stranded()
    assert lost.run_id == RUN
    assert lost.step_id == "intake"
    assert "the queue has no record of job" in lost.error
    assert lost.attempt == 0
    (said,) = [e for e in store.events(RUN) if e.type == "worker.lost"]
    assert "the worker's process is gone" in said.message
    assert said.payload["job_id"] == lost.job_id

    # Said once: asking again does not raise it again.
    pool_two.stranded()
    assert len([e for e in store.events(RUN) if e.type == "worker.lost"]) == 1

    # Picked up under the lock it still holds, and the pass runs to its end.
    placed = pool_two.resume(RUN)
    assert placed.waiting_on == WAITING_ON_WORKER
    assert lock.holder(ENG).run_id == RUN
    pool_two.work()
    assert store.run(RUN).is_finished, store.run(RUN).state
    assert lock.holder(ENG) is None, "the lock is let go when the run ends"
    assert pool_two.stranded() == ()


def test_the_console_no_longer_refuses_to_act_on_it(store, bus, lock, make_pool, blobs) -> None:
    """The stuck-run check consults `pool.stranded()`, so with the pool answering, Halt is
    no longer refused with RUN.HELD for a run no worker holds."""
    stepper = left_mid_pass(store, bus, lock, make_pool, blobs)
    ports.reset()
    pool_two = make_pool(stepper, workers=1)
    console = Console(store, bus)
    app = create_app(console, ReviewSurface(store, bus, queue=pool_two.queue), pool=pool_two)
    client = TestClient(app)
    answer = client.post(
        f"/api/runs/{RUN}/halt", json={"who": "Caleb", "reason": "the laptop closed on it"}
    )
    assert answer.status_code != 409, answer.json()
    assert "RUN.HELD" not in answer.text


def test_a_run_a_worker_still_holds_is_not_called_stranded(
    store, bus, lock, make_pool, blobs
) -> None:
    """The other half: a run whose job this queue *does* know, queued or running, is not
    stranded - a pool that called every running run stranded would resume them twice."""
    stepper = Stepper(blobs)
    pool = make_pool(stepper, workers=1)
    start(store, RUN, ENG)
    pool.submit(RUN)
    store.transition(RUN, RunState.RUNNING, "a worker took it up")
    assert pool.stranded() == ()


# ------------------------------------------------------------- the server, at start


def test_the_server_picks_stranded_runs_up_before_its_first_sweep(
    store, bus, lock, make_pool, blobs, capsys
) -> None:
    import threading

    from tools.serve import sweep_forever

    stepper = left_mid_pass(store, bus, lock, make_pool, blobs)
    ports.reset()
    pool_two = make_pool(stepper, workers=1)

    class Served:
        pool = pool_two
        # Nothing else is reached: the stop event is set before the loop is entered, so the
        # sweep body never runs and the pickup before it is the only thing that does. That
        # is also why this goes through `sweep_forever` rather than calling the pickup
        # directly - the revert harness showed a direct call stays green with the wire cut.

    stop = threading.Event()
    stop.set()
    sweep_forever(Served(), 1, stop)
    out = capsys.readouterr().out
    assert RUN in out and "mid-pass when the last process ended" in out and "(in intake)" in out
    pool_two.work()
    assert store.run(RUN).is_finished


# ---------------------------------------------------------- the sixteenth preflight check


def test_preflight_warns_on_the_fake_adapter_and_fails_on_a_missing_key(
    monkeypatch, tmp_path
) -> None:
    from admin.preflight import CHECKS, Preflight
    from registries.errors import MODEL_NOT_REACHED

    assert dict(CHECKS)["model_answers"]
    assert len(CHECKS) == 16

    class Secrets:
        def __init__(self, names: set[str]) -> None:
            self.names = names

        def has(self, name: str) -> bool:
            return name in self.names

    def check(adapter: str, secrets: set[str]) -> Any:
        monkeypatch.setenv("AA_LLM_ADAPTER", adapter)
        ports.reset()
        preflight = Preflight.__new__(Preflight)
        preflight.secrets = Secrets(secrets)
        return preflight._model_answers()

    # The fixture replayer is a warning, not a failure: every test and rehearsal runs
    # under it, and a developer's machine is allowed to. The sentence is the whole point.
    amber = check("fake", set())
    assert amber.status == "warn"
    assert "AA_LLM_ADAPTER is 'fake'" in amber.detail
    assert "on a work laptop set it to one that answers" in amber.detail
    assert "anthropic_messages" in amber.detail
    assert amber.failures == (), "a warning does not refuse activation"

    key = ports.credentials_for("llm", "anthropic_messages")
    assert key, "the real adapter declares the key it needs"
    no_key = check("anthropic_messages", set())
    assert no_key.status == "fail"
    assert key[0] in no_key.detail
    assert "not in the Secrets Port" in no_key.detail
    assert no_key.failures[0].diagnostic.code == MODEL_NOT_REACHED
    assert "anthropic_messages" in no_key.failures[0].diagnostic.what_now

    green = check("anthropic_messages", set(key))
    assert green.status == "pass"
    assert "anthropic_messages" in green.detail


def test_the_setup_page_counts_sixteen() -> None:
    """The page derives its sentence from `len(CHECKS)` (P148), so it moves with the
    table; the README is prose and is held here."""
    from admin.preflight import CHECKS

    readme = (ROOT / "admin" / "README.md").read_text(encoding="utf-8")
    assert "Sixteen checks" in readme
    assert len(CHECKS) == 16


# ------------------------------------------------------------------- where the data is


def test_check_and_the_guide_say_where_the_record_is() -> None:
    from tools.serve import _record_path, readiness

    seams = {s.name: s for s in readiness()}
    assert "the record" in seams
    assert "run_store.db" in seams["the record"].detail
    assert "not in git" in seams["the record"].detail
    assert _record_path().endswith("runs/run_store.db")

    guide = (ROOT / "docs" / "USING.md").read_text(encoding="utf-8")
    assert "runs/run_store.db" in guide
    assert "Where your data is" in guide
    assert "ten today" in guide, "the methodology count the guide gives is the tree's"


def test_a_db_url_elsewhere_is_reported_as_set(monkeypatch) -> None:
    from tools.serve import _record_path

    monkeypatch.setenv("AA_DB_URL", "sqlite:///D:/chartwell/analyst.db")
    assert _record_path() == "D:/chartwell/analyst.db"
    monkeypatch.setenv("AA_DB_URL", "postgresql+psycopg://host/analyst")
    assert _record_path() == "postgresql+psycopg://host/analyst"
