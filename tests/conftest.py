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
import sys
from pathlib import Path
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


@pytest.fixture(scope="session", autouse=True)
def synthetic_templates() -> None:
    """Build the synthetic model templates if they are not on disk.

    `templates/*.xlsx` is gitignored and .dockerignored, because the firm's real masters
    are its own and must never reach a git history or an image layer. The synthetic ones
    stand in for them, and they are generated from the input schemas in
    `templates/inputs/`, which *are* tracked - so this is a build step, not a download.

    Autouse and session-scoped because the alternative is every phase that touches a
    workbook carrying its own copy of this, and the failure without it is nineteen tests
    erroring with DELIVER.TEMPLATE_MISSING on a machine that has simply never run the
    tool. A clean clone, a container and a developer's laptop are the same case, and this
    is what makes them behave that way.
    """
    import subprocess

    root = Path(__file__).resolve().parents[1]
    schemas = sorted((root / "templates" / "inputs").glob("*.yaml"))
    assert schemas, "templates/inputs/ is tracked and should not be empty"

    import yaml

    missing = [
        name
        for name in (
            yaml.safe_load(schema.read_text(encoding="utf-8"))["template"] for schema in schemas
        )
        if not (root / "templates" / name).is_file()
    ]
    if not missing:
        return
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(root / "tools" / "synthesize_templates.py")],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (
        f"could not build the synthetic templates ({', '.join(missing)}):\n"
        f"{result.stdout}{result.stderr}"
    )


@pytest.fixture(scope="session", autouse=True)
def cleared_methodology() -> None:
    """Clear the repo's own methodology files, if this checkout has not cleared them.

    `foundations/cleared.yaml` is gitignored, like the templates and for a related
    reason: a clearance is a record of somebody at the firm having read a file, and
    shipping one in the repo would be recording a decision nobody made. So a clone has
    nothing cleared, which is the honest starting state and the one preflight reports.

    That leaves the suite needing the files cleared before anything can build a context.
    This does it through the real API rather than by writing the register directly, so
    every session actually runs both scanners over the three files the firm ships - if
    somebody adds a worked example with a real engagement id in it, the suite refuses to
    start rather than clearing it and moving on.
    """
    from registries.methodology import ClearanceRefused, MethodologyRegister

    register = MethodologyRegister()
    uncleared = [f for f in register.review() if not f.attachable]
    if not uncleared:
        return
    for path in register.files():
        try:
            register.clear(path, cleared_by="tests: the repo's own foundations")
        except ClearanceRefused as refused:  # pragma: no cover - the whole point is that
            raise AssertionError(  # this does not happen on the files the repo ships
                f"the repo's own methodology will not clear: {refused.diagnostic.detail}"
            ) from refused


@pytest.fixture(scope="session", autouse=True)
def registered_recipes() -> None:
    """Register the recipes the repo ships, if this checkout has not.

    `recipes/registered.yaml` is gitignored for the same reason `foundations/cleared.yaml`
    is: a registration records that somebody at the firm approved a workflow, and shipping
    one would be recording a decision nobody made. A clone has nothing registered and
    `load_recipe` refuses, which is the honest starting state.

    This writes to the register directly rather than through the board, and says so: a
    board decision needs a governance record and a content store, and a session fixture
    that built one would leave a firm's approval trail full of rows created by a test run.
    The approver name says what it is. The rule that only `governance/board.py` writes here
    is held over shipped code by a test in tests/p33, the same way the skill register's is
    - a fixture standing in for a firm's approvals is not the thing that rule is about.
    """
    from registries.recipes import RecipeRegister, digest_of_recipe

    register = RecipeRegister()
    missing = [p for p in register.files() if not register.is_registered(digest_of_recipe(p))]
    for path in missing:
        # A recipe the repo changed is a new version of it, never version 1 again - the
        # register refuses a second set of bytes under a registered version, correctly.
        registered = [r.version for r in register.registered() if r.name == path.stem]
        register.register(
            path,
            version=max(registered, default=0) + 1,
            approved_by="tests: the recipes the repo ships",
            decision_ref=f"test-suite/{path.stem}",
        )


@pytest.fixture(autouse=True)
def _the_suite_is_somebody(monkeypatch: pytest.MonkeyPatch) -> None:
    """Who the suite is, to the identity port.

    P36 made the name on a recorded change the one the system resolved rather than the one
    the caller sent, so a test that posts `who: "C. Smit"` has to actually be C. Smit. The
    local-user adapter answers with the operating-system user, and `AA_IDENTITY_NAME` is
    what a container or a test says instead - consulted only for a request that already
    came from this machine, so it is not a way to be somebody else anywhere it matters.

    Autouse because the alternative is every test that touches the surface remembering,
    and the one that forgets fails with a 403 that looks like a bug in the surface.
    """
    monkeypatch.setenv("AA_IDENTITY_NAME", "C. Smit")


def needs_a_checkout(what: str) -> None:
    """Skip when this is not a git checkout.

    Some tests ask git what is tracked, or read files the image deliberately does not
    ship - `.git` and `.github` are both in `.dockerignore`, because an image is the
    built thing rather than the repository that built it. Those questions are about the
    repository, they are answered on every developer machine and in CI, and inside a
    container the honest answer is that this is not the place to ask.

    A skip with a reason, never a silent pass: `pytest -q` prints an `s`, and the reason
    is one `-rs` away.
    """
    import shutil
    import subprocess

    root = Path(__file__).resolve().parents[1]
    if not shutil.which("git") or not (root / ".git").exists():
        pytest.skip(f"{what} needs a git checkout; this is not one")
    probe = subprocess.run(  # noqa: S603
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if probe.returncode != 0:
        pytest.skip(f"{what} needs a git checkout; git says this is not one")


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
