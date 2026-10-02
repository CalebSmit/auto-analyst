"""P148: four sentences on the consoles count something, and two counted wrong.

| where | the sentence said | what it counts |
|---|---|---|
| Setup, over Preflight | **Fourteen** checks over the live configuration | `CHECKS` has **15** |
| Help, over the colour key | **Three** colours carry meaning everywhere | **4** rows |
| Setup, over the checklist | Eleven steps, in order | 11 - right |
| Help, over the walkthrough | Six steps | 6 - right |

The first is the worst, because the page disagrees with itself **on the same screen**: the
panel under that sentence prints the live count and reads `15 checks · 3 warnings`. A reader
meets both in one glance.

A third was in `admin/page.py`'s own module docstring, which named a count of the checklist
that had been wrong for about a hundred phases. That paragraph is the first thing anybody
maintaining the page reads.

**`tests/counting.py` already existed for this**, with the rule written at the top: *assert
that the prose and the list agree, and derive the prose from the list - never write the
number down twice.* It was written because the count of preflight checks came to be typed in
three places and was wrong in all three the day P114 added one. It had six users and not one
of them was a console.

The reason it did not hold is worth stating: the table lived under `tests/`, so a test could
check a sentence after the fact and a page could never *build* one. A rule a page cannot
reach is a rule a page will break. The table is `ui/words.py` now and `tests/counting.py`
re-exports it, so the test measures the thing the sentence was built from.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from admin.page import PAGE as SETUP
from admin.preflight import CHECKS
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.help_page import MEANINGS
from ops.console.help_page import PAGE as HELP
from tests.counting import WORDS, in_words

ROOT = Path(__file__).resolve().parents[2]
PAGES = ((SETUP, "Setup"), (ACTIVITY, "Activity"), (ANALYTICS, "Analytics"), (HELP, "Help"))


def prose(page: str) -> list[str]:
    """The sentences a reader meets: a panel's `.why`, the page's own lead, a heading.

    Not the script. A number in code is a number doing something; a number in a sentence is
    a claim about something else, and only the second kind can be left behind.
    """
    found = []
    for pattern in (
        r'<p class="why">(.*?)</p>',
        r"<h1>(.*?)</h1>",
        r"<h2>(.*?)</h2>",
        r'<div class="page-head">\s*<h1>.*?</h1>\s*<p>(.*?)</p>',
    ):
        for block in re.findall(pattern, page, re.S):
            found.append(" ".join(re.sub(r"<[^>]+>", "", block).split()))
    return found


# ----------------------------------------------------- the two that were wrong, by name


def test_the_count_of_preflight_checks_is_the_number_of_checks() -> None:
    """Named one by one, because a sweep that passes because the sentence was deleted is a
    sweep that has stopped watching what it was written for."""
    said = re.search(r"(\w+) checks over the live configuration", SETUP)
    assert said, "the Preflight panel no longer says how many checks it runs"
    assert said.group(1) == in_words(len(CHECKS)), (
        f"the page says {said.group(1)!r} and preflight has {len(CHECKS)} checks"
    )


def test_the_page_does_not_disagree_with_itself_on_one_screen() -> None:
    """The panel under that sentence prints the live count. They are two renderings of one
    number and a reader meets both at once, which is what made this worth a phase rather
    than a line in the backlog."""
    assert "checks.length" in SETUP, (
        "the panel no longer prints the live count, so there is nothing to disagree with"
    )
    assert "Fourteen checks" not in SETUP


def test_the_count_of_colours_is_the_number_of_colours() -> None:
    said = re.search(r"(\w+) colours carry meaning", HELP)
    assert said, "the colour key no longer says how many colours there are"
    assert said.group(1) == in_words(len(MEANINGS)), (
        f"the help page says {said.group(1)!r} and lists {len(MEANINGS)}"
    )
    rows = re.search(r"<h2>What the colours mean</h2>(.*?)</section>", HELP, re.S)
    assert rows and rows.group(1).count('<div class="r">') == len(MEANINGS), (
        "the rows and the list the sentence counts have come apart"
    )


def test_the_colour_key_is_built_from_the_list_rather_than_typed_beside_it() -> None:
    """What makes the test above hold tomorrow. A fifth colour added as a row of markup
    would leave the sentence saying four and nothing would notice.

    Asked of the module's source as well as its output, because a generated row and a typed
    one produce the same string - which is the whole difficulty with checking this class of
    thing.
    """
    for kind, name, _ in MEANINGS:
        assert f'<span class="pill {kind}"><i class="dot"></i>{name}</span>' in HELP
    written = (ROOT / "ops" / "console" / "help_page.py").read_text(encoding="utf-8")
    assert "for kind, name, says in MEANINGS" in written, "the rows are not generated"
    typed = re.findall(r'<div class="r"><span class="pill (?:good|warn|bad|accent)\b', written)
    assert typed == [], f"a colour row is typed out as well as generated: {typed}"


# ------------------------------------------------------------------ and all the others


# Every number in a sentence on these four pages, and what accounts for it. An entry that is
# not derived is a claim that this number cannot drift, with the reason - which is the part
# no sweep can work out, and the part worth writing down.
ACCOUNTED = {
    "Eleven steps": "counts the setup checklist; held to the array below",
    "Six steps": "counts the help page's walkthrough; held to its rows below",
    "first two against this machine": (
        "which steps, not how many - the first two of the checklist are about the machine "
        "and the rest about the configuration"
    ),
    "first two are once per engagement": "the same shape, on the walkthrough",
    "three in the afternoon": "an hour of the day, not a count of anything",
    "two answers it matters most not to confuse": (
        "counts the two named in the same sentence - never ran and passed - so it cannot "
        "come apart from them"
    ),
}


def accounted_for(word: str, around: str) -> str | None:
    """Either the reason this number cannot drift, or the fact that the page computed it.

    It takes the words on both sides, not just what follows: two of the six entries are
    *"the first two ..."*, and the part that makes them a claim about which rather than how
    many is the word before the number.
    """
    for phrase, why in ACCOUNTED.items():
        if phrase.lower() in around.lower():
            return why
    if word == in_words(len(CHECKS)) and "checks over" in around:
        return "derived from preflight.CHECKS"
    if word == in_words(len(MEANINGS)) and "colours carry" in around:
        return "derived from the colour list"
    return None


def test_every_number_in_a_sentence_is_derived_or_accounted_for() -> None:
    """The sweep. Eight numbers across the four pages: two are computed, two are counts of
    a list this file checks, and four are not counts at all and say why.

    It reads the rendered page, so a derived number and a typed one look identical here -
    which is exactly why the list above carries a reason rather than a tick.
    """
    words = "|".join(WORDS[2:])  # "one" is an article far more often than a count
    stray = []
    for page, where in PAGES:
        for sentence in prose(page):
            for match in re.finditer(rf"\b({words})\b", sentence, re.I):
                around = sentence[max(0, match.start() - 14) : match.end() + 40]
                if accounted_for(match.group(1), around) is None:
                    stray.append(f"{where}: ...{around}")
    assert stray == [], (
        "a number is written into a sentence and nothing accounts for it:\n" + "\n".join(stray)
    )


def test_nothing_is_accounted_for_that_is_not_there() -> None:
    """The allowlist's own check. An entry for a sentence that has been deleted is a reason
    nobody will read again, and it hides the next one that needs writing."""
    every = " ".join(line for page, _ in PAGES for line in prose(page))
    missing = [phrase for phrase in ACCOUNTED if phrase.lower() not in every.lower()]
    assert missing == [], f"these are accounted for and no longer said: {missing}"


def test_the_two_counts_that_are_still_typed_are_the_ones_they_say_they_are() -> None:
    """The allowlist, paid for. Both are stable lists in markup rather than data, so
    deriving them would mean generating the markup in order to count it - and that costs
    more than this does, as long as this exists."""
    steps = re.search(r"const steps = \[(.*?)\n  \];", SETUP, re.S)
    assert steps, "the setup checklist is no longer an array"
    assert len(re.findall(r"t:\s*'", steps.group(1))) == 11, "the checklist is not eleven"

    walk = re.search(r"<h2>Putting an engagement through</h2>(.*?)</section>", HELP, re.S)
    assert walk and walk.group(1).count('<div class="step">') == 6, "the walkthrough is not six"


# ----------------------------------------- the table a page can reach, and what it refuses


def test_the_table_lives_where_a_page_can_read_it() -> None:
    """The whole reason the rule did not hold: `tests/counting.py` could check a sentence
    and never build one."""
    from ui import words as production

    assert production.in_words(15) == "Fifteen"
    assert in_words is production.in_words, "there are two tables again"


def test_it_refuses_rather_than_rendering_a_digit() -> None:
    """A page that quietly printed `21 checks` where every other sentence says a word would
    not be noticed for a hundred phases, which is how long the last one lasted."""
    with pytest.raises(AssertionError, match="past this table"):
        in_words(len(WORDS))


def test_the_pages_docstring_no_longer_counts_its_own_steps() -> None:
    """It named six about eleven, in the first paragraph a maintainer reads."""
    import admin.page

    said = re.search(r"the first thing they see is the (\w+)", admin.page.__doc__ or "")
    assert said is None or said.group(1).capitalize() not in WORDS, (
        f"the docstring counts the checklist again, and says {said.group(1)!r}"
    )


# ------------------------------------------------ the two C81 found, after this closed


def test_no_module_keeps_a_table_of_number_words_of_its_own() -> None:
    """`tests/p80` had one. It was written before `tests/counting.py` existed and did the
    right thing with it - derived its count from the list - which is why nothing noticed
    that the table itself was the third copy. Found by C81 asking a question this phase's
    own tests could not.
    """
    spare = []
    for folder in ("tests", "ui", "ops", "admin", "tools"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            if "__pycache__" in path.parts or path == ROOT / "ui" / "words.py":
                continue
            source = path.read_text(encoding="utf-8")
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, ast.Assign):
                    continue
                value = node.value
                if isinstance(value, ast.List | ast.Tuple) and any(
                    isinstance(e, ast.Constant) and e.value == "Eleven" for e in value.elts
                ):
                    spare.append(str(path.relative_to(ROOT)))
    assert spare == [], f"a second table of number words: {spare}"


def test_the_guide_can_run_each_check_it_counts() -> None:
    """A count is only worth stating if the things counted are reachable. The guide said
    *Three checks you can point at anything* and printed a copyable command line for one of
    them - so a reader of that file could not run the formula audit or the reasonableness
    questions at all, and the second takes a flag it has no default for.
    """
    guide = (ROOT / "docs" / "USING.md").read_text(encoding="utf-8")
    for name in ("formula_audit", "prose_checks", "reasonableness"):
        assert f"tools/{name}.py" in guide, f"the guide counts {name} and cannot run it"
    assert "--move points=" in guide, (
        "the figures check has no default tolerance and the guide shows no --move"
    )
