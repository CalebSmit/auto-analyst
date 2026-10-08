"""P175 - checks that have never been green.

This repository has had a remote since 18 September and its checks have never once passed:
twenty-one runs, no successes. Nobody looked, because the command that stands in for them
locally - `tools/verify.py` - skips exactly the three things they run, and says so honestly
every time: *did not run: postgres, redis, container*. Honest and unread.

Two causes, and neither was about continuous integration.

**Reaching uv.** `verify.py` ran every check through `python -m uv run`. There are two ways
uv is installed and they are not interchangeable: `pip install uv` puts a module in an
interpreter *and* a shim on PATH, so both spellings work, while the installer at
https://docs.astral.sh/uv/ puts only a binary, where `python -m uv` is nothing at all. On
a runner - and on any laptop that followed the documented install - all six checks failed
instantly with *No module named uv*, in zero seconds, which is the tell nobody read.

This build already knew the answer in two places: `tools/gate.py::resolve` has resolved the
prefix since it was written, and `tools/start.ps1` has asked the same question since P43 -
binary first, module second. `verify.py` and `tools/postgres.py` were the two that assumed.

**Bytecode from somebody else's machine.** A `.dockerignore` pattern is anchored to the
context root unless it begins with `**/`. `__pycache__/` therefore excluded one directory
at the top of the repo, which does not exist - so **840 `__pycache__` directories and 7,509
`.pyc` files compiled on a Windows developer's machine were copied into a Linux image**, and
Python used them in preference to the source beside them. The suite inside the image
reported failures whose locations read `C:\\dev\\automated-analyst\\...`; 64 failed and 23
errored, and the image's own job had never passed. An image assembled from whatever happened
to be lying around on one machine is the exact opposite of the claim its Dockerfile opens
with.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCKERIGNORE = (ROOT / ".dockerignore").read_text(encoding="utf-8")
RUNBOOK = (ROOT / "docs" / "WORK-LAPTOP.md").read_text(encoding="utf-8")


# ----------------------------------------------------------------- reaching uv


def python_files() -> list[Path]:
    return [
        path
        for path in (ROOT / "tools").rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def code_of(path: Path) -> str:
    """A module's code with its docstrings and comments taken out.

    Every one of these files *documents* `python -m uv run` in its header, because that is
    the spelling the rest of the repo writes. The question here is what the file does.
    """
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'"""·?.*?"""', "", text, flags=re.S)
    text = re.sub(r'"""(?:[^"]|"(?!""))*"""', "", text, flags=re.S)
    return re.sub(r"(?m)^\s*#.*$", "", text)


def test_no_tool_assumes_one_of_the_two_ways_uv_is_installed() -> None:
    """A file that builds a uv command has to have asked which uv is here. Asked of the
    code rather than of the whole file, because every one of them names the other spelling
    in its own documentation."""
    assumes = []
    for path in python_files():
        code = code_of(path)
        builds = re.search(r'["\']-m["\']\s*,\s*["\']uv["\']|python -m uv run', code)
        if not builds:
            continue
        if 'shutil.which("uv")' not in code:
            assumes.append(str(path.relative_to(ROOT)))
    assert assumes == [], (
        "these build a uv command without asking which uv this machine has: " + ", ".join(assumes)
    )


@pytest.mark.parametrize("name", ["gate.py", "verify.py", "postgres.py"])
def test_each_one_prefers_the_binary_and_falls_back_to_the_module(name: str) -> None:
    """Named one by one, because a sweep that passes because a file stopped calling uv is a
    sweep that has stopped watching what it was written for. The order matters: the binary
    is the documented install, and the module is the one that is only sometimes there."""
    code = code_of(ROOT / "tools" / name)
    assert 'shutil.which("uv")' in code, f"{name} does not look for the binary"
    assert re.search(r'["\']-m["\']\s*,\s*["\']uv["\']|python -m uv', code), (
        f"{name} has no fallback for a machine where only the module is there"
    )


def test_the_message_a_stuck_person_reads_names_the_spelling_that_works_here() -> None:
    """`tools/_environment.py` is what prints when a tool is run with the wrong
    interpreter - the one moment somebody has already been refused once. It told them to
    type `python -m uv run`, which on a machine with only the binary is the thing that will
    refuse them again.

    Named rather than left to the sweep above, which the revert harness caught passing with
    this undone: the file mentions `shutil.which` in a second place, so *does this file ask
    the question* was true while the line that matters had stopped asking it.
    """
    code = code_of(ROOT / "tools" / "_environment.py")
    prefix = re.search(r"prefix\s*=\s*(.+)", code)
    assert prefix, "the message no longer chooses a prefix at all"
    assert 'shutil.which("uv")' in prefix.group(1), (
        f"the prefix is fixed rather than chosen: {prefix.group(1).strip()}"
    )
    assert '"uv run"' in prefix.group(1), "the binary spelling is not one of the choices"


def test_the_powershell_entry_point_asks_the_same_question() -> None:
    """`start.cmd` is the first thing a work laptop runs, and it has asked correctly since
    P43 - this is here so the four answers cannot drift apart."""
    start = (ROOT / "tools" / "start.ps1").read_text(encoding="utf-8")
    # The code, not the header that explains it - the comment at the top names both
    # spellings and names the module one first, which is a sentence about the design
    # rather than the order the script tries them in.
    code = "\n".join(
        line for line in start.splitlines() if not line.lstrip().startswith("#")
    )
    binary = code.index("Get-Command uv")
    module = code.index("python -m uv")
    assert binary < module, "start.ps1 reaches for the module before the binary"


def test_the_runbook_says_what_to_do_when_the_documented_spelling_refuses() -> None:
    """Every command in every document carries `python -m uv run`, and `tests/p58` holds
    them to it. On a machine with only the binary that spelling is the one that does not
    work, so the runbook has to say so."""
    assert "No module named uv" in RUNBOOK, "nothing tells a reader what that error means"
    assert "uv run python tools/" in RUNBOOK, "nothing gives the spelling that works instead"


def test_the_runbook_no_longer_says_start_cmd_installs_uv() -> None:
    """It does not. It looks for uv two ways and stops with a sentence if it finds neither -
    which on a machine where IT controls what gets installed is the difference between a
    first morning and a dead end."""
    start = (ROOT / "tools" / "start.ps1").read_text(encoding="utf-8")
    assert "uv is not installed" in start, "start.ps1 no longer refuses when uv is missing"
    assert not re.search(r"start\.cmd installs it", RUNBOOK), (
        "the runbook claims start.cmd installs uv, and it stops instead"
    )
    assert "nothing here installs it" in RUNBOOK


# -------------------------------------------------- what reaches a layer


RECURSIVE = ("__pycache__/", "*.py[cod]", "*.db", "*.sqlite3", ".pytest_cache/")


@pytest.mark.parametrize("pattern", RECURSIVE)
def test_a_pattern_meant_for_any_depth_is_written_for_any_depth(pattern: str) -> None:
    """The defect, as a property. Without `**/` the pattern is anchored to the context root,
    and every one of these names a thing that lives at depth rather than at the top."""
    lines = [line.strip() for line in DOCKERIGNORE.splitlines() if line.strip()]
    assert f"**/{pattern}" in lines, f"{pattern} is anchored to the context root"
    assert pattern not in lines, f"{pattern} is also there unanchored, which does nothing"


def test_the_reason_travels_with_the_patterns() -> None:
    """A `**/` that somebody tidies away is the defect back. The measurement is the
    argument, so it is written beside them."""
    assert "anchored to the context root" in DOCKERIGNORE
    assert "7,509" in DOCKERIGNORE, "the count that made this visible is not recorded"


def test_nothing_the_repository_tracks_is_newly_excluded() -> None:
    """The other half: a recursive pattern is only safe if no committed file matches one.
    `fixtures/` could perfectly well have held a `.db` that a test reads.

    And it asks git, so it is one of the thirty-nine - which the image found by failing on
    it. A test about what reaches a layer cannot run from inside the layer.
    """
    from tests.conftest import needs_a_checkout

    needs_a_checkout("what the repository tracks")
    tracked = subprocess.run(  # noqa: S603
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.splitlines()
    caught = [
        path
        for path in tracked
        if re.search(r"\.(db|sqlite3|pyc|pyo|pyd)$|__pycache__|Thumbs\.db|\.DS_Store", path)
    ]
    assert caught == [], f"these are tracked and would no longer reach the image: {caught[:5]}"


def test_the_skip_for_a_repository_question_does_not_fire_on_a_repository() -> None:
    """The danger in giving thirty-five tests a skip is that it becomes a way of not
    running them. It is conditional on the thing it names, so on any developer machine and
    in the `verify` job - both of which are checkouts - every one of them still runs, and
    only the image skips. If this ever starts skipping here, those tests have quietly
    stopped being tests."""
    from _pytest.outcomes import Skipped

    from tests.conftest import needs_a_checkout

    if not (ROOT / ".git").exists():
        pytest.skip("there is no checkout here, so the guard below has nothing to prove")
    # Caught rather than simply called. `pytest.skip` raises, and a test that skips is not
    # a test that fails - so calling it bare left this green with the guard made
    # unconditional, which is precisely the state it exists to catch. The revert harness
    # found that; the first version of this proved nothing at all.
    try:
        needs_a_checkout("the guard itself")
    except Skipped as fired:  # pragma: no cover - the whole point is that it does not
        pytest.fail(f"the guard fired on a checkout, so all forty now skip everywhere: {fired}")


def test_the_tests_that_ask_about_the_repository_say_so_before_they_read_it() -> None:
    """Thirty-five of them, and each has to call the guard *first* - a call after the read
    is a test that still errors on the file it was about to be excused from."""
    import ast

    def calls_guard(node: ast.stmt) -> bool:
        return (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", None) == "needs_a_checkout"
        )

    late = []
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        if "__pycache__" in path.parts or path.name == Path(__file__).name:
            # This file is about the guard rather than excused by it: the one call in it
            # asserts the precondition first, on purpose, to prove the guard does *not*
            # fire on a checkout.
            continue
        text = path.read_text(encoding="utf-8")
        if "needs_a_checkout(" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            # A docstring reads nothing and an import reads nothing, so neither counts as
            # the thing the guard is meant to come before.
            body = [
                stmt
                for stmt in node.body
                if not isinstance(stmt, ast.Import | ast.ImportFrom)
            ]
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            where = next((n for n, stmt in enumerate(body) if calls_guard(stmt)), None)
            if where is not None and where != 0:
                late.append(f"{path.relative_to(ROOT)}::{node.name}")
    assert late == [], "the guard comes after the thing it excuses: " + ", ".join(late[:4])


def test_the_image_ships_no_bytecode_from_the_machine_that_built_it(
    container_runtime: str,
) -> None:
    """The one that needs a runtime, and the only one that proves the fix rather than the
    pattern. Everything under `.venv` is compiled inside the image on purpose - that is what
    `UV_COMPILE_BYTECODE=1` is for - so the question is about everything else."""
    tag = "automated-analyst:p175"
    build = subprocess.run(  # noqa: S603 - the runtime name comes from a closed set
        [container_runtime, "build", "-t", tag, "."],
        cwd=ROOT, capture_output=True, text=True, timeout=1800, check=False,
    )
    assert build.returncode == 0, build.stderr[-4000:]

    found = subprocess.run(  # noqa: S603
        [container_runtime, "run", "--rm", tag,
         "sh", "-c", "find /app -name '*.pyc' -not -path '/app/.venv/*' | wc -l"],
        cwd=ROOT, capture_output=True, text=True, timeout=600, check=False,
    )
    assert found.returncode == 0, found.stderr[-2000:]
    assert found.stdout.strip() == "0", (
        f"{found.stdout.strip()} compiled files reached the image from the build machine; "
        "Python will use them in preference to the source beside them"
    )
