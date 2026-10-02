"""C76 - what the consoles say about a run in front of them.

Two phases, both found the same way: `simulate_firm.py --keep` into a directory that
survives it, a server on the store it left, and a person reading the screen.

* **P138** - "1 need a person" in the engagement header, "quarantined · in progress" with
  the tooltip "still running" on a run that had stopped, and two keys the map answers to
  and never mentions.
* **P139** - the Analytics console still calling the same condition "Needs attention", the
  run detail still saying "Waiting on you", and the Help page defining neither the phrase
  the chrome counts with nor two of the states the screens show.

Every one of them had been on the screen for as long as the screen had, and the suite was
green through all of it. What a checkpoint can ask is whether the two phases left the
vocabulary and the state model agreeing with each other - because P138 added a second list
of run states and P139 made a rule about words, and those are the two things that drift.
"""

from __future__ import annotations

import re
from pathlib import Path

from ops.console.app import PAGE as ACTIVITY

ROOT = Path(__file__).resolve().parents[3]


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))


def without_comments(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", text)


# ------------------------------------------------- the lists of run states agree with each other


def test_every_list_of_run_states_names_states_the_page_explains() -> None:
    """There are three now - what a state means, which states want a person, and which have
    stopped - and they are deliberately different lists over one set of names. The way that
    goes wrong is a name on one of them that is not on STATE_SAYS, which is this page's one
    place that says what a state *is*."""
    body = without_comments(script())
    says = re.search(r"const STATE_SAYS = \{(.*?)\n\};", body, re.S)
    assert says, "nothing says what a state means"
    explained = set(re.findall(r"(\w+): '", says.group(1)))

    for name in ("NEEDS_ATTENTION", "STOPPED"):
        found = re.search(rf"const {name} = new Set\(\[(.*?)\]\);", body, re.S)
        assert found, f"{name} is gone"
        named = set(re.findall(r"'([a-z_]+)'", found.group(1)))
        assert named, f"{name} is empty"
        assert named <= explained, f"{name} names {named - explained}, which nothing explains"


def test_a_run_that_wants_a_person_is_a_run_that_has_stopped() -> None:
    """The two lists are not the same - a halted run has stopped and wants nobody - but one
    contains the other, and a state that wanted a person without having stopped would be a
    run the page asks somebody to look at while it is still working."""
    body = without_comments(script())

    def members(name: str) -> set[str]:
        found = re.search(rf"const {name} = new Set\(\[(.*?)\]\);", body, re.S)
        assert found
        return set(re.findall(r"'([a-z_]+)'", found.group(1)))

    wants, stopped = members("NEEDS_ATTENTION"), members("STOPPED")
    assert wants < stopped, f"{wants - stopped} wants a person and has not stopped"
    assert stopped - wants, "every stopped run now wants a person, which halted does not"


def test_the_server_and_the_page_still_agree_on_which_states_want_a_person() -> None:
    """P63 pinned this and both phases touched the lists around it."""
    from ops.console.app import NEEDS_ATTENTION

    declared = re.search(r"const NEEDS_ATTENTION = new Set\(\[(.*?)\]\);", script(), re.S)
    assert declared
    assert tuple(re.findall(r"'([a-z_]+)'", declared.group(1))) == NEEDS_ATTENTION


# ----------------------------------------------------- one vocabulary, over every surface


def test_the_phrase_has_one_home_and_every_surface_that_shows_it_calls_it() -> None:
    """P138 put the phrase and its verb in one function; P139 made the rule apply to every
    surface. Together that is: nothing writes these words itself."""
    body = without_comments(script())
    assert body.count("const needAPerson") == 1
    assert body.count("needAPerson(") == 2


def test_no_surface_speaks_a_retired_vocabulary() -> None:
    """Across every page that defines one, because the list of pages is what went stale."""
    pages = [*(ROOT / "ops" / "console").glob("*.py"), ROOT / "admin" / "page.py"]
    served = [
        p for p in pages
        if re.search(r"^PAGE(: ?str)? = ", p.read_text(encoding="utf-8"), re.M)
    ]
    assert len(served) >= 4, f"only {len(served)} surfaces found; the search is wrong"
    for path in served:
        source = re.sub(r"^\s*#.*$", " ", path.read_text(encoding="utf-8"), flags=re.M)
        body = without_comments(source)
        for retired in ("need attention", "needs attention", "waiting on you"):
            assert retired not in body.lower(), f"{path.name} says {retired!r}"


def test_help_can_be_asked_about_every_word_the_screens_use() -> None:
    from ops.console.help_page import GLOSSARY
    from ops.console.help_page import PAGE as HELP

    entries = dict(GLOSSARY)
    assert "Needs a person" in entries
    says = re.search(r"const STATE_SAYS = \{(.*?)\n\};", script(), re.S)
    assert says
    for state in set(re.findall(r"(\w+): '", says.group(1))):
        assert state in HELP.lower(), f"the screens show {state!r} and Help does not define it"


# ------------------------------------------ and nothing was said that is not true of a run


def test_the_scorecard_pill_reads_the_run_rather_than_only_itself() -> None:
    """The specific thing P138 fixed, held at the level of the rule: the scorecard's
    vocabulary and the run's are two, and one of them is not read in the other's terms."""
    body = without_comments(script())
    found = re.search(r"function scorecardPill\(c, state\) \{(.*?)\n\}", body, re.S)
    assert found, "the pill is built inline again"
    assert "STOPPED.has(state)" in found.group(1)
    assert "'no verdict'" in found.group(1)


def test_the_map_promises_exactly_the_keys_it_keeps() -> None:
    source = (ROOT / "ops" / "console" / "map_view.py").read_text(encoding="utf-8")
    hint = re.search(r'<span class="keys">(.*?)</span>', source, re.S)
    assert hint, "the hint line is gone"
    handled = set(re.findall(r"e\.key === '([^']+)'", source))
    aliases = {"]", "[", "Tab", "Enter", "="}
    for key in handled - aliases:
        spelled = {"-": "&minus;", "Escape": "Esc"}.get(key, key)
        assert spelled in hint.group(1), f"the map answers to {key!r} and never says so"
