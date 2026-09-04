"""Fixtures for P25: a real store, bus, lock and executor, and a bounded pool over them.

The model's half is a test double that takes a little wall time per step - so that
concurrency is a thing the tests can measure rather than assert about - and that can,
once, block on a person or die mid-step. A `BaseException` out of the runner is what a
killed worker looks like from inside the process: frames unwind, nothing catches it,
nothing after it runs. What it leaves on the record is what SIGKILL leaves.
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import ports
from graph.compile import CompiledGraph, PlanContext, compile_recipe
from graph.execute import Attempt, Blocked, ExecutionReport, StepExecutor
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver
from intake.lock import EngagementLock
from ops.blobs import ContentRef, LocalContentStore
from ops.events import EventBus
from ops.manifest import close_out
from ops.models import Outcome, RunState
from ops.run_store import SqlRunStore, open_store
from registries.contracts import ContractRegistry
from workers import WorkerPool

HEND = "HEND-2026-04"
MERC = "MERC-2026-02"
NOVK = "NOVK-2026-07"
CONTEXT_REF = "context:" + "7c" * 8
PLAN_HASH_VERSIONS = {
    "model_pin": "claude-opus-5 @ effort=high",
    "skills": ["timing-normalization@0.1.0"],
    "contracts": "1.0.0",
    "constraints": "1.0.0",
    "taxonomy": "coa-taxonomy@1.0.0",
}


class WorkerKilled(BaseException):
    """The worker died. Not an Exception: nothing in the executor catches it, exactly as
    nothing catches a process being killed."""


class Stepper:
    """A runner that takes wall time, and can be told to block, hold, or die once.

    Intervals are measured with `perf_counter`: on Windows under 3.12, `monotonic` ticks
    every 15.6 ms, so steps shorter than a tick read as zero-length and intervals that
    merely touch read as overlapping - which once made a two-thread pool look like four.
    """

    def __init__(self, blobs: LocalContentStore, delay: float = 0.02) -> None:
        self.blobs = blobs
        self.delay = delay
        self.calls: Counter[tuple[str, str]] = Counter()
        self.intervals: list[tuple[str, str, float, float]] = []
        self.kill: set[tuple[str, str]] = set()
        self.block: set[tuple[str, str]] = set()
        self.hold: dict[tuple[str, str], threading.Event] = {}
        self.entered: dict[tuple[str, str], threading.Event] = {}
        self.meet: dict[tuple[str, str], threading.Barrier] = {}
        self._lock = threading.Lock()

    def meet_at(self, step_id: str, *run_ids: str, timeout: float = 10.0) -> threading.Barrier:
        """Make these runs wait for each other inside this step. Proof of concurrency
        that owes nothing to timing: a pool running them one at a time never gets the
        second party to the barrier, the first times out, and the step fails loudly."""
        barrier = threading.Barrier(len(run_ids), timeout=timeout)
        for run_id in run_ids:
            self.meet[(run_id, step_id)] = barrier
        return barrier

    def hold_at(self, run_id: str, step_id: str) -> tuple[threading.Event, threading.Event]:
        """Make the runner wait inside this step until released. Returns (entered,
        release): the test waits on the first and sets the second."""
        key = (run_id, step_id)
        self.entered[key] = threading.Event()
        self.hold[key] = threading.Event()
        return self.entered[key], self.hold[key]

    def __call__(self, attempt: Attempt) -> ContentRef:
        key = (attempt.run_id, attempt.step_id)
        started = time.perf_counter()
        with self._lock:
            self.calls[key] += 1
            nth = self.calls[key]
        if key in self.hold:
            self.entered[key].set()
            self.hold[key].wait(timeout=30)
        if key in self.meet:
            self.meet[key].wait()  # BrokenBarrierError if the others never come
        if nth == 1 and key in self.kill:
            raise WorkerKilled(f"killed during {attempt.step_id}")
        if nth == 1 and key in self.block:
            raise Blocked(f"clarify:{attempt.step_id}", f"{attempt.step_id}: needs a person")
        time.sleep(self.delay)
        ref = self.blobs.put_json(
            {
                "step": attempt.step_id,
                "run": attempt.run_id,
                "inputs": {n: r.content_hash for n, r in sorted(attempt.inputs.items())},
            },
            name=attempt.step_id,
        )
        with self._lock:
            self.intervals.append((attempt.run_id, attempt.step_id, started, time.perf_counter()))
        return ref

    def span(self, run_id: str) -> tuple[float, float]:
        mine = [(a, b) for r, _, a, b in self.intervals if r == run_id]
        return min(a for a, _ in mine), max(b for _, b in mine)


def max_concurrent_runs(intervals: list[tuple[str, str, float, float]]) -> int:
    """The most distinct runs that were inside a step at the same instant."""
    points: list[tuple[float, int, str]] = []
    for run_id, _, a, b in intervals:
        points.append((a, 1, run_id))
        points.append((b, -1, run_id))
    points.sort(key=lambda p: (p[0], p[1]))
    live: Counter[str] = Counter()
    peak = 0
    for _, delta, run_id in points:
        live[run_id] += delta
        if live[run_id] <= 0:
            del live[run_id]
        peak = max(peak, len(live))
    return peak


def overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


@pytest.fixture(scope="session")
def contracts() -> ContractRegistry:
    return ContractRegistry.load()


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqlRunStore]:
    opened = open_store(f"sqlite:///{(tmp_path / 'p25.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def bus(store: SqlRunStore, contracts: ContractRegistry) -> EventBus:
    return EventBus(store, contracts=contracts)


@pytest.fixture
def blobs(tmp_path: Path) -> LocalContentStore:
    return LocalContentStore(tmp_path / "blobs")


@pytest.fixture
def lock(store: SqlRunStore, bus: EventBus) -> EngagementLock:
    return EngagementLock(store, bus)


@pytest.fixture
def environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: Any) -> None:
    """Ports from configuration, the way a real process gets them: the pool asks the
    compute port how wide it may be, and the queue adapter is whatever is named."""
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(outbox))
    monkeypatch.setenv("AA_WORKDIR", str(tmp_path / "work"))
    monkeypatch.setenv("AA_REDIS_URL", f"fakeredis://p25-{request.node.name}")
    ports.reset()
    yield
    ports.reset()


_PLANS: dict[str, CompiledGraph] = {}


def plan_for(engagement_id: str) -> CompiledGraph:
    if engagement_id not in _PLANS:
        _PLANS[engagement_id] = compile_recipe(
            load_recipe("monthly-refresh"),
            PlanContext(
                engagement_id=engagement_id,
                scope=ScopeResolver().resolve("valuation/esop/repeat"),
                taxonomy_version="coa-taxonomy@1.0.0",
                precedent_snapshot="precedent_snapshot_2026_09_01",
            ),
        )
    return _PLANS[engagement_id]


@pytest.fixture
def inputs_for(blobs: LocalContentStore) -> Callable[[str], dict[str, ContentRef]]:
    """Every run gets its own source documents, as real runs do. Two runs with byte-
    identical inputs and context would share step keys, and the second would be
    satisfied from the first's ledger rows without running - which is the design, and
    not what these tests are about."""

    def build(run_id: str) -> dict[str, ContentRef]:
        return {
            "source_documents": blobs.put_json(
                {"files": ["FY25 TB.xlsx"], "run": run_id}, name="source_documents"
            ),
            "engagement_profile": blobs.put_json(
                {"industry": "mfg", "run": run_id}, name="engagement_profile"
            ),
        }

    return build


def start(store: SqlRunStore, run_id: str, engagement_id: str) -> str:
    """A run the launcher would have registered: queued, nothing allocated."""
    store.start_run(
        run_id=run_id,
        engagement_id=engagement_id,
        plan_hash=plan_for(engagement_id).plan_hash,
        versions=PLAN_HASH_VERSIONS,
    )
    return run_id


@pytest.fixture
def make_passes(
    store: SqlRunStore,
    bus: EventBus,
    blobs: LocalContentStore,
    inputs_for: Callable[[str], dict[str, ContentRef]],
    environment: None,
) -> Callable[[Any], Callable[[str], ExecutionReport]]:
    """What the host registers: one pass of the executor, and a close-out when the pass
    finished the plan. The pool never sees the plan, the runner or the ending."""

    def build(runner: Any) -> Callable[[str], ExecutionReport]:
        executor = StepExecutor(store, bus, runner, blobs=blobs)

        def run_pass(run_id: str) -> ExecutionReport:
            engagement = store.run(run_id).engagement_id
            report = executor.execute(
                plan_for(engagement), run_id, inputs_for(run_id), f"{CONTEXT_REF}:{run_id}"
            )
            if report.finished:
                close_out(
                    store, run_id, RunState.HALTED, Outcome.BLOCKED, ports.get_delivery(), bus=bus
                )
            return report

        return run_pass

    return build


@pytest.fixture
def make_pool(
    store: SqlRunStore,
    bus: EventBus,
    lock: EngagementLock,
    make_passes: Callable[[Any], Callable[[str], ExecutionReport]],
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., WorkerPool]:
    def build(runner: Any, *, workers: int = 2, adapter: str = "in_process") -> WorkerPool:
        monkeypatch.setenv("AA_MAX_PARALLELISM", str(workers))
        monkeypatch.setenv("AA_QUEUE_ADAPTER", adapter)
        ports.reset()
        return WorkerPool(store, bus, lock, make_passes(runner), clock=lambda: datetime.now(tz=UTC))

    return build


def events_of(store: SqlRunStore, run_id: str, event_type: str) -> list[Any]:
    return [e for e in store.events(run_id) if e.type == event_type]
