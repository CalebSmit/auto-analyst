"""P144: six pieces of text below the contrast floor this sheet sets for itself.

Measured in the browser, every text element on all three consoles against the surface
actually behind it - 354 on Activity, 244 on Setup, 108 on Analytics:

    2.63:1   the "N needs a person" count          --gold on white, 12.5px
    2.64:1   "at step <id>", where a run failed     --ink-4 on the diagnostic wash
    2.86:1   the engagement / scope / run id line   --ink-4 on white
    2.86:1   a finding's rule and its formula       --ink-4 on white
    2.86:1   "Did not run: ..." on the audit        --ink-4 on white
    2.86:1   "not yet", where a figure would be     --ink-4 on white, 13.8px

The floor is 4.5:1 and the sheet states it in prose, about itself:

    Ink is measured, not chosen. Body text sits at 12:1 against the paper, secondary at
    7:1 and the quiet grey at 4.6:1 - the floor for normal text, not a preference.
    `--ink-4` is below it on purpose and is for a placeholder, a disabled control or a
    node no run reached; nothing a person has to read is set in it.

Three of the six are the things this build most insists on being able to read: a locator,
the formula behind a finding, and the list of checks that did not run. And the gold one
carried the most important sentence on the most-looked-at screen.

**Why the existing test did not catch them.** `tests/p46` checks `--ink-4` against four
hand-written selectors - `.card .why`, `.metric .c`, `.r .d`, `.note` - and the real uses
were in none of them. A list of four is the shape that goes stale. This sweeps every use in
the sheet and in all three pages, and names the exceptions the theme itself allows.
"""

from __future__ import annotations

import re
from pathlib import Path

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ui.theme import CSS, SHELL

ROOT = Path(__file__).resolve().parents[2]
SURFACES = ((CSS, "the sheet"), (SETUP, "Setup"), (ACTIVITY, "Activity"), (ANALYTICS, "Analytics"))

# The purposes the sheet names for the decorative grey, each with the rule that wears it.
# An entry here is a claim that nobody reads this text; adding one without that being true
# is how the token spread in the first place.
MAY_BE_INK_4 = {
    "input::placeholder": "a placeholder, which is what the token is for",
    ".node": "a node no run reached - named rather than drawn, and not read",
    "details>summary::before": "the disclosure chevron, which is a mark rather than words",
    ".mn:not(.on)": "the same node on the full map, for the same reason",
    'button[aria-pressed="false"]': "a legend filter that is switched off - a disabled control",
}


def tokens() -> dict[str, str]:
    """Every token resolved to a literal, following `var()` one hop at a time.

    `--gold` is `var(--brand-s3)` and `--warn` is `var(--gold-ink)`; reading only the hex
    declarations would silently leave both out of the measurement, which is how a colour
    stops being measured without anybody removing a test.
    """
    block = CSS[CSS.index(":root{") : CSS.index("}", CSS.index(":root{"))]
    raw = dict(re.findall(r"--([\w-]+):\s*([^;]+);", block))
    resolved: dict[str, str] = {}
    for _ in range(4):
        for name, value in raw.items():
            value = value.strip()
            ref = re.fullmatch(r"var\(--([\w-]+)\)", value)
            if ref and ref.group(1) in resolved:
                resolved[name] = resolved[ref.group(1)]
            elif value.startswith("#"):
                resolved[name] = value
    return resolved


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    parts = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# --------------------------------------------- the floor, and which tokens are under it


def test_the_tokens_under_the_floor_are_the_ones_the_sheet_says_are() -> None:
    """Measured, so the list of tokens a reader may not be asked to read is derived rather
    than remembered."""
    t = tokens()
    under = {
        name
        for name in ("ink", "ink-2", "ink-3", "ink-4", "gold", "warn", "good", "bad")
        if name in t and contrast(t[name], t["bg"]) < 4.5
    }
    assert under == {"ink-4", "gold"}, f"the tokens under the floor on paper are {under}"


def test_the_gold_has_a_darker_twin_made_for_text() -> None:
    """`--warn` is `--gold-ink`. The accent is for a hairline and a chip on navy; the ink
    is for a word on paper, and the two are not interchangeable."""
    t = tokens()
    assert contrast(t["gold-ink"], t["bg"]) >= 4.5, "the text gold is under the floor too"
    assert contrast(t["gold"], t["bg"]) < 4.5, "then the distinction has stopped mattering"


# ------------------------------------------------------ swept, rather than listed


def uses(token: str) -> list[tuple[str, str]]:
    """Every `color:var(--token)` anywhere, with the rule or the markup around it."""
    found = []
    for text, where in SURFACES:
        for match in re.finditer(rf"color:\s*var\(--{re.escape(token)}\)", text):
            start = max(0, match.start() - 220)
            found.append((where, text[start : match.start()]))
    return found


def test_the_decorative_grey_is_used_only_for_what_the_sheet_says_it_is_for() -> None:
    """The sweep the hand-written list of four selectors was standing in for.

    Each remaining use has to be traceable to a named purpose. The check is deliberately
    crude - does the context mention one of the allowed selectors - because the alternative
    is a second list that goes stale the same way.
    """
    stray = []
    for where, before in uses("ink-4"):
        if not any(selector in before for selector in MAY_BE_INK_4):
            stray.append(f"{where}: ...{before[-90:].strip()}")
    assert stray == [], "the decorative grey on something a person reads:\n" + "\n".join(stray)


def test_the_accent_gold_is_never_a_word_on_paper() -> None:
    """It may be a hairline, a chip on the navy chrome, and a focus ring. On white it is
    2.63:1, and it was carrying the count of runs that have stopped."""
    stray = []
    for where, before in uses("gold"):
        if ".chip{" not in before and ".top " not in before and "--gold)" not in before[-12:]:
            stray.append(f"{where}: ...{before[-90:].strip()}")
    assert stray == [], "the accent gold set as text:\n" + "\n".join(stray)


def test_the_chip_is_the_one_place_gold_is_text_and_it_sits_on_navy() -> None:
    """Gold on the navy chrome measures 5.6:1. The rule is right where it is and would be
    wrong on a card, so where it is used is part of the claim."""
    assert ".chip{color:var(--gold)" in CSS
    for page, where in ((SETUP, "Setup"), (ACTIVITY, "Activity"), (ANALYTICS, "Analytics")):
        for chip in re.findall(r'class="chip"[^>]*', page):
            assert "chrome-right" in page, f"{where}: a chip outside the chrome: {chip[:60]}"


# --------------------------------------- and the pages name a class rather than a colour


def test_the_three_that_moved_are_named_in_the_sheet() -> None:
    for name in ("wants-a-person", "quiet-note", "not-measured"):
        assert f".{name}{{color:var(--ink-3)}}" in CSS or f".{name}{{color:var(--warn)}}" in CSS, (
            f".{name} is used by a page and has no rule"
        )


# Each of the six, as the thing a person reads and the class it has to be carrying. The
# markup around them has moved twice since - P172 rewrote the diagnostic and P173 took the
# hand-written lengths off the pages - so each is found by its own words and asked what
# class it is in, rather than by a spelling of the whole element. A sweep that passes
# because the markup moved is a sweep that has stopped watching what it was written for;
# one that fails because the markup moved is watching the markup.
THE_SIX = (
    ("the count of runs that need somebody", ACTIVITY, "wants-a-person", None),
    ("where a run failed", ACTIVITY, "code", "at step "),
    ("the rule behind a finding", ACTIVITY, "quiet-note", "${esc(f.check)}"),
    ("the checks that did not run", ACTIVITY, "quiet-note", "Did not run: "),
    ("a figure nobody has measured", SHELL, "not-measured", "not yet"),
)


def enclosing_class(markup: str, at: int) -> str:
    """The class of the element that actually contains the text at `at`.

    Walking back to the nearest `class="..."` is not the same question, and the difference
    is the whole of what this file checks: with a window of a couple of hundred characters
    the sentence can be moved *out* of the readable class and still have one nearby. So the
    tags before it are walked with a depth counter, and the first opening tag still open is
    the one whose colour the words are drawn in.
    """
    depth = 0
    for tag in reversed(list(re.finditer(r"<(/?)(\w+)([^>]*)>", markup[:at]))):
        if tag.group(1):
            depth += 1
        elif depth:
            depth -= 1
        else:
            found = re.search(r'class="([^"]*)"', tag.group(3))
            return found.group(1) if found else ""
    return ""


def test_each_of_the_six_is_fixed_where_it_was() -> None:
    """Named one by one, because a sweep over the tokens cannot tell that *this* sentence is
    the one that used to be unreadable."""
    for what, page, klass, words in THE_SIX:
        # Comments out first: every one of these is explained in prose beside the code that
        # draws it, and the prose contains the words being looked for.
        drawn = re.sub(r"/\*.*?\*/", "", page, flags=re.S)
        assert f'class="{klass}' in drawn, f"{what} no longer carries a class at all"
        if words is not None:
            holder = enclosing_class(drawn, drawn.index(words))
            assert klass in holder.split(), (
                f"{what} is drawn inside class={holder!r} rather than {klass!r}"
            )
    # And the id line, which is a rule rather than a piece of markup.
    mono = re.search(r"\.r \.sub\.mono\{([^}]*)\}", CSS)
    assert mono and "var(--ink-3)" in mono.group(1), "the id line is back on the decorative grey"
