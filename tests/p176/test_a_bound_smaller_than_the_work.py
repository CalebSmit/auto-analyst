"""P176 - a job given less time than the work it is asked to do.

The Postgres job was cancelled at exactly thirty minutes on every run it ever started,
which is the shape of a hang and was arithmetic. `verify.py --postgres --redis --repeat 2`
is five gates and then the whole suite *twice*, and the bound was written when the suite
was a fraction of its present size. Nothing noticed, because a timeout is reported as a
failed check with no failing test in it - the same red as a real defect, in a place where
nobody looks for a measurement.

The measurement is real and is named here with where it came from, because a bound with no
measurement behind it is the thing that was already there. Run 37717781284 of 2026-10-08
left it in the Postgres container's own log, which GitHub dumps at `Stop containers` and
which therefore survives a cancellation when the step's own buffered stdout does not:

    first database contact      02:30:43   step started 02:25:52   ->  gates 4m51s
    a mark in pass 1            02:35:43   the same mark in pass 2 02:50:44  ->  15m01s
    the next mark in pass 1     02:37:08   the same mark in pass 2 02:52:10  ->  15m02s

So one pass of the suite is 15m01s and the gates ahead of it are 4m51s. These are rounded
*up* to whole minutes below, because a bound is a ceiling and rounding a ceiling down is
how this happened.

What this holds is not the number 60. It is that each job's bound covers the work that
job's own run lines ask for - so asking for a third pass of the suite, or adding a service
to start, goes red here rather than at minute thirty of a run somebody is waiting on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"

# Minutes, rounded up, from the run named in the docstring.
GATES = 5  # 4m51s: surfaces, lint, types, blueprint, state
ONE_PASS = 16  # 15m01s: the whole suite once, against Postgres and Redis
IMAGE = 36  # 35m22s: build the image and run the container half inside it

# A hung job should still be killed, so a bound is required and may not be enormous.
CEILING = 120


def spec() -> dict:
    yaml = pytest.importorskip("yaml")
    if not WORKFLOW.is_file():
        pytest.skip(".github is not shipped in the image; this is a question about the repo")
    return yaml.safe_load(WORKFLOW.read_text())


def runs(job: dict) -> str:
    return " ".join(str(step.get("run", "")) for step in job["steps"])


def passes_asked_for(job: dict) -> int:
    """How many times this job's own command line says to run the suite."""
    said = runs(job)
    if "verify.py" not in said:
        return 0
    after = said.split("--repeat", 1)
    if len(after) == 1:
        return 1
    return int(after[1].split()[0])


def test_every_job_declares_a_bound() -> None:
    """GitHub's default is six hours. A job that hangs with no bound is six hours of
    somebody's money, and this build has had two jobs hang."""
    for name, job in spec()["jobs"].items():
        assert "timeout-minutes" in job, f"{name} has no bound, so its bound is six hours"
        assert 0 < job["timeout-minutes"] <= CEILING, (
            f"{name} is bounded at {job['timeout-minutes']} minutes, which is not a bound"
        )


def test_the_suite_job_has_room_for_every_pass_it_asks_for() -> None:
    """The defect itself, as a property: the bound is compared against what the run line
    says, so the two cannot drift apart again."""
    verify = spec()["jobs"]["verify"]
    asked = passes_asked_for(verify)
    assert asked >= 2, f"this job used to run the suite twice and now asks for {asked}"
    needed = GATES + asked * ONE_PASS
    assert verify["timeout-minutes"] >= needed, (
        f"the job runs {asked} passes of the suite after {GATES} minutes of gates, which "
        f"is {needed} minutes of measured work, inside a bound of "
        f"{verify['timeout-minutes']}. It will be cancelled, and the cancellation will "
        f"look like a failing test."
    )


def test_the_image_job_has_room_for_the_build() -> None:
    """Its bound was never wrong, and it is here so that lowering it is caught by the same
    rule rather than by a cancelled run."""
    container = spec()["jobs"]["container"]
    assert container["timeout-minutes"] >= IMAGE, (
        f"building the image and running the container half measured {IMAGE} minutes, "
        f"inside a bound of {container['timeout-minutes']}"
    )


def test_the_measurement_is_written_down_beside_the_bound() -> None:
    """A number with no measurement behind it is what was there before. The run id is the
    part that matters: it is how the next person checks the arithmetic instead of adding
    ten minutes and pushing again.

    *Beside* is load-bearing and was wrong on the first attempt. Asking whether the file
    mentions the run stayed green when the measurement was taken off the job it belongs to,
    because the other job's bound cites the same run - so the question has to be asked of
    each job's own lines. The revert harness said so.
    """
    said = WORKFLOW.read_text()
    jobs = {
        "verify": said.split("  verify:", 1)[1].split("  container:", 1)[0],
        "container": said.split("  container:", 1)[1],
    }
    for name, block in jobs.items():
        assert "37717781284" in block, (
            f"{name}'s bound does not name the run it was measured from"
        )
    for figure in ("4m51", "15m01", "34m53"):
        assert figure in jobs["verify"], f"the arithmetic no longer states {figure}"
    assert "35m22" in jobs["container"], "the image build's measurement is gone"
