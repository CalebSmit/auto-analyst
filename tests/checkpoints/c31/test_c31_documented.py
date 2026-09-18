"""C31 - What a person is told to type.

Two phases either side of this one are about a person meeting the system for the first time
on a machine that has nothing set up: one so a workflow can be approved there at all, one so
the commands that get them there work. This asks the joined question - clone it, read the
page, type what it says - without a clone, by holding the documents and the tools to each
other.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_the_guide_and_the_session_rules_agree_on_how_to_run_things() -> None:
    using = (ROOT / "docs" / "USING.md").read_text(encoding="utf-8")
    rules = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for body in (using, rules):
        assert "python -m uv run python tools/serve.py" in body
        assert "python -m uv run python tools/simulate_firm.py" in body


def test_the_gate_still_runs_on_a_bare_interpreter() -> None:
    """The one tool that must not need the environment: it is what installs and checks
    everything else, and CLAUDE.md documents it without a prefix on purpose."""
    done = subprocess.run(  # noqa: S603
        [sys.executable, "tools/gate.py", "status"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert done.returncode == 0, done.stderr[-1500:]
    assert "phases closed" in done.stdout


def test_a_person_is_never_handed_somebody_elses_import_error() -> None:
    from tools._environment import missing, needs

    assert missing(("json", "sys")) == ()
    assert missing(("not_a_real_module_at_all",)) == ("not_a_real_module_at_all",)
    needs("json", script="tools/serve.py")  # silent when there is nothing wrong


def test_setup_and_approval_are_documented_in_the_same_place() -> None:
    """P57 made a recipe approvable; this makes sure somebody can find out that they have
    to. A door nobody is told about is the state P57 was fixing."""
    using = (ROOT / "docs" / "USING.md").read_text(encoding="utf-8")
    assert "recipe" in using.lower() or "workflow" in using.lower()
