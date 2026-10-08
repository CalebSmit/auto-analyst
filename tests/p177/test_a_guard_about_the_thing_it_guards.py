"""P177 - a guard has to be about the thing it guards.

Two tests written in this block read `.github/workflows/verify.yml`, which the image
deliberately does not ship, and both got the guard wrong in a different way.

One had **no guard**: it read the file directly, so inside the image it raised
`FileNotFoundError` and was the single failure in a run of 5,097. P175 already has a scan
for this - *the tests that ask about the repository say so before they read it* - and it did
not catch this one, because it begins

    if "needs_a_checkout(" not in text: continue

So it asks, of the files that already use the guard, whether the call comes first. It never
asks which files need one. A file with no guard anywhere is not examined at all, which is
the one case that matters.

The other had **the wrong guard**: it called `needs_a_checkout`, which asks whether there
is a `.git` directory. In the image there is neither a checkout nor a `.github`, so it
skipped for the right reason by accident. Those are two different absences, and a tarball
with `git init` run in it has one and not the other.

The rule that catches both is the same sentence: **a read of a path the image does not ship
must be guarded by a condition that names that path.** Not a guard about some other
absence, and not no guard. Found by hiding `.github` and running the tests, which took
about a minute and is the thing neither scan was doing.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.conftest import needs_a_checkout

ROOT = Path(__file__).resolve().parents[2]

# Top-level paths `.dockerignore` keeps out of the image, named here rather than parsed out
# of it: the point is the few a test is likely to read, and a parse would also hand back
# `.venv` and `runs`, which no test asks about.
NOT_SHIPPED = (".github", ".git")

READS = ("read_text", "read_bytes", "open", "iterdir", "glob", "rglob")


def excluded_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level names bound to a path under something the image does not ship."""
    found: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        literals = [
            piece.value
            for piece in ast.walk(node.value)
            if isinstance(piece, ast.Constant) and isinstance(piece.value, str)
        ]
        for excluded in NOT_SHIPPED:
            if excluded in literals:
                found[target.id] = excluded
    return found


def names_in(node: ast.AST) -> set[str]:
    return {inner.id for inner in ast.walk(node) if isinstance(inner, ast.Name)}


def test_a_read_of_what_the_image_lacks_is_guarded_by_asking_about_it() -> None:
    """Over every test in the suite, including the ones this phase wrote.

    The guard has to be in the same function as the read and has to mention the same
    constant. A function that reads through a module helper mentions the helper rather than
    the constant, and the helper is checked on its own - which is the shape p176 settled
    on, one guarded door.
    """
    needs_a_checkout("the test files themselves")

    offenders: list[str] = []
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        if "__pycache__" in path.parts or path.name == Path(__file__).name:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = excluded_constants(tree)
        if not constants:
            continue
        rel = path.relative_to(ROOT).as_posix()

        for function in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            # Which excluded constants does this function actually read from?
            read_from: set[str] = set()
            for call in [n for n in ast.walk(function) if isinstance(n, ast.Call)]:
                attribute = call.func
                if not isinstance(attribute, ast.Attribute) or attribute.attr not in READS:
                    continue
                receiver = attribute.value
                read_from |= names_in(receiver) & set(constants)
            if not read_from:
                continue

            # A skip in this function whose condition names the same constant.
            guarded: set[str] = set()
            for branch in [n for n in ast.walk(function) if isinstance(n, ast.If)]:
                raises_skip = any(
                    isinstance(inner, ast.Call)
                    and getattr(inner.func, "attr", None) == "skip"
                    for inner in ast.walk(branch)
                )
                if raises_skip:
                    guarded |= names_in(branch.test) & read_from

            missing = sorted(read_from - guarded)
            if missing:
                offenders.append(
                    f"{rel}:{function.lineno} {function.name} reads {', '.join(missing)} "
                    f"(under {', '.join(sorted({constants[m] for m in missing}))}) without "
                    f"a skip that asks whether it is there"
                )

    assert not offenders, (
        "the image ships none of these paths, so a read of one has to ask first - and ask "
        "about the path it is reading rather than about some other absence:\n  "
        + "\n  ".join(offenders)
    )
