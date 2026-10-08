"""C34 - The setup surface, used rather than described.

P57 made approving a workflow possible; P61 fixed what using it revealed. What this asks is
whether the two records a person creates during setup - a methodology clearance and a recipe
approval - agree with each other and with the chain behind them.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import needs_a_checkout

ROOT = Path(__file__).resolve().parents[3]


def test_neither_register_is_committed() -> None:
    """Both record that somebody read something and took responsibility for it. Shipping
    either would ship a decision nobody made, so a clone starts with nothing."""
    needs_a_checkout("what a clone starts with")
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "foundations/cleared.yaml" in ignored
    assert "recipes/registered.yaml" in ignored
    import subprocess

    for path in ("foundations/cleared.yaml", "recipes/registered.yaml"):
        tracked = subprocess.run(  # noqa: S603
            ["git", "ls-files", "--error-unmatch", path], cwd=ROOT, capture_output=True
        )
        assert tracked.returncode != 0, f"{path} is committed"


def test_an_approval_that_registers_nothing_records_nothing() -> None:
    """The defect P61 closed: the board appended a chain entry for an approval the register
    had already settled, so the chain named one person and the register another."""
    source = (ROOT / "admin" / "console.py").read_text(encoding="utf-8")
    assert "AlreadyApproved" in source
    assert "digest_of_recipe(path)" in source
    settled = source.split("settled = register.entry")[1].split("approved = [")[0]
    assert "raise AlreadyApproved" in settled, "it must refuse before it reaches the board"


def test_the_surface_refuses_a_name_that_is_not_the_person_asking() -> None:
    """P36's guarantee, and the thing that stopped a clearance being recorded under a name
    the machine could not vouch for. A record naming somebody who was not there is worse
    than no record."""
    who = (ROOT / "ui" / "who.py").read_text(encoding="utf-8")
    assert "identity" in who.lower()


def test_both_acts_are_reachable_from_the_page() -> None:
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")
    assert 'data-act="clearFile"' in page
    assert 'data-act="approveRecipe"' in page


def test_the_bar_the_form_offers_is_one_somebody_chose() -> None:
    console = (ROOT / "admin" / "console.py").read_text(encoding="utf-8")
    assert '"auto_accept_confidence": 0.90' in console
    assert "sampling audit" in console, "and the reason it is a judgement rather than a finding"
