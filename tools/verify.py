"""One command that runs everything that has to be true, and says what it did not run.

The gate answers "is this phase done". This answers a different question, and the one
that matters every time somebody changes something afterwards: **is the whole thing still
correct**. Seven checks, in the order that fails fastest:

    1. surfaces      has a public surface moved without anybody deciding it should
    2. lint          ruff over the tree
    3. types         mypy over every shipped package
    4. blueprint     is graph/architecture.json the export of the current blueprint
    5. state         does `gate render` change anything, i.e. is BUILD/ stale
    6. tests         the whole suite
    7. flake         the suite again, if --repeat asks, to catch order and timing luck

What it will not do is pretend. The Postgres, Redis and container runs are opt-in because
they need something this machine may not have, and the summary says in words which of
them did not happen. A green verdict here means "green on what ran", and the report says
what that was.

**One step writes.** `state` runs `gate render`, which rewrites `BUILD/PLAN.md`,
`BUILD/STATE.md` and the phase files from the plan. That is idempotent, and anything it
changes was already owed - but it means this command is not read-only, and stale state is
reported as red rather than as a green run with a failing exit code.

    python tools/verify.py                  # everything that can run here
    python tools/verify.py --fast           # skip the suite: lint, types, surfaces, freshness
    python tools/verify.py --repeat 2       # run the suite twice; a flake fails the run
    python tools/verify.py --postgres --redis --container    # the opt-in halves too
    python tools/verify.py --changed        # only the suites a change could have touched
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Every package mypy is run over. The same list the phase checks use, in one place.
TYPED_PACKAGES = [
    "admin", "deliver", "evals", "governance", "graph", "guards", "harness", "intake",
    "ops", "orchestrate", "ports", "precedent", "privacy", "registries", "report",
    "review", "tools", "ui", "workers",
]

# Which test suites cover which package, for --changed. A package with no entry runs the
# whole suite, deliberately: guessing narrowly is how a regression gets missed, so the
# default when this table does not know is to run everything.
COVERAGE: dict[str, tuple[str, ...]] = {
    "ports": ("tests/p03", "tests/p28"),
    "registries": ("tests/p02", "tests/p05", "tests/p14", "tests/regression"),
    "graph": ("tests/p06", "tests/p07", "tests/p08", "tests/p26"),
    "harness": ("tests/p09", "tests/p10", "tests/p11", "tests/p12", "tests/p14"),
    "privacy": ("tests/p12", "tests/p13"),
    "guards": ("tests/p13", "tests/p14"),
    "review": ("tests/p15",),
    "intake": ("tests/p16", "tests/p17", "tests/p24", "tests/p95", "tests/p96"),
    "deliver": ("tests/p21",),
    "evals": ("tests/p22", "tests/p27"),
    "ops": ("tests/p04", "tests/p23", "tests/p25"),
    "admin": ("tests/p24",),
    "workers": ("tests/p25",),
    "orchestrate": ("tests/p26",),
    "governance": ("tests/p27",),
    "precedent": ("tests/p19",),
    "report": ("tests/p91", "tests/p92"),
    "tools": ("tests/p01", "tests/p22", "tests/regression"),
    # The three pages share one design language, and the tests that hold each page to
    # the data it renders live beside the front door.
    "ui": ("tests/p23", "tests/p24", "tests/regression"),
}


@dataclass
class Step:
    name: str
    why: str
    command: list[str]
    optional: bool = False


@dataclass
class Result:
    step: Step
    code: int
    seconds: float
    output: str = field(repr=False, default="")

    @property
    def ok(self) -> bool:
        return self.code == 0


def run(step: Step, *, verbose: bool) -> Result:
    started = time.monotonic()
    print(f"  {step.name:<11} {step.why}")
    completed = subprocess.run(  # noqa: S603 - commands are built here, not passed in
        step.command,
        cwd=ROOT,
        capture_output=not verbose,
        text=True,
        check=False,
    )
    seconds = time.monotonic() - started
    output = "" if verbose else (completed.stdout or "") + (completed.stderr or "")
    mark = "ok  " if completed.returncode == 0 else "FAIL"
    print(f"  {'':<11} {mark} {seconds:5.1f}s")
    return Result(step, completed.returncode, seconds, output)


def changed_packages() -> list[str]:
    """Top-level packages with uncommitted or newly committed changes."""
    diff = subprocess.run(  # noqa: S603
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout
    found: set[str] = set()
    for line in diff.splitlines():
        path = line[3:].strip().strip('"')
        top = path.split("/")[0]
        if (ROOT / top / "__init__.py").is_file():
            found.add(top)
    return sorted(found)


def suites_for(packages: list[str]) -> list[str]:
    """The suites that cover those packages, or everything if any of them is unmapped."""
    if not packages:
        return ["tests"]
    suites: set[str] = set()
    for package in packages:
        if package not in COVERAGE:
            return ["tests"]
        suites.update(COVERAGE[package])
    return sorted(suites)


def build_steps(args: argparse.Namespace) -> list[Step]:
    # `python -m uv run`, with the python on PATH rather than sys.executable: under uv,
    # sys.executable is the virtualenv, which carries the project's dependencies but not
    # uv. This is the same invocation every phase check and the README use.
    uv = ["python", "-m", "uv", "run"]
    pytest_flags = ["-q", "-p", "no:cacheprovider"]
    for flag in ("postgres", "redis", "container"):
        if getattr(args, flag):
            pytest_flags.append(f"--{flag}")

    targets = ["tests"]
    if args.changed:
        packages = changed_packages()
        targets = suites_for(packages)
        print(f"  changed:    {', '.join(packages) or 'nothing tracked'} -> {' '.join(targets)}")

    steps = [
        Step(
            "surfaces",
            "has a public surface moved without a decision",
            [*uv, "python", str(ROOT / "tools" / "surfaces.py"), "--check"],
        ),
        Step("lint", "ruff over the tree", [*uv, "ruff", "check", "."]),
        Step("types", "mypy over every shipped package", [*uv, "mypy", *TYPED_PACKAGES]),
        Step(
            "blueprint",
            "is the exported graph the current blueprint",
            [*uv, "python", str(ROOT / "tools" / "export_architecture.py"), "--check"],
        ),
        Step(
            "state",
            "are BUILD/PLAN.md and STATE.md what the plan renders to",
            ["python", str(ROOT / "tools" / "gate.py"), "render"],
        ),
    ]
    if not args.fast:
        steps.append(Step("tests", f"the suite: {' '.join(targets)}",
                          [*uv, "python", "-m", "pytest", *pytest_flags, *targets]))
        for n in range(args.repeat - 1):
            steps.append(
                Step(
                    "flake",
                    f"the suite again ({n + 2} of {args.repeat}): order and timing luck",
                    [*uv, "python", "-m", "pytest", *pytest_flags, *targets],
                )
            )
    return steps


def state_is_dirty() -> list[str]:
    """Which generated files `gate render` just changed. Stale state is a real finding:
    it means the plan and what the repo says about it had drifted apart."""
    changed = subprocess.run(  # noqa: S603
        ["git", "status", "--porcelain", "BUILD/"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    ).stdout
    return [line[3:].strip() for line in changed.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fast", action="store_true", help="skip the test suite")
    parser.add_argument("--changed", action="store_true", help="only the suites a change touched")
    parser.add_argument("--repeat", type=int, default=1, help="run the suite N times")
    parser.add_argument("--postgres", action="store_true", help="also run against Postgres")
    parser.add_argument("--redis", action="store_true", help="also run against a real Redis")
    parser.add_argument("--container", action="store_true", help="also build the image")
    parser.add_argument("-v", "--verbose", action="store_true", help="stream each command")
    args = parser.parse_args(argv)

    before = state_is_dirty()
    print("\n  Verifying the whole build.\n")
    results = [run(step, verbose=args.verbose) for step in build_steps(args)]

    print()
    failed = [r for r in results if not r.ok]
    for result in failed:
        print(f"  ---- {result.step.name} failed " + "-" * 46)
        tail = result.output.strip().splitlines()[-25:]
        print("\n".join(f"  {line}" for line in tail) or "  (no output)")
        print()

    # `gate render` writes; if it wrote something that was not already dirty, the state
    # files were stale, which rule 5 exists to prevent.
    now_dirty = [p for p in state_is_dirty() if p not in before]
    if now_dirty:
        print(f"  STATE WAS STALE - render rewrote {', '.join(now_dirty)}.")
        print("  Commit them: BUILD/ is generated, and a stale copy is a plan that")
        print("  disagrees with itself.\n")

    total = sum(r.seconds for r in results)
    skipped = [
        name
        for name, asked in (("postgres", args.postgres), ("redis", args.redis),
                            ("container", args.container))
        if not asked
    ]
    # Stale state is a red verdict, not a green one with a failing exit code. A report
    # that says GREEN and then returns 1 is a report nobody will trust twice.
    red = bool(failed or now_dirty)
    if red:
        reasons = [r.step.name for r in failed] + (["state was stale"] if now_dirty else [])
        print(f"  RED - {len(reasons)} problem(s) in {total:.0f}s: {', '.join(reasons)}")
        print(f"        {len(results) - len(failed)} of {len(results)} checks passed.")
    else:
        print(f"  GREEN - {len(results)} checks in {total:.0f}s.")

    # What did not run is reported either way. It is most needed on a red run, where the
    # temptation is to read the failure and stop: a verdict that only admits its coverage
    # when everything passed is a verdict that hides its coverage exactly when somebody is
    # deciding what to do next.
    indent = "        " if red else "          "
    if args.fast:
        print(f"{indent}--fast: the suite did not run.")
    if skipped:
        print(f"{indent}did not run: {', '.join(skipped)}. This is green on")
        print(f"{indent}what ran; each of those needs something this machine may not have.")
    print()
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
