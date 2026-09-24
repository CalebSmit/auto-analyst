"""P100 - the hundredth phase, and the comparison that broke on it.

C59 went red on `tests/p01` the moment the plan reached a hundred phases. Nothing in the
tree had moved; the ids had simply grown a digit, and `"P100" < "P99"`.

Six places compared them as strings - four in the gate, two in the tests that check the
gate - and every one of them is a **safety net** rather than a step. That is what made it
worth a phase. A safety net that has stopped working looks exactly like one with nothing to
catch: `gate extend P100` printed no OWED warning, and the only reason anybody noticed was
that a checkpoint re-ran a test that happened to assert on it.

What each would have allowed, in the order it would have bitten:

* `phases_covered_by` - `"P100" <= "P40"` put the hundredth phase inside a checkpoint that
  predates it by sixty, so an old checkpoint would re-run new work and could fail on it.
* `cmd_close`'s in-order rule - `"P99"` is not less than `"P100"`, so the hundredth phase
  could have closed over an open ninety-ninth, and "phases close in order" is the rule the
  whole plan leans on.
* `phases_after_last_checkpoint` - stopped reporting anything owed at all.
* `cmd_seal`'s sort - would have filed a checkpoint after P100 between those after P10 and
  P11, so `checkpoints[-1]` would have stopped being the last one.
* `tests/p01`'s own `sorted(ids)` and `phase <= still_open[0]` - four green tests turning
  red against a tree that had not changed.

The gate is the only thing permitted to mark a phase done. A gate that mis-orders phases is
the one defect that can let every other defect through, which is why this is a phase and not
a one-line fix.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from tools.gate import number_of, phases_after_last_checkpoint, phases_before

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "gate.py"
PLAN = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))


def a_plan(phases: list[str], checkpoints: list[tuple[str, str]]) -> dict:
    return {
        "phases": [{"id": p, "status": "done"} for p in phases],
        "checkpoints": [{"id": c, "after": after} for c, after in checkpoints],
    }


# ============================================================ the ordering itself


@pytest.mark.parametrize(
    ("pid", "expected"),
    [("P1", 1), ("P07", 7), ("P99", 99), ("P100", 100), ("C3", 3), ("C60", 60)],
)
def test_an_id_orders_by_its_number(pid: str, expected: int) -> None:
    assert number_of(pid) == expected


def test_the_comparison_that_broke() -> None:
    """Stated as the fact it is, so the next person reading this file does not have to
    take the docstring's word for it."""
    assert "P100" < "P99", "as strings, which is the whole bug"
    assert number_of("P100") > number_of("P99")


def test_an_id_with_no_number_is_refused_rather_than_silently_zero() -> None:
    """A zero would sort before every real phase and read as "the earliest", which is the
    worst possible answer to give quietly."""
    with pytest.raises(ValueError, match="carries no phase or checkpoint number"):
        number_of("P")


# ============================================================ what each net now catches


def test_a_checkpoint_does_not_cover_a_phase_added_after_it() -> None:
    """`"P100" <= "P40"` is True. An old checkpoint re-running new work can fail on a phase
    that did not exist when it was written, and there is no way to read that failure."""
    plan = a_plan(["P10", "P11", "P40", "P99", "P100"], [("C1", "P40")])
    covered = [p["id"] for p in phases_before(plan, "C1")]
    assert covered == ["P10", "P11", "P40"]
    assert "P100" not in covered


def test_the_phases_past_the_last_checkpoint_are_still_reported() -> None:
    """The check that caught this, and the one that had gone silent. `gate extend` printed
    no OWED for P100 at all."""
    plan = a_plan(["P98", "P99", "P100"], [("C59", "P99")])
    assert phases_after_last_checkpoint(plan) == ["P100"]


def test_the_last_checkpoint_is_found_by_number_not_by_spelling() -> None:
    """With `max()` over strings, a checkpoint after P99 beat one after P100 and the plan
    thought it was further along than it was."""
    plan = a_plan(["P99", "P100", "P101"], [("C59", "P99"), ("C60", "P100")])
    assert phases_after_last_checkpoint(plan) == ["P101"]


def test_phases_still_close_in_order_at_three_digits() -> None:
    """The rule the whole plan leans on. Held on the gate's source because the alternative
    is running `gate close` against the real plan, which writes."""
    source = GATE.read_text(encoding="utf-8")
    assert 'q["id"] < p["id"]' not in source, "the string comparison is back"
    assert 'number_of(q["id"]) < number_of(p["id"])' in source


# ============================================================ none of them come back


def test_no_comparison_of_two_ids_in_the_gate_is_a_string_comparison() -> None:
    """The general form, because four of these were found by hand and a fifth would be
    found the same way. Any `<`, `<=`, `>` or `>=` between two things that look like phase
    ids has to go through `number_of`.
    """
    tree = ast.parse(GATE.read_text(encoding="utf-8"))
    suspects: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, ast.Lt | ast.LtE | ast.Gt | ast.GtE) for op in node.ops):
            continue
        for side in (node.left, *node.comparators):
            # `x["id"]` or `x["after"]` compared directly, rather than wrapped.
            if (
                isinstance(side, ast.Subscript)
                and isinstance(side.slice, ast.Constant)
                and side.slice.value in ("id", "after")
            ):
                suspects.append(ast.unparse(node))
    assert not suspects, "compare these by number: " + "; ".join(suspects)


def test_the_gate_sorts_checkpoints_by_number() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert 'sort(key=lambda c: c["after"])' not in source
    assert 'sort(key=lambda c: number_of(c["after"]))' in source


def test_the_tests_that_check_the_gate_do_not_repeat_the_mistake() -> None:
    """Two of the six were here. A test file that orders ids as strings reports a plan in
    perfect order as broken, which is how this was found and is not how it should be found
    next time."""
    source = (ROOT / "tests" / "p01" / "test_structure.py").read_text(encoding="utf-8")
    assert "assert ids == sorted(ids)," not in source
    assert "phase <= still_open[0]" not in source


# ============================================================ the real plan


def test_the_real_plan_is_in_order_by_number() -> None:
    ids = [p["id"] for p in PLAN["phases"]]
    assert ids == sorted(ids, key=number_of)
    assert len(ids) >= 100, "this phase exists because the plan passed a hundred"


def test_every_real_checkpoint_covers_a_contiguous_run_ending_at_its_own_phase() -> None:
    """Re-asked by number over the real plan, because the spacing check in `tests/p01` is
    the one that would have gone quietly wrong as more three-digit phases arrived."""
    ids = [p["id"] for p in PLAN["phases"]]
    reached = 0
    for c in PLAN["checkpoints"]:
        assert c["after"] in ids
        at = ids.index(c["after"]) + 1
        assert at > reached, f"{c['id']} covers nothing new"
        assert at - reached <= 4, f"{c['id']} covers {at - reached} phases"
        reached = at
