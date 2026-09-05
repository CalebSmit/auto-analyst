"""The verification command itself, and the table it narrows the suite with.

`--changed` is the one part of `verify` that can be quietly wrong: a coverage table that
has gone stale narrows the run without saying so, which is the failure mode of every
hand-maintained list in this repo and the reason the import-boundary scan was derived in
P28. So the table is checked against the tree, and the fallback is checked too - when the
table does not know a package, the answer has to be "run everything".
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools.verify import COVERAGE, TYPED_PACKAGES, suites_for

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = sorted(
    p.name for p in ROOT.iterdir() if p.is_dir() and (p / "__init__.py").is_file()
    and p.name != "tests"
)


def test_every_package_the_coverage_table_names_exists() -> None:
    for package in COVERAGE:
        assert (ROOT / package / "__init__.py").is_file(), package


def test_every_suite_the_coverage_table_names_exists() -> None:
    for package, suites in COVERAGE.items():
        for suite in suites:
            assert (ROOT / suite).is_dir(), f"{package} -> {suite}"


def test_every_shipped_package_is_covered_or_runs_everything() -> None:
    """A package the table does not know is not a gap - it makes `--changed` run the
    whole suite. That is the safe direction, and this test says which packages take it,
    so the choice is visible rather than accidental."""
    uncovered = [p for p in SHIPPED if p not in COVERAGE]
    assert uncovered == ["harness", "privacy"] or not uncovered, uncovered
    for package in uncovered:
        assert suites_for([package]) == ["tests"], package


def test_an_unmapped_package_runs_the_whole_suite() -> None:
    assert suites_for(["something-nobody-mapped"]) == ["tests"]
    assert suites_for([]) == ["tests"]
    assert suites_for(["workers"]) == ["tests/p25"]
    assert suites_for(["ports", "workers"]) == ["tests/p03", "tests/p25", "tests/p28"]


def test_the_typed_package_list_is_every_package_that_ships() -> None:
    """mypy over a list that has gone stale is mypy over less than it looks like."""
    missing = [p for p in SHIPPED if p not in TYPED_PACKAGES]
    assert missing == [], missing
    for package in TYPED_PACKAGES:
        assert (ROOT / package / "__init__.py").is_file(), package


def test_verify_runs_and_reports_what_it_did_not_run() -> None:
    """The honesty the whole apparatus rests on: a verdict says what it covered.

    `--fast` so this stays a test of the reporting rather than a second full suite inside
    the first one.

    Two outcomes are legitimate and this accepts both. Green is the ordinary one. Red for
    stale state is correct when the tree is mid-edit, because the `state` step runs `gate
    render` and reports what it rewrote - asserting a clean exit here would make the test
    depend on when somebody happened to run it, which is exactly the flake this apparatus
    exists to catch. What is not negotiable is that the report says which happened.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "tools" / "verify.py"), "--fast"],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=900,
    )
    out = result.stdout
    for step in ("surfaces", "lint", "types", "blueprint", "state"):
        assert step in out, step
    assert "the suite did not run" in out
    assert "did not run: postgres, redis, container" in out

    if result.returncode == 0:
        assert "GREEN" in out
    else:
        assert "state was stale" in out, out[-3000:]
        assert "STATE WAS STALE" in out


def test_the_change_protocol_is_written_down() -> None:
    """A safety net nobody knows the shape of gets routed around the first time it is
    inconvenient."""
    changing = (ROOT / "CHANGING.md").read_text(encoding="utf-8")
    for named in (
        "tools/verify.py", "tools/surfaces.py", "gate amend", "BUILD/surfaces.json",
        "governance/README.md", ".env.example",
    ):
        assert named in changing, named
    for section in ("What protects you", "The surface snapshot", "Adding things"):
        assert section in changing, section
    assert "not automatically a bug" in changing
    assert "The reason recorded beside it is." in changing


@pytest.mark.parametrize("workflow", ["verify"])
def test_the_ci_workflow_runs_what_this_machine_cannot(workflow: str) -> None:
    """The container and Postgres halves are the two claims a laptop may not be able to
    make. CI is where they get made, so the file has to actually ask for them."""
    import yaml

    spec = yaml.safe_load((ROOT / ".github" / "workflows" / f"{workflow}.yml").read_text())
    assert set(spec["jobs"]) == {"verify", "container"}
    verify = spec["jobs"]["verify"]
    assert set(verify["services"]) == {"postgres", "redis"}
    steps = " ".join(str(s.get("run", "")) for s in verify["steps"])
    assert "--postgres" in steps and "--redis" in steps and "--repeat 2" in steps
    container = " ".join(str(s.get("run", "")) for s in spec["jobs"]["container"]["steps"])
    assert "--container" in container
