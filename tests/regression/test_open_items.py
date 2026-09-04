"""The open register says what is waiting on a person, and does not quietly lose one.

A hand-written list rots. This one is checked against the two records that already know
some of its contents - the plan's own tasks, and the blueprint's list of decisions that
belong to people - so an item cannot be dropped from the register while it is still owed
somewhere else.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPEN = ROOT / "BUILD" / "OPEN.md"
PLAN = ROOT / "BUILD" / "plan.json"
BLUEPRINT = ROOT / "docs" / "architecture.html"


def text() -> str:
    return OPEN.read_text(encoding="utf-8")


def test_the_register_exists_and_is_committed() -> None:
    """It is the thing a next session reads. A file that is not tracked is a file that
    does not travel to the work machine."""
    tracked = subprocess.run(  # noqa: S603
        ["git", "ls-files", "BUILD/OPEN.md"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert tracked == "BUILD/OPEN.md"


def test_every_task_that_needs_the_work_machine_is_in_the_register() -> None:
    """P28 carries four tasks that need material only the firm has. If one is added to
    the plan and not to the register, the register has started lying."""
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    p28 = next(p for p in plan["phases"] if p["id"] == "P28")
    owed = [t for t in p28["tasks"] if t.startswith("On the work machine")]
    assert len(owed) == 4, owed

    register = text().lower()
    for fragment in ("timing", "taxonomy", "add-back", "model builder"):
        assert fragment in register, fragment
    assert "CF_LBO_Model_v3" in text()
    assert "human baseline" in register


def test_every_decision_the_blueprint_gives_a_person_is_in_the_register() -> None:
    """The blueprint names nine. The register carries all nine, so the two cannot
    disagree about what is owed and by whom."""
    html = BLUEPRINT.read_text(encoding="utf-8")
    block = html[html.index("const DECISIONS = [") : html.index("const MEASURES")]
    decisions = re.findall(r"\['([^']+)',", block)
    assert len(decisions) == 9, decisions

    register = text()
    for decision in decisions:
        # The register's wording is shortened for the table; match on the first words,
        # which are what makes each row identifiable.
        opening = " ".join(decision.replace("\\u2019", "'").split()[:4])
        assert opening in register, opening


def test_every_entry_says_why_it_is_blocked_and_what_happens_next() -> None:
    """An item with no consequence attached is one nobody will act on."""
    register = text()
    for heading in (
        "Waiting on your word",
        "Decisions that are yours",
        "Evidence only the work machine can produce",
        "Questions I am holding",
        "Settled",
    ):
        assert heading in register, heading
    assert "Why it is blocked" in register
    assert "When you answer" in register
    assert "rather than being deleted" in register


def test_the_register_names_the_things_this_build_is_actually_waiting_on() -> None:
    """The four from this build specifically, so a new session picks them up without
    reading the whole history."""
    register = text()
    for item in ("P28 sign-off", "container proof", "P26 sign-off", "Redis"):
        assert item in register, item
    assert "gate close P28" in register
    assert "gate checkpoint C10" in register


def test_the_register_is_pointed_at_from_the_rules_a_session_reads() -> None:
    """A register nobody is told to read is a register nobody reads."""
    rules = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "OPEN.md" in rules
    assert "BUILD/OPEN.md" in (ROOT / "README.md").read_text(encoding="utf-8")
