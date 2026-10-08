"""P177 - green today, red tomorrow.

The Postgres job ran to completion for the first time in this repository and reported, in
its own words, `POSTGRES RAN - 65 store conformance test(s)` and `REDIS RAN - 8 queue
adapter test(s)`. Both passed. Then it failed on three things no cancelled job could have
shown, and two of them are not about CI at all - they are about a machine that has just
cloned this repository, which is the machine this build is for.

**The clock in a generated file.** `BUILD/STATE.md` carried `*Last written <today>*`, and
the `state` step of the verifier runs `gate render` and fails if `BUILD/` came back
changed. That check is right: a stale generated file is a plan disagreeing with itself. But
with the clock in the output, render always came back changed the day after a commit - so
every commit that was green went red the next morning, on every machine, and the red said
`state was stale` about a file nobody had touched. It had been true since the gate was
written and was invisible because nothing ran the check a day late. CI ran it a day late.

**A gate asked the wrong question.** `tools/surfaces.py` snapshots what each recipe file
declares, and it did so through `load_recipe`, which refuses a recipe the board has not
approved. Approval lives in `recipes/registered.yaml`, which git ignores on purpose, and
the test suite writes it through a session fixture. `surfaces` is the *first* step the
verifier runs, in its own process, before any fixture exists - so a fresh clone could not
get past step one, and this machine never noticed because that file had been sitting in the
working tree since September.

Both are the same shape, which is why they are one phase: a check that cannot pass on a
clean machine teaches everybody to ignore it, and then it is not a check.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import needs_a_checkout

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "BUILD"
GENERATED = ("STATE.md", "PLAN.md")


def test_no_generated_file_carries_the_day_it_was_generated() -> None:
    """The property, over the renderer's output rather than over its source.

    Asked as *does rendering twice give the same bytes* would not catch it - two renders a
    second apart agree. What catches it is that nothing in the output is today's date, and
    that is checkable now.
    """
    needs_a_checkout("the generated files under BUILD/")
    import datetime as dt

    today = dt.date.today().isoformat()
    plan = json.loads((BUILD / "plan.json").read_text(encoding="utf-8"))
    recorded = {
        item["closed"]
        for group in ("phases", "checkpoints")
        for item in plan.get(group, [])
        if item.get("closed")
    }

    for name in GENERATED:
        text = (BUILD / name).read_text(encoding="utf-8")
        if today in text and today not in recorded:
            raise AssertionError(
                f"BUILD/{name} contains {today}, which is today and is not a date the plan "
                f"records. A generated file carrying the clock cannot be checked against "
                f"what generates it: the state step will call it stale tomorrow."
            )


def test_rendering_a_day_later_changes_nothing() -> None:
    """The same claim, proved rather than inspected - the clock is moved, not waited for.

    `gate render` is run in a subprocess whose `date.today` is a year ahead. If anything it
    writes depends on when it ran, the bytes move and this fails. Nothing in the repository
    is touched: the render is pointed at a copy.
    """
    needs_a_checkout("the gate's renderer")
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "repo"
        work.mkdir()
        shutil.copytree(BUILD, work / "BUILD")
        for module in ("tools",):
            shutil.copytree(ROOT / module, work / module)

        before = {name: (work / "BUILD" / name).read_bytes() for name in GENERATED}

        # A fake today, a year on, installed before the gate reads its own clock. Written
        # as a file rather than passed to `-c`, where a class statement after a semicolon
        # is a syntax error.
        shim = work / "_render_later.py"
        shim.write_text(
            "import datetime as real, sys\n"
            "later = real.date(2027, 12, 31)\n"
            "class Fixed(real.date):\n"
            "    @classmethod\n"
            "    def today(cls):\n"
            "        return later\n"
            "real.date = Fixed\n"
            "sys.argv = ['gate.py', 'render']\n"
            "gate = 'tools/gate.py'\n"
            "exec(open(gate).read(), {'__name__': '__main__', '__file__': gate})\n",
            encoding="utf-8",
        )
        moved = subprocess.run(  # noqa: S603
            [sys.executable, str(shim)],
            cwd=work, capture_output=True, text=True, check=False,
        )
        assert moved.returncode == 0, moved.stdout + moved.stderr
        for name in GENERATED:
            assert (work / "BUILD" / name).read_bytes() == before[name], (
                f"BUILD/{name} is different when rendered on a later date, so a green "
                f"check goes red with nothing changed but the calendar"
            )


def test_the_surface_snapshot_does_not_need_an_approval_register() -> None:
    """What a clone has: the files, and no record of anybody approving anything.

    Run in a copy with `recipes/registered.yaml` absent, which is what git gives you. The
    collector has to answer, and has to answer the *same* thing - a snapshot that differed
    by whether the machine had approvals would make every clone report a moved surface.
    """
    needs_a_checkout("the surface collector")
    import shutil
    import tempfile

    here = subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import json,sys;sys.path.insert(0,'.');"
         "from tools.surfaces import recipes_surface, plans_surface;"
         "print(json.dumps({'r': recipes_surface(), 'p': plans_surface()}, sort_keys=True))"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert here.returncode == 0, here.stdout + here.stderr

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(
            ROOT, work,
            ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "runs", "*.db"),
        )
        register = work / "recipes" / "registered.yaml"
        if register.exists():
            register.unlink()
        assert not register.exists()

        clone = subprocess.run(  # noqa: S603
            [sys.executable, "-c", "import json,sys;sys.path.insert(0,'.');"
             "from tools.surfaces import recipes_surface, plans_surface;"
             "print(json.dumps({'r': recipes_surface(), 'p': plans_surface()}, sort_keys=True))"],
            cwd=work, capture_output=True, text=True, check=False,
        )
        assert clone.returncode == 0, (
            "the surface collector refuses on a clone with no approval register:\n"
            + clone.stdout + clone.stderr
        )
        assert json.loads(clone.stdout) == json.loads(here.stdout), (
            "the surface a clone collects is not the surface this machine collects, so "
            "every clone would report that a public surface had moved"
        )


def test_the_declared_shape_is_reachable_without_the_gate_and_the_gate_still_refuses(
    tmp_path: Path,
) -> None:
    """Both halves of the split, because either one alone is the wrong fix.

    Reading the shape must not need an approval; running a recipe still must. A fix that
    only did the first would be an exemption flag with a longer name.

    The refusing register is a real `RecipeRegister` pointed at a file with nothing in it,
    rather than a stub that raises - a stub would prove the test can raise, not that the
    gate still asks.
    """
    from graph.recipes import RECIPES_DIR, declared_in, load_recipe, recipe_names
    from registries.recipes import RecipeRegister, RegistrationRefused

    name = recipe_names()[0]
    path = RECIPES_DIR / f"{name}.yaml"

    # The ungated half answers.
    assert declared_in(path).name == name
    assert declared_in(path).steps, "a recipe with no steps is not a recipe"

    # The gated half refuses, against a register that has approved nothing.
    empty = tmp_path / "registered.yaml"
    empty.write_text("registered: []\n", encoding="utf-8")
    with pytest.raises(RegistrationRefused) as refused:
        load_recipe(name, RECIPES_DIR, RecipeRegister(path=empty))
    assert "never been approved" in str(refused.value), str(refused.value)

    # And the two are the same parser, so the snapshot cannot describe a different recipe.
    assert declared_in(path) == load_recipe(name)


def test_a_container_failure_names_the_test_that_failed() -> None:
    """The fourth finding of that run, and the reason the other three took so long to read.

    The image's suite reported `1 failed, 5097 passed` and the assertion that surfaced it
    printed `run.stdout[-8000:]` - and the last eight thousand characters of a pytest run
    are its *skip* report. So the name of the failing test had scrolled off the front, and
    working out which test it was meant reasoning from what had changed. That is guessing,
    about the one test whose whole job is to say what happened inside the image.
    """
    from tests.conftest import what_failed_inside

    stdout = (
        "........F...\n"
        "FAILED tests/p176/test_a_bound_smaller_than_the_work.py::test_the_measurement - "
        "FileNotFoundError: .github/workflows/verify.yml\n"
        "1 failed, 5097 passed, 307 skipped in 1005.15s\n"
        + "SKIPPED [15] tests/conftest.py:181: needs a git checkout; this is not one\n" * 400
    )
    said = what_failed_inside(stdout, "")

    assert "test_the_measurement" in said, (
        "the message does not name the test that failed, which is the only thing a reader "
        "needs from it"
    )
    assert "1 failed, 5097 passed" in said, "the counts are gone"
    assert said.index("test_the_measurement") < said.index("SKIPPED"), (
        "the failure is reported after the skip list, which is how it got lost"
    )
