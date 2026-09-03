"""No module under skills/ can import anything under tools/.

The exit criterion, and the one non-negotiable from CLAUDE.md that P10 owns: a skill
proposes, it never acts. Tools are reached by name through the Guarded Tool Runtime after
the Policy Gate authorises the call. If a skill could import a tool, the gate would be a
suggestion.

Walked over the import graph rather than asked of people, because the failure is
invisible - the code works perfectly until the day somebody asks what a skill actually
did. Two directions: nothing under skills/ reaches tools/, and nothing outside the
runtime binds a tool implementation.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"

# The six tool modules, as the repo listing names them. They arrive with P13 and P18; the
# boundary is declared now so it is already in force when they do.
TOOL_MODULES = ("tools.normalize", "tools.recompute", "tools.write_template")


def imported(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    named: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            named.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            named.add(node.module)
    return named


def reaches_tools(names: set[str]) -> set[str]:
    return {n for n in names if n == "tools" or n.startswith("tools.")}


def test_the_skill_tree_is_not_a_python_package() -> None:
    """The stronger form of the criterion, true today: skills are SKILL.md files, and
    there is no Python under skills/ at all. A skill has no code, so it has no imports.
    The test below covers the day that changes."""
    assert SKILLS.is_dir()
    assert not list(SKILLS.rglob("*.py"))
    assert len(list(SKILLS.rglob("SKILL.md"))) == 13


SKILL_SCRIPTS = sorted(SKILLS.rglob("*.py"))


@pytest.mark.parametrize("path", SKILL_SCRIPTS, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_module_under_skills_imports_tools(path: Path) -> None:
    offending = reaches_tools(imported(path))
    assert not offending, f"{path.relative_to(ROOT)} imports {sorted(offending)}"


def test_a_skill_script_would_be_caught() -> None:
    """A guard over an empty set passes forever. Prove the walker sees an import when
    there is one, on a file it will never find in the tree."""
    probe = SKILLS.parent / "tests" / "p10" / "_probe_skill_script.py"
    probe.write_text("from tools import recompute\n", encoding="utf-8")
    try:
        assert reaches_tools(imported(probe)) == {"tools"}
    finally:
        probe.unlink()


def test_only_the_runtime_may_bind_a_tool_implementation() -> None:
    """The other direction. Outside tools/ itself and the tests, the only module that may
    import a tool module is harness/runtime.py - and today not even that does, because
    the tools are registered by name from outside. The list is the design; the test is
    what keeps it a list rather than a hope."""
    allowed = {ROOT / "harness" / "runtime.py"}
    offenders: list[str] = []
    for package in ("harness", "graph", "privacy", "guards", "ops", "registries", "skills"):
        for path in sorted((ROOT / package).rglob("*.py")):
            names = imported(path)
            binds = any(n in TOOL_MODULES or n.startswith("tools.") for n in names)
            if binds and path not in allowed:
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"{offenders} bind a tool implementation outside the runtime"


def test_the_runtime_takes_tools_by_name_not_by_import() -> None:
    """The runtime is constructed with a mapping. It imports no tool module itself, so
    the set of things a skill can reach is a value somebody passed in - visible,
    testable, and empty until something is registered."""
    names = imported(ROOT / "harness" / "runtime.py")
    assert not reaches_tools(names)
    names = imported(ROOT / "harness" / "policy.py")
    assert not reaches_tools(names)
