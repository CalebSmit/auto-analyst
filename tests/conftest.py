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


def postgres_url() -> str:
    return os.environ.get(PG_URL_VAR) or DEFAULT_PG_URL


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: pytest.Config) -> None:
    """Say what happened to the Postgres run, every time, whichever way it went."""
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
        write(f"POSTGRES RAN - {POSTGRES['ran']} store conformance test(s) against "
              f"{POSTGRES['url']}", green=True)
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
        f"  To run it: start a server and re-run with --postgres "
        f"({PG_URL_VAR} overrides the URL).",
        yellow=True,
    )
