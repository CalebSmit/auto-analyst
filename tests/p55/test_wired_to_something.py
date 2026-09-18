"""Three things that were built, registered, tested, and connected to nothing.

None of them failed. That is the point: each passed its own tests and did nothing in the
only wiring that runs, and two of the three were reproduced by the nearest end-to-end test
rather than caught by it. A component handed to everything except the thing that reads it
is not built, and a suite that is green over one is not checking what it appears to check.

What is asserted here reaches through `tools.serve.build()` - the composition root, the same
stores and ports a real run uses - rather than through a double assembled by the test. A
double would have been wired correctly by whoever wrote it, which is exactly how the
omission survived.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from graph.execute import StepExecutor
from harness.context import NoPrecedents
from tests.p08.conftest import CONTEXT_REF
from tools.serve import Seam, build, precedent_is_wired, readiness, served_context

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The whole system, wired, against a database of this test's own."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'serve.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    # Without a vault key the pool does not start, and this test needs the pool: the
    # object that was wired wrongly is the dispatcher the pool's driver builds.
    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    (tmp_path / "inbox").mkdir()
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    system = build()
    yield system
    system.close()
    ports.reset()


# ------------------------------------------------------- 1. precedent, in the served runtime


def test_the_served_runtime_can_retrieve_precedent(served: Any) -> None:
    """The bug, stated as the thing it cost.

    `PrecedentStore(store)` was built in the composition root, handed to the precedent
    lookup tool and to `RunWiring`, and not to the Context Builder eighteen lines below it.
    So every served run assembled its context with `NoPrecedents()`: an answer a person gave
    on one engagement was never shown to the model on the next, and `precedent_ids` came
    back empty on every dispatch. Nothing raised, nothing degraded, nothing was logged.

    Reached through the pool the command builds, because that is the object that was wrong.
    """
    assert served.pool is not None, "no pool built; this test cannot say anything"
    dispatcher = served.pool.passes.wiring.dispatcher_for("run_probe")
    assert not isinstance(dispatcher.context.precedents, NoPrecedents), (
        "the served runtime assembles context with no precedent source, so no decision "
        "anybody has made reaches the model"
    )
    assert hasattr(dispatcher.context.precedents, "retrieve")


def test_the_one_construction_site_requires_what_was_forgotten() -> None:
    """`served_context` takes `precedents` positionally and without a default, so the served
    graph cannot be built without answering the question. The Context Builder keeps its
    default because a component test legitimately has no store - what changed is that the
    default stopped being reachable by forgetting."""
    import inspect

    signature = inspect.signature(served_context)
    precedents = signature.parameters["precedents"]
    assert precedents.default is inspect.Parameter.empty


def test_the_seam_reports_it(served: Any) -> None:
    seams = {seam.name: seam for seam in readiness()}
    assert "precedent retrieval" in seams, "a joined port nobody reports is one nobody checks"
    assert seams["precedent retrieval"].ready
    assert isinstance(seams["precedent retrieval"], Seam)


def test_the_seam_goes_red_when_the_wiring_drops_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """The half that matters. A seam that can only say yes is the same kind of check as a
    scan that can only say clean."""
    monkeypatch.setattr(
        "tools.serve.served_context",
        lambda tree, blobs, bus, store, precedents: __import__(
            "harness.context", fromlist=["ContextBuilder"]
        ).ContextBuilder(tree, blobs, bus, store=store),
    )
    assert precedent_is_wired() is False
    assert not {s.name: s for s in readiness()}["precedent retrieval"].ready


# ------------------------------------------------------------ 2. a gate that exists to call


def test_the_release_path_does_not_read_a_field_that_was_never_there() -> None:
    """`workers/driver.py` read `w.release_gate`, and `RunWiring` has no such field.

    `w.delivery` is truthy, so the `and` did not short-circuit: the line would have raised
    `AttributeError` into a quarantine with no diagnostic code the first time any run
    reached `release`. It never has - both shipped recipes end at `qc-tieout`, which has no
    mechanical half - so the suite, the rehearsals and every run agreed it was fine.
    """
    from dataclasses import fields

    from workers.driver import RunWiring

    names = {f.name for f in fields(RunWiring)}
    assert "release_gate" not in names, "still not a field; the gate is built from the wiring"
    assert {"store", "bus", "delivery"} <= names, "and these are what building one needs"

    # The only regression guard available for this line, because `_release` is not
    # reachable until a run can get to it (B-004). Read as code rather than as text: the
    # first version of this searched the raw file and tripped over the comment explaining
    # the fix, which is a test failing on its own documentation.
    import ast

    tree = ast.parse((ROOT / "workers" / "driver.py").read_text(encoding="utf-8"))
    reads = {
        f"{node.value.id}.{node.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
    }
    assert "w.release_gate" not in reads, "the wiring is read for a field it does not have"
    assert {"w.store", "w.bus", "w.delivery"} <= reads, "the gate is built from what it has"


def test_the_served_wiring_carries_what_a_gate_is_built_from(served: Any) -> None:
    """The join, made against the real composition root.

    Not a run reaching `release` - that still waits on the qc-tieout procedure that does not
    exist (B-004), and pretending otherwise is what the old docstring did. What is provable
    today is the thing that was false: that the wiring a served run carries is enough to
    build the gate the release path calls, so the line fails on what delivery does rather
    than on a field nobody ever added.
    """
    from deliver.release import ReleaseGate

    assert served.pool is not None
    w = served.pool.passes.wiring
    gate = ReleaseGate(w.store, w.bus, w.delivery)

    assert gate.delivery is w.delivery, "the gate delivers through the run's own port"
    assert gate.store is w.store and gate.bus is w.bus
    assert gate.qc is not None, "a gate with no QC would release whatever it was handed"
    assert callable(gate.release)


# --------------------------------------------------- 3. a quarantine that names its failure


def test_a_failure_that_carries_a_diagnostic_keeps_its_code() -> None:
    from guards import GuardFailed, GuardResult

    result = GuardResult(
        guard="schema",
        passed=False,
        checked=1,
        failed=1,
        code="SKILL.SCHEMA_INVALID",
        reasons=("one violation",),
    )
    assert StepExecutor._code_of(GuardFailed(result, locator="ebitda")) == {
        "diagnostic_code": "SKILL.SCHEMA_INVALID"
    }


def test_a_failure_that_carries_none_is_not_given_an_invented_one() -> None:
    """Uncoded is an honest record. A code chosen to fill the column would be read as a
    classification somebody made, and `ops/analytics.py` ranks the failure breakdown by it."""
    assert StepExecutor._code_of(AttributeError("release_gate")) == {}
    assert StepExecutor._code_of(RuntimeError("no")) == {}


def test_a_guard_failure_reaches_the_record_carrying_its_code(
    executor_with: Any, plan: Any, started: str, run_inputs: dict[str, Any], store: Any
) -> None:
    """Run it, rather than read the source for the fix.

    `ops/analytics.py` ranks the failure breakdown by `diagnostic_code`, and every guard
    failure arrived with `SKILL.SCHEMA_INVALID`, `POLICY.*`, `PRIVACY.*` or `BUDGET.*` in
    hand and had it stringified into the message. So the breakdown has never once shown a
    guard failure, on any run, and the answer to "what is failing" was silently partial.
    """
    from guards import GuardFailed, GuardResult

    def fails_a_guard(attempt: Any) -> Any:
        raise GuardFailed(
            GuardResult(
                guard="schema",
                passed=False,
                checked=3,
                failed=1,
                code="SKILL.SCHEMA_INVALID",
                reasons=("proposal.adjustments[0].amount is not a number",),
            ),
            locator=attempt.step_id,
        )

    report = executor_with(fails_a_guard).execute(plan, started, run_inputs, CONTEXT_REF)

    assert report.quarantined, "the step should have quarantined"
    (event,) = [e for e in store.events(started) if e.type == "step.quarantined"]
    assert event.diagnostic_code == "SKILL.SCHEMA_INVALID", (
        "the guard's code reached the message and not the column the analytics read"
    )
    assert event.level == "error"
