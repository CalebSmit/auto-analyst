"""C77 - a rule written in a file, and the file keeping it.

One phase, because it is one idea arriving twice in a morning.

**The gate ordered an id as a string, in a fourth place.** `number_of()` exists for exactly
this and its docstring already named three sites fixed when the plan crossed a hundred
phases. `amend_checkpoint` had a fourth, missed because it is a *sort key* rather than a
comparison - so a sweep looking for `<` could not see it. Moving C76 to cover P140 ran it,
and the plan came back with its seventy-six checkpoints out of order from the hundredth
phase on. The red that followed was the tool reporting itself.

**A refusal gave advice about another problem.** `SCOPE.UNKNOWN_CRITERIA` was raised at four
sites that are not about criteria, so `aa owed` answered a division with no request list by
telling somebody to pin a criteria version under `ops/criteria/`.

What a checkpoint can ask here, which the phase cannot: whether the two halves of each rule
still agree with each other across the files that hold them, and whether the plan on disk -
the thing the next session reads - is the plan the gate believes it wrote.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


# ------------------------------------------------- the gate and the plan it has written


def test_the_plan_on_disk_is_ordered() -> None:
    """Asserted on the file rather than on the code that writes it. The two can disagree,
    and only one of them is what the next session opens."""
    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    numbers = [int(re.sub(r"\D", "", c["after"])) for c in plan["checkpoints"]]
    assert numbers == sorted(numbers), "the checkpoints are out of order in the plan"

    phases = [int(re.sub(r"\D", "", p["id"])) for p in plan["phases"]]
    assert phases == sorted(phases), "the phases are out of order in the plan"


def test_the_last_checkpoint_covers_the_last_phase() -> None:
    """`tests/p01` says this too. It is here because this block exists on account of that
    rule firing, and a checkpoint that did not re-ask it would be taking the phase's word."""
    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    last_phase = plan["phases"][-1]["id"]
    assert plan["checkpoints"][-1]["after"] == last_phase


def test_both_places_the_gate_sorts_checkpoints_sort_the_same_way() -> None:
    """`seal` was right and `amend` was wrong, and the two are forty lines apart. The
    property is not that either is correct in isolation - it is that there is one way."""
    source = (ROOT / "tools" / "gate.py").read_text(encoding="utf-8")
    sorts = re.findall(r'plan\["checkpoints"\]\.sort\((.*?)\)\n', source)
    assert len(sorts) >= 2, "a sort was removed; this checkpoint is about there being two"
    assert len(set(sorts)) == 1, f"the two sorts disagree: {set(sorts)}"
    assert "number_of" in sorts[0]


def test_every_checkpoint_in_the_plan_reaches_the_page_a_person_reads() -> None:
    """`save()` renders PLAN.md from the plan, so a checkpoint the plan has and the page
    does not is a reader looking at a different build from the gate.

    Not asserted as an order. PLAN.md is laid out by **block** - "The interview" is its own
    section - so C27 appears under one heading and C28 under another, and the document runs
    in block order rather than in numeric order. An earlier draft of this test read that as
    disorder, which it is not: the ordering invariant belongs to `plan["checkpoints"]`, and
    the test above holds it there.
    """
    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    rendered = (ROOT / "BUILD" / "PLAN.md").read_text(encoding="utf-8")
    named = set(re.findall(r"\*\*(C\d+) - ", rendered))
    declared = {c["id"] for c in plan["checkpoints"]}
    missing, extra = declared - named, named - declared
    assert missing == set(), f"the plan has checkpoints PLAN.md lacks: {missing}"
    assert extra == set(), f"PLAN.md names checkpoints the plan lacks: {extra}"


# ------------------------------------------- a code's advice is about a code's problem


def test_no_refusal_carries_a_code_written_about_something_else() -> None:
    """Across every module that raises one, rather than the two that were found. The way
    this happens is somebody reaching for the nearest code that exists."""
    borrowed = {
        "UNKNOWN_CRITERIA": ("ops/scorecard.py",),
    }
    for code, allowed in borrowed.items():
        for path in sorted(ROOT.glob("*/[a-z]*.py")) + sorted(ROOT.glob("*/*/[a-z]*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith(("tests/", ".venv/")):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            raised = {
                node.args[0].id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "diagnose"
                and node.args
                and isinstance(node.args[0], ast.Name)
            }
            if code in raised:
                assert rel in allowed, f"{rel} raises {code}, which is not about it"


def test_every_code_this_block_added_is_registered_and_actionable() -> None:
    from registries.diagnostics import DiagnosticsRegistry

    registry = DiagnosticsRegistry.load()
    for code in (
        "SCOPE.NO_REQUEST_LIST",
        "SCOPE.UNKNOWN_APPENDIX",
        "SCOPE.APPENDIX_REGISTRY_INVALID",
    ):
        entry = registry.get(code)
        assert entry.family == "SCOPE"
        assert entry.owner == "config"
        assert len(entry.what_now.split()) >= 12, f"{code} says nothing to do"
        assert "ops/criteria/" not in entry.what_now, f"{code} carries the borrowed advice"


def test_the_registry_still_self_checks() -> None:
    """Three codes were added by hand. The registry's own check is what says they are
    declared once and registered, rather than spelled twice."""
    from registries.diagnostics import DiagnosticsRegistry

    assert DiagnosticsRegistry.load().self_check() == []
