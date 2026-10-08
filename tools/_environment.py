"""What a tool says when it is run without the environment it needs.

Every command in `docs/USING.md` and `CLAUDE.md` is spelled `python tools/serve.py`, and
every one of them fails on a machine where nobody has activated the virtualenv:

    ModuleNotFoundError: No module named 'fastapi'

That is a traceback about somebody else's library, handed to a person who did exactly what
they were told. The answer is one prefix long - `python -m uv run python tools/serve.py` -
and nothing anywhere said so.

This is the same mistake as the phase checks written `python -m pytest` rather than
`python -m uv run pytest`, one layer further out. There it cost an evening of phases
reporting FAIL for suites that passed; here it is the first thing somebody meets on a new
machine, which is a worse place to put it.

A tool imports `needs` and names what it cannot run without. Nothing is re-executed and no
process is spawned: guessing at somebody's shell is how a tool ends up doing something
surprising, and the useful part is knowing what to type.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

__all__ = ["missing", "needs"]

ROOT = Path(__file__).resolve().parents[1]


def missing(modules: tuple[str, ...]) -> tuple[str, ...]:
    """Which of these are not importable here. Uses the finder rather than importing, so
    asking the question costs nothing and cannot half-import a package."""
    absent = []
    for name in modules:
        try:
            if importlib.util.find_spec(name) is None:
                absent.append(name)
        except (ImportError, ValueError):
            absent.append(name)
    return tuple(absent)


def needs(*modules: str, script: str | None = None) -> None:
    """Exit with the command to run, if this interpreter cannot import what is named.

    Called at the top of a tool a person runs directly. On the machine that has the
    environment - which is every machine running the suite, the gate or the rehearsals -
    this does nothing at all and costs one `find_spec` per module.
    """
    absent = missing(modules)
    if not absent:
        return

    where = script or Path(sys.argv[0]).name
    if not where.startswith("tools"):
        where = f"tools/{where}"
    argv = " ".join(sys.argv[1:])
    # The spelling that works on *this* machine. The documented one is `python -m uv run`,
    # which is right where uv was pip-installed and is nothing at all where the official
    # installer put a binary and no module - and this is the message somebody reads at the
    # exact moment a command has already refused them once. Telling them to type the other
    # thing that will also refuse is the worst available answer.
    prefix = "uv run" if shutil.which("uv") else "python -m uv run"
    sync = "uv sync" if shutil.which("uv") else "python -m uv sync"
    print(
        f"{where} needs {', '.join(absent)}, and this interpreter does not have "
        f"{'them' if len(absent) > 1 else 'it'}.\n"
        f"\n"
        f"  {sys.executable}\n"
        f"\n"
        f"This project's dependencies live in its own environment. Run it through uv:\n"
        f"\n"
        f"  {prefix} python {where}{' ' + argv if argv else ''}\n"
        f"\n"
        f"On Windows, start.cmd does the whole of setting up and starting for you.\n"
        f"If uv is not installed, install it once (https://docs.astral.sh/uv/ or\n"
        f"pip install uv), then {sync}.",
        file=sys.stderr,
    )
    raise SystemExit(2)
