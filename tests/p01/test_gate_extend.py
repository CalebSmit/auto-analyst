"""`gate extend`: the plan can grow, on the record, and only in one direction.

The gate could change a phase and could not add one. That was correct while the plan was
fixed at 28 phases and became the thing in the way the moment there was agreed work past
the end of it. The alternative - editing `BUILD/plan.json` by hand - is the one thing the
session rules forbid outright, because it is how a plan and its real state start to
disagree.

Every test here runs against a copy of the real plan in a temp directory. Nothing touches
the repo's own build state, which is the point: a test that could rewrite the plan is a
test nobody should run twice.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "gate.py"


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A copy of the build state, and a gate pointed at it."""
    build = tmp_path / "BUILD"
    build.mkdir()
    (build / "phases").mkdir()
    for name in ("plan.json", "AMENDMENTS.md", "LEDGER.md"):
        shutil.copy2(ROOT / "BUILD" / name, build / name)
    gate = tmp_path / "tools"
    gate.mkdir()
    shutil.copy2(GATE, gate / "gate.py")
    (tmp_path / "docs").mkdir()
    return tmp_path


def run(sandbox: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(sandbox / "tools" / "gate.py"), *args],
        cwd=sandbox, capture_output=True, text=True, check=False,
    )


def plan_of(sandbox: Path) -> dict:
    return json.loads((sandbox / "BUILD" / "plan.json").read_text(encoding="utf-8"))


def extend(sandbox: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return run(
        sandbox, "extend", "because the plan grew and the reason belongs on the record",
        "--title", "A new phase",
        "--block", "Block Z - later work",
        "--intent", "Something the plan did not cover when it was written.",
        *extra,
    )


def test_a_phase_is_added_at_the_end_with_the_next_id(sandbox: Path) -> None:
    before = plan_of(sandbox)["phases"]
    result = extend(sandbox, "--exit", "it does the thing", "--check", "true")
    assert result.returncode == 0, result.stdout + result.stderr

    after = plan_of(sandbox)["phases"]
    assert len(after) == len(before) + 1
    assert [p["id"] for p in after[:-1]] == [p["id"] for p in before], "history is untouched"

    added = after[-1]
    last_before = int(before[-1]["id"][1:])
    assert added["id"] == f"P{last_before + 1:02d}", "the id follows the last, with no gap"
    assert added["status"] == "open"
    assert added["title"] == "A new phase"
    assert added["exit"] == ["it does the thing"]
    assert added["checks"] == ["true"]


def test_the_reason_is_recorded_like_every_other_plan_change(sandbox: Path) -> None:
    extend(sandbox, "--exit", "it does the thing", "--check", "true")
    amendments = (sandbox / "BUILD" / "AMENDMENTS.md").read_text(encoding="utf-8")
    assert "because the plan grew and the reason belongs on the record" in amendments
    assert "phase added:" in amendments
    assert "exit criterion: it does the thing" in amendments


def test_a_phase_with_no_exit_criterion_is_refused(sandbox: Path) -> None:
    """A phase that can close on nothing is a phase that means nothing.

    "Nothing was written" is counted against the plan as it was a moment ago, not against
    a number typed here - the plan is meant to grow, and a literal count turns that into
    a failure.
    """
    before = len(plan_of(sandbox)["phases"])
    result = extend(sandbox, "--check", "true")
    assert result.returncode != 0
    assert "exit criterion" in result.stdout + result.stderr
    assert len(plan_of(sandbox)["phases"]) == before, "nothing was written"


def test_a_phase_with_no_check_is_refused(sandbox: Path) -> None:
    """`gate close` runs the checks. With none, closing is an assertion, not a test."""
    before = len(plan_of(sandbox)["phases"])
    result = extend(sandbox, "--exit", "it does the thing")
    assert result.returncode != 0
    assert "check" in result.stdout + result.stderr
    assert len(plan_of(sandbox)["phases"]) == before, "nothing was written"


def test_a_judgment_phase_says_what_a_person_confirms(sandbox: Path) -> None:
    refused = extend(sandbox, "--exit", "e", "--check", "true", "--gate", "human")
    assert refused.returncode != 0
    assert "human-check" in refused.stdout + refused.stderr

    ok = extend(
        sandbox, "--exit", "e", "--check", "true", "--gate", "human",
        "--human-check", "You confirm the thing on ten real engagements",
    )
    assert ok.returncode == 0
    added = plan_of(sandbox)["phases"][-1]
    assert added["gate"] == "human"
    assert added["human_check"].startswith("You confirm")


def test_extending_renders_the_phase_file_and_the_plan(sandbox: Path) -> None:
    """A phase nobody can read is a phase that exists only in JSON."""
    extend(sandbox, "--exit", "it does the thing", "--check", "true")
    pid = plan_of(sandbox)["phases"][-1]["id"]
    rendered = (sandbox / "BUILD" / "phases" / f"{pid}.md").read_text(encoding="utf-8")
    assert "A new phase" in rendered
    assert "it does the thing" in rendered
    assert "Block Z - later work" in rendered
    assert (sandbox / "BUILD" / "STATE.md").is_file()


def test_the_new_phase_becomes_current_only_after_the_ones_before_it(sandbox: Path) -> None:
    """Phases close in order, so a phase added at the end waits its turn. The status
    output keeps naming the first phase still open, not the newest one.

    Which phase that is comes from the plan rather than from a name written here. A test
    that pins today's current phase fails every time one closes, and a phase closing is
    the most routine thing this build does.
    """
    before = plan_of(sandbox)["phases"]
    first_open = next(x["id"] for x in before if x["status"] != "done")

    added = extend(sandbox, "--exit", "it does the thing", "--check", "true")
    assert first_open not in added.stdout.split("added")[0]

    status = run(sandbox, "status").stdout
    assert f"CURRENT   {first_open}" in status, status
    after = plan_of(sandbox)["phases"]
    assert after[-1]["id"] != first_open, "the new phase is not the current one"
    assert f"{len(after)}/{len(after)}" not in status, "not everything is closed"


def test_a_block_is_sealed_with_a_checkpoint(sandbox: Path) -> None:
    """Every block of work ends in one, and the tool says so when one is owed."""
    added = extend(sandbox, "--exit", "e", "--check", "true")
    assert "OWED" in added.stdout, added.stdout
    assert "gate seal" in added.stdout

    sealed = run(
        sandbox, "seal", "the block is finished",
        "--title", "A new checkpoint", "--proves", "the block holds together",
    )
    assert sealed.returncode == 0, sealed.stdout + sealed.stderr
    checkpoints = plan_of(sandbox)["checkpoints"]
    assert checkpoints[-1]["title"] == "A new checkpoint"
    assert checkpoints[-1]["after"] == plan_of(sandbox)["phases"][-1]["id"]
    assert checkpoints[-1]["checks"], "a checkpoint runs an integration test"

    again = run(sandbox, "seal", "twice", "--title", "x", "--proves", "y")
    assert again.returncode != 0
    assert "nothing to seal" in again.stdout + again.stderr


def test_block_h_is_in_the_real_plan_and_is_open(sandbox: Path) -> None:
    """The five phases this command was added for. Read from the repo's own plan rather
    than the sandbox copy, because this is a fact about the build, not about the tool."""
    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    block = [p for p in plan["phases"] if p["block"].startswith("Block H")]
    assert [p["id"] for p in block] == ["P29", "P30", "P31", "P32", "P33"]
    assert all(p["status"] == "open" for p in block)
    assert all(p["exit"] and p["checks"] for p in block)
    titles = [p["title"] for p in block]
    assert titles[0].startswith("Scope choices")
    assert "Registered methodology" in titles[1]
