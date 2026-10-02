"""C74 - the screen says one thing, and it is true.

Three phases, all found by running the console against a store of eighteen real runs and
reading it rather than reading the source. Each is small on its own; what a checkpoint can
ask is whether they left the three surfaces agreeing.

**One vocabulary.** P132 renamed what the chrome counts. The engagement header counts the
same thing and said something else, and the Help page is where somebody goes when a word on
a screen is unfamiliar - so all three have to use one set of words, or the page teaches a
term its own help does not define.

**One claim about order.** P133 made the funnel a funnel. The panel's sentence and its
numbers now agree, and the test that holds them together is the one that fails if either
moves without the other.

**One rule about what a person is shown before they decide.** P134 put the headers in front
of the reviewer. The reveal discipline - Accept and Correct wait until the proposal is
shown - is older than all three of these phases, and the kind of change that erodes it is
exactly the kind made here: adding something else to the same modal.
"""

from __future__ import annotations

import re

from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.help_page import PAGE as HELP


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))


def without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", text)


# ------------------------------------------------------------------ one vocabulary


def test_the_page_uses_one_phrase_for_a_run_that_wants_a_person() -> None:
    """The chrome, the engagement header and the filter button all count the same states.
    Three names for it is the reader's problem."""
    body = without_comments(script())
    assert "need attention" not in body, "two phrases for one thing"
    # One function owns the phrase, and both surfaces call it. This used to count the
    # literal twice, which held the words together and not the grammar - the engagement
    # header said "1 need a person" on a real engagement and the count was satisfied.
    assert body.count("const needAPerson") == 1, "the phrase has more than one home"
    assert body.count("needAPerson(") == 2, "the chrome and the engagement header both call it"
    assert "'needs' : ' need'" in body or "? ' needs' : ' need'" in body, "it stopped inflecting"
    assert "Needs a person" in body, "and the button that filters to them"


def test_the_help_page_defines_the_words_the_screen_now_uses() -> None:
    """Help is where somebody goes when a word on a screen is unfamiliar. A screen that
    uses a term its own help does not is a screen that has outgrown its documentation."""
    assert "quarantined" in HELP.lower()
    assert "review item" in HELP.lower()
    # The two states the counts are built from are each explained there.
    assert "stopped" in HELP.lower()


def test_the_states_the_counts_are_built_from_are_still_the_servers() -> None:
    """P63 pinned this and it has to survive a phase that changed what the count is
    called: the page counts these for its chrome and `engagements()` counts them per
    engagement, from one list."""
    from ops.console.app import NEEDS_ATTENTION

    declared = re.search(r"const NEEDS_ATTENTION = new Set\(\[(.*?)\]\);", script(), re.S)
    assert declared
    named = tuple(re.findall(r"'([a-z_]+)'", declared.group(1)))
    assert named == NEEDS_ATTENTION


# ------------------------------------------------------------- one claim about order


def test_the_funnel_panel_and_the_funnel_numbers_make_the_same_claim() -> None:
    """The sentence says the stages are in order and that a stage counts only what got
    through the ones before. The computation is what makes that true, and the two are
    asserted together so neither can move alone."""
    import ast
    from pathlib import Path

    assert "Every run passes through these in order" in ANALYTICS
    assert "got through every stage before it" in ANALYTICS

    root = Path(__file__).resolve().parents[3]
    source = (root / "ops" / "analytics.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    funnel = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_funnel"
    )
    body = ast.unparse(funnel)
    assert "alive" in body, "the stages no longer carry survivors forward"
    assert "max(0," not in body, "the drop is clamped again, which hides a contradiction"


def test_the_stage_names_say_what_they_measure() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    tree = ast.parse((root / "ops" / "analytics.py").read_text(encoding="utf-8"))
    funnel = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_funnel"
    )
    names = {n.value for n in ast.walk(funnel) if isinstance(n, ast.Constant) and n.value}
    assert "Skills ran" in names
    assert "Skills dispatched" not in names


# --------------------------------------- one rule about what is shown before deciding


def test_nothing_added_to_the_review_modal_weakened_what_it_gates() -> None:
    """Three phases added to this page. The reveal rule is older than all of them and is
    the one thing on it that is a control rather than a presentation."""
    body = script()
    assert 'data-d="accepted" disabled' in body
    assert 'data-d="corrected" disabled' in body
    assert 'data-act="reveal"' in body
    assert "the asking is recorded" in body, "the reason the gate exists is still said"


def test_the_modal_shows_a_source_or_says_there_is_none() -> None:
    """Both branches exist, which is the property P134 added. One branch alone is how it
    came to advise reading something that was not there."""
    body = script()
    assert "Read the source first." in body
    assert "No excerpt was recorded" in body
    assert "item.source_excerpt" in body


def test_every_control_on_the_page_is_a_named_action() -> None:
    """`ui/who.py`'s rule, across everything these three phases added: a page builds no
    handler out of data, because a client's line item is whatever the client typed."""
    body = script()
    assert "onclick=" not in body
    assert "javascript:" not in body
    # The confirm dialog's two buttons are handled by a listener on the dialog itself
    # rather than by the shared table, which is right: that listener is scoped to one
    # element and reads nothing from a client's file. Named here with the reason, because
    # an exemption without one is how a rule stops being a rule.
    scoped_to_their_own_dialog = {"ok", "cancel"}

    named = (
        set(re.findall(r'data-act="([a-zA-Z]+)"', ACTIVITY))
        | set(re.findall(r"act: '([a-zA-Z]+)'", body))
    ) - scoped_to_their_own_dialog
    assert named, "no named actions at all"
    for action in named:
        assert f"ACTIONS.{action}" in body, f"{action} is used and never registered"
    assert "ACTIONS.auditFile" in body, "the one built through data() is registered"
