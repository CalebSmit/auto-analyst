"""C60 - the gate's own arithmetic.

Every other checkpoint asks whether the phases agree with each other. This one asks whether
the thing that decides that question can still count.

P100 fixed six string comparisons of phase ids. What makes it worth a checkpoint of its own
is not the size of the fix but what the six had in common: each is a **safety net**, none of
them is on the path of any ordinary command, and a net that has stopped working is
indistinguishable from a net with nothing to catch. They failed silently for as long as the
plan had fewer than a hundred phases *and would have kept failing silently afterwards* - the
only reason any of it surfaced is that a checkpoint re-ran a test that happened to assert on
one of them.

So the three questions here are the ones a unit test of `number_of` cannot ask:

1. **Do the nets fire end to end**, through the gate's real commands against a real plan on
   disk, rather than through a helper called directly?
2. **Is the plan this repo actually carries well-ordered** by number, at a hundred phases and
   whatever comes after?
3. **Did fixing the gate leave the gate's other promises alone** - a phase still cannot be
   marked done without its checks passing, and `render` still writes what the plan says?
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "tools" / "gate.py"
PLAN = ROOT / "BUILD" / "plan.json"

sys.path.insert(0, str(ROOT))
from tools.gate import REENTRY as GATE_REENTRY  # noqa: E402


def outside_a_gate_run() -> dict[str, str]:
    """An environment with the gate's re-entry guard cleared.

    The gate skips re-running checks when it is already inside a gate run - a sensible
    guard, and one that made this checkpoint's own test pass alone and fail inside
    `gate checkpoint C60`, which is where it actually runs. The environment was deciding
    the result, which is the same defect P75 carried for twenty phases.
    """
    return {**os.environ, GATE_REENTRY: "0"}


def a_gate(home: Path, plan: dict) -> list[str]:
    """The real gate, run against a copy of the plan somewhere else.

    Against a copy because these commands write, and `run_commands_against_a_temp_copy` is
    a rule this project learned by destroying two committed records.
    """
    (home / "BUILD").mkdir(parents=True, exist_ok=True)
    (home / "BUILD" / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    for name in ("PLAN.md", "STATE.md", "AMENDMENTS.md", "LEDGER.md", "OPEN.md"):
        (home / "BUILD" / name).write_text("# generated\n", encoding="utf-8")
    (home / "BUILD" / "phases").mkdir(exist_ok=True)
    # Under `tools/`, because the gate finds the plan from its own location rather than
    # from the working directory - one level up from the file, exactly as in the repo.
    (home / "tools").mkdir(exist_ok=True)
    shutil.copy2(GATE, home / "tools" / "gate.py")
    return [sys.executable, str(home / "tools" / "gate.py")]


@pytest.fixture
def plan_at_a_hundred() -> dict:
    """A hundred closed phases, a red checkpoint after the ninety-ninth, and one more phase
    open past it - the exact state this session was in when the gate went quiet.

    Built by cloning the real plan's own first phase and checkpoint rather than by writing
    the keys out here. `save()` renders on every write and the renderer reads a dozen
    fields; a hand-made fixture goes stale the first time one is added, and then this
    checkpoint fails for a reason that has nothing to do with what it is asking.
    """
    real = json.loads(PLAN.read_text(encoding="utf-8"))
    template = dict(real["phases"][0])
    checkpoint = dict(real["checkpoints"][0])
    nothing = f'{sys.executable} -c "pass"'

    phases = []
    for n in range(1, 101):
        phase = dict(template)
        phase.update(
            id=f"P{n}",
            title=f"Phase {n}",
            block="B",
            status="done" if n < 100 else "open",
            checks=[nothing],
        )
        if n < 100:
            phase["closed"] = "2026-01-01"
        else:
            phase.pop("closed", None)
        phases.append(phase)

    checkpoint.update(
        id="C59", title="the one before", after="P99", status="open", checks=[nothing]
    )
    return {
        **{k: v for k, v in real.items() if k not in ("phases", "checkpoints")},
        "blocks": [{"name": "B", "intent": "x"}],
        "phases": phases,
        "checkpoints": [checkpoint],
    }


# ================================================ 1. the nets fire, through real commands


def test_a_red_checkpoint_blocks_the_hundredth_phase(tmp_path: Path, plan_at_a_hundred) -> None:
    """The net that had already failed. C59 is red and sits after P99; P100 must not close
    over it, and until P100 the gate let it through without a word."""
    gate = a_gate(tmp_path, plan_at_a_hundred)
    done = subprocess.run(
        [*gate, "close", "P100"],
        capture_output=True, text=True, cwd=tmp_path, env=outside_a_gate_run(),
    )
    assert done.returncode != 0, done.stdout
    assert "C59" in done.stdout + done.stderr


def test_the_gate_still_says_what_is_owed_at_three_digits(
    tmp_path: Path, plan_at_a_hundred
) -> None:
    """`gate extend` printed no OWED for P100 at all - in the very command that added it."""
    gate = a_gate(tmp_path, plan_at_a_hundred)
    added = subprocess.run(
        [*gate, "extend", "because", "--title", "A phase", "--block", "B",
         "--intent", "x", "--task", "t", "--exit", "e", "--check", "true"],
        capture_output=True, text=True, cwd=tmp_path, env=outside_a_gate_run(),
    )
    assert added.returncode == 0, added.stdout + added.stderr
    assert "OWED" in added.stdout, added.stdout
    assert "P101" in added.stdout


def test_a_phase_out_of_order_is_still_refused_at_three_digits(
    tmp_path: Path, plan_at_a_hundred
) -> None:
    """`"P99" < "P100"` is False, so the hundredth phase could close over an open
    ninety-ninth. Here P99 is reopened and P100 must refuse."""
    plan = plan_at_a_hundred
    for p in plan["phases"]:
        if p["id"] == "P99":
            p["status"] = "open"
    plan["checkpoints"][0]["status"] = "done"
    gate = a_gate(tmp_path, plan)
    done = subprocess.run(
        [*gate, "close", "P100"],
        capture_output=True, text=True, cwd=tmp_path, env=outside_a_gate_run(),
    )
    assert done.returncode != 0, done.stdout
    assert "P99" in done.stdout + done.stderr


def test_a_checkpoint_re_runs_its_own_phases_and_not_later_ones(
    tmp_path: Path, plan_at_a_hundred
) -> None:
    """`"P100" <= "P40"` is True, so an old checkpoint would re-run a phase added sixty
    phases after it was written - and could go red on work it was never about."""
    sys.path.insert(0, str(ROOT))
    from tools.gate import phases_before

    covered = [p["id"] for p in phases_before(plan_at_a_hundred, "C59")]
    assert covered[-1] == "P99"
    assert "P100" not in covered


# ================================================ 2. the plan this repo carries


def test_the_real_plan_is_ordered_and_fully_covered() -> None:
    """The plan on disk, not a fixture. A hundred phases is where this started going wrong
    and the plan only grows from here."""
    sys.path.insert(0, str(ROOT))
    from tools.gate import number_of

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    ids = [p["id"] for p in plan["phases"]]
    assert ids == sorted(ids, key=number_of)

    afters = [c["after"] for c in plan["checkpoints"]]
    assert afters == sorted(afters, key=number_of), "checkpoints out of order in the file"
    assert number_of(afters[-1]) == number_of(ids[-1]), "the last checkpoint misses the last phase"


def test_no_two_checkpoints_cover_the_same_phase() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    afters = [c["after"] for c in plan["checkpoints"]]
    assert len(afters) == len(set(afters))


# ================================================ 3. the rest of the gate is untouched


def test_a_phase_whose_check_fails_still_does_not_close(
    tmp_path: Path, plan_at_a_hundred
) -> None:
    """The gate's first promise, re-asked because P100 edited the function that closes a
    phase. "It works on my machine" is not a state transition."""
    plan = plan_at_a_hundred
    plan["checkpoints"][0]["status"] = "done"
    for p in plan["phases"]:
        if p["id"] == "P100":
            p["checks"] = [f"{sys.executable} -c \"raise SystemExit(1)\""]
    gate = a_gate(tmp_path, plan)
    done = subprocess.run(
        [*gate, "close", "P100"],
        capture_output=True, text=True, cwd=tmp_path, env=outside_a_gate_run(),
    )
    assert done.returncode != 0
    assert "REFUSED" in done.stdout

    after = json.loads((tmp_path / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    assert [p["status"] for p in after["phases"] if p["id"] == "P100"] == ["open"], (
        "a failed close wrote to the plan"
    )


def test_status_reads_the_plan_rather_than_the_rendered_files(
    tmp_path: Path, plan_at_a_hundred
) -> None:
    """STATE.md is generated from the plan and never the other way round. Held here because
    a gate that mis-orders phases would report the wrong current phase, and the rendered
    file is what the next session reads first."""
    gate = a_gate(tmp_path, plan_at_a_hundred)
    said = subprocess.run(
        [*gate, "status"],
        capture_output=True, text=True, cwd=tmp_path, env=outside_a_gate_run(),
    )
    assert said.returncode == 0, said.stdout + said.stderr
    assert "P100" in said.stdout, said.stdout
