"""P141 (draft): the fourth site, and the borrowed code.

Two findings that are the same shape - the right answer was already written down in the
same file, and a second site did it differently.

**The gate ordered ids as strings, in a fourth place.** `number_of()` exists precisely for
this, and its docstring names the three sites fixed on 2026-09-22 when the plan crossed a
hundred phases: `phases_covered_by`, `cmd_close`'s in-order check, and
`phases_after_last_checkpoint`. `amend_checkpoint` has a fourth - `sort(key=lambda x:
x["after"])` - which that sweep missed because it is not a *comparison*, so looking for `<`
could not find it. Moving C76 to cover P140 ran it, and the plan came back with its 76
checkpoints in the order P03, P06, P09, **P100**, P102, ... and C59-after-P99 last.

Nothing was lost: `gate render` rewrites PLAN.md from the plan, and the order was repaired
numerically before anything was generated from it. What it cost was the hour of a red
checkpoint whose cause was the tool reporting it.

**And a refusal that gives advice for a different problem.** `aa owed` on an engagement
whose division has no request list says the right thing and then says:

    what to do: The run criteria version named is not a file under ops/criteria/, or names
    a criterion the scorecard cannot measure. Pin a version that exists ...

`SCOPE.UNKNOWN_CRITERIA` is borrowed in two places that are not about criteria -
`admin/console.py` for a missing request list and `report/appendices.py` for an unknown
appendix - and `what to do` is the half a person acts on.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# What an id looks like when it is being ordered: a plan entry's key, or a variable the
# gate passes one around in.
ID_KEYS = {"id", "after"}
ID_NAMES = {"pid", "cid", "phase_id", "checkpoint_id"}


def gate() -> ast.Module:
    return ast.parse((ROOT / "tools" / "gate.py").read_text(encoding="utf-8"))


def _is_id_expression(node: ast.AST) -> bool:
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
        return node.slice.value in ID_KEYS
    return isinstance(node, ast.Name) and node.id in ID_NAMES


def _counts_by_number(node: ast.AST) -> bool:
    """Whether this expression has gone through `number_of`."""
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "number_of"
        for n in ast.walk(node)
    )


def test_nothing_in_the_gate_orders_an_id_as_a_string() -> None:
    """The rule the three fixed sites were instances of, asserted over the whole file so
    that a fourth cannot be written. `amend_checkpoint` was the fourth."""
    offenders = []
    for node in ast.walk(gate()):
        if isinstance(node, ast.Compare) and any(
            isinstance(op, ast.Lt | ast.LtE | ast.Gt | ast.GtE) for op in node.ops
        ):
            sides = [node.left, *node.comparators]
            if any(_is_id_expression(s) for s in sides) and not all(
                _counts_by_number(s) for s in sides
            ):
                offenders.append(f"line {node.lineno}: {ast.unparse(node)}")
    assert offenders == [], "ids ordered as strings: " + "; ".join(offenders)


def test_every_sort_in_the_gate_sorts_by_number() -> None:
    """The shape the 2026-09-22 sweep could not see: a sort key is not a comparison, so
    looking for `<` found three sites and left a fourth."""
    offenders = []
    for node in ast.walk(gate()):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(
            node.func, "id", ""
        )
        if name not in {"sort", "sorted"}:
            continue
        key = next((k.value for k in node.keywords if k.arg == "key"), None)
        if key is None:
            continue
        if any(_is_id_expression(n) for n in ast.walk(key)) and not _counts_by_number(key):
            offenders.append(f"line {node.lineno}: {ast.unparse(key)}")
    assert offenders == [], "sorted on the spelling of an id: " + "; ".join(offenders)


def test_the_helper_that_exists_for_this_says_where_it_is_needed() -> None:
    """`number_of` carries the three sites it was written for. A fourth is now named, so
    the next person reading it is told that a sort counts as well as a comparison."""
    source = (ROOT / "tools" / "gate.py").read_text(encoding="utf-8")
    found = re.search(r"def number_of\(pid: str\) -> int:\n    \"\"\"(.*?)\"\"\"", source, re.S)
    assert found, "number_of is gone"
    assert "amend_checkpoint" in found.group(1), "the fourth site is not written down"
    assert "sort" in found.group(1), "it still reads as being only about comparisons"


def test_the_checkpoints_are_in_order_in_the_plan_as_it_stands() -> None:
    """The plan this repaired, asserted on the file rather than on the code that writes
    it - the two can disagree and only one of them is what the next session reads."""
    import json

    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    numbers = [int(re.sub(r"\D", "", c["after"])) for c in plan["checkpoints"]]
    assert numbers == sorted(numbers), "the checkpoints are out of order in the plan"


# ------------------------------------------------ and a refusal that answers its own problem


def raised_codes(rel: str) -> dict[int, str]:
    """Every `diagnose(CODE, ...)` in a file, by line, read from the tree.

    Grepping would find the import as well, and the point of this is which code each
    *refusal* carries.
    """
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    out = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "diagnose"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            out[node.lineno] = node.args[0].id
    return out


def test_the_criteria_code_is_raised_only_where_criteria_are() -> None:
    """It was borrowed in two files for four refusals, none of them about a criteria
    version - so `aa owed` answered a missing request list with "pin a version that
    exists". `what to do` is the half a person acts on."""
    # Three files, not the two the phase first looked at. C77 walked every module that
    # raises a diagnostic and found `report/setup.py` answering "this appendix carries
    # forward and nothing updates it" with the criteria advice - a sixth distinct problem
    # wearing the same code, and the reason this list is now the result of a walk rather
    # than of a search.
    for rel in ("admin/console.py", "report/appendices.py", "report/setup.py"):
        borrowed = [line for line, code in raised_codes(rel).items() if code == "UNKNOWN_CRITERIA"]
        assert borrowed == [], f"{rel} raises UNKNOWN_CRITERIA at {borrowed}"

    scorecard = raised_codes("ops/scorecard.py")
    assert "UNKNOWN_CRITERIA" in scorecard.values(), "the code is now raised nowhere at all"


def test_each_new_code_says_what_to_do_about_its_own_problem() -> None:
    """A code's whole value is its `what_now`. Borrowing one borrows advice written about
    something else, which is worse than no advice: it sends somebody somewhere."""
    from registries.diagnostics import DiagnosticsRegistry

    registry = DiagnosticsRegistry.load()
    said = {
        "SCOPE.NO_REQUEST_LIST": ("starting list", "intake/request_lists/"),
        "SCOPE.UNKNOWN_APPENDIX": ("appendix", "listed ids"),
        "SCOPE.APPENDIX_REGISTRY_INVALID": ("appendix registry", "report/appendices.py"),
        "SCOPE.APPENDIX_CARRIES_FORWARD": ("already written", "name one of those"),
    }
    for code, must in said.items():
        what_now = registry.get(code).what_now
        for phrase in must:
            assert phrase in what_now, f"{code} does not mention {phrase!r}"
        for wrong in ("ops/criteria/", "scorecard", "criteria version"):
            assert wrong not in what_now, f"{code} still gives the criteria advice: {wrong}"


def test_the_refusal_a_person_actually_meets() -> None:
    """End to end through the console, because the two halves - which code is raised and
    what that code says - are in different files and each was self-consistent."""
    from registries.diagnostics import DiagnosticsRegistry
    from registries.errors import NO_REQUEST_LIST

    registry = DiagnosticsRegistry.load()
    entry = registry.get(NO_REQUEST_LIST)
    assert entry.family == "SCOPE"
    assert len(entry.what_now.split()) >= 12, "a what-to-do nobody can act on"
    # The two halves do different jobs and must not do the same one. The *message* says
    # what happened and why another division's list is not lent; the *what to do* says
    # where to put one. Written the other way round, a reader meets the same three
    # sentences twice - which is what the first draft of this entry did.
    assert "intake/request_lists/" in entry.what_now, "it does not say where a list goes"
    assert "walks up" in entry.what_now, "it does not say which scopes a file serves"

    from admin.console import AdminConsole  # noqa: F401 - the message lives at its raise site

    said = (ROOT / "admin" / "console.py").read_text(encoding="utf-8")
    assert "does not borrow another division" in said, "the message stopped saying why"
