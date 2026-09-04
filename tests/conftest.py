"""Options shared by the whole suite.

Only one so far, and it exists because of a specific way test suites lie. The run store
is meant to be one URL away from Postgres, and the way that claim rots is that SQLite
passes, the Postgres case is marked skipped, `-q` prints a dot for it, and eighteen
months later somebody discovers the SQL was SQLite-only all along.

So `--postgres` is opt-in, and *not* running it is reported at the end of every run, in
words, with a count. A skip nobody reads is the same as no test.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

PG_URL_VAR = "AA_TEST_PG_URL"
DEFAULT_PG_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/analyst_test"

# Filled in by the store fixture in tests/p04/conftest.py. Module state rather than a
# fixture because the terminal summary runs after every fixture has been torn down.
POSTGRES: dict[str, Any] = {"requested": False, "ran": 0, "not_run": 0, "url": "", "error": ""}

# Adversarial fixtures whose target guard a later phase builds. Filled in by tests/p13;
# reported at the end of the session so "6 of 10 fire" never reads as "all 10 fire".
PENDING_FIXTURES: list[tuple[str, str, str]] = []

# The Redis + RQ queue adapter runs over an in-memory fake unless --redis is given, and
# the summary says which. Filled in by tests/p03/conftest.py.
REDIS_URL_VAR = "AA_TEST_REDIS_URL"
DEFAULT_REDIS_URL = "redis://localhost:6379/15"
REDIS: dict[str, Any] = {"requested": False, "fake": 0, "real": 0, "url": "", "error": ""}

# The container run. Opt in with --container on a machine that has an OCI runtime; the
# summary says which one, or says the image has never been built here.
RUNTIMES = ("podman", "docker", "nerdctl", "finch")
CONTAINER: dict[str, Any] = {"requested": False, "ran": 0, "not_run": 0, "runtime": ""}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--postgres",
        action="store_true",
        default=False,
        help=(
            "Run the store conformance suite against Postgres as well as SQLite. "
            "Requires a reachable server; the run fails rather than skips if there "
            f"is none. URL from {PG_URL_VAR}, default {DEFAULT_PG_URL}"
        ),
    )

    parser.addoption(
        "--redis",
        action="store_true",
        default=False,
        help=(
            "Run the queue conformance suite against a real Redis server rather than the "
            "in-memory fake; fails rather than skips if none answers. URL from "
            f"{REDIS_URL_VAR}, default {DEFAULT_REDIS_URL}"
        ),
    )


    parser.addoption(
        "--container",
        action="store_true",
        default=False,
        help=(
            "Build the image and run the suite inside it. Needs an OCI runtime - podman, "
            "docker, nerdctl or finch - and no step depends on Docker Desktop."
        ),
    )


def container_runtime_name() -> str:
    """The first OCI runtime on PATH, or empty. Any of them runs this image."""
    import shutil

    return next((r for r in RUNTIMES if shutil.which(r)), "")


def postgres_url() -> str:
    return os.environ.get(PG_URL_VAR) or DEFAULT_PG_URL


def redis_url() -> str:
    return os.environ.get(REDIS_URL_VAR) or DEFAULT_REDIS_URL


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: pytest.Config) -> None:
    """Say what happened to the Postgres run, every time, whichever way it went - and
    which adversarial fixtures are waiting on a guard that is not built yet."""
    if PENDING_FIXTURES:
        write = terminalreporter.write_line
        pending = sorted(set(PENDING_FIXTURES), key=lambda p: (p[2], p[0]))
        phases = sorted({built_by for _, _, built_by in pending})
        write("")
        write(
            f"GUARD FIXTURES PENDING - {len(pending)} of the blueprint's ten target "
            f"a guard not built yet ({', '.join(phases)}).",
            yellow=True,
            bold=True,
        )
        for fixture_id, guard, built_by in pending:
            write(f"  {fixture_id}: waits for {guard} ({built_by})", yellow=True)
    _redis_summary(terminalreporter)
    _container_summary(terminalreporter)
    if not POSTGRES["not_run"] and not POSTGRES["ran"] and not POSTGRES["error"]:
        return  # this invocation did not include the store conformance suite

    write = terminalreporter.write_line
    if POSTGRES["error"]:
        write("")
        write(
            f"POSTGRES UNREACHABLE - --postgres was given but no server answered at "
            f"{POSTGRES['url']}.",
            red=True,
            bold=True,
        )
        write(f"  {POSTGRES['error']}", red=True)
        write(
            "  Red rather than skipped on purpose: asking for a backend and being "
            "handed a green run that never touched it is the failure this guards.",
            red=True,
        )
        return

    if POSTGRES["ran"]:
        write("")
        write(
            f"POSTGRES RAN - {POSTGRES['ran']} store conformance test(s) against {POSTGRES['url']}",
            green=True,
        )
        return

    write("")
    write(
        f"POSTGRES NOT RUN - {POSTGRES['not_run']} store conformance test(s) did not "
        f"execute against Postgres.",
        yellow=True,
        bold=True,
    )
    write(
        "  SQLite passing is not evidence the Postgres path works. This suite is green "
        "on one backend of two.",
        yellow=True,
    )
    write(
        f"  To run it: start a server and re-run with --postgres ({PG_URL_VAR} overrides the URL).",
        yellow=True,
    )


def _redis_summary(terminalreporter: Any) -> None:
    """The same honesty for the queue adapter: say whether Redis was real or a fake."""
    write = terminalreporter.write_line
    if REDIS["error"]:
        write("")
        write(
            f"REDIS UNREACHABLE - --redis was given but no server answered at {REDIS['url']}.",
            red=True,
            bold=True,
        )
        write(f"  {REDIS['error']}", red=True)
        return
    if REDIS["real"]:
        write("")
        write(
            f"REDIS RAN - {REDIS['real']} queue adapter test(s) against {REDIS['url']}",
            green=True,
        )
        return
    if REDIS["fake"]:
        write("")
        write(
            f"REDIS FAKED - {REDIS['fake']} queue adapter test(s) ran the redis_rq adapter "
            f"over an in-memory fake, not a server.",
            yellow=True,
            bold=True,
        )
        write(
            f"  That proves the adapter's use of RQ, not Redis itself. To run it for real: "
            f"start a server and re-run with --redis ({REDIS_URL_VAR} overrides the URL).",
            yellow=True,
        )


@pytest.fixture
def container_runtime(request: pytest.FixtureRequest) -> str:
    """The runtime to build with, or a skip that is counted and reported.

    Asking for --container with no runtime installed is a failure rather than a skip: a
    run that was asked to prove the image builds and quietly proved nothing is worse
    than a red one.
    """
    if not request.config.getoption("--container"):
        CONTAINER["not_run"] += 1
        pytest.skip(
            "the container run is opt-in; re-run with --container (reported in the summary)"
        )
    runtime = container_runtime_name()
    if not runtime:
        pytest.fail(
            "--container was given but no OCI runtime is on PATH (looked for "
            f"{', '.join(RUNTIMES)}). Docker Desktop is not required - podman, nerdctl "
            "or Docker Engine all run this image."
        )
    CONTAINER["requested"] = True
    CONTAINER["runtime"] = runtime
    CONTAINER["ran"] += 1
    return runtime


def _container_summary(terminalreporter: Any) -> None:
    """Say whether the image was built, every time, whichever way it went."""
    write = terminalreporter.write_line
    if CONTAINER["ran"]:
        write("")
        write(
            f"CONTAINER RAN - the image was built with {CONTAINER['runtime']} and the "
            f"suite ran inside it.",
            green=True,
        )
        return
    if not CONTAINER["not_run"]:
        return  # this invocation did not include the portability suite
    write("")
    write(
        f"CONTAINER NOT BUILT - {CONTAINER['not_run']} test(s) did not build the image.",
        yellow=True,
        bold=True,
    )
    write(
        "  The Dockerfile and compose file are checked statically, which is not the same "
        "as knowing they build. 'It is portable' is a claim about a machine nobody has "
        "run it on until somebody does.",
        yellow=True,
    )
    found = container_runtime_name()
    write(
        f"  To run it: re-run with --container ({found} is on PATH)."
        if found
        else "  No OCI runtime is installed here. Install podman, nerdctl or Docker "
        "Engine - Docker Desktop is not required - then re-run with --container.",
        yellow=True,
    )
