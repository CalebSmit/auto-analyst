"""C33 - A run that ends says so.

Two phases sit behind this one. P59 made the declared loops enterable; P60 made what an
ending leaves behind real. They are two halves of the same finding: `RunStore.hold()` was
the only writer of a quarantine record and was reachable only from the loop path, so the
loops being dead and the quarantine store being empty were the same fact seen twice.

The question here is whether a run that stops now leaves enough for a person to act on it -
and whether the three failure policies every recipe declares have actually come to mean
three different things.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_the_rule_the_constraints_state_is_honoured_by_something_reachable() -> None:
    """`constraints.yaml`: exhaustion always produces an artifact - a quarantine record or a
    review item. The code that honoured it was behind a path nothing could enter."""
    rules = (ROOT / "constraints" / "constraints.yaml").read_text(encoding="utf-8")
    assert "always produces an artifact" in rules

    tree = ast.parse((ROOT / "graph" / "execute.py").read_text(encoding="utf-8"))
    holds = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "hold"
    ]
    assert holds, "the executor writes no quarantine record, so a run that stops leaves none"


def test_the_three_failure_policies_mean_three_different_things() -> None:
    """`halt`, `review` and `quarantine` are declared on every step of every recipe and were
    read by nothing, so all three ended a step identically."""
    source = (ROOT / "graph" / "execute.py").read_text(encoding="utf-8")
    assert 'step.on_failure == "review"' in source
    assert 'step.on_failure == "halt"' in source
    assert "halt_on" in source


def test_only_the_driver_ends_a_run() -> None:
    """One door out, with a manifest behind it. `store.transition` refuses a terminal state
    for exactly that reason, so an executor that tried to finish a halted run itself would
    raise inside the pass instead of ending it."""
    from ops.models import RunState

    executor = (ROOT / "graph" / "execute.py").read_text(encoding="utf-8")
    assert "close_out" not in executor, "the executor writes a manifest"
    assert f"RunState.{RunState.HALTED.name}" not in executor

    driver = (ROOT / "workers" / "driver.py").read_text(encoding="utf-8")
    assert "report.halt_on" in driver
    assert "close_out(" in driver


def test_every_declared_policy_is_one_the_executor_knows() -> None:
    """A recipe that declared a fourth policy would now be a recipe whose steps quietly fall
    through to the default."""
    import yaml

    from graph.recipes import RECIPES_DIR

    known = {"halt", "review", "quarantine"}
    for recipe in sorted(RECIPES_DIR.glob("*.yaml")):
        if recipe.stem == "registered":
            continue
        body = yaml.safe_load(recipe.read_text(encoding="utf-8")) or {}
        for step in body.get("steps", ()) or ():
            assert step.get("on_failure") in known, f"{recipe.name}:{step['id']}"


def test_a_quarantine_record_is_write_once_per_step_key(tmp_path: Path) -> None:
    """A quarantined step is not in the ledger, so a resumed pass re-reaches it. The first
    version of this hit the table's unique constraint and raised inside the executor.

    Asked of the behaviour rather than the text: the module declares `hold` twice - once on
    the Protocol and once on the implementation - and reading the first found a stub.
    """
    from ops.run_store import QuarantineRecord, open_store

    store = open_store(f"sqlite:///{(tmp_path / 'c33.db').as_posix()}")
    try:
        store.start_run(
            run_id="run_c33",
            engagement_id="E-1",
            plan_hash="sha256:" + "0" * 64,
            versions={"model_pin": "p", "skills": [], "contracts": "1", "constraints": "1"},
        )
        record = QuarantineRecord(
            step_id="timing",
            step_key="sha256:" + "b" * 64,
            code="PROCESS.QUARANTINED",
            owner="system",
            reason="first",
        )
        store.hold("run_c33", record)
        store.hold("run_c33", record)
        (held,) = store.quarantines("run_c33")
        assert held.reason == "first"
    finally:
        store.close()


def test_the_new_code_is_in_the_blueprint() -> None:
    """Every code in the registry appears in the blueprint's own table - a diagnostic the
    design does not list is one nobody reading the design can look up."""
    from registries.errors import TRANSPORT_EXHAUSTED

    blueprint = (ROOT / "docs" / "architecture.html").read_text(encoding="utf-8")
    assert TRANSPORT_EXHAUSTED.split(".", 1)[1] in blueprint
