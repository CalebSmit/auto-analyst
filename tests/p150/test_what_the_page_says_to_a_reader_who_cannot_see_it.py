"""P150: two things the consoles did not say to a reader who cannot see them.

**There was no `main` landmark on any of the four pages.** The shell emits a `nav` inside
the chrome and every page then opened a plain `div.wrap`, so a screen reader had a
navigation region to jump to and nothing to jump *from* it to. A skip link would have had no
target to point at. Measured across the three boards and the help page: one `nav`, seven
`header`s, **zero** `main`s.

**And a panel heading welded its title to its count.** `<h2>Runs<span class="of">3</span>`
with the span at `display:inline` - so no browser inserts anything between them and the
heading's accessible name is `Runs3`, heard as *"Runs three"*. The same shape was on
Engagements, Waiting on a person and Alerts.

**Three of my four findings here were measurement artefacts, and that is worth recording.**
The first sweep read `textContent` as a proxy for an accessible name and reported the Setup
progress block as *"2 steps leftNext: Connect the AI model 9 of 11done"*. It is not: the
`b` inside it computes to `display:block` and so does `.of.done`, and a browser inserts
whitespace at a block boundary. `textContent` does not. Only the heading count is genuinely
inline, which is why it is the only one this phase changed - the instrument has to be the
thing the name is computed from, and here that meant checking `display` before believing the
string.

The dots are the small third thing. `<i class="dot">` is empty and drawn in CSS, so it was
already contributing nothing to a name; it carries `aria-hidden` now so that stays true if
somebody ever puts a character in it.
"""

from __future__ import annotations

import re

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.help_page import PAGE as HELP
from ops.console.map_view import MAP_HTML
from ui.theme import CSS, SHELL

PAGES = ((SETUP, "Setup"), (ACTIVITY, "Activity"), (ANALYTICS, "Analytics"), (HELP, "Help"))


# ------------------------------------------------------------- the landmark to jump to


def test_every_page_has_exactly_one_main() -> None:
    """Zero is a page a reader cannot get into; two is a page where `main` has stopped
    meaning the main thing."""
    for page, where in PAGES:
        opens = len(re.findall(r"<main\b", page))
        assert opens == 1, f"{where} has {opens} main landmarks"
        assert page.count("</main>") == 1, f"{where} does not close its main"


def test_the_board_is_inside_the_main_and_the_chrome_is_not() -> None:
    """A landmark is only worth having if it contains the thing it names. The chrome is the
    nav and the identity; what a reader came for is the board."""
    for page, where in PAGES:
        body = page[page.index("<main") : page.index("</main>")]
        assert "<nav" not in body, f"{where} puts the navigation inside the main content"
        assert 'class="board"' in body or 'class="page-head"' in body, (
            f"{where}'s main holds neither the board nor the page's own heading"
        )
        before = page[: page.index("<main")]
        assert "<nav" in before, f"{where} has no navigation before its main"


def test_the_main_is_the_wrapper_rather_than_a_new_element_around_it() -> None:
    """The content wrapper already existed and already had the layout on it. Wrapping it in
    a second element would have meant two boxes where the sheet expects one."""
    assert '<main class="wrap">' in SHELL or all(
        '<main class="wrap">' in page for page, _ in PAGES
    ), "the main is not the wrapper the sheet sizes"
    assert re.search(r"(?:^|\n)\.wrap\{", CSS), "the wrapper has no rule any more"
    assert "div.wrap" not in CSS, "a rule still expects the wrapper to be a div"


# --------------------------------------------------- a heading, and the count beside it


def test_no_heading_opens_an_element_straight_after_a_word() -> None:
    """Swept over the shape rather than over the text, because the text is not there.

    The count is written in by script, so the markup only ever holds `<span class="of"
    id="n-runs"></span>` - empty. A sweep that looked for a letter beside a digit in the
    served page would have found nothing to object to on the day the page read `Runs3`, and
    that is what the first version of this test did: both halves of the revert harness
    passed on the welded markup. What can be seen statically is the shape that causes it -
    a word, and then an element opening with nothing between them.
    """
    welded = []
    for page, where in PAGES:
        for heading in re.findall(r"<h[123][^>]*>(.*?)</h[123]>", page, re.S):
            for match in re.finditer(r"[A-Za-z0-9)}]<(?!/)", heading):
                found = " ".join(heading[max(0, match.start() - 24) : match.start() + 40].split())
                welded.append(f"{where}: ...{found}")
    assert welded == [], (
        "a heading opens an element with no space before it, so its name runs together:\n"
        + "\n".join(welded)
    )


def test_the_four_that_carried_a_count_are_separated_by_name() -> None:
    """Named one by one, because the sweep above passes just as happily on a page with no
    counts left on it."""
    for page, title in ((ACTIVITY, "Runs"), (ACTIVITY, "Waiting on a person"),
                        (ACTIVITY, "Alerts"), (SETUP, "Engagements")):
        assert f'<h2>{title} <span class="of"' in page, f"{title} is welded to its count again"


def test_the_count_is_still_inline_which_is_why_the_space_is_needed() -> None:
    """The fact the fix rests on, and the one the first measurement got wrong. If the count
    ever becomes a block the browser inserts its own separator - and this fails, so somebody
    reads the reason rather than finding a stray space."""
    rule = re.search(r"\.card h2 \.of\{([^}]*)\}", CSS)
    assert rule, "the count beside a heading has no rule"
    assert "display:block" not in rule.group(1), (
        "the count is a block now; a browser separates it and the space in the markup is "
        "doing nothing - see this test's docstring before removing it"
    )


# ------------------------------------------ what is read out, and what is only drawn


def test_a_mark_that_is_only_drawn_is_not_read_out() -> None:
    """`<i class="dot">` is empty and painted in CSS. It contributed nothing to a name
    already; saying so keeps that true if a character ever lands in it."""
    stray = []
    for page, where in [*PAGES, (MAP_HTML, "the map")]:
        for found in re.findall(r"<i class=\"dot\"[^>]*>", page):
            if "aria-hidden" not in found:
                stray.append(f"{where}: {found}")
    assert stray == [], "a drawn mark is read out:\n" + "\n".join(stray)


def test_the_mark_that_carries_meaning_is_still_read() -> None:
    """The other half, and the reason this is not just `aria-hidden` everywhere: the step
    marks carry a tick or a number, which is the only thing saying whether a step is done.
    """
    assert 'class="mark"' in SETUP, "the setup steps have lost their marks"
    assert 'class="mark" aria-hidden' not in SETUP, (
        "the tick that says a step is done has been hidden from the reader who most needs it"
    )
    pill = re.search(r'<span class="pill[^"]*"[^>]*><i class="dot"[^>]*></i>([^<]*)', ACTIVITY)
    assert pill, "a state pill no longer carries its own word"


def test_the_pages_still_say_what_they_said(  ) -> None:
    """A landmark and a space are the whole change. If either page lost content to it, that
    would show here before it showed on a screen."""
    for page, where in PAGES:
        assert "</main>" in page and 'class="top"' in page, where
        assert page.count('<section class="card') >= 1, f"{where} has lost its panels"
