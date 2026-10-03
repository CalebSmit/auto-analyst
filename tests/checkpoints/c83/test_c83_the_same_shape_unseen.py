"""C83 - the four pages are one product to a reader who cannot see them.

**P150.** There was no `main` landmark on any of the four pages - a navigation region to
jump to and nothing to jump from it to - and four panel headings welded their title to their
count, so the Runs panel's accessible name was `Runs3`.

What a checkpoint can ask that the phase could not.

The phase fixed what it found, page by page. The property is about the four together:
**a reader who cannot see these pages should meet the same shape on each one.** One way in,
one heading at the top, levels that descend without gaps, and every control carrying a name.
Four files, one shell, and nothing until now asking whether they still agree about any of it.

It also holds the thing a browser measurement found and a test could not: *every* control has
a name. That was swept in the browser while looking for the next thing to improve, came back
clean on all three boards, and was then true of nothing but that afternoon. A measurement
nobody can repeat is a measurement that stops being true quietly, which is what this file is
for.

**One caution it carries.** `textContent` is not an accessible name - a browser inserts
whitespace at a block boundary and `textContent` does not. P150's first sweep read the two
as the same thing and reported three defects that were not there. What can be asked of the
source is the *shape* that produces a name, and that is what is asked here.
"""

from __future__ import annotations

import re

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.help_page import PAGE as HELP
from ui.theme import SHELL

PAGES = ((SETUP, "Setup"), (ACTIVITY, "Activity"), (ANALYTICS, "Analytics"), (HELP, "Help"))


def headings(page: str) -> list[int]:
    """The heading levels a reader meets, in the order they are written."""
    return [int(level) for level in re.findall(r"<h([1-6])[^>]*>", page)]


# ------------------------------------------------------------ one way in, on every page


def test_every_page_offers_the_same_two_landmarks() -> None:
    """A reader navigates by these before reading anything. Four pages that differ here are
    four products."""
    for page, where in PAGES:
        assert len(re.findall(r"<main\b", page)) == 1, f"{where} does not have one main"
        assert len(re.findall(r"<nav\b", page)) == 1, f"{where} does not have one nav"


def test_the_navigation_is_the_shared_one_and_not_a_copy() -> None:
    """Four navs that happen to agree is the state this build is most often wrong about.
    There is one, in the shell, and the pages are served it."""
    assert SHELL.count("<nav") + sum(
        page.split("</style>")[-1].count("<nav") for page, _ in PAGES
    ) >= 4
    for page, where in PAGES:
        body = page[page.index("<main") :]
        assert "<nav" not in body, f"{where} has navigation inside its main content"


def test_every_page_has_one_h1_and_skips_no_level() -> None:
    """A reader who moves by heading jumps from h1 to h2 to h3. A page that goes h1 then h3
    reads as though something is missing, because to them it is."""
    for page, where in PAGES:
        levels = headings(page)
        assert levels.count(1) == 1, f"{where} has {levels.count(1)} top-level headings"
        assert levels[0] == 1, f"{where} opens at h{levels[0]}"
        seen = set()
        for level in levels:
            assert level <= max(seen, default=0) + 1 or level in seen, (
                f"{where} jumps to h{level} from h{max(seen, default=0)}"
            )
            seen.add(level)


# ------------------------------------------------------ and every control carries a name


def test_every_control_on_every_page_has_something_to_be_called() -> None:
    """Swept in the browser once and clean; held here so it stays that way.

    A control is named by its own text, by `aria-label`, or by `title`. A template hole
    counts - it is filled from the data, and whether *that* is empty is the data's business
    rather than the page's.
    """
    nameless = []
    for page, where in PAGES:
        for match in re.finditer(r"<(button|a)\b([^>]*)>(.*?)</\1>", page, re.S):
            tag, attrs, inner = match.groups()
            if tag == "a" and "href" not in attrs:
                continue
            text = re.sub(r"<[^>]+>", "", inner).strip()
            named = bool(text) or "aria-label" in attrs or "title=" in attrs
            if not named:
                nameless.append(f"{where}: <{tag}{attrs[:48]}>")
    assert nameless == [], "a control with nothing to call it:\n" + "\n".join(nameless)


def test_a_control_that_is_only_a_symbol_says_what_it_does() -> None:
    """The map's step and zoom controls are a chevron and a minus sign. Their text is the
    glyph, which is a shape rather than a word, so the name has to come from somewhere.

    The entities have to be unescaped first, which is what the first version of this missed:
    it matched a label of up to three characters and the markup says `&minus;`, which is
    seven. It examined none of the four buttons it was written for and passed.
    """
    import html

    checked = 0
    for match in re.finditer(r"<button([^>]*)>([^<]*)</button>", ACTIVITY):
        attrs, raw = match.groups()
        label = html.unescape(raw).strip()
        if not label or len(label) > 2 or label.isalnum():
            continue
        checked += 1
        assert "aria-label" in attrs or "title=" in attrs, (
            f"a button whose whole label is {label!r} and nothing says what it does"
        )
    assert checked >= 4, (
        f"only {checked} symbol-only controls examined; the map alone has four, so this "
        "has stopped looking at the thing it was written for"
    )


# -------------------------------------------- what is read out, said once for all four


def test_the_same_marks_are_hidden_on_every_page() -> None:
    """The dot is drawn in CSS and carries nothing; the step mark is a tick and carries
    whether a step is done. A page that disagreed about either would be read differently
    from its neighbour for no reason a reader could discover."""
    for page, where in PAGES:
        for found in re.findall(r"<i class=\"dot\"[^>]*>", page):
            assert "aria-hidden" in found, f"{where} reads out a drawn mark"
        for found in re.findall(r"<span class=\"mark\"[^>]*>", page):
            assert "aria-hidden" not in found, f"{where} hides the mark that says what happened"


def test_no_heading_anywhere_opens_an_element_against_a_word() -> None:
    """P150's shape test, over all four pages rather than the two that had the defect -
    because the next count beside a title will be on whichever page needs one next."""
    welded = []
    for page, where in PAGES:
        for heading in re.findall(r"<h[1-6][^>]*>(.*?)</h[1-6]>", page, re.S):
            for match in re.finditer(r"[A-Za-z0-9)}]<(?!/)", heading):
                found = heading[max(0, match.start() - 20) : match.start() + 36]
                welded.append(f"{where}: ...{' '.join(found.split())}")
    assert welded == [], "a heading's name runs together:\n" + "\n".join(welded)
