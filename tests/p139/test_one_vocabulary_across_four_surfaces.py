"""P139: C74 held three surfaces to one vocabulary, and there are four.

P132 replaced "need attention" with "need a person" on the Activity console, and C74 added
the test that keeps the chrome, the engagement header and the Help page saying one thing.
The Analytics console was not in that list. Opened it against a store with three real runs
and the panel for work that has stopped was titled **Needs attention**, next to a chrome on
the page before it reading **2 need a person** - the same condition, two names, one tab
apart.

And the Help page, which exists so that somebody who meets an unfamiliar word on a screen
can look it up, defined `Waiting` and `Quarantined` and not the word that covers both and
is printed larger than either.

The fix is small. What is worth having is the test: it walks **every** surface rather than
the three somebody happened to list, so the next page added to this product is held to the
same words without anybody remembering to add it here.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def surfaces() -> dict[str, str]:
    """Every page this product serves, found rather than listed.

    A list is what let the Analytics console drift: three names were written down when
    there were three pages, a fourth arrived, and the test went on passing. These are the
    modules that define a PAGE, which is what a surface *is* here.
    """
    found = {}
    for path in sorted((ROOT / "ops" / "console").glob("*.py")) + [ROOT / "admin" / "page.py"]:
        text = path.read_text(encoding="utf-8")
        if re.search(r"^PAGE(: ?str)? = ", text, re.M):
            found[str(path.relative_to(ROOT))] = text
    return found


def without_comments(text: str) -> str:
    """Python comments, JavaScript comments and HTML comments.

    All three, because the reason a phrase was retired is written beside the code that
    retired it, in whichever comment syntax that file speaks - and a check that reads them
    finds the rule it is enforcing and calls it a breach. P132 did this to itself once.
    """
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"(?<!:)//[^\n]*", " ", text)
    return re.sub(r"^\s*#.*$", " ", text, flags=re.M)


# --------------------------------------------------------------------- the retired phrase


def test_no_surface_says_the_retired_phrase() -> None:
    """Across every page, not the three that were listed when the rule was written."""
    pages = surfaces()
    assert len(pages) >= 4, f"only {len(pages)} surfaces found; the search is wrong"
    for name, text in pages.items():
        body = without_comments(text).lower()
        assert "need attention" not in body, f"{name} still says it"
        assert "needs attention" not in body, f"{name} still says it"
        assert "waiting on you" not in body, f"{name} uses the other retired phrase"


def test_the_surfaces_that_name_the_condition_name_it_the_same_way() -> None:
    """Two of the four show this condition. Both say the same words for it."""
    pages = surfaces()
    saying = {
        name: text
        for name, text in pages.items()
        if "a person" in without_comments(text).lower()
    }
    assert len(saying) >= 3, f"only {sorted(saying)} mention a person at all"
    assert any("analytics" in name for name in saying), "the Analytics console is silent again"


def test_the_analytics_panel_is_titled_with_it() -> None:
    page = (ROOT / "ops" / "console" / "analytics_page.py").read_text(encoding="utf-8")
    found = re.search(r"function stuck\(s\) \{\{(.*?)\n\}\}", page, re.S)
    assert found, "the panel is gone"
    assert "'Needs a person'" in found.group(1)
    assert "'Nothing is stuck'" in found.group(1), "the all-clear wording went with it"


# ------------------------------------------------------------- and it can be looked up


def test_help_defines_every_state_word_the_screens_show() -> None:
    """Derived from `STATE_SAYS`, so a state added to the console without an entry here
    fails rather than appearing on a screen whose own help has never heard of it."""
    from ops.console.help_page import PAGE as HELP

    console = (ROOT / "ops" / "console" / "app.py").read_text(encoding="utf-8")
    says = re.search(r"const STATE_SAYS = \{(.*?)\n\};", console, re.S)
    assert says, "STATE_SAYS is gone"
    states = set(re.findall(r"(\w+): '", says.group(1)))
    assert states, "no states parsed"
    lowered = HELP.lower()
    for state in states:
        assert state in lowered, f"the screens show {state!r} and Help does not define it"


def test_help_defines_the_phrase_that_is_not_a_state() -> None:
    """"Needs a person" is the two below it named together, and it is the largest word on
    the most-looked-at screen. It was the one word in this vocabulary with no entry."""
    from ops.console.help_page import GLOSSARY

    entries = dict(GLOSSARY)
    assert "Needs a person" in entries, "the phrase the chrome counts with is not defined"
    said = entries["Needs a person"].lower()
    assert "waiting" in said and "quarantined" in said, "it does not say which two it covers"
    assert "stopped" in said, "it does not say what the two have in common"


def test_the_entry_says_where_the_reader_saw_it() -> None:
    """A glossary entry that defines a word and not where it appears leaves somebody
    knowing what it means and still not knowing what to press."""
    from ops.console.help_page import GLOSSARY

    said = dict(GLOSSARY)["Needs a person"]
    assert "Activity" in said
    assert "pressing it" in said, "it does not say the count is a control"
