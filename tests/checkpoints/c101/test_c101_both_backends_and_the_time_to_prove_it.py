"""Checkpoint C101 - both backends, and the time to prove it.

P176 fixed one check constraint and raised one bound. What a checkpoint can ask that the
phase could not is the question underneath both, and it is the same question: **this build
claims two backends and one of its checks had only ever run against one of them.**

The tell is in `ops/models.py` itself, and it is worth stating plainly because it is the
most instructive thing in the phase. The same portability question is asked twice in that
one class and was answered two different ways. The triggers that keep the precedent store
append-only are written per dialect - `_PRECEDENT_DECISION_EXISTS.format(true='1')` for
SQLite and `.format(true='true')` for Postgres - which is correct, and somebody clearly
understood that a boolean is not the same literal on both. The check constraint beside them
could not be parameterised the same way, being one entry in `__table_args__`, and so it got

    CheckConstraint("masked = 1 OR masked = true")

which is the same understanding expressed as a hope. Postgres rejects `boolean = integer`
while *planning* the CREATE TABLE, so the statement failed, so the table never existed, so
every one of the 65 store conformance tests failed against it - and the suite stayed green
for months because the Postgres half skips unless asked.

So this checkpoint does not look at one constraint. It takes **every statement
`create_all` would send to each backend** - tables, indexes, constraints, triggers,
functions, all of it, through a mock engine that needs no server - and asks of the whole
set what P176 asked of one line. That reaches the triggers, which the phase's own tests do
not, and it would have caught the defect from the other side: the precedent table simply
missing from what Postgres gets.

The second half is the bound, because a check that cannot finish is a check that does not
run. It is the same failure wearing a different face: thirty minutes of a job that needs
thirty-five is thirty-one days of red checks nobody can read, exactly as one backend of two
is a conformance suite nobody can trust.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import create_mock_engine

from ops.models import Base

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"

URLS = {"postgresql": "postgresql+psycopg://", "sqlite": "sqlite://"}


def everything_sent_to(backend: str) -> list[str]:
    """Every DDL statement `create_all` would send to this backend, in order.

    No server, no connection. A mock engine hands each statement to a callback instead of
    a socket, which is the only way to see the trigger and function DDL - that is attached
    to `after_create` events and so does not appear in any table's own compiled form.
    """
    sent: list[str] = []
    engine = create_mock_engine(
        URLS[backend],
        lambda sql, *args, **kw: sent.append(str(sql.compile(dialect=engine.dialect))),
    )
    Base.metadata.create_all(engine, checkfirst=False)
    return [" ".join(statement.split()) for statement in sent]


def boolean_columns() -> set[str]:
    return {
        column.name
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.type.__class__.__name__ == "Boolean"
    }


def test_nothing_sent_to_postgres_compares_a_boolean_to_a_number() -> None:
    """Asked of the whole of what Postgres gets, not of the check constraints.

    The same comparison on SQLite is correct and stays correct - `writes_precedent = 1` is
    what that backend's own trigger says, deliberately. The rule is not *never write 1*,
    it is *write what the backend you are talking to can parse*, which is why this is asked
    per backend rather than over the source.
    """
    booleans = boolean_columns()
    assert booleans, "no boolean column in the model; this test has stopped asking anything"

    offences = []
    for statement in everything_sent_to("postgresql"):
        for column in booleans:
            for found in re.finditer(rf"\b{re.escape(column)}\s*(?:=|<>|!=)\s*-?\d", statement):
                offences.append(f"{found.group(0)!r} in: {statement[:90]}")
    assert not offences, (
        "Postgres has no boolean = integer operator and will refuse the statement:\n  "
        + "\n  ".join(offences)
    )


def test_the_sqlite_trigger_still_says_1_because_that_is_its_answer() -> None:
    """The converse, so that the rule above cannot be satisfied by making every backend
    the same. These two backends are given different literals on purpose, and a later
    reader flattening them to one would break the backend that is working."""
    sqlite = " ".join(everything_sent_to("sqlite"))
    assert "writes_precedent = 1" in sqlite, (
        "the SQLite trigger no longer compares the flag the way SQLite compares booleans"
    )
    postgres = " ".join(everything_sent_to("postgresql"))
    assert "writes_precedent = true" in postgres, (
        "the Postgres trigger no longer compares the flag the way Postgres does"
    )


def test_the_guarantee_is_installed_on_both_backends() -> None:
    """*Only a human decision writes to the Precedent Store* is a non-negotiable, and it is
    enforced by DDL rather than by application code so that a psql prompt is refused too.
    A guarantee present on one backend of two is a guarantee that depends on the URL."""
    for backend in URLS:
        sent = " ".join(everything_sent_to(backend))
        assert "precedent_needs_decision" in sent, (
            f"{backend} is not sent the guard that refuses a precedent with no decision"
        )
        assert "PROCESS.PRECEDENT_NO_DECISION" in sent, (
            f"{backend}'s guard does not carry the code the rest of the build reports"
        )
        assert "PROCESS.APPEND_ONLY_VIOLATION" in sent, (
            f"{backend} is not sent the append-only guard"
        )


def test_the_job_that_proves_it_can_finish() -> None:
    """A check that cannot finish is a check that does not run, and reads as a failing test.

    This is the other half of the same defect: the conformance suite was green because
    nobody ran it, and the job that would have run it was cancelled at thirty minutes on
    every attempt. Held here as a join rather than as a number - the bound is compared
    against what the job's own command line asks for, and the flag it asks with has to be
    one `verify.py` actually parses, because a bound sized for a command that does not run
    is no better than the bound that was there.
    """
    # Guarded on the file this reads, not on `.git`. It used to call `needs_a_checkout`,
    # which asks whether there is a checkout - and in the image there is neither a checkout
    # nor a `.github`, so it skipped for the right reason by luck. They are two different
    # absences: a tarball with `git init` run in it has a checkout and no workflows, and
    # this failed there. Ask about the thing you are about to read.
    if not WORKFLOW.is_file():
        pytest.skip(".github is not shipped in the image; this is a question about the repo")
    yaml = pytest.importorskip("yaml")
    spec = yaml.safe_load(WORKFLOW.read_text())

    verify = spec["jobs"]["verify"]
    # The one step that runs verify.py, not every step in the job: `uv sync --frozen
    # --all-groups` is in there too, and sweeping the whole job put its flags into a
    # question about verify.py's argument parser.
    runs = [str(step.get("run", "")) for step in verify["steps"]]
    lines = [line for line in runs if "verify.py" in line]
    assert len(lines) == 1, f"expected one step to run verify.py, found {len(lines)}"
    said = lines[0]
    passes = int(said.split("--repeat", 1)[1].split()[0]) if "--repeat" in said else 1

    # 4m51s of gates and 15m01s a pass, measured on run 37717781284 and rounded up.
    needed = 5 + passes * 16
    assert verify["timeout-minutes"] >= needed, (
        f"{passes} passes of the suite is {needed} minutes of measured work inside a bound "
        f"of {verify['timeout-minutes']}; the job will be cancelled and the cancellation "
        f"will look like a failing test"
    )

    # Asked the way round that catches an invented flag. Checking that the three flags
    # named here are in verify.py passes happily while the job also passes a fourth that
    # argparse rejects - and argparse rejecting it is the job doing nothing in under a
    # second, which is a bound nobody will ever hit and a check that never ran.
    parser = (ROOT / "tools" / "verify.py").read_text()
    taken = set(re.findall(r'"(--[a-z-]+)"', parser))
    passed = {flag for flag in re.findall(r"(--[a-z-]+)", said)}
    assert passed, "the job no longer passes verify.py anything"
    assert passed <= taken, (
        f"the job passes {sorted(passed - taken)}, which verify.py does not take; argparse "
        f"will refuse the line and the job will fail in a second without running anything"
    )
    assert {"--postgres", "--redis", "--repeat"} <= passed, (
        f"the job no longer asks for the things only it can run: {sorted(passed)}"
    )
