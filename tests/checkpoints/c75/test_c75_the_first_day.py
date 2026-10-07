"""C75 - a machine nobody has configured, configured from its own dashboard.

Three phases, and what they have in common is how each was found: by using the thing the
way a person about to use it would, on the machine state that person will actually meet.
None of the three was visible from the source, and the suite was green throughout.

* **P135** opened `/admin` against an empty store. The page threw on load and rendered
  nothing, under a banner blaming the network for a server that had answered.
* **P136** measured the same page at a laptop's viewport. The panel a first day is spent in
  was showing 35% of its own content.
* **P137** ran the three reads over documents shaped like the work. Two of them asserted
  things they had not established - a bullet list reported as a sentence missing its full
  stop, and twelve confident questions about ratios that cannot exist.

What a checkpoint can ask that a phase cannot is whether the three agree. They touch one
page, one stylesheet and two of the three reviewer's reads, and the places they overlap are
where a later change will break one by fixing another.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from admin.page import PAGE as SETUP_PAGE
from ops.console.app import PAGE as ACTIVITY
from ui.theme import CSS

ROOT = Path(__file__).resolve().parents[3]


def script(page: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", page, re.S))


def without_comments(text: str) -> str:
    """A comment says what the code must not do, and names the thing it must not do. A
    check that reads them finds every rule it is enforcing and calls each one a breach."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", text)


# ------------------------------------------------- one answer to "is this set up yet"


def test_the_three_pages_agree_on_what_an_empty_machine_looks_like() -> None:
    """P135 split "the configuration" from "is there one". The thing that makes that split
    hold is that nothing anywhere goes back to reading the data for the answer."""
    body = without_comments(script(SETUP_PAGE))
    assert "!SETUP" not in body and "!!SETUP" not in body
    assert "CONFIGURED" in body

    # And the other two consoles never had a configuration document to read, so neither of
    # them should have grown a second way of asking. Asserted because the obvious way to
    # "fix" a missing value on one of them is to copy the pattern from the page that has it.
    for page in (ACTIVITY,):
        assert "CONFIGURED" not in without_comments(script(page)), "a second answer"


def test_a_refusal_is_a_refusal_on_every_page() -> None:
    """`refusal()` is in the shared theme, so marking it was one change for all three. The
    thing worth holding is that no page has since gone back to inferring it."""
    theme = (ROOT / "ui" / "theme.py").read_text(encoding="utf-8")
    found = re.search(r"async function refusal\(response\) \{(.*?)\n\}", theme, re.S)
    assert found, "refusal() is gone"
    assert found.group(1).count("refused: true") == 3, "a return was added without the mark"
    for page in (SETUP_PAGE, ACTIVITY):
        assert "e.code) offline" not in script(page), "a page infers it from the code again"


# ----------------------------------------------- one layout, and the fallback from it


def test_the_fallback_is_written_once_per_dimension_and_not_per_page() -> None:
    """Whatever breakpoints exist live in the theme, so all three consoles fall back
    together. A page-level copy is how two of them would end up behaving differently at the
    same size.

    One dimension now, not two. P136 added a height breakpoint and P142 removed it, having
    made the board's rows as tall as their content at every size - so a short screen needs no
    rule of its own. Width still does: how many columns fit is a question about width.
    """
    assert "@media (max-width:1100px)" in CSS
    assert "@media (max-height" not in CSS, "a height breakpoint is back"

    # A page may carry a breakpoint for a component of its own - the map view moves its
    # side panel to the bottom on a narrow screen, which is about `#dmap` and nothing else.
    # What it may not do is have an opinion about the board, because then two of the three
    # consoles behave differently at the same size and only one of them is in the theme.
    for page in (SETUP_PAGE, ACTIVITY):
        own = page.split("</style>")[0].split(CSS)[-1]
        for block in re.findall(r"@media[^{]*\{(.*?)\n\}", own, re.S):
            for rule in re.findall(r"^\s*([^{\n]+)\{", block, re.M):
                assert rule.strip().startswith("#"), (
                    f"a page's own breakpoint restyles {rule.strip()!r}, which is not its own"
                )


def test_the_board_is_a_grid_whose_rows_fit_what_is_in_them() -> None:
    """It filled the screen exactly until P142 measured what that cost: seven of twenty
    panels hiding content behind an inner scrollbar while eight sat under seventy per cent
    full, on the same screens."""
    assert ".board{display:grid;gap:var(--s3);align-content:start}" in CSS
    # How many rows the board has is a layout decision that has moved twice - P136 gave the
    # checklist a fourth, P172 laid the board out in three bands with nothing spanning a row
    # - and neither moved the thing this test is about. What has to stay true is that a row
    # is as tall as what is in it, which is a question about `min-content` rather than about
    # the count.
    rows = re.search(r"grid-template-rows:\s*repeat\(\d+,\s*min-content\)", SETUP_PAGE)
    assert rows, "the Setup board's rows are no longer sized to what is in them"
    assert "fr" not in rows.group(0), "a row is a share of the screen again"


def test_every_page_that_lays_out_a_board_places_every_area_it_names() -> None:
    """P136 edited a grid template. This is the invariant that makes editing one safe,
    across every page that has one rather than only the one that changed."""
    for page in (SETUP_PAGE, ACTIVITY):
        placed = set(re.findall(r'style="grid-area:([a-z]+)"', page))
        # The quoted row strings of the template and nothing past them. `(.*?)\}\}` ran to
        # the next doubled brace anywhere in the file, which on a page that is not an
        # f-string is most of the page.
        templates = re.findall(r'grid-template-areas:((?:\s*"[^"]*")+)', page)
        if not templates:
            continue
        for template in templates:
            named = set(re.findall(r"[a-z]+", template))
            assert named == placed, f"areas and panels disagree: {named ^ placed}"


# ------------------------------------- one rule about what a read is allowed to assert


def test_each_read_still_says_what_it_could_not_do() -> None:
    """The oldest rule these three share, and the one P137 was an instance of breaking.
    Each of the three reads reports what it could not ask as well as what it found."""
    audit = (ROOT / "tools" / "formula_audit.py").read_text(encoding="utf-8")
    prose = (ROOT / "tools" / "prose_checks.py").read_text(encoding="utf-8")
    ratios = (ROOT / "tools" / "reasonableness.py").read_text(encoding="utf-8")

    assert "unevaluated" in audit, "the audit stopped counting the totals it skipped"
    assert "unread" in prose, "a document that could not be read reads as clean"
    assert "could_not_evaluate" in ratios, "a question nobody asked is no longer reported"


def test_an_impossible_figure_is_not_dressed_as_a_business_question() -> None:
    """The specific form P137 fixed, asserted at the level of the sentence a person reads:
    the two phrasings must not meet on one finding."""
    ratios = (ROOT / "tools" / "reasonableness.py").read_text(encoding="utf-8")
    found = re.search(r"if impossible:(.*?)\n            continue", ratios, re.S)
    assert found, "the impossible-value branch is gone"
    assert "What changed in the business" not in found.group(1)
    assert "cannot produce" in found.group(1)


def test_the_command_that_runs_all_three_still_dispatches_to_all_three() -> None:
    """`aa review` is the one door P135's slash commands and this checkpoint both go
    through, and a read that nothing reaches is the defect this repo names most often."""
    import ast

    tree = ast.parse((ROOT / "tools" / "aa.py").read_text(encoding="utf-8"))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    } | {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    reached: set[Any] = called | imported
    for read in ("audit", "check", "run_questions"):
        assert read in reached, f"nothing in aa.py reaches the {read} read"
