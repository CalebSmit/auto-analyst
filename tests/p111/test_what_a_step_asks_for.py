"""P111 - what a step declares it needs, and what its handler actually asks for.

`release` declared `needs: [model]`. Its handler asks for the output of `model` *and* of
`timing`: the writer resolves every `figure_ref` in the mapping against a catalogue built
from timing's output, so a release handed a mapping alone has the destinations and nothing
to look the figures up in. It failed five steps into the first real client folder with
*"release needs the output of 'timing', which this run does not have (it has: model)"*.

Two reasons nothing caught it. `needs` is a line in a recipe and the ask is a line in a
handler, and no test compared the two. And the three recipes that shipped before this one
all end at `qc-tieout`, which has no procedure - so in this build's whole history, no run
had ever reached a release step to find out.

So the fix is the recipe, and the test is the comparison: walk the code for what each kind
of step will ask for, walk the recipes for what each step is handed, and fail on the
difference. Derived rather than declared, because a table of "what release needs" is one
more thing to keep in step with the code, and the code is what runs.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "workers" / "driver.py"
INPUTS = ROOT / "harness" / "inputs.py"
RUNNER = ROOT / "harness" / "runner.py"
RECIPES = ROOT / "recipes"

# One step known to ask for something it is not handed, with the reason. An allowlist
# entry without one fails as loudly as the defect, so this is the reason:
#
# `full-ddr-intake` has no `model` step at all - it goes intake, mask, ddr, timing,
# tagging, qc, release - and its release step's handler asks for a mapping. There is no
# `needs` list that fixes it, because there is nothing to name. That recipe tags a DDR
# response against a request schedule; whether its ending should write a workbook at all
# is a question about what the recipe is for, not a line to edit. Recorded as B-067.
KNOWN = {("full-ddr-intake", "release", "model"), ("full-ddr-intake", "release", "timing")}


# ============================================================ reading the code


def _literal_args(node: ast.AST, func: str, position: int) -> list[str]:
    """Every string literal passed at `position` to a call named `func` under `node`."""
    found: list[str] = []
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        name = (
            call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")
        )
        if name != func or len(call.args) <= position:
            continue
        arg = call.args[position]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            found.append(arg.value)
    return found


def skill_upstreams() -> dict[str, frozenset[str]]:
    """skill name -> the upstream step outputs `build_inputs` will ask it for.

    Read out of `harness/inputs.py`: each branch is `if name == "<skill>":`, and every
    `_upstream(step_id, "<output>", ...)` inside it is an ask that must have been handed
    over.
    """
    tree = ast.parse(INPUTS.read_text(encoding="utf-8"))
    build = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_inputs"
    )
    out: dict[str, frozenset[str]] = {}
    for branch in build.body:
        if not isinstance(branch, ast.If) or not isinstance(branch.test, ast.Compare):
            continue
        left, comparators = branch.test.left, branch.test.comparators
        if not (isinstance(left, ast.Name) and left.id == "name" and comparators):
            continue
        skill = comparators[0]
        if not (isinstance(skill, ast.Constant) and isinstance(skill.value, str)):
            continue
        asks = {a for node in branch.body for a in _literal_args(node, "_upstream", 1)}
        out[skill.value] = frozenset(asks) - {_verification_input()}
    return out


def _verification_input() -> str:
    """The ref the *runner* supplies on a verification pass, which no `needs` list names.

    Read from `harness/runner.py` rather than spelled here, so this exclusion follows the
    constant rather than becoming a second place that has to know its value."""
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "VERIFICATION_INPUT":
                    return str(node.value.value)
    raise AssertionError("harness/runner.py no longer declares VERIFICATION_INPUT")


def io_upstreams() -> dict[str, frozenset[str]]:
    """io step id -> the upstream step outputs the driver's handler will ask for.

    `self._output(attempt, "<name>")` is the direct ask. `build_inputs("<skill>", ...)`
    inherits that skill's asks. A helper method handed `attempt` is followed into, because
    that is where the ask actually lives: the real defect sat two calls down, `_io` ->
    `_release` -> `_figures` -> `build_inputs("model-load")`, and a scan that read only
    the handler's own body would have passed the broken recipe.
    """
    source = DRIVER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    methods = {
        n.name: n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name.startswith("_")
    }
    skills = skill_upstreams()

    def asks_of(node: ast.AST, seen: frozenset[str]) -> set[str]:
        found = set(_literal_args(node, "_output", 1))
        for skill in _literal_args(node, "build_inputs", 0):
            found |= set(skills.get(skill, ()))
        for call in ast.walk(node):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            name = call.func.attr
            helper = methods.get(name)
            takes_attempt = any(isinstance(a, ast.Name) and a.id == "attempt" for a in call.args)
            if helper is not None and takes_attempt and name not in seen:
                found |= asks_of(helper, seen | {name})
        return found

    # The ids come from the module's own constants, so a renamed step renames here too.
    constants = {
        target.id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    io = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_io")
    out: dict[str, frozenset[str]] = {}
    for branch in ast.walk(io):
        if not isinstance(branch, ast.If) or not isinstance(branch.test, ast.Compare):
            continue
        right = branch.test.comparators[0] if branch.test.comparators else None
        if not isinstance(right, ast.Name) or right.id not in constants:
            continue
        out[constants[right.id]] = frozenset(asks_of(branch, frozenset()))
    return out


def recipes() -> list[tuple[str, dict]]:
    return [
        (path.stem, yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(RECIPES.glob("*.yaml"))
    ]


# ============================================================ the scan itself


@pytest.mark.parametrize("name,recipe", recipes(), ids=lambda v: v if isinstance(v, str) else "")
def test_every_step_is_handed_what_its_handler_asks_for(name: str, recipe: dict) -> None:
    """The comparison nobody was making.

    `needs` is what a step is handed - not the order it runs in, and not what its
    ancestors produced. A handler asking for an output that is only a grandparent gets
    `InputsUnavailable` at run time, which is a quarantine five steps in rather than a
    red test here.
    """
    skills, io = skill_upstreams(), io_upstreams()
    missing: list[str] = []
    for step in recipe.get("steps") or []:
        handed = set(step.get("needs") or [])
        if step.get("kind") == "skill":
            wanted = skills.get(str(step.get("skill", "")), frozenset())
        else:
            wanted = io.get(str(step.get("id", "")), frozenset())
        for want in sorted(wanted - handed):
            if (name, step["id"], want) in KNOWN:
                continue
            missing.append(
                f"{step['id']} is handed [{', '.join(sorted(handed)) or 'nothing'}] "
                f"and its handler asks for {want!r}"
            )
    assert not missing, f"{name}: " + "; ".join(missing)


def test_the_release_step_is_handed_the_figures() -> None:
    """The instance, named, so the fix cannot be quietly undone by a reformat that keeps
    the general scan passing for some other reason."""
    recipe = yaml.safe_load((RECIPES / "valuation-input-prep.yaml").read_text(encoding="utf-8"))
    release = next(s for s in recipe["steps"] if s["id"] == "release")
    assert set(release["needs"]) >= {"model", "timing"}


# ============================================================ the scan can see a miss


def test_the_scan_reports_a_step_that_is_not_handed_what_it_asks_for() -> None:
    """A scan over four recipes that happen to be right is indistinguishable from a scan
    that checks nothing. Take `timing` away from the release step in memory and check the
    same rule reports it."""
    recipe = yaml.safe_load((RECIPES / "valuation-input-prep.yaml").read_text(encoding="utf-8"))
    for step in recipe["steps"]:
        if step["id"] == "release":
            step["needs"] = ["model"]
    with pytest.raises(AssertionError, match="asks for 'timing'"):
        test_every_step_is_handed_what_its_handler_asks_for("in-memory", recipe)


# ============================================================ it reads the real code


def test_the_requirement_comes_from_the_code() -> None:
    """Not from a table here. A list of "what release needs" written in a test is one more
    thing that has to be kept in step with the thing it describes, and the thing it
    describes is what runs."""
    assert "timing" in io_upstreams()["release"], "found by following _release -> _figures"
    assert "model" in io_upstreams()["release"]
    assert io_upstreams()["intake"] == frozenset(), "intake reads no upstream output"
    assert io_upstreams()["mask"] == frozenset()


def test_it_knows_what_the_skills_ask_for_too() -> None:
    found = skill_upstreams()
    assert found["line-item-tagging"] == frozenset({"timing"})
    assert found["model-load"] == frozenset({"timing"})
    assert found["timing-normalization"] == frozenset(), "the first skill reads no output"


def test_following_one_hop_is_what_finds_it() -> None:
    """The defect hid exactly one call deep: `_release` asks for `model` itself and
    inherits `timing` from `_figures`. A scan that looked only at the handler's own body
    would have passed the broken recipe."""
    source = DRIVER.read_text(encoding="utf-8")
    release = next(
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.FunctionDef) and n.name == "_release"
    )
    assert "timing" not in _literal_args(release, "_output", 1), "not asked for directly"
    assert "timing" in io_upstreams()["release"], "and found anyway"
