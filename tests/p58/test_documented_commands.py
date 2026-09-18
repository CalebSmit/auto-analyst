"""The commands the documentation gives, run the way the documentation gives them.

Every `python tools/...` line in `docs/USING.md` and `CLAUDE.md` failed on a machine where
nobody had activated the virtualenv:

    ModuleNotFoundError: No module named 'fastapi'

A traceback about somebody else's library, handed to a person who did exactly what they
were told, five hundred lines into a file they were not reading. It is invisible from a
shell that already has the environment, which is every shell this was ever developed in -
and it is the first thing a clone on the work machine meets.

Found by running the rehearsal exactly as CLAUDE.md documents it. The same class of mistake
as the four phase checks written `python -m pytest` rather than `python -m uv run pytest`,
one layer further out, where a person rather than the gate is the one being misled.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# A line in a fenced block that invokes one of this project's tools.
INVOCATION = re.compile(r"^(?P<cmd>[a-z][^#\n]*?tools/[a-z_]+\.py[^#\n]*?)(?:\s+#.*)?$")


def documented_commands(page: Path) -> list[str]:
    found, inside = [], False
    for line in page.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            inside = not inside
            continue
        if not inside:
            continue
        match = INVOCATION.match(line.strip())
        if match:
            found.append(match.group("cmd").strip())
    return found


# ------------------------------------------------------- what the documents tell a person


@pytest.mark.parametrize("page", ["docs/USING.md", "CLAUDE.md"])
def test_every_documented_command_carries_the_environment_with_it(page: str) -> None:
    """`python tools/x.py` is only correct inside an activated shell, and the page is read
    by somebody who has just cloned. `gate.py` is the exception and says so itself: it has
    no dependencies beyond the standard library, which is why it can run the others."""
    commands = documented_commands(ROOT / page)
    assert commands, f"no tool invocations found in {page}; has the format changed?"

    wrong = [
        c
        for c in commands
        if c.startswith("python tools/") and not c.startswith("python tools/gate.py")
    ]
    assert not wrong, (
        f"{page} tells a person to run a command that fails outside an activated shell: "
        f"{wrong}. Use `python -m uv run python tools/...`."
    )


# ----------------------------------------------------------- and what happens if they do


@pytest.mark.parametrize("tool", ["serve.py", "simulate_firm.py"])
def test_the_tools_a_person_runs_ask_before_they_work(tool: str) -> None:
    """Each of these checks its environment as the first thing `main` does.

    Asserted structurally rather than by launching an interpreter without the project on
    its path: which interpreter that is differs by machine, and a test that had to find one
    would be testing the machine. The behaviour of `needs` itself is proved below, by
    calling it; this is the wiring, and the wiring is what was missing.
    """
    tree = ast.parse((ROOT / "tools" / tool).read_text(encoding="utf-8"))
    main = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main"), None
    )
    assert main is not None, f"{tool} has no main()"

    first = main.body[0]
    called = (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Call)
        and isinstance(first.value.func, ast.Name)
        and first.value.func.id == "needs"
    )
    assert called, (
        f"{tool} does something before checking it can: whatever it imports on the way "
        f"there raises first, and the person gets that traceback instead of the answer"
    )
    named = {a.value for a in first.value.args if isinstance(a, ast.Constant)}
    assert named, f"{tool} calls needs() without naming anything"


def test_the_explanation_names_the_command_rather_than_describing_it() -> None:
    """A message that said "install the dependencies" would be true and useless. What a
    person needs is the line to type, with their own arguments still on it."""
    from tools._environment import needs

    with pytest.raises(SystemExit) as left:
        needs("a_module_that_is_not_installed_anywhere", script="tools/serve.py")
    assert left.value.code == 2

    import io
    from contextlib import redirect_stderr

    buffer = io.StringIO()
    with redirect_stderr(buffer), pytest.raises(SystemExit):
        needs("a_module_that_is_not_installed_anywhere", script="tools/serve.py")
    said = buffer.getvalue()
    assert "python -m uv run python tools/serve.py" in said
    assert "start.cmd" in said, "the Windows path a person is most likely on"
    assert "pip install uv" in said, "and what to do if uv itself is missing"


def test_it_costs_nothing_when_the_environment_is_there() -> None:
    """This runs at the top of every invocation of these tools, including inside the gate
    and both rehearsals. It must be silent and cheap when there is nothing wrong."""
    from tools._environment import missing, needs

    assert missing(("sys", "json", "pathlib")) == ()
    needs("sys", "json", script="tools/serve.py")  # returns, raises nothing
