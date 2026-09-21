"""C40 - An unwired seam is a decision, and the decision is on the record.

P71 turned "built, and wired to nothing" from a defect found by careful reading into one
found by the suite. A checkpoint asks the part a unit test cannot: whether the code and the
written record still agree about what is unwired and why.

That pairing is the whole value. A scan with an allowlist is only as honest as the reasons
in it, and a reason that lives solely in a test file is one nobody reading the backlog will
ever see. So each excused seam has to exist in both places, and the backlog entry has to be
findable from the code.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.p71.test_nothing_is_unwired import ALLOWED, key, unwired

ROOT = Path(__file__).resolve().parents[3]


def backlog() -> str:
    return (ROOT / "knowledge" / "backlog.md").read_text(encoding="utf-8")


def test_the_scan_is_quiet_on_the_tree_as_it_stands() -> None:
    """A failure after this means something new, which is the only way the check is worth
    running."""
    surprises = [f"{w}:{n}" for w, _, n in unwired() if key(w, n) not in ALLOWED]
    assert not surprises, surprises


def test_every_excused_seam_is_written_down_where_a_person_would_look() -> None:
    """A reason in a test file is a reason nobody reads. Each allowlisted seam names a
    backlog item, and that item exists."""
    for entry, why in ALLOWED.items():
        found = re.search(r"\bB-0\d\d\b", why)
        assert found, f"{entry} is excused without naming a backlog item"
        item = found.group(0)
        assert f"## {item}" in backlog(), f"{entry} names {item}, which is not in the backlog"


def test_an_excused_seam_is_not_also_claimed_as_built() -> None:
    """The contradiction that would make both records useless: the backlog saying a thing
    is built while the scan says nothing calls it."""
    for _entry, why in ALLOWED.items():
        item = re.search(r"\bB-0\d\d\b", why)
        assert item
        body = backlog().split(f"## {item.group(0)}", 1)[1].split("\n## ", 1)[0]
        assert "status: built" not in body, f"{item.group(0)} says built; nothing calls its code"


def test_the_two_shapes_this_phase_exists_for_are_both_resolved() -> None:
    """Three ways a seam ends, and P71 has now produced all three.

    `read_draft` was deleted, because there was nothing to record: dead code with no
    intent behind it. `provenance_of` was kept and excused, because there *was* - it ran
    the real Provenance Gate and nothing called it, so deleting it would have removed the
    only trace of the intent. P86 wired it, which is the third ending and the one the
    excuse existed to make possible.

    So the allowlist is empty, and that is what resolved looks like rather than a check
    that stopped looking - `tests/checkpoints/c53` is where the emptiness is held to
    meaning something.
    """
    conformance = (ROOT / "governance" / "conformance.py").read_text(encoding="utf-8")
    assert "def read_draft" not in conformance

    metrics = (ROOT / "evals" / "metrics.py").read_text(encoding="utf-8")
    assert "def provenance_of" in metrics, "kept, so that it could be wired"
    assert "provenance_of(world, output, versions, run_id=run_id)" in metrics, "and wired"
    assert "evals.metrics.provenance_of" not in ALLOWED, "wired, so no longer excused"


def test_the_earlier_findings_of_this_shape_stayed_fixed() -> None:
    """P55 and P60 each fixed one by hand. If any regressed, the scan should be the thing
    that says so rather than a person noticing again."""
    wiring = (ROOT / "tools" / "serve.py").read_text(encoding="utf-8")
    assert "PrecedentStore" in wiring, "P55: the served graph names the precedent store"

    executor = (ROOT / "graph" / "execute.py").read_text(encoding="utf-8")
    assert "on_failure" in executor, "P60: on_failure is read by something that executes"
