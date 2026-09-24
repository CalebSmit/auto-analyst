"""One place for "what does this module import", by tree rather than by text.

The companion to `tests/counting.py`. That one exists because a number written down twice
drifts; this one exists because a *substring* standing in for a property is a test that
passes for the wrong reason — and an audit of this suite found seven of them, four
guarding named non-negotiables.

The rule, written where somebody adding a test will read it:

    **Walk the tree, never the text.**

Two ways a substring check goes wrong, both of which happened here:

- **It misses.** `"intake.config" not in source` is defeated by `from intake import
  config`; `"urllib.request" not in source` by `from urllib import request`; and
  `"proxy_headers=False" in source` was satisfied by the *comment* that explained the
  line, so deleting the line itself left the test green.
- **It fires on nothing.** `"skills" in line` matched `from registries.recipes import
  unbuilt_skills`, which imports no skill at all. A guard that cries wolf on a correct
  change is a guard people learn to route around.

`reaches()` answers the question these were all reaching for: does this module import
that package, under any spelling.
"""

from __future__ import annotations

import ast
from pathlib import Path


def imported_modules(source: str) -> set[str]:
    """Every module this source imports, by dotted name.

    `import a.b` yields `a.b`; `from a.b import c` yields `a.b`, and also `a.b.c`, because
    `from pkg import module` is how a module is imported without the dot. The imported
    *names* are never returned on their own — `from x import skills_helper` imports `x`,
    and judging it on the name is what produced the false positive above.
    """
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def reaches(source: str, package: str) -> bool:
    """Whether this source imports that package or anything under it."""
    return any(
        name == package or name.startswith(f"{package}.") for name in imported_modules(source)
    )


def reaches_any(source: str, packages: tuple[str, ...]) -> tuple[str, ...]:
    """Which of those packages this source reaches. Empty when none, which is the shape a
    boundary assertion wants: `assert reaches_any(...) == ()` names the offender."""
    return tuple(p for p in packages if reaches(source, p))


def module_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")
