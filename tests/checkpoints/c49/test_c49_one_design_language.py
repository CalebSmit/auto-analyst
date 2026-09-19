"""C49 - One design language, still one.

P81 reviewed one page and changed the stylesheet all four are built from. Nine components
were added or altered, and two of them - `.step` and `.steps` - were already worn by the
activity console and the help page, which nobody looked at while the rail was being drawn.

That is the shape of change this checkpoint exists for. A page's own tests read that page's
own markup, so a stylesheet edit that improves one screen and ruins another passes every
one of them. What the phase could not check about itself is here: that the components it
introduced belong to one language rather than being local fixes with general names, and
that the pages it did not look at still get a sheet that suits them.

`test_a_page_that_never_heard_of_this_change_still_gets_a_sequence` is the one worth
having. The rail was drawn for a seven-step checklist that marks steps done; the help
page's six steps mark nothing, and if the rail had been keyed to `.done` it would have
rendered there as a rule hanging off the last mark into empty space.
"""

from __future__ import annotations

import re

import pytest

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.help_page import PAGE as HELP
from ui.theme import CSS

PAGES = {"setup": SETUP, "activity": ACTIVITY, "analytics": ANALYTICS, "help": HELP}

# Everything P81 added to the sheet or changed in it.
INTRODUCED = (
    ".excerpt.path",
    ".excerpt.said",
    ".drop",
    ".code-area",
    ".r.lede",
    ".note.tight",
    ".sm",
    ".aside",
    "button.primary.danger",
    ".progress",
    ".cols.two.ask",
)


def body_of(page: str) -> str:
    """A page without the stylesheet it inlines."""
    return page[page.rindex("</style>") :]


def classes_worn(page: str) -> set[str]:
    """Every class name the page actually puts on an element.

    Read out of `class="..."` rather than searched for as a word, because the loose version
    of this passed for `.drop` on the strength of `id="drop"` and for `.danger` on the
    strength of `danger: true` in a dialog's arguments - which is the check having no
    opinion at all. A value may be part template expression, so the expressions are reduced
    to the string literals inside them: `class="primary${danger ? ' danger' : ''}"` wears
    `primary` and `danger` and nothing called `danger ? ' danger' : ''`.
    """
    def literals(expression: re.Match[str]) -> str:
        return " ".join(re.findall(r"'([^']*)'", expression.group(1)))

    worn: set[str] = set()
    for value in re.findall(r'class="([^"]*)"', body_of(page)):
        plain = re.sub(r"\$\{([^}]*)\}", literals, value)
        worn.update(t for t in plain.split() if re.fullmatch(r"[\w-]+", t))
    return worn


def page_style(page: str) -> str:
    """A page's own style block, with the shared sheet it inlines taken back out."""
    inner = page[page.index("<style>") + len("<style>") : page.rindex("</style>")]
    return inner.replace(CSS, "")


def rule(selector: str) -> str:
    """One rule out of the sheet, by its exact selector."""
    found = re.search(re.escape(selector) + r"\{([^}]*)\}", CSS)
    assert found, f"{selector} is not in the stylesheet"
    return found.group(1)


# -------------------------------------------------- the pages nobody looked at


@pytest.mark.parametrize("name", sorted(PAGES))
def test_every_page_still_renders_whole(name: str) -> None:
    page = PAGES[name]
    assert page.lstrip().startswith("<!doctype html>")
    assert "<title>" in page and "</script>" in page
    assert "<h1>" in page, "the page has no heading"


def test_a_page_that_never_heard_of_this_change_still_gets_a_sequence() -> None:
    """The help page's six steps and the activity page's four wear `.step` and mark none of
    them done. The rail was drawn for a checklist that does, so if it had been keyed to
    `.done` - or if the last mark's rule had been - those pages would have got a line
    hanging off the bottom into nothing.

    They are numbered sequences, so the rail is right for them; what has to be true is that
    it is right for them without either page saying anything."""
    for name in ("help", "activity"):
        body = body_of(PAGES[name])
        assert '<div class="steps"' in body, f"{name} no longer uses the shared stepper"
        assert '<div class="step">' in body, f"{name} marks steps done now"
    assert ".step:last-child::before{display:none}" in CSS, "the rail would run past the end"
    assert "display:none" in rule(".step:last-child::before")


def test_the_rail_needs_nothing_of_a_page_but_the_markup_it_already_had() -> None:
    """`.steps` carries `--mark`, so a page that only ever wrote `<div class="steps">` gets
    a rail that lines up. Had the variable been put on `:root` or on the setup page, the
    other two would have drawn theirs against an undefined length."""
    assert "--mark:" in rule(".steps"), "the mark size is not where every stepper can see it"
    assert "--mark" not in page_style(SETUP), "the setup page defines it for itself"


@pytest.mark.parametrize("name", sorted(PAGES))
def test_no_page_was_left_setting_a_value_the_sheet_now_owns(name: str) -> None:
    """Nine things moved out of inline styles. A page still writing one of them by hand
    would look right and stop following the sheet."""
    body = body_of(PAGES[name])
    assert "font-family:var(--mono);font-size:.86rem" not in body
    assert "text-transform:none;letter-spacing:0" not in body, "an un-shouted label, by hand"
    assert "background:var(--bad);border-color:var(--bad)" not in body, "a danger button, by hand"


# -------------------------------------------------- the components are a language


@pytest.mark.parametrize("selector", INTRODUCED)
def test_every_component_introduced_is_built_from_the_scales(selector: str) -> None:
    """A component with a general name and a hand-picked value is a local fix that will be
    reached for generally. The exceptions are the ones the scales do not cover: a hairline
    or a dashed border is 1-3px whatever the type is set at, and `min(22rem,45vh)` is a
    ceiling against the viewport rather than a step in a rhythm."""
    declared = rule(selector)
    allowed = (
        r"\b(?:border|box-shadow|outline)[^;]*",  # rules and hairlines
        r"min\([^)]*\)",  # a ceiling against the viewport
        r"var\(--[\w-]+\)",  # the scales themselves
    )
    left = declared
    for pattern in allowed:
        left = re.sub(pattern, "", left)
    stray = re.findall(r"(?<![\w(-])(\d*\.?\d+)(px|rem|em)\b", left)
    assert stray == [], f"{selector} chooses its own {['' .join(s) for s in stray]}"


@pytest.mark.parametrize("selector", INTRODUCED)
def test_every_component_introduced_is_worn_by_something(selector: str) -> None:
    """A rule nothing wears is not a component, it is a leftover - and this build's most
    repeated defect is something built and wired to nothing."""
    everywhere: set[str] = set()
    for page in PAGES.values():
        everywhere |= classes_worn(page)
    # A compound like `.primary.danger` is applied in two pieces, so the tokens are checked
    # one at a time rather than as the joined string. A leading element name is not a class
    # - `button.primary.danger` asks about `primary` and `danger`, not about `button`.
    # `.excerpt.path` splits to ['', 'excerpt', 'path']; `button.primary.danger` to
    # ['button', 'primary', 'danger']. Dropping the first leaves the classes either way.
    tokens = selector.split()[-1].split(".")[1:]
    assert tokens, f"{selector} names no class"
    for token in tokens:
        assert token in everywhere, f"{selector} is in the sheet and no page wears {token!r}"


def test_the_sheet_did_not_gain_a_second_way_to_say_something_it_already_said() -> None:
    """`.sm` is one step down from body. `--t-sm` already existed and so did `.r .sub`, so
    the thing to check is that it was added as a use of the scale rather than as a second
    small size beside it."""
    assert rule(".sm") == "font-size:var(--t-sm)"
    assert rule(".note.tight") == "margin-top:0"


# -------------------------------------------------- and the invariants still hold


@pytest.mark.parametrize("name", sorted(PAGES))
def test_no_page_invents_a_colour(name: str) -> None:
    """P46's rule, re-run here because P81 touched the one file that could break it for
    every page at once."""
    assert re.findall(r"#[0-9a-fA-F]{6}\b", body_of(PAGES[name])) == []


def test_the_danger_button_is_the_palettes_plum_rather_than_a_red() -> None:
    """The sheet's own note: meaning is carried by three of the firm's colours rather than
    a traffic light, so that a dialog about ending something reads as information and not
    as an alarm somebody bolted on."""
    declared = rule("button.primary.danger")
    assert "var(--bad)" in declared
    for red in re.findall(r"#([0-9a-fA-F]{6})", declared):
        r, g, b = (int(red[i : i + 2], 16) for i in (0, 2, 4))
        assert b > g, f"#{red} is a red, not a plum"


def test_one_scale_still_and_nothing_off_it() -> None:
    for name in ("s1", "s2", "s3", "s4", "s5", "s6", "s7"):
        assert f"--{name}:" in CSS
    for name in ("t-display", "t-title", "t-subtitle", "t-body", "t-sm", "t-xs", "t-label"):
        assert f"--{name}:" in CSS
