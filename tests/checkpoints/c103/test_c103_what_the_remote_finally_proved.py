"""Checkpoint C103 - what the remote finally proved.

Four phases, and the thread through them is a single sentence: **a claim nobody has
executed is not evidence, and a check that cannot run where it is pointed never executes
it.** Each phase found one way that goes wrong, and each one had been in the repository
for weeks or months, passing.

- P176: `precedent` carried `CheckConstraint("masked = 1 OR masked = true")`, so the table
  could not be created on Postgres at all. The store conformance suite had been printing
  *this suite is green on one backend of two* on every run since P04, to nobody.
- P176 again: the job that would have found it was cancelled at thirty minutes on every
  attempt, because the bound predated most of the suite. A timeout is a red check with no
  failing test in it, which is the one shape nobody reads as a measurement.
- P177: a generated file carried the clock, so every green commit went red the next
  morning; the first step of the verifier asked an approval gate about bytes on disk, so no
  clone could reach the second; a test asserted what one platform's mime table knows; and a
  test read a path the image does not ship without asking whether it was there.
- P178: the measurement that fixed the bound was itself taken from a job that never
  finished, and understated the work by seven minutes.

What a checkpoint can ask that none of them could is whether the **reporting** is now
honest, because every one of these defects survived by being reported in a way that read as
fine. The suite says what it did not run, in words, with counts; `verify.py` says which of
its stages ran; the container assertion names the test that failed inside the image. Those
three sentences are the only reason any of this was found, and they are what this holds.

It deliberately does not assert that Postgres ran here. On a developer machine it has not,
and a checkpoint that demanded it would be a checkpoint that only passes in CI - which is
the mistake four phases just finished fixing. It asserts that the machine *says so*.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import needs_a_checkout

ROOT = Path(__file__).resolve().parents[3]


def test_the_suite_says_what_it_did_not_run_with_a_count() -> None:
    """The sentence that found the whole block, held to still being printed.

    `POSTGRES NOT RUN - 65 store conformance test(s) did not execute against Postgres` is
    what made the Postgres path worth chasing at all. It has to carry a **count**, because
    *not run* with no number attached is a sentence a reader's eye slides off, and it has to
    name what would make it run.
    """
    # The three suites that populate the tallies: the store conformance suite, the queue
    # adapter and the portability tests. Any other target reports nothing about them -
    # correctly, and the first version of this asked `tests/p01` and got an empty answer.
    done = subprocess.run(  # noqa: S603
        [
            sys.executable, "-m", "pytest",
            "tests/p04", "tests/p03", "tests/p28",
            "-q", "-p", "no:cacheprovider",
        ],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=1800,
    )
    said = done.stdout + done.stderr

    for backend in ("POSTGRES", "REDIS", "CONTAINER"):
        assert backend in said, f"the summary no longer mentions {backend} at all"

    # Whichever way round each one went, it has to be stated with a number.
    for pattern in (
        r"POSTGRES (NOT RUN|RAN) - \d+ store conformance test",
        r"REDIS (FAKED|RAN) - \d+ queue adapter test",
        r"CONTAINER (NOT BUILT|RAN)",
    ):
        assert re.search(pattern, said), (
            f"nothing in the summary matches {pattern!r}, so a reader cannot tell what ran"
        )

    if "POSTGRES NOT RUN" in said:
        assert "--postgres" in said, "it does not say what would make it run"
        # Both halves of the claim, because the phrase and the reasoning are separable and
        # the revert harness proved it: blunting *is not evidence the Postgres path works*
        # into something agreeable left this green while `one backend of two` survived.
        assert "one backend of two" in said, (
            "it no longer says how much of the store the suite covered"
        )
        assert "is not evidence the Postgres path works" in said, (
            "it no longer says what passing on SQLite alone fails to prove, which is the "
            "whole content of the sentence"
        )


def test_the_verifier_says_which_of_its_stages_ran() -> None:
    """`verify.py`'s own report, which is where the timing measurement comes from now.

    P178 took its figures from the per-stage lines this prints. A report that stopped
    printing them would leave the next bound to be guessed, which is where the thirty
    minutes came from.
    """
    needs_a_checkout("the verification command")
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "tools" / "verify.py"), "--fast"],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=900,
    )
    said = done.stdout
    for stage in ("surfaces", "lint", "types", "blueprint", "state"):
        assert stage in said, stage
    assert re.search(r"(GREEN|RED)", said), "the report reaches no verdict"
    assert re.search(r"\d+\.\d+s|\d+s", said), (
        "no stage reports how long it took, so a bound cannot be measured from this"
    )
    # The list, not the phrase. `did not run` also appears in `--fast: the suite did not
    # run.`, so asking for the words left this green with the names deleted - which is the
    # part that matters, because `did not run: postgres, redis, container` is the sentence
    # that went unread for a month and started all of this.
    named = re.search(r"did not run: ([a-z, ]+)\.", said)
    assert named, (
        "the report no longer names which of the opt-in halves it skipped; `did not run` "
        "on its own is the --fast line and says nothing about postgres, redis or container"
    )
    assert named.group(1).strip(), "it says it skipped something and does not say what"


def test_a_failure_inside_the_image_names_the_test_that_failed() -> None:
    """The fix that made the fourth defect readable, held over the helper itself.

    The image reported `1 failed, 5097 passed` through an assertion printing the last 8,000
    characters of the run - which are its skip list - so the failure could not name itself
    and had to be deduced from the diff. Both container assertions go through one helper
    now, and it leads with what pytest already prints for the purpose.
    """
    from tests.conftest import what_failed_inside

    stdout = (
        "FAILED tests/pNN/test_something.py::test_the_thing - FileNotFoundError: x\n"
        "1 failed, 5097 passed, 307 skipped in 1005.15s\n"
        + "SKIPPED [15] tests/conftest.py:181: needs a git checkout\n" * 400
    )
    said = what_failed_inside(stdout, "")
    assert "test_the_thing" in said
    assert said.index("test_the_thing") < said.index("SKIPPED")

    # And both callers use it, because the one that does not is the one that will fail.
    for rel in (
        "tests/p28/test_portability.py",
        "tests/checkpoints/c10/test_c10_v1_portable_and_handed_off.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "what_failed_inside(run.stdout, run.stderr)" in text, rel
        assert "run.stdout[-8000:]" not in text, f"{rel} is back to printing the tail"


@pytest.mark.parametrize(
    "claim",
    [
        "the schema is the same schema on both backends",
        "the bound comes from a run where nothing was skipped",
        "nothing generated carries the day it was generated",
        "the surface collector needs no approval register",
        "a read of what the image lacks asks about that path",
    ],
)
def test_each_phase_in_the_block_has_a_test_that_fails_without_its_fix(claim: str) -> None:
    """A roll-call, deliberately: the five properties this block rests on, each pointed at
    the suite that holds it. It is here so that deleting one of those suites is a failure in
    the checkpoint rather than a quiet reduction in what is checked."""
    holders = {
        "the schema is the same schema on both backends": "tests/p176",
        "the bound comes from a run where nothing was skipped": "tests/p178",
        "nothing generated carries the day it was generated": "tests/p177",
        "the surface collector needs no approval register": "tests/p177",
        "a read of what the image lacks asks about that path": "tests/p177",
    }
    suite = ROOT / holders[claim]
    assert suite.is_dir(), f"{holders[claim]} is gone and nothing holds: {claim}"
    tests = [
        node
        for path in suite.rglob("test_*.py")
        for node in __import__("ast").walk(__import__("ast").parse(path.read_text("utf-8")))
        if isinstance(node, __import__("ast").FunctionDef) and node.name.startswith("test_")
    ]
    assert len(tests) >= 3, f"{holders[claim]} has {len(tests)} tests; it has been hollowed"
