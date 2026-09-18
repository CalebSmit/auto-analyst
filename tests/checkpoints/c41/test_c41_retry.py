"""C41 - The retry path, joined at both ends.

P72 moved `TransportFailure` to the port so the adapter could raise what the executor
catches. A checkpoint asks whether the two ends now meet, and whether the scan that found
the gap would still find it if it reopened.

The defect is worth remembering for its shape rather than its size. Every piece was
present and correct - a documented class, a retry loop, an event, a diagnostic code, a
`retries` setting on every recipe - and the one thing missing was anything raising it. No
rehearsal could have shown it, because the fake and scripted adapters have no network.
"""

from __future__ import annotations

import ast
from pathlib import Path

from ports.llm import TransportFailure
from ports.llm.anthropic_messages import _is_transient

ROOT = Path(__file__).resolve().parents[3]


def test_the_class_the_adapter_raises_is_the_class_the_executor_catches() -> None:
    from graph.execute import TransportFailure as CaughtByExecutor

    assert CaughtByExecutor is TransportFailure
    assert TransportFailure.__module__ == "ports.llm"


def test_production_raises_it_now() -> None:
    """The exact check that found the defect: an exception class raised only by tests. If
    the adapter ever stops raising it, this says so rather than a retry quietly never
    happening again."""
    raisers = set()
    for path in ROOT.rglob("*.py"):
        parts = path.parts
        if ".venv" in parts or "__pycache__" in parts or "tests" in parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.exc is not None:
                called = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
                name = getattr(called, "id", None) or getattr(called, "attr", None)
                if name == "TransportFailure":
                    raisers.add(str(path.relative_to(ROOT)))
    assert raisers, "nothing in production raises TransportFailure - the retry cannot happen"


def test_the_retry_loop_still_has_something_to_do() -> None:
    """The executor's side, from P08, read here as the other half of the seam."""
    executor = (ROOT / "graph" / "execute.py").read_text(encoding="utf-8")
    assert "except TransportFailure as failure:" in executor
    assert "step.transport_failed" in executor
    assert "TRANSPORT_EXHAUSTED" in executor


def test_the_two_directions_still_disagree_about_a_refusal() -> None:
    """Transient and permanent must stay different questions. If they ever collapse, either
    a network blip ends a run or a rejected request is sent four times."""

    class Err(Exception):
        def __init__(self, status: int) -> None:
            super().__init__(str(status))
            self.status_code = status

    assert _is_transient(Err(503))
    assert not _is_transient(Err(400))


def test_no_rehearsal_could_have_caught_this_and_that_is_recorded() -> None:
    """The fake and scripted adapters have no network, so the gap was invisible to the two
    rehearsals that exist precisely to catch what the suite misses. Worth knowing when
    trusting a clean rehearsal."""
    for adapter in ("fake.py", "scripted.py"):
        source = (ROOT / "ports" / "llm" / adapter).read_text(encoding="utf-8")
        assert "TransportFailure" not in source, (
            f"{adapter} now raises TransportFailure; if that is deliberate, the rehearsals "
            "can exercise the retry path and this test should say so instead"
        )
