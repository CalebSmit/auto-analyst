#!/usr/bin/env python
"""Start, stop and check the local Postgres the conformance suite runs against.

The store is meant to be one URL away from Postgres, and the only thing that keeps that
true is running the suite against a real server. A check nobody can easily start is a
check that quietly stops being run, so this exists to make it one command:

    python tools/postgres.py start
    python -m uv run pytest tests/p04 -q --postgres

**No container and no Windows service.** The server is the portable binaries, extracted
into a folder, with its data directory beside them. It starts when asked and not before,
it needs no admin rights, and the whole thing deletes with one `rmdir`. That is
deliberate - see BUILD/AMENDMENTS.md on P28 for why Docker Desktop is not in this
project, and BUILD/LEDGER.md for why the binaries zip rather than winget.

The server holds nothing but test fixtures. `tests/p04/conftest.py` drops and recreates
every table around each test, and client data never enters this repo in any form.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Where `tools/postgres.py setup` puts it, and where this looks unless told otherwise.
DEFAULT_HOME = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "pgsql17"
HOME_VAR = "AA_PG_HOME"
PORT = 5432


def home() -> Path:
    return Path(os.environ.get(HOME_VAR) or DEFAULT_HOME)


def binary(name: str) -> str:
    """pg_ctl and friends, from the portable install or from PATH.

    PATH second rather than first: a machine with a system Postgres and a portable one
    should use the one this project set up, not whichever happens to be earlier in PATH.
    """
    suffix = ".exe" if sys.platform == "win32" else ""
    local = home() / "pgsql" / "bin" / f"{name}{suffix}"
    if local.is_file():
        return str(local)
    found = shutil.which(name)
    if found:
        return found
    sys.exit(
        f"no {name} found.\n"
        f"  Looked in {local}\n"
        f"  and on PATH.\n"
        f"Set {HOME_VAR} to a portable install, or see ops/README.md for how to make one."
    )


def data_dir() -> Path:
    return home() / "data"


def pg_ctl(*args: str) -> int:
    return subprocess.call([binary("pg_ctl"), "-D", str(data_dir()), *args])


def cmd_status() -> int:
    if not data_dir().is_dir():
        print(f"  no cluster at {data_dir()} - nothing has been initialised here.")
        return 1
    return pg_ctl("status")


def cmd_start() -> int:
    if not data_dir().is_dir():
        sys.exit(f"no cluster at {data_dir()}. See ops/README.md to create one.")
    log = home() / "server.log"
    code = pg_ctl("-l", str(log), "-o", f"-p {PORT}", "start")
    if code == 0:
        print(f"\n  Postgres is up on port {PORT}. Log: {log}")
        print("  python -m uv run pytest tests/p04 -q --postgres\n")
    return code


def cmd_stop() -> int:
    return pg_ctl("-m", "fast", "stop")


def cmd_check() -> int:
    """Start if needed, then run the half of the suite that needs a server."""
    if cmd_status() != 0:
        print("  starting it first...")
        if cmd_start() != 0:
            return 1
    # Asked rather than assumed, the same way `tools/gate.py::resolve` and
    # `tools/start.ps1` ask it: the official uv installer puts a binary on PATH and no
    # module in any interpreter, so `-m uv` is not a thing on a machine that followed the
    # documented install. And `pytest` through the interpreter rather than through the
    # generated launcher, which a Windows Application Control policy refuses to start.
    uv = [exe, "run"] if (exe := shutil.which("uv")) else [sys.executable, "-m", "uv", "run"]
    return subprocess.call(
        [*uv, "python", "-m", "pytest", "tests/p04", "-q", "--postgres"],
        cwd=Path(__file__).resolve().parents[1],
    )


COMMANDS = {
    "start": cmd_start,
    "stop": cmd_stop,
    "status": cmd_status,
    "check": cmd_check,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"The install lives at {DEFAULT_HOME} unless {HOME_VAR} says otherwise.\n"
            "It is not a service: it does not survive a reboot, and `start` is how it\n"
            "comes back. That is the point - nothing runs on this machine unasked."
        ),
    )
    parser.add_argument("command", choices=sorted(COMMANDS))
    return COMMANDS[parser.parse_args().command]()


if __name__ == "__main__":
    raise SystemExit(main())
