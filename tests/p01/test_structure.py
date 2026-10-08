"""P01 - the repo is the shape the blueprint says it is, and the gate works.

These tests are deliberately about structure only. No domain logic exists yet, so
there is nothing else true to assert.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tests.conftest import needs_a_checkout

ROOT = Path(__file__).resolve().parents[2]

# The directory tree the blueprint's repo listing specifies.
EXPECTED_DIRS = [
    "BUILD",
    "BUILD/phases",
    "contracts",
    "constraints",
    "scope",
    "skills/_firm",
    "skills/valuation/_group",
    "skills/valuation/_repeat",
    "skills/valuation/_non-repeat",
    "skills/valuation/esop/_segment",
    "skills/consulting",
    "skills/corporate-finance",
    "harness",
    "graph",
    "privacy",
    "tools",
    "guards",
    "review",
    "intake",
    "ports/storage",
    "ports/delivery",
    "ports/secrets",
    "ports/queue",
    "ports/llm",
    "ops",
    "ops/console",
    "fixtures",
    "tests",
]

# Directories that must explain themselves.
README_DIRS = [
    "BUILD", "contracts", "constraints", "scope", "skills", "harness", "graph",
    "privacy", "tools", "guards", "ports", "ops", "fixtures", "tests",
]

PACKAGES = ["harness", "graph", "privacy", "tools", "guards", "ports", "ops"]


# ------------------------------------------------------------------ tree


def plan() -> dict:
    return json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))


def open_phases() -> list[str]:
    return [p["id"] for p in plan()["phases"] if p["status"] != "done"]




@pytest.mark.parametrize("d", EXPECTED_DIRS)
def test_directory_exists(d: str) -> None:
    assert (ROOT / d).is_dir(), f"{d} is in the blueprint repo tree and missing here"


@pytest.mark.parametrize("d", README_DIRS)
def test_directory_explains_itself(d: str) -> None:
    """A directory nobody documented is a directory that erodes by month three."""
    readme = ROOT / d / "README.md"
    assert readme.is_file(), f"{d}/README.md missing"
    text = readme.read_text(encoding="utf-8")
    assert "What belongs here" in text, f"{d}/README.md does not say what belongs here"
    assert "What does not" in text, f"{d}/README.md does not say what does not belong here"


@pytest.mark.parametrize("p", PACKAGES)
def test_is_importable_package(p: str) -> None:
    assert (ROOT / p / "__init__.py").is_file(), f"{p} is not a package"


# The phase that first puts a module in each package. Until that phase closes, the
# package holds nothing but __init__.py - which is how "work has not run ahead of the
# plan" stays checkable as the plan advances, instead of being a list that has to be
# edited every phase until it agrees with whatever happened.
FIRST_BUILT_BY = {
    "ops": "P04",       # event bus, run store, manifest
    "graph": "P05",     # resolve, compile, execute, assertions
    "harness": "P08",   # the step executor and what wraps one step
    "privacy": "P11",   # payload scan first (P11 builds it); mask, vault, unmask in P12
    "guards": "P13",    # schema, provenance, tieout, reconcile, numeric lock
    "review": "P15",    # checkpoint policy, confidence router, queue, surface, decision log
    "intake": "P16",    # roster, config store, sweep, bind, fingerprint, window, lock
}


def test_the_package_map_covers_what_it_claims_to() -> None:
    """A guard over an empty set passes forever."""
    plan_ids = {p["id"] for p in plan()["phases"]}
    assert set(FIRST_BUILT_BY.values()) <= plan_ids
    for package in FIRST_BUILT_BY:
        assert (ROOT / package).is_dir()


@pytest.mark.parametrize("package", sorted(FIRST_BUILT_BY))
def test_no_package_is_built_before_its_phase(package: str) -> None:
    """Work has not run ahead of the plan.

    "Ahead" means a package whose phase has not been reached yet - writing the mask
    engine during P05. The current phase building its own package is the work, not a
    violation, so the check starts one phase out.

    This is worth a test because running ahead never feels like running ahead at the
    time.
    """
    phase = FIRST_BUILT_BY[package]
    still_open = open_phases()
    # By number. `"P11" <= "P100"` is False, so on the hundredth phase every package
    # built before it read as work running ahead of the plan - four green tests turning
    # red at once, against a tree that had not moved.
    if not still_open or int(phase[1:]) <= int(still_open[0][1:]):
        # Its phase has closed, or is the one being worked now. A package the current
        # phase exists to build is not "running ahead" - it is the work.
        return

    offenders = [
        str(f.relative_to(ROOT))
        for f in (ROOT / package).rglob("*.py")
        if f.name != "__init__.py"
    ]
    assert not offenders, (
        f"{package}/ is built by {phase}, which is still open, but these modules "
        f"already exist: {', '.join(offenders)}"
    )


# ------------------------------------------------------------------ toolchain


def test_pyproject_pins_python_312() -> None:
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert cfg["project"]["requires-python"].startswith(">=3.12")


def test_pyproject_is_the_single_config() -> None:
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    for tool in ("ruff", "pytest", "mypy"):
        assert tool in cfg["tool"], f"{tool} should be configured in pyproject, not its own file"
    for stray in ("setup.cfg", "pytest.ini", ".ruff.toml", "tox.ini", "mypy.ini"):
        assert not (ROOT / stray).exists(), f"{stray} splits configuration across files"


def test_env_example_exists_and_no_real_env_is_committed() -> None:
    assert (ROOT / ".env.example").is_file()
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore, ".env must be gitignored - it will hold an API key"
    assert "runs/" in gitignore, "run artifacts hold client data and must never be committed"


def test_claude_md_carries_the_session_rules() -> None:
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "BUILD/STATE.md" in text, "CLAUDE.md must point at the cursor first"
    assert "gate close" in text
    assert "max_turns == 1" in text, "the single-turn rule is non-negotiable and must be stated"


# ------------------------------------------------------------------ the plan


def test_plan_is_wellformed() -> None:
    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    ids = [p["id"] for p in plan["phases"]]
    # By number, not by spelling. `sorted(ids)` puts P100 between P10 and P11, so this
    # assertion started failing on the hundredth phase against a plan that was in perfect
    # order - the same defect P100 fixes in the gate, sitting in the test that checks it.
    assert ids == sorted(ids, key=lambda i: int(i[1:])), "phases must be in order"
    assert len(ids) == len(set(ids)), "duplicate phase id"
    for p in plan["phases"]:
        for key in ("id", "title", "block", "gate", "status", "intent", "tasks", "exit", "checks"):
            assert key in p, f"{p.get('id')} missing {key}"
        assert p["gate"] in ("auto", "human")
        assert p["tasks"], f"{p['id']} has no tasks"
        assert p["exit"], f"{p['id']} has no exit criteria"
        assert p["checks"], f"{p['id']} has no executable check - it could never close"
        if p["gate"] == "human":
            assert p.get("human_check"), (
                f"{p['id']} is a judgment gate but does not say what a person checks"
            )


def test_every_phase_has_a_file_and_a_test_directory() -> None:
    needs_a_checkout("every phase's own directory")
    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    for p in plan["phases"]:
        assert (ROOT / "BUILD" / "phases" / f"{p['id']}.md").is_file(), f"{p['id']}.md missing"
        assert (ROOT / "tests" / p["id"].lower()).is_dir(), f"tests/{p['id'].lower()} missing"


def test_checkpoints_land_on_real_phases_and_roughly_every_three() -> None:
    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    ids = [p["id"] for p in plan["phases"]]
    prev = 0
    for c in plan["checkpoints"]:
        assert c["after"] in ids, f"{c['id']} lands after a phase that does not exist"
        assert c["checks"], f"{c['id']} has no integration test"
        span = ids.index(c["after"]) + 1 - prev
        assert 1 <= span <= 4, f"{c['id']} covers {span} phases - checkpoints should stay small"
        prev = ids.index(c["after"]) + 1
    assert prev == len(ids), "the last checkpoint must cover the last phase"


def test_generated_files_say_they_are_generated() -> None:
    for f in ("PLAN.md", "STATE.md"):
        text = (ROOT / "BUILD" / f).read_text(encoding="utf-8")
        assert "Generated" in text or "generated" in text, f"{f} must warn against hand editing"


# ------------------------------------------------------------------ the gate


def gate(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gate.py"), *args],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_gate_status_runs_with_no_arguments() -> None:
    r = gate("status")
    assert r.returncode == 0, r.stdout + r.stderr
    # Either a phase is in progress or the plan is finished. Both are states the gate
    # prints properly, and a test that only knows the first one fails on the last day.
    assert "CURRENT" in r.stdout or "Every phase is closed" in r.stdout


def test_gate_refuses_to_close_a_phase_out_of_order() -> None:
    """A check-off mechanism that cannot refuse is decoration.

    The target is derived from the plan rather than named. An earlier version of this
    test hardcoded P02, which meant it asserted the gate was broken the moment P02
    legitimately closed - a test that has to be edited every phase is a test that will
    eventually be edited into agreeing with whatever happened.
    """
    still_open = open_phases()
    if len(still_open) < 2:
        pytest.skip("only one phase left open - nothing is out of order any more")
    ahead = still_open[1]
    r = gate("close", ahead)
    assert r.returncode == 1, (
        f"closing {ahead} while {still_open[0]} is open should have been refused"
    )
    assert "REFUSED" in r.stdout


def test_gate_refuses_a_checkpoint_whose_phases_are_open() -> None:
    """Likewise derived. A checkpoint whose phases are all done would actually run here,
    which is a slow and surprising thing for a unit test to do."""
    ids = [p["id"] for p in plan()["phases"]]
    done = {p["id"] for p in plan()["phases"] if p["status"] == "done"}
    for c in plan()["checkpoints"]:
        covered = ids[: ids.index(c["after"]) + 1]
        if any(p not in done for p in covered):
            r = gate("checkpoint", c["id"])
            assert r.returncode == 1
            assert "REFUSED" in r.stdout
            return
    pytest.skip("every checkpoint's phases are closed")


def test_gate_check_does_not_mutate_the_plan() -> None:
    before = (ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8")
    # The first phase still open, or the last one there is when the plan is finished.
    # `check` re-runs a closed phase quite happily; what this is about is that it writes
    # nothing either way.
    still_open = open_phases()
    gate("check", still_open[0] if still_open else plan()["phases"][-1]["id"])
    after = (ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8")
    assert before == after, "check must never write state - only close may"
