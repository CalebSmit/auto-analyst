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
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# A line in a fenced block that invokes one of this project's tools.
INVOCATION = re.compile(r"^(?P<cmd>[a-z][^#\n]*?tools/[a-z_]+\.py[^#\n]*?)(?:\s+#.*)?$")

# The same invocation written inline, in backticks, in the middle of a sentence.
#
# Added after this check missed nine of them. `interview/PROTOCOL.md` opens by instructing
# the reader to run every command in it through uv and then writes `python
# tools/interview.py status` seven times without the prefix; `CLAUDE.md` does it twice
# more. Every one was invisible here, because this file read fenced blocks only - and
# `interview.py` needs PyYAML, so on a fresh clone each was the exact
# `ModuleNotFoundError` that P58 exists to prevent. A check that looks in one of the two
# places a command can be written has a blind spot the size of the other one.
INLINE = re.compile(r"`(?P<cmd>python[^`\n]*?tools/[a-z_]+\.py[^`\n]*?)`")

# Every page that tells somebody - or something - to run a command. The slash commands are
# here because they are read by a model that will *try* the line, rather than by a person
# who would notice it was wrong.
PAGES = (
    "docs/USING.md",
    "CLAUDE.md",
    "CHANGING.md",
    "interview/PROTOCOL.md",
    *sorted(
        str(q.relative_to(ROOT).as_posix())
        for q in (ROOT / ".claude" / "commands").glob("*.md")
    ),
)


def documented_commands(page: Path) -> list[str]:
    """Every invocation on a page, fenced or inline.

    Both, because both are read as instructions. A line in a fenced block is a line
    somebody copies; a line in backticks mid-sentence is a line somebody copies. The only
    difference was that this function used to see one of them.
    """
    found, inside = [], False
    text = page.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("```"):
            inside = not inside
            continue
        if inside and (match := INVOCATION.match(line.strip())):
            found.append(match.group("cmd").strip())
    found.extend(
        match.group("cmd").strip()
        for match in INLINE.finditer(text)
        if "..." not in match.group("cmd")  # the sentence stating the rule, not a command
    )
    return found



def needs_the_environment(tool: str) -> bool:
    """Whether a bare `python tools/<tool>` would fail on a machine nobody has set up.

    Derived, not listed. The original version of this check exempted `gate.py` by name,
    with a comment explaining that it has no dependencies beyond the standard library -
    which is the right reason and the wrong mechanism, because `verify.py` has exactly the
    same property and was being reported as an offence while `surfaces.py`, which does
    need the environment, was exempt from nothing and documented bare anyway.

    So: a tool is exempt when it imports nothing outside the standard library **anywhere
    in the file**, and nothing from this project except `tools._environment`. Anywhere
    matters: `serve.py` and `surfaces.py` have no third-party import at module level
    because they defer them into functions, and a check reading only the top of the file
    would call both of them dependency-free.
    """
    tree = ast.parse((ROOT / "tools" / tool).read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    project = {
        p.name for p in ROOT.iterdir() if p.is_dir() and (p / "__init__.py").is_file()
    } | {"tools"}
    outside = {r for r in roots if r not in sys.stdlib_module_names}
    # `tools` is this package itself; `tools._environment` is the module whose whole job
    # is saying what to type, and it imports nothing but the standard library.
    return bool((outside - {"tools"}) | (outside & project - {"tools"}))


def test_the_discriminator_tells_the_two_cases_apart() -> None:
    """A sanity check on the property, not a census of the tools.

    The first version of this asserted that exactly `gate.py` and `verify.py` need no
    environment, and that was wrong in both directions: several tools are stdlib-only
    because they are pure arithmetic, and a list of names would have had to be kept. What
    matters is that the property separates the two cases it exists to separate.
    """
    # Needs nothing: it runs the others, so it cannot need them.
    assert not needs_the_environment("gate.py")
    # Needs nothing: everything it runs, it runs through `python -m uv run` as a subprocess.
    assert not needs_the_environment("verify.py")
    # Needs the environment, and both defer their imports into functions - which is why
    # reading only the top of the file would have called them dependency-free.
    assert needs_the_environment("serve.py")
    assert needs_the_environment("surfaces.py")
    # Needs the environment at module level, which is the obvious case.
    assert needs_the_environment("interview.py")


def test_every_tool_that_needs_the_environment_says_so_when_it_does_not_have_it() -> None:
    """The other half of the same promise. A tool documented with the prefix is still run
    without it by somebody in a hurry, and `needs()` is the difference between the line to
    type and a traceback about PyYAML.

    Not every tool is a command somebody types - `_environment.py` is a helper and
    `postgres.py` is run by the suite - so the ones held to this are the ones a document
    tells a person to run.
    """
    told = {
        Path(part).name
        for page in PAGES
        for command in documented_commands(ROOT / page)
        for part in command.split()
        if part.startswith("tools/") and part.endswith(".py")
    }
    silent = [
        tool
        for tool in sorted(told)
        if needs_the_environment(tool)
        and "needs(" not in (ROOT / "tools" / tool).read_text(encoding="utf-8")
    ]
    assert not silent, (
        f"{silent} need the project environment and say nothing when they do not have "
        f"it. Add `needs(...)` so the message is the line to type."
    )

# ------------------------------------------------------- what the documents tell a person


@pytest.mark.parametrize("page", PAGES)
def test_every_documented_command_carries_the_environment_with_it(page: str) -> None:
    """`python tools/x.py` is only correct inside an activated shell, and the page is read
    by somebody who has just cloned. `gate.py` is the exception and says so itself: it has
    no dependencies beyond the standard library, which is why it can run the others."""
    commands = documented_commands(ROOT / page)
    if page.startswith(".claude/"):
        # A slash command legitimately runs nothing - `improve-agent` hands the whole
        # conversation to a protocol file. The prose pages below are documentation of
        # commands and an empty list there means the format has changed.
        pass
    else:
        assert commands, f"no tool invocations found in {page}; has the format changed?"

    wrong = [
        c
        for c in commands
        if c.startswith("python tools/")
        and needs_the_environment(Path(c.split()[1]).name)
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


# ------------------------------------------- and whether the line actually starts


def every_documented_tool() -> list[str]:
    """Every `tools/*.py` any document tells somebody to run, by filename."""
    return sorted(
        {
            Path(part).name
            for page in PAGES
            for command in documented_commands(ROOT / page)
            for part in command.split()
            if part.startswith("tools/") and part.endswith(".py")
        }
    )


@pytest.mark.parametrize("tool", every_documented_tool())
def test_a_documented_tool_gets_as_far_as_its_own_arguments(tool: str) -> None:
    """Run it. The whole of this file above asks whether a command is *spelled* right, and
    none of it asks whether it starts.

    That gap had a cost the same evening it was written. Adding `needs()` to six tools put
    `from tools._environment import needs` at the top of each - correct in four of them,
    and wrong in `simulate_files.py` and `bootstrap_scaffold.py`, which put `tools/` on the
    path rather than the repo so that they can import a sibling. Both raised
    `ModuleNotFoundError: No module named 'tools'` on their first line. The suite was
    green: `simulate_files` is a rehearsal the suite does not run, `bootstrap_scaffold` is
    run by hand, and every check above was satisfied by the *text* of the invocation.

    **And the first version of this test was green on the break too**, which is worth
    writing down because it is the defect this repository is named for. It ran the tool
    through `python -m uv run`, and `uv` is installed in the system interpreter rather than
    in the virtualenv - so under pytest the subprocess died with `No module named uv`,
    which contains neither "Traceback" nor "ModuleNotFoundError", and both assertions
    passed on a command that never started. Hence the return code: a tool that ran and
    printed its help exits 0, one that refused its arguments exits 2, and **1 is a
    traceback or a launcher that could not launch**. The interpreter running the suite is
    already the project's, so there is nothing to wrap it in.

    `--help` is the argument every one of them takes and none acts on, so this reaches the
    end of the imports and the top of `main` and stops.
    """
    done = subprocess.run(
        [sys.executable, f"tools/{tool}", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    said = done.stdout + done.stderr
    assert done.returncode in (0, 2), (
        f"tools/{tool} exited {done.returncode}. 0 is its help, 2 is it refusing "
        f"arguments, and anything else is a tool that did not start:\n{said[-1500:]}"
    )
    assert "Traceback" not in said, f"tools/{tool} does not start:\n{said[-1500:]}"
    assert said.strip(), f"tools/{tool} printed nothing at all for --help"


def test_that_check_covers_the_tools_that_broke() -> None:
    """A parametrised test over an empty list passes forever. These two are the ones the
    gap cost, so they are the ones named."""
    covered = every_documented_tool()
    assert "simulate_files.py" in covered
    assert "bootstrap_scaffold.py" in covered
    assert len(covered) >= 10, covered
