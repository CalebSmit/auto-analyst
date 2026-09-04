"""`gate eval <skill>` as a first-class command."""

from __future__ import annotations

import subprocess
import sys

from tests.p22.conftest import ROOT


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gate.py"), "eval", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=600,
    )


def test_gate_eval_scores_a_skill_and_exits_zero_on_a_pass() -> None:
    result = run("timing-normalization")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "timing-normalization@0.1.0  PASS" in result.stdout
    assert "arithmetic_agreement: 1 >= 1  PASS" in result.stdout


def test_gate_eval_coverage_names_what_is_not_covered() -> None:
    result = run("--coverage")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "skills NOT covered (9)" in result.stdout
    assert "guards NOT covered (6)" in result.stdout
    assert "shadow_disagreement" in result.stdout


def test_gate_eval_refuses_an_unshipped_skill_with_a_nonzero_exit() -> None:
    result = run("ddr-tagging")
    assert result.returncode == 1
    assert "ddr-tagging" in result.stdout and "FAIL" in result.stdout


def test_gate_eval_needs_a_skill_or_a_flag() -> None:
    assert run().returncode == 2
