"""Checkpoint C102 - checks a clean machine can pass.

P177 fixed four things. What a checkpoint can ask that the phase could not is the one
sentence underneath all four, and the four are worth listing because they are the same
mistake in four costumes:

- a generated file carried the clock, so every green commit went red the next morning;
- the first step of the verifier asked an *approval* gate a question about *bytes on disk*,
  so no clone could reach step two;
- a test asserted what one platform's mime table happens to know;
- a test read a path the image does not ship without asking whether it was there.

Each one passed, for weeks or months, on the machine it was written on. Each one could only
fail somewhere else - on a clone, in an image, on Linux, or tomorrow. So the property is
not about dates or registers or mime types. It is: **a check is only a check where it can
run, and every check here has to run on a machine that has nothing but the tracked files.**

So this does the thing none of the four phases did. It builds a tree out of `git ls-files`
alone - no register, no clearances, no templates, no `.venv`, no `.git` - and runs the
verifier's own collectors inside it. That is a clone, made the only way that cannot
accidentally include something this working tree has had lying around since September.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tests.conftest import needs_a_checkout

ROOT = Path(__file__).resolve().parents[3]

COLLECT = (
    "import json, sys; sys.path.insert(0, '.');"
    "from tools.surfaces import collect;"
    "print(json.dumps(collect(), sort_keys=True, default=str))"
)


@pytest.fixture(scope="module")
def a_clone() -> Path:
    """A tree of exactly what git tracks, and nothing else.

    `git ls-files` rather than a copy-with-exclusions, because an exclusion list is a guess
    about what a clone lacks and this is the answer. It is also what caught the original:
    `recipes/registered.yaml` is not on this list and had been in the working tree for
    weeks.
    """
    needs_a_checkout("the set of files a clone would get")
    listed = subprocess.run(  # noqa: S603
        ["git", "ls-files", "-z"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert listed.returncode == 0, listed.stderr
    tracked = [name for name in listed.stdout.split("\0") if name]
    assert len(tracked) > 500, f"only {len(tracked)} tracked files; the listing is wrong"

    holder = tempfile.mkdtemp()
    work = Path(holder) / "clone"
    for name in tracked:
        source = ROOT / name
        if not source.is_file():  # a deleted-but-staged path
            continue
        target = work / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    # The things a clone demonstrably does not have, asserted rather than assumed - if any
    # of these turned up, this fixture would be re-proving what the working tree already
    # believes and the checkpoint would be worthless.
    for absent in (
        "recipes/registered.yaml",
        "foundations/cleared.yaml",
        ".git",
        ".venv",
    ):
        assert not (work / absent).exists(), f"a clone would not have {absent}"
    assert not list((work / "templates").glob("*.xlsx")), "a clone has no built templates"
    return work


def test_the_surface_collector_answers_on_a_clone_and_answers_the_same(a_clone: Path) -> None:
    """The whole snapshot, not only the recipe half.

    Fourteen groups, and the one that refused was reached on the way to the others - so
    asking only about recipes would leave the next collector that grows a dependency on a
    machine-local file to be found by somebody's first morning.
    """
    here = subprocess.run(  # noqa: S603
        [sys.executable, "-c", COLLECT], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert here.returncode == 0, here.stdout + here.stderr

    there = subprocess.run(  # noqa: S603
        [sys.executable, "-c", COLLECT],
        cwd=a_clone, capture_output=True, text=True, check=False,
    )
    assert there.returncode == 0, (
        "the surface collector cannot run on a tree of only the tracked files, so the "
        "first step of verify.py refuses on every clone:\n" + there.stdout + there.stderr
    )
    assert json.loads(there.stdout) == json.loads(here.stdout), (
        "a clone collects a different public surface than this machine does, so every "
        "clone reports that a surface moved and the check means nothing"
    )


def test_the_generated_files_a_clone_holds_are_what_its_plan_renders_to(a_clone: Path) -> None:
    """`verify.py`'s state step, run where it had never been run: on a clone, and twice.

    The second render is the part that matters. It is the same process a day apart as far as
    anything date-dependent is concerned, and a generated file carrying the clock comes back
    different - which is the defect that made every commit go red the morning after.
    """
    first = subprocess.run(  # noqa: S603
        [sys.executable, "tools/gate.py", "render"],
        cwd=a_clone, capture_output=True, text=True, check=False,
    )
    assert first.returncode == 0, first.stdout + first.stderr

    rendered = {
        name: (a_clone / "BUILD" / name).read_bytes() for name in ("STATE.md", "PLAN.md")
    }
    for name, bytes_ in rendered.items():
        assert bytes_ == (ROOT / "BUILD" / name).read_bytes(), (
            f"BUILD/{name} as committed is not what a clone renders it to, so the state "
            f"step calls it stale on a machine that has changed nothing"
        )

    second = subprocess.run(  # noqa: S603
        [sys.executable, "tools/gate.py", "render"],
        cwd=a_clone, capture_output=True, text=True, check=False,
    )
    assert second.returncode == 0, second.stdout + second.stderr
    for name, bytes_ in rendered.items():
        assert (a_clone / "BUILD" / name).read_bytes() == bytes_, (
            f"BUILD/{name} is not a function of the plan alone"
        )


def test_a_clone_carries_no_record_of_a_decision_nobody_made(a_clone: Path) -> None:
    """The reason those files are gitignored, held as a property rather than as a habit.

    A registration says somebody at the firm approved a workflow and a clearance says
    somebody read a methodology file. Shipping either would ship a decision nobody made,
    which is why the honest starting state is empty - and why the collectors above must not
    need them. The two halves have to stay true together: the moment one of these is
    tracked, the tests above start passing for the wrong reason.
    """
    needs_a_checkout("what the repository tracks")
    listed = subprocess.run(  # noqa: S603
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.splitlines()
    for owed in ("recipes/registered.yaml", "foundations/cleared.yaml"):
        assert owed not in listed, (
            f"{owed} is tracked, which ships a decision nobody made - and makes the clone "
            f"tests in this file prove nothing"
        )
