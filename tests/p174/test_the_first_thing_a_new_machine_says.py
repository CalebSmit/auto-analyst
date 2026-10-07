"""P174 - the first thing a new machine says.

The repository was cloned from GitHub the way a work laptop would clone it, and the runbook
was walked line by line against it. Two of its sentences were not what the machine does.

**A position in a list is not a name.** The runbook said *preflight warns at the sixteenth
check - `model_answers`*. There are sixteen checks and `model_answers` is the **third** of
them; P168's note - "preflight gained a sixteenth check" - was about the count, and the
runbook turned it into an ordinal. A reader looking for a warning scrolls to the bottom of
a list of sixteen and does not find it. The runbook names the check now, and the test below
holds that claim to the registry, because a count in prose is a count nothing checks.

**The loudest line on a healthy new machine was an exception class name.** `--check` is step
one of the runbook and setting `AA_VAULT_KEY` is step two, so on a first morning there is
never a key yet and the vault always fails to open. That printed as `the pool did not start:
RegistryError: PRIVACY.VAULT_UNAVAILABLE [system] at AA_VAULT_KEY - ` followed by two
sentences joined with a pipe, above eight green `[ok]` lines. It reads as a setup step now,
in the voice the rest of the report already uses for a binding that would not register:
what it means, then the command, then the code on a line of its own.

The clone itself is the part no test can keep: `tests/p169` drives `set_up` against a machine
that has nothing, which is as close as the suite gets. What was actually done on 2026-10-07 is
written into the runbook beside the claim it supports.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from admin.preflight import CHECKS

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = (ROOT / "docs" / "WORK-LAPTOP.md").read_text(encoding="utf-8")


def test_the_runbook_names_the_model_check_rather_than_a_place_in_the_list() -> None:
    """The defect, said as a property: a check is found by its name, and the ordinal the
    runbook gives for it has to be the one the registry gives."""
    assert "`model_answers`" in RUNBOOK, "the runbook no longer names the check at all"
    where = [n for n, (name, _label) in enumerate(CHECKS, 1) if name == "model_answers"]
    assert where, "preflight no longer has a model_answers check for the runbook to name"
    position = where[0]
    said = re.search(r"(\w+) in the list of (\w+)", RUNBOOK)
    assert said, "the runbook no longer says where in the list the check is"
    words = {
        "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
        "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
        "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
        "sixteen": 16, "seventeen": 17, "eighteen": 18,
    }
    assert words.get(said.group(1)) == position, (
        f"the runbook calls model_answers the {said.group(1)} check and it is number {position}"
    )
    assert words.get(said.group(2)) == len(CHECKS), (
        f"the runbook says there are {said.group(2)} checks and there are {len(CHECKS)}"
    )


def test_the_runbook_quotes_the_label_the_page_actually_shows() -> None:
    """Somebody matching the runbook against the screen matches on the label, so the label
    in the runbook has to be the registry's."""
    label = dict(CHECKS)["model_answers"]
    # Whitespace flattened first: a Markdown line break inside the quoted label is a fact
    # about the column width of the file, not about the words.
    flat = " ".join(RUNBOOK.lower().split())
    assert " ".join(label.lower().split()) in flat, f"the runbook does not quote {label!r}"


@pytest.mark.parametrize("name,_label", CHECKS)
def test_every_check_the_runbook_names_is_one_preflight_has(name: str, _label: str) -> None:
    """The other direction. A check named in the runbook and deleted from the registry is a
    reader sent to look for something that is not there."""
    for quoted in set(re.findall(r"`(\w+)`", RUNBOOK)):
        if quoted.endswith("_answers") or quoted in {n for n, _ in CHECKS}:
            assert quoted in {n for n, _ in CHECKS}, f"the runbook names a check {quoted!r}"


def test_the_vault_line_leads_with_what_it_means_and_keeps_the_code_for_quoting() -> None:
    """The same rule the consoles follow since P173, in the one place a new machine reads
    first."""
    source = inspect.getsource(__import__("tools.serve", fromlist=["_pool"])._pool)
    opening = source[source.index("open_vault(") :]
    opening = opening[: opening.index("return None")]
    assert "unopened.__class__.__name__" not in opening, (
        "the first line a new machine prints is an exception class name again"
    )
    assert 'getattr(found, "detail", None)' in opening, (
        "it no longer prefers the diagnostic's own sentence"
    )
    assert "textwrap.wrap" in opening, "the sentence is printed on one line again"
    assert 'getattr(found, "code", None)' in opening, "the code is no longer there to quote"


def test_the_runbook_warns_that_the_first_command_says_this() -> None:
    """It fires on every first morning, so a runbook that does not mention it is a runbook
    that stops being followed at step one."""
    step_one = RUNBOOK[RUNBOOK.index("## 1. Clone and install") : RUNBOOK.index("## 2.")]
    assert "AA_VAULT_KEY" in step_one, "step one does not say the vault line is coming"
    assert "mask vault will not open" in step_one, (
        "step one does not quote what the machine actually prints"
    )
    assert "expected" in step_one.lower(), "step one does not say it is expected"


def test_the_runbook_records_the_clone_it_was_walked_against() -> None:
    """A runbook claiming a rehearsal is a claim with a date on it, or it is a claim about
    some earlier version of itself."""
    assert re.search(r"fresh-clone rehearsal was run to the end on \d{4}-\d{2}-\d{2}", RUNBOOK), (
        "the runbook no longer says when it was last walked against a clone"
    )
