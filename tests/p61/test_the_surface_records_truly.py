"""Two things the setup surface got wrong, both found by operating it rather than reading it.

P57 gave a person a way to approve a workflow, which had been impossible. Using it turned up
what testing it had not: the recipe register is write-once per digest - the same bytes are
the same approval, which is correct - so approving an already-approved file returns the
existing row and writes nothing. P57 sent it through the board anyway, so the governance
chain gained a REGISTERED entry naming a person whose approval produced no registration,
beside a register still naming whoever approved it first.

A chain that records approvals which changed nothing is a chain nobody can audit. And the
page would have shown the first approver's name after a second approval "succeeded", which
is the surface telling somebody their action did not work when in fact it did nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from admin.console import AdminConsole, AlreadyApproved
from registries.recipes import RecipeRegister, digest_of_recipe

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def console() -> AdminConsole:
    return AdminConsole.__new__(AdminConsole)


def approve(
    console: AdminConsole,
    register: Any,
    board: Any,
    reason: str = "the order we work in",
) -> Any:
    return console.approve_recipe(
        "monthly-refresh", who="Caleb Smit", reason=reason, register=register, board=board
    )


# ------------------------------------------------- approving what is already approved


def test_a_second_approval_of_the_same_bytes_is_refused(
    console: AdminConsole, register: RecipeRegister, board: Any
) -> None:
    approve(console, register, board)

    with pytest.raises(AlreadyApproved) as settled:
        approve(console, register, board, reason="reading it again")

    said = str(settled.value)
    assert "Caleb Smit" in said, "it says who approved it"
    assert "un-approves it" in said, "and what would make approving it meaningful again"


def test_it_appends_nothing_to_the_governance_chain(
    console: AdminConsole, register: RecipeRegister, board: Any, record: Any
) -> None:
    """The defect itself. A chain entry for an approval that registered nothing is a row
    an auditor cannot reconcile against the register it points at."""
    approve(console, register, board)
    before = len([e for e in record.entries() if e.candidate == "recipe:monthly-refresh"])

    with pytest.raises(AlreadyApproved):
        approve(console, register, board, reason="again")

    after = [e for e in record.entries() if e.candidate == "recipe:monthly-refresh"]
    assert len(after) == before, "the chain grew for an approval that changed nothing"


def test_the_register_still_names_whoever_approved_it_first(
    console: AdminConsole, register: RecipeRegister, board: Any
) -> None:
    approve(console, register, board)
    with pytest.raises(AlreadyApproved):
        approve(console, register, board)

    rows = [r for r in register.registered() if r.name == "monthly-refresh"]
    assert len(rows) == 1, "one approval per set of bytes"
    assert rows[0].version == 1


# --------------------------------------------------- and an edited file still approves


def test_a_recipe_edited_since_approval_is_still_approvable(
    console: AdminConsole, register: RecipeRegister, board: Any, recipes: Path
) -> None:
    """The path this must not break: the digest changed, so it is a different workflow and
    a second decision. The refusal is about identical bytes, not about the name."""
    approve(console, register, board)
    path = recipes / "monthly-refresh.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "\n# one more thought\n", encoding="utf-8")

    again = approve(console, register, board, reason="read the change")
    assert again["version"] == 2
    assert again["digest"] == digest_of_recipe(path)


# ------------------------------------------------------------------ the auto-accept bar


def test_the_profile_offers_the_bar_that_was_chosen() -> None:
    """0.90, recorded as a working number somebody picked rather than a default nobody did.
    Read from the console's own skeleton, so it cannot drift from what the form shows."""
    import inspect

    from admin import console as module

    source = inspect.getsource(module)
    assert '"auto_accept_confidence": 0.90' in source
    assert '"always_review_categories": ["owner_related"]' in source


def test_the_decision_behind_the_bar_is_recorded() -> None:
    """A number in a form with no reason behind it is the state this replaced."""
    open_items = (ROOT / "BUILD" / "OPEN.md").read_text(encoding="utf-8")
    assert "auto-accept bar" in open_items
    assert "0.90" in open_items
    assert "sampling audit" in open_items, "and what would make a bar safe rather than chosen"
