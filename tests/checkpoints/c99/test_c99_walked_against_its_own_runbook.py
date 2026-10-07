"""Checkpoint C99 - walked against its own runbook.

P174 corrected two sentences in `docs/WORK-LAPTOP.md` and changed what a machine with no
vault key prints. Those are three files that cannot see each other: the runbook is prose,
the checks are a registry, and the report is printed by `tools/serve.py`. A reader following
the runbook on a machine that has nothing is relying on all three agreeing, and nothing in
any of them notices when they stop.

What a checkpoint can ask that the phase could not: every command the runbook tells a new
machine to type is one that exists and parses, and every check it names is one preflight has,
under the label it quotes. The phase asked that of the one check it changed. This asks it of
all of them, and of the commands too - because the failure mode on a work laptop is not a
wrong sentence, it is a person at step one with nothing to do next.
"""

from __future__ import annotations

import inspect
import re
import shlex
from pathlib import Path

import pytest

from admin.preflight import CHECKS

ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = (ROOT / "docs" / "WORK-LAPTOP.md").read_text(encoding="utf-8")
FLAT = " ".join(RUNBOOK.split())


def commands() -> list[str]:
    """Every command the runbook gives, from a fenced block or from the prose.

    Both, because most of the commands a reader actually types are in a sentence rather than
    in a block - *`python -m uv run python tools/watch_run.py --once` says what it is doing*
    - and a sweep over the fences alone covers four of the eleven. The revert harness caught
    that: a tool renamed to one nobody wrote left this green.

    A `KEY=value` line is not a command. The `.env` block is fenced like one and is a file's
    contents, and treating it as a command is how a sweep comes to assert nothing about
    four of the lines it is counting.
    """
    found = []
    for block in re.findall(r"```\n(.*?)```", RUNBOOK, re.S):
        found += block.splitlines()
    # The fences come out before the prose is scanned, or their own backticks read as one
    # enormous inline span holding every line of the block joined together.
    prose = re.sub(r"```.*?```", "", RUNBOOK, flags=re.S)
    # A span may wrap across a line - a line break inside backticks is a space in Markdown -
    # so newlines are allowed inside one and flattened, but a blank line ends a paragraph
    # and cannot be inside a command.
    found += [
        " ".join(span.split())
        for span in re.findall(r"`([^`]+)`", prose, re.S)
        if "\n\n" not in span
    ]
    out = []
    for line in found:
        line = line.split("#")[0].strip().strip("`")
        if not line or re.fullmatch(r"[A-Z][A-Z0-9_]*=.*", line):
            continue
        if line.split()[0] in {"python", "git", "cd", "pytest"}:
            out.append(line)
    return sorted(set(out))


def test_the_runbook_has_commands_to_check_at_all() -> None:
    """A sweep that passes because the fences changed shape is a sweep that has stopped."""
    found = commands()
    assert len(found) >= 10, found
    assert any("watch_run" in c for c in found), (
        "the commands in the prose are not being collected, and most of them are in prose"
    )


@pytest.mark.parametrize("line", commands())
def test_every_command_the_runbook_gives_names_a_file_that_exists(line: str) -> None:
    """The runbook is the one document a work machine is read from on its first morning, and
    a command that names a tool nobody wrote is that morning over."""
    parts = shlex.split(line, posix=False)
    for n, word in enumerate(parts):
        if word.endswith(".py") and "/" in word:
            assert (ROOT / word).is_file(), f"{line!r} names {word}, which is not in the repo"
        if word == "-m" and n + 1 < len(parts) and parts[n + 1] not in {"uv"}:
            module = parts[n + 1].replace(".", "/")
            assert (ROOT / module).exists() or (ROOT / f"{module}.py").is_file(), (
                f"{line!r} runs -m {parts[n + 1]}, which is not a module here"
            )


@pytest.mark.parametrize("line", [c for c in commands() if "tools/" in c])
def test_every_tool_the_runbook_runs_carries_the_prefix_that_works(line: str) -> None:
    """P58's rule, re-asked over this document: without `python -m uv run` the project's
    dependencies are not on the path, and the command fails with an import error that says
    nothing about the real problem."""
    assert line.startswith("python -m uv run python tools/") or line.startswith("python tools/"), (
        line
    )
    if line.startswith("python tools/"):
        # The two in the install block run before `uv sync` has been explained, and the
        # runbook says so in the sentence under them.
        assert "uv sync" in RUNBOOK[: RUNBOOK.index(line)], (
            f"{line!r} runs without the prefix and nothing before it explains why"
        )


@pytest.mark.parametrize("name,label", CHECKS)
def test_every_check_the_runbook_quotes_is_still_the_registrys(name: str, label: str) -> None:
    """Both directions at once: a check the runbook names must exist, and a label it quotes
    must still be the words on the page."""
    if f"`{name}`" in RUNBOOK:
        assert " ".join(label.split()).lower() in FLAT.lower(), (
            f"the runbook names {name} and quotes a label preflight no longer uses"
        )


def test_the_runbook_names_no_check_preflight_does_not_have() -> None:
    known = {name for name, _ in CHECKS}
    quoted = set(re.findall(r"`([a-z][a-z_]{4,})`", RUNBOOK))
    # Only the words that look like a check name and are not something else the repo has.
    suspects = {
        word
        for word in quoted
        if word.endswith(("_answers", "_paths", "_present", "_cleared", "_approved"))
    }
    assert suspects <= known, (
        f"the runbook names checks preflight does not have: {sorted(suspects - known)}"
    )


def test_a_machine_with_no_vault_key_is_told_what_to_do_rather_than_what_broke() -> None:
    """The report, the registry's sentence and the runbook's warning, held together. This is
    the first thing a work laptop prints and the last place an exception class name belongs.
    """
    from tools.serve import _pool

    source = inspect.getsource(_pool)
    opening = source[source.index("open_vault(") : source.index("blobs = LocalContentStore()")]
    assert "__class__.__name__" not in opening, "it prints an exception class name again"
    assert "textwrap" in opening, "it prints the sentence on one line again"

    step_one = RUNBOOK[RUNBOOK.index("## 1. Clone and install") : RUNBOOK.index("## 2.")]
    quoted = re.search(r"\*(no run can be picked up yet[^*]*)\*", step_one)
    assert quoted, "step one no longer quotes what the machine prints"
    assert quoted.group(1).split(" - ")[0] in source, (
        "the runbook quotes a sentence the report does not print"
    )
