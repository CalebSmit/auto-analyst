"""C69 - bounding a real call, and being able to watch one.

Both phases are about the same evening: the first run with a real key.

* **P122** is the bound. Every step declared a timeout, the executor computed
  `min(step's, the firm ceiling)` and put it on the attempt, and nothing between there
  and the provider read it — while the SDK retried twice *inside* a step the executor
  would itself retry, which is a loop the graph does not own and cannot count.
* **P123** is the seeing. Everything a person wants while a run is going was already
  recorded and reachable only through a browser page somebody keeps refreshing.

They are two halves of one question — **what happens when a call is slow** — and they have
to agree about it. The bound decides when a slow call becomes a failure; the watcher
decides whether anybody knows before it does. A bound nobody can see is a silence with a
timer on it, and a watcher that reports against a bound nothing enforces is a reassurance.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tools.watch_run import Step, steps_of

ROOT = Path(__file__).resolve().parents[3]
T0 = datetime(2026, 9, 24, 21, 0, tzinfo=UTC)


def stamp(seconds: int) -> str:
    return (T0 + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def event(at: int, kind: str, step: str = "") -> Any:
    return type(
        "E",
        (),
        {
            "seq": at,
            "ts": stamp(at),
            "type": kind,
            "step_id": step,
            "cost_usd": 0.0,
            "diagnostic_code": "",
            "message": "",
            "payload": {},
        },
    )()


# ============================================================ they mean the same bound


def test_the_watcher_marks_a_step_against_the_bound_the_call_is_given() -> None:
    """One number, two uses. The recipe declares `timeout_s`, the executor hands it to the
    provider as the call's timeout, and the watcher marks a step slow against the same
    figure - so "past the time its step allows" means the call is about to be cut off,
    rather than being a separate opinion about slowness."""
    import yaml

    recipe = yaml.safe_load(
        (ROOT / "recipes" / "valuation-input-prep.yaml").read_text(encoding="utf-8")
    )
    timing = next(s for s in recipe["steps"] if s["id"] == "timing")
    bound = float(timing["timeout_s"])

    running_inside = Step("timing", stamp(0), False, bound - 1, 1, 0.0)
    running_past = Step("timing", stamp(0), False, bound + 1, 1, 0.0)
    assert "past the time" not in running_inside.line(bound)
    assert "past the time" in running_past.line(bound)


def test_the_watcher_reads_that_bound_from_the_recipe_the_run_ran() -> None:
    """Not from a constant of its own. A second copy of the number is a second number."""
    from tools.watch_run import bounds_for

    run = type("R", (), {"versions": {"recipe": "valuation-input-prep"}})()
    found = bounds_for(run)
    assert found.get("timing") == 300.0


def test_a_run_whose_recipe_cannot_be_read_is_still_reported() -> None:
    """A watcher that said nothing because it could not find a plan would be worse than
    one that does not mark a step."""
    from tools.watch_run import bounds_for

    assert bounds_for(type("R", (), {"versions": {}})()) == {}
    assert bounds_for(type("R", (), {"versions": {"recipe": "nonesuch"}})()) == {}


# ============================================================ the bound is real


def test_the_call_is_given_the_step_s_timeout() -> None:
    from contextlib import suppress

    from ports.llm import LLMRequest, Message, ModelPin
    from ports.llm.anthropic_messages import AnthropicMessagesLLM

    class Recorder:
        def __init__(self) -> None:
            self.kwargs: dict[str, Any] = {}
            self.messages = self

        def create(self, **kwargs: Any) -> Any:
            self.kwargs = kwargs
            raise RuntimeError("stop here")

    adapter = AnthropicMessagesLLM()
    recorder = Recorder()
    adapter._client = recorder  # noqa: SLF001
    with suppress(Exception):
        adapter.complete(
            LLMRequest(
                pin=ModelPin(model="claude-sonnet-5", effort="high"),
                system="s",
                messages=(Message("user", "{}"),),
                timeout_s=300.0,
            )
        )
    assert recorder.kwargs["timeout"] == 300.0


def test_and_the_transport_adds_no_attempts_of_its_own() -> None:
    """*The graph owns every loop.* Six HTTP attempts under a run that counted one is a
    loop nothing declared, and it is also the difference between a slow step and an
    unbounded one."""
    tree = ast.parse((ROOT / "ports" / "llm" / "anthropic_messages.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "Anthropic"
        ):
            given = {kw.arg: kw.value for kw in node.keywords}
            retries = given.get("max_retries")
            assert isinstance(retries, ast.Constant) and retries.value == 0


# ============================================================ and it can be seen going


def test_a_step_still_running_is_timed_against_now() -> None:
    """Which is what makes the mark mean anything while it matters, rather than after."""
    found = steps_of([event(0, "step.started", "timing")], T0 + timedelta(seconds=301))
    assert found[0].ended is False
    assert found[0].seconds == 301.0
    assert "past the time" in found[0].line(300.0)


def test_the_stall_detector_is_still_the_thing_that_records_it() -> None:
    """The watcher is a pair of eyes, not a second alarm. What goes on the record when a
    step overruns is `ops/stall.py`'s, raised by the sweep - and the watcher showing the
    same fact does not make it an event."""
    served = (ROOT / "tools" / "serve.py").read_text(encoding="utf-8")
    assert "_raise_alerts(served)" in served
    stall = (ROOT / "ops" / "stall.py").read_text(encoding="utf-8")
    assert "per-step timeout" in stall


def test_the_watcher_writes_nothing_at_all() -> None:
    """Two things looking at one run, and only one of them may touch it."""
    tree = ast.parse((ROOT / "tools" / "watch_run.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"append_event", "emit", "transition", "end_run"}
