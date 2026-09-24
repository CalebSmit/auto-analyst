"""P107 - "Ready to run" has to mean it.

The Setup page's checklist promises that each step is checked against the live
configuration, so it *"cannot tell you something is done when it is not"*. It kept that
promise for the seven things in the configuration document and had no idea about the two
that are not there: the mask vault's key and the model adapter both come from `.env`.

So the page said **Ready to run** on a machine whose worker pool will not start because
nothing can be masked, and on one where every skill is answered by a recorded fixture and
no work happens at all. Both states were reached on this machine today while setting a real
engagement up.

A checklist that reports done on a machine that cannot mask is worse than no checklist. It
is the one screen a first-time reader trusts, and the whole reason it exists is that the
setup order is not guessable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "admin" / "page.py"
CONSOLE = ROOT / "admin" / "console.py"


class Secrets:
    """A Secrets Port with whatever the test wants in it."""

    def __init__(self, **values: str) -> None:
        self.values = values

    def has(self, name: str) -> bool:
        return name in self.values

    def get(self, name: str) -> str:
        return self.values[name]


def environment_of(secrets: Any) -> dict[str, Any]:
    """`AdminConsole._environment` with nothing but a secrets port behind it."""
    from admin.console import AdminConsole

    console = AdminConsole.__new__(AdminConsole)
    console.preflight = type("P", (), {"secrets": secrets})()
    return console._environment()  # noqa: SLF001


# ============================================================ the vault


def test_a_machine_with_no_key_is_told_so() -> None:
    report = environment_of(Secrets())
    assert report["vault"]["ready"] is False
    assert "AA_VAULT_KEY" in report["vault"]["detail"]
    assert "Fernet.generate_key" in report["vault"]["detail"], "and how to make one"


def test_a_key_that_is_present_and_malformed_reads_as_not_done() -> None:
    """The state this screen must not call done. `secrets.has()` would report it present,
    and a key that survives setup and fails at the first run is the worst place to find
    out - so the vault is opened rather than counted."""
    report = environment_of(Secrets(AA_VAULT_KEY="not-a-fernet-key"))
    assert report["vault"]["ready"] is False
    assert "not a valid Fernet key" in report["vault"]["detail"]


def test_a_real_key_opens_the_vault_and_says_so() -> None:
    from cryptography.fernet import Fernet

    report = environment_of(Secrets(AA_VAULT_KEY=Fernet.generate_key().decode()))
    assert report["vault"]["ready"] is True
    assert "opens the vault" in report["vault"]["detail"]


def test_the_check_opens_a_vault_that_leaves_nothing_behind() -> None:
    """A setup page that wrote a file every time somebody loaded it would be a setup page
    that created state by being looked at."""
    source = CONSOLE.read_text(encoding="utf-8")
    body = source[source.index("def _environment") : source.index("def _ai_model")]
    assert "sqlite:///:memory:" in body
    assert ".close()" in body


# ============================================================ the model door


def test_a_machine_answering_from_fixtures_is_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """`fake` and `scripted` both finish a run and neither does any work. A checklist that
    counted them as connected would be telling somebody their setup was complete when no
    client file would ever be looked at by anything."""
    import ports

    for stand_in in ("fake", "scripted"):
        monkeypatch.setenv("AA_LLM_ADAPTER", stand_in)
        ports.reset()
        report = environment_of(Secrets())
        assert report["model"]["ready"] is False, stand_in
        assert report["model"]["adapter"] == stand_in


def test_the_model_step_says_what_is_answering_rather_than_just_failing() -> None:
    """"Not connected" sends somebody to check a key. "Answered by fake - replays recorded
    fixtures, no API call, no spend" tells them nothing is wrong and nothing is happening,
    which are different problems."""
    import ports

    report = environment_of(Secrets())
    assert report["model"]["adapter"] == ports.selected("llm")
    assert report["model"]["detail"]


# ============================================================ the checklist itself


def test_both_are_steps_rather_than_a_note_somewhere() -> None:
    """A warning beside a checklist that says "Ready to run" loses to the checklist. They
    are steps, they are first, and the count includes them."""
    page = PAGE.read_text(encoding="utf-8")
    checklist = page[page.index("function checklist()") : page.index("const next = steps")]
    assert "t: 'Set the masking key'" in checklist
    assert "t: 'Connect the AI model'" in checklist
    assert checklist.index("Set the masking key") < checklist.index("Set this environment up")


def test_the_checklist_reads_them_from_the_live_system() -> None:
    """Not from a flag somebody sets. The page's own promise is that a step cannot read
    done when it is not, and the only way to keep it is to ask."""
    page = PAGE.read_text(encoding="utf-8")
    assert "SETUP.environment_ready" in page
    assert '"environment_ready": self._environment(),' in CONSOLE.read_text(encoding="utf-8")


def test_the_heading_counts_the_steps_it_is_beside() -> None:
    """A count in prose beside a list that grew. It said seven while showing nine, which
    is the smallest possible version of the thing this whole phase is about.

    Asserted as the relationship rather than as the word. Written as `"Nine steps" in
    page`, this was itself the eleventh roll-call test in this build (B-066) and went red
    the moment P117 added a tenth step - correctly reporting a fact about the day it was
    written as though it were a defect."""
    from tests.counting import in_words

    page = PAGE.read_text(encoding="utf-8")
    steps = page.count("{{done:")
    assert steps >= 9, "the two P107 added are still there"
    assert f"{in_words(steps)} steps, in order." in page


def test_ready_to_run_claims_what_a_run_would_do() -> None:
    """The sentence it ends on. "Every step is done" is true of a list; "a run would mask,
    ask a model and write a workbook" is a claim about the machine, which is what somebody
    reading it is actually asking."""
    page = PAGE.read_text(encoding="utf-8")
    assert "A run would mask, ask a model and write a workbook." in page
    assert "Every step is done and checked against the live configuration." not in page


def test_the_vault_step_offers_the_one_thing_a_button_cannot_do() -> None:
    """The key is generated on the machine and never typed into a browser, so the action is
    a command to run rather than a form to fill. The command is in `body`, which is
    monospace and keeps its line breaks - a note collapses to one line, and a one-line shell
    command with quotes in it is the kind of thing people mistype."""
    page = PAGE.read_text(encoding="utf-8")
    block = page[page.index("ACTIONS.explainVault") : page.index("ACTIONS.signInShareFile")]
    assert "Fernet.generate_key" in block
    assert "body:" in block
    assert "note:" in block and ".env is never committed" in block


def test_the_model_step_reuses_the_connection_test() -> None:
    """P102 built the button. A second way of asking the same question would be a second
    answer to keep in step with the first."""
    page = PAGE.read_text(encoding="utf-8")
    checklist = page[page.index("function checklist()") : page.index("const next = steps")]
    assert "'testModel'" in checklist
    assert "ACTIONS.testModel = () => testConnection('model');" in page
