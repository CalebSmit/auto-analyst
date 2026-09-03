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


def test_no_domain_logic_yet() -> None:
    """P01 delivers shape, toolchain, gate and plan. Nothing else.

    If this fails, work has run ahead of the plan - which is the thing the phase
    structure exists to prevent.
    """
    offenders = []
    for pkg in ("harness", "graph", "privacy", "guards", "ops"):
        for f in (ROOT / pkg).rglob("*.py"):
            if f.name == "__init__.py":
                continue
            offenders.append(str(f.relative_to(ROOT)))
    assert not offenders, (
        "P01 is structure only, but these modules already exist: " + ", ".join(offenders)
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
    assert ids == sorted(ids), "phases must be in order"
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
    assert "CURRENT" in r.stdout


def test_gate_refuses_to_close_a_phase_out_of_order() -> None:
    """A check-off mechanism that cannot refuse is decoration."""
    r = gate("close", "P02")
    assert r.returncode == 1, "closing P02 before P01 should have been refused"
    assert "REFUSED" in r.stdout


def test_gate_refuses_a_checkpoint_whose_phases_are_open() -> None:
    r = gate("checkpoint", "C1")
    assert r.returncode == 1
    assert "REFUSED" in r.stdout


def test_gate_check_does_not_mutate_the_plan() -> None:
    before = (ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8")
    gate("check", "P02")
    after = (ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8")
    assert before == after, "check must never write state - only close may"
