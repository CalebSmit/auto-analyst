"""P178 - a measurement taken while the thing measured was broken.

P176 raised a bound from 30 to 60 minutes and was careful to write the measurement down
beside it, on the grounds that a bound with no measurement behind it is how the 30 got
there. The measurement was wrong by seven minutes, and wrong for a reason worth keeping:

**it was taken from a job that never finished.** A cancelled run leaves no step output -
the stdout is buffered and dies with it - so the figures came from the only trace that
survives, the Postgres container's own log, and were inferred from intervals between
marks in it. Two errors came out of that:

- *4m51s of gates* was the interval from step start to the first database contact, which
  is the five gates (32.3s) **plus four minutes of the first pass** before anything
  touched Postgres;
- *15m01s a pass* was timed while the 65 store conformance tests were failing in
  milliseconds against a table Postgres refused to create. Doing their actual work costs
  21 minutes.

So `GATES + 2 * ONE_PASS` came to 37 where the real figure is 43, and the guard written to
stop a bound being smaller than the work would have approved a 40-minute bound for a
42-minute job. The bound itself was never in danger, because the headroom P176 argued for -
explicitly on the grounds that the Postgres tests in that measurement were not really
running - absorbed all seven minutes. The reasoning was right and the arithmetic was not.

Run 37738346007 is the first in this repository's history in which Postgres, Redis and
every test actually executed, and it prints its own per-stage timings on success. That is
what the figures come from now.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"

# Which runs each job may not quote a timing from, because *that job* did not finish.
#
# Per job, not per run, which the first version of this got wrong and said so immediately.
# A run has two jobs and they fail independently: on 37717781284 the verify job was
# cancelled at thirty minutes - the measurement this phase is about - while the container
# job completed in 35m22s. So that run is a legitimate source for one bound and not the
# other, and a rule that banned the id outright was banning a real measurement.
CANNOT_BE_A_MEASUREMENT = {
    "verify": {
        "37717781284": "was cancelled at 30 minutes inside its second pass",
        "37729399616": "failed, and nothing printed its stage timings",
    },
    "container": {
        "37729399616": "failed on a test that read a path the image does not ship",
    },
}


def workflow_text() -> str:
    if not WORKFLOW.is_file():
        pytest.skip(".github is not shipped in the image; this is a question about the repo")
    return WORKFLOW.read_text()


def test_no_timing_is_attributed_to_a_run_that_did_not_finish() -> None:
    """The property, as a property: a figure is only a measurement if everything ran.

    Named runs rather than a general rule, because there is no way to ask GitHub offline
    whether a run finished - and the ones that must never be quoted again are the ones this
    build already mistook for measurements.
    """
    said = workflow_text()
    blocks = {
        "verify": said.split("  verify:", 1)[1].split("  container:", 1)[0],
        "container": said.split("  container:", 1)[1],
    }
    assert re.search(r"\b3\d{10}\b", said), (
        "no run is named, so no figure here can be checked by anybody"
    )

    wrong = []
    for job, block in blocks.items():
        quoted = set(re.findall(r"\b(3\d{10})\b", block))
        for run in sorted(quoted & set(CANNOT_BE_A_MEASUREMENT[job])):
            wrong.append(
                f"the {job} bound cites run {run}, whose {job} job "
                f"{CANNOT_BE_A_MEASUREMENT[job][run]} - its timings are not measurements"
            )
    assert not wrong, "\n".join(wrong)


def test_the_figures_in_the_file_are_the_figures_the_tests_hold_it_to() -> None:
    """One measurement, in three places, agreeing.

    The workflow comment, the constants in `tests/p176`, and the arithmetic in
    `tests/checkpoints/c101` all carried the same numbers, and when the numbers turned out
    wrong two of the three were corrected. A figure kept in three places is a figure that
    will disagree with itself; c101 imports p176's constants now, and this holds the file
    to them.
    """
    from tests.p176.test_a_bound_smaller_than_the_work import (
        GATES,
        MEASURED_ON,
        ONE_PASS,
    )

    said = workflow_text()
    assert MEASURED_ON in said, "the workflow does not name the run the constants come from"

    verify = said.split("  verify:", 1)[1].split("  container:", 1)[0]
    needed = GATES + 2 * ONE_PASS
    assert f"{needed} minutes" in verify, (
        f"the constants say {needed} minutes of work and the file does not say so"
    )

    bound = int(re.search(r"timeout-minutes: (\d+)", verify).group(1))
    assert bound >= needed, f"the bound is {bound} and the work is {needed}"

    # The headroom is stated rather than left for a reader to subtract, because the last
    # time this was wrong the headroom is the only thing that saved the job.
    assert f"{bound - needed} to spare" in verify, (
        f"the file does not say what the {bound - needed} minutes of headroom are for"
    )


def test_the_stage_timings_quoted_are_the_ones_the_step_prints() -> None:
    """A measurement is quotable only if somebody can find it again.

    `verify.py` prints a line per stage and a total; those are the figures in the comment,
    in the format the step prints them, so the next person can match them against a job log
    instead of trusting a paraphrase.
    """
    verify = workflow_text().split("  verify:", 1)[1].split("  container:", 1)[0]
    for printed in ("32.3s", "1253.9s", "1225.1s", "2511s"):
        assert printed in verify, (
            f"{printed} is one of the figures the verify step prints and the comment no "
            f"longer carries it, so the arithmetic cannot be checked against a log"
        )
