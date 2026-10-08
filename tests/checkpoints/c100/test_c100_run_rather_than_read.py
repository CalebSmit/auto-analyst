"""Checkpoint C100 - run rather than read.

The remote has had checks since 18 September and they had never once passed. Twenty-one
runs, no successes, and nobody noticed - because the command that stands in for them locally
skips exactly the three things they run, and says so honestly every time. *Did not run:
postgres, redis, container.* An honest sentence nobody read is the same as a silent one.

What a checkpoint can ask that P175 could not. The phase fixed two causes; the property
underneath them is one claim about the whole repository, and it is the one worth holding:
**every way this build reaches out to the machine it is running on asks what is there rather
than assuming.** uv is the instance that cost a month of red checks. The others in the same
family are here too, because each of them is one hard-coded assumption away from the same
outcome and none of their own tests would notice.

And the half about what gets built: an image is only evidence if it was built from the
repository rather than from whatever was lying around beside it.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

from tests.conftest import needs_a_checkout

ROOT = Path(__file__).resolve().parents[3]
DOCKERIGNORE = (ROOT / ".dockerignore").read_text(encoding="utf-8")


def tools() -> list[Path]:
    return [p for p in (ROOT / "tools").rglob("*.py") if "__pycache__" not in p.parts]


def executable_code(path: Path) -> str:
    """A module without its docstrings or comments - what it does, not what it says."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


# ------------------------------------------- what is on the machine is asked, not assumed


def test_nothing_in_tools_assumes_how_uv_got_here() -> None:
    """The claim, over the whole of `tools/` rather than over the two files P175 fixed.

    Four of them build a uv command and every one has to have asked. The fifth way to get
    this wrong is a sixth tool written next month.
    """
    assuming = []
    for path in tools():
        code = executable_code(path)
        if not re.search(r"['\"]-m['\"],\s*['\"]uv['\"]|python -m uv run", code):
            continue
        if 'shutil.which' not in code or "'uv'" not in code.replace('"', "'"):
            assuming.append(path.relative_to(ROOT).as_posix())
    assert assuming == [], "these assume one of the two installs: " + ", ".join(assuming)


def test_the_entry_point_a_work_laptop_runs_asks_the_same_question() -> None:
    """`start.cmd` is the first thing typed on a new machine, and the only one of the five
    that is not Python."""
    start = (ROOT / "tools" / "start.ps1").read_text(encoding="utf-8")
    code = "\n".join(l for l in start.splitlines() if not l.lstrip().startswith("#"))  # noqa: E741
    assert code.index("Get-Command uv") < code.index("python -m uv")


@pytest.mark.parametrize(
    "what,asked",
    [
        ("a container runtime", r"RUNTIMES\b.*\n?.*shutil\.which|shutil\.which\(r\)"),
        ("an OCR engine", r"AA_OCR_ADAPTER"),
        ("a Postgres server", r"AA_TEST_PG_URL|shutil\.which\(.pg_ctl"),
    ],
)
def test_the_other_things_that_may_not_be_here_are_asked_about_too(what: str, asked: str) -> None:
    """The same family. Each is something a machine may or may not have, and each is one
    hard-coded path away from the month of red this checkpoint is named for."""
    everywhere = "\n".join(
        p.read_text(encoding="utf-8") for p in [*tools(), *(ROOT / "tests").rglob("conftest.py")]
    )
    assert re.search(asked, everywhere), f"nothing asks whether there is {what}"


# -------------------------------------------- an image built from the repository


RECURSIVE = ("__pycache__/", "*.py[cod]")


@pytest.mark.parametrize("pattern", RECURSIVE)
def test_what_must_not_reach_a_layer_is_excluded_at_every_depth(pattern: str) -> None:
    """A `.dockerignore` pattern is anchored to the context root unless it opens with
    `**/`, and neither of these names a thing that lives at the root."""
    lines = [line.strip() for line in DOCKERIGNORE.splitlines() if line.strip()]
    assert f"**/{pattern}" in lines, f"{pattern} is anchored to the root and matches nothing"


def test_the_working_tree_actually_has_the_thing_the_pattern_is_for() -> None:
    """Otherwise the two above are a rule about nothing. There are compiled files beside
    the source on any machine that has run the suite once, which is every machine that
    builds this image."""
    needs_a_checkout("the working tree the exclusion is about")
    found = [p for p in ROOT.rglob("__pycache__") if ".venv" not in p.parts]
    assert found, "no compiled files anywhere, so the exclusion above proves nothing today"


def test_a_question_about_the_repository_is_asked_from_a_repository() -> None:
    """The third of the three, and the one that turns forty failures into forty skips.

    `knowledge/` is kept out of an image because it may carry a client's name and an image
    is a thing people push; `.git` and `.github` are kept out because an image is the built
    thing rather than the repository that built it. A test that reads any of them is asking
    about the repository, and inside the image the honest answer is that this is not the
    place to ask.
    """
    # The function first, then its callers. Counting the call sites alone is counting text:
    # the revert harness renamed the definition and this stayed green, because forty test
    # bodies still *said* `needs_a_checkout` while nothing of that name existed to call.
    from tests import conftest

    assert callable(getattr(conftest, "needs_a_checkout", None)), (
        "the guard every one of these calls is not in tests/conftest.py under that name"
    )

    guarded, unguarded = [], []
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            body = ast.unparse(node)
            reads = re.search(r"knowledge/|knowledge\"|'knowledge'|\"git\"|'git'", body)
            if not reads:
                continue
            where = f"{path.relative_to(ROOT).as_posix()}::{node.name}"
            (guarded if "needs_a_checkout" in body else unguarded).append(where)
    assert len(guarded) >= 30, (
        f"only {len(guarded)} tests say they are asking about the repository; before P175 "
        "there were four, and the image failed on thirty-nine"
    )
    # Deliberately not a count of the *unguarded* ones. Mentioning `knowledge` is not the
    # same as reading the repository's own copy of it - most of these build their own under
    # `tmp_path` - and a threshold over a substring search is a number that has to be
    # re-tuned every time somebody writes the word. What settles it is the image running
    # the suite, which `tests/p28::test_the_image_is_built_and_the_suite_runs_inside_it`
    # does with `--container`. This says only that the habit is widespread, which is the
    # part a static check can honestly see.
    assert unguarded, "every test naming it is guarded, which is more than the rule asks"


def test_the_image_is_built_from_the_repository_and_not_from_beside_it(
    container_runtime: str,
) -> None:
    """The one that needs a runtime. Everything under `.venv` is compiled inside the image
    on purpose; the question is whether anything else was carried in from the host."""
    tag = "automated-analyst:c100"
    build = subprocess.run(  # noqa: S603 - the runtime name comes from a closed set
        [container_runtime, "build", "-t", tag, "."],
        cwd=ROOT, capture_output=True, text=True, timeout=1800, check=False,
    )
    assert build.returncode == 0, build.stderr[-4000:]
    carried = subprocess.run(  # noqa: S603
        [container_runtime, "run", "--rm", tag,
         "sh", "-c", "find /app -name '*.pyc' -not -path '/app/.venv/*' | wc -l"],
        cwd=ROOT, capture_output=True, text=True, timeout=600, check=False,
    )
    assert carried.returncode == 0, carried.stderr[-2000:]
    assert carried.stdout.strip() == "0", (
        f"{carried.stdout.strip()} compiled files came from the build machine - Python will "
        "use them in preference to the source beside them, and did"
    )
