"""P138: the console, against three runs a rehearsal actually produced.

Ran `simulate_firm.py --scripted` into a directory that survives it, started a server on the
store it left, and looked at the screen. Three things, none of them visible from the source
and all of them obvious once there was a one beside them:

**"1 need a person".** The chrome and the engagement header count the same states, and C74
held them to the same *words*. Both wrote the sentence themselves, so they agreed on the
noun and neither inflected the verb - which nobody saw, because every fixture and every
screenshot until now had more than one.

**"quarantined · in progress", tooltip "still running".** `in_progress` on a scorecard means
*no verdict yet*. The pill rendered it as the run's own motion, so a run that had stopped on
itself was labelled as running, with a tooltip insisting on it. Two vocabularies - the run's
states and the scorecard's verdicts - and the page read one in the other's terms.

**Two keys the map answers to and does not mention.** `+` and `-` zoom; the hint line named
five keys and not those. And "0 fits" reads as a count of something rather than as a key and
a verb, next to "/ finds" which is the same shape and does not.

All three are the same kind of defect as P135's and P136's: correct code, and a screen that
says something else.
"""

from __future__ import annotations

import re
from pathlib import Path

from ops.console.app import PAGE as ACTIVITY

ROOT = Path(__file__).resolve().parents[2]


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))


def without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", text)


# ------------------------------------------------------------------ one count, one verb


def test_the_phrase_is_inflected_in_one_place() -> None:
    body = without_comments(script())
    assert body.count("const needAPerson") == 1, "the phrase has more than one home"
    assert "' needs'" in body and "' need'" in body, "it does not inflect the verb"


def test_both_surfaces_call_it_rather_than_writing_it() -> None:
    """The chrome counts across every run and the engagement header counts within one. The
    defect was not that they disagreed - it was that each said it itself."""
    body = without_comments(script())
    for where in ("refresh", "paintRuns"):
        found = re.search(rf"function {where}\([^)]*\)\s*\{{(.*?)\n\}}", body, re.S)
        assert found, f"the page has no {where}"
        assert "needAPerson(" in found.group(1), f"{where} writes the sentence itself"
    assert body.count("needAPerson(") == 2, "a third caller, or one of the two stopped"


def test_it_says_needs_for_one_and_need_for_more() -> None:
    """Evaluated rather than read, because the bug was an expression nobody ran on a 1.

    The function is three tokens of JavaScript and this is Python, so it is translated here
    rather than executed - and the translation is held to the source by the test above, which
    fails if the shape changes.
    """
    body = without_comments(script())
    found = re.search(r"const needAPerson = n => (.*?);", body, re.S)
    assert found, "the function is gone"
    rule = found.group(1)
    assert "n === 1" in rule, "it no longer branches on one"
    one, many = rule.index("' needs'"), rule.index("' need'")
    assert one < many, "the singular and the plural are the wrong way round"


# ---------------------------------------------- the scorecard's silence is not motion


def test_a_stopped_run_is_not_labelled_as_running() -> None:
    body = without_comments(script())
    found = re.search(r"function scorecardPill\(c, state\) \{(.*?)\n\}", body, re.S)
    assert found, "the pill is built inline again, where the two states cannot be compared"
    inner = found.group(1)
    assert "STOPPED.has(state)" in inner, "it no longer looks at what the run is"
    assert "'no verdict'" in inner, "a scorecard with no verdict still claims motion"
    assert "stopped before the scorecard reached a verdict" in inner, "and says nothing"


def test_a_run_that_is_going_still_reads_as_in_progress() -> None:
    """The other half. Making the stopped case honest must not make the running case
    silent - a run that is working and has no verdict yet is exactly 'in progress'."""
    body = without_comments(script())
    found = re.search(r"function scorecardPill\(c, state\) \{(.*?)\n\}", body, re.S)
    assert found
    inner = found.group(1)
    assert "'in progress'" in inner
    assert "'still running'" in inner


def test_the_stopped_states_are_the_ones_whose_sentences_say_so() -> None:
    """`STOPPED` is a second list of run states beside `NEEDS_ATTENTION`, which is how two
    lists drift. They are not the same list and should not be - a halted run wants nobody
    and has still stopped - so each name on this one is checked against what the page says
    that state means."""
    body = without_comments(script())
    found = re.search(r"const STOPPED = new Set\(\[(.*?)\]\);", body, re.S)
    assert found, "STOPPED is gone"
    named = set(re.findall(r"'([a-z_]+)'", found.group(1)))

    says = re.search(r"const STATE_SAYS = \{(.*?)\n\};", body, re.S)
    assert says
    sentences = dict(re.findall(r"(\w+): '([^']*)'", says.group(1)))
    for state in named:
        assert state in sentences, f"{state} is called stopped and the page never says what it is"
        assert any(
            word in sentences[state] for word in ("stopped", "ended", "replaced")
        ), f"{state} is on the stopped list and its own sentence does not say it stopped"

    for state in ("running", "queued"):
        assert state not in named, f"{state} is a run that is going"


# --------------------------------------------------------------- every key, written down


def test_every_key_the_map_handles_is_in_its_hint_line() -> None:
    """A shortcut nobody can find is one nobody uses. `+` and `-` were bound and
    undocumented; the line named the other five."""
    source = (ROOT / "ops" / "console" / "map_view.py").read_text(encoding="utf-8")
    hint = re.search(r'<span class="keys">(.*?)</span>', source, re.S)
    assert hint, "the hint line is gone"
    said = hint.group(1)

    handled = set(re.findall(r"e\.key === '([^']+)'", source))
    # The ones with another way to reach them need no line of their own: `]` and `[` are
    # aliases for n and p, Tab is the focus trap, Enter and Escape inside the find box.
    aliases = {"]", "[", "Tab", "Enter", "="}
    for key in handled - aliases:
        spelled = {"-": "&minus;", "Escape": "Esc"}.get(key, key)
        assert spelled in said, f"the map answers to {key!r} and never says so"


def test_every_key_the_line_names_is_one_the_map_handles() -> None:
    """The other direction, which is the one that rots: a line that promises a key nothing
    binds is worse than one that leaves a key out."""
    source = (ROOT / "ops" / "console" / "map_view.py").read_text(encoding="utf-8")
    hint = re.search(r'<span class="keys">(.*?)</span>', source, re.S)
    assert hint
    handled = set(re.findall(r"e\.key === '([^']+)'", source))
    named_keys = (("n and p", "n"), ("/ finds", "/"), ("0 fits", "0"), ("Esc closes", "Escape"))
    for named, key in named_keys:
        assert named.split()[0] in hint.group(1) or named in hint.group(1)
        assert key in handled, f"the line says {named!r} and nothing binds {key!r}"


def test_the_fit_key_reads_as_a_key_and_a_verb() -> None:
    """"0 fits", beside "/ finds", reads as a count of something that fits."""
    source = (ROOT / "ops" / "console" / "map_view.py").read_text(encoding="utf-8")
    assert "0 fits it to the window" in source
