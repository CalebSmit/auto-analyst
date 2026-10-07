"""P173 - every box, every target, every name.

A sweep over every text node, control and box the four pages paint, at 1366 and at 1900,
asking the three things a person notices and a reader of the source does not: is anything
clipped or pushed out of the panel that paints it, is anything below the contrast floor the
sheet sets for itself, and is anything too small to hit. What it found:

* **One row shattered.** On the Setup page's *All sixteen checks* list, the detail of the
  model-adapter check is a sentence about a thousand pixels long, and `.r .sub` forced it to
  one line. It took the row with it: the label beside it is `flex:1;min-width:0` and *will*
  shrink, so it was crushed to one word a line and ran eleven lines tall, and the check's own
  status pill was pushed 630px past a panel that clips its overflow - so the one check that
  tells a new machine its model is a replay adapter showed no status at all. Nine places had
  already worked around that `nowrap` by hand, which is the declaration being wrong.
* **Ninety-eight names under the floor.** The Run trace panel draws the design's nodes, and
  the ones a run never reached were set in `--ink-4` at 2.86:1 - a token this sheet reserves,
  in its own words, for "a placeholder, a disabled control or a node no run reached". The
  third of those was wrong, and it was the one with ninety-eight instances.
* **Seventeen controls under 24px.** The five actions on an engagement row measured 20px and
  sit a few pixels apart, so neither target-size exception applied to any of them.
* **Ten sizes off a scale that says nothing is off it.** `--t-title` was declared and worn by
  nothing while three headings a few millimetres apart each chose their own, and eight bare
  pixel lengths sat on a page whose root is fluid - which makes them *proportionally smaller*
  on the bigger monitor they had more room on.

Each is asked here as a question about the source, so it can be checked without a browser;
`tests/checkpoints/c98` asks the same of what the server actually serves.
"""

from __future__ import annotations

import re

import pytest

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.help_page import PAGE as HELP
from ops.console.map_view import MAP_STYLE
from tests.reading import page_code
from ui.theme import CSS

PAGES = {"Setup": SETUP, "Activity": ACTIVITY, "Analytics": ANALYTICS, "Help": HELP}
SHEETS = CSS + MAP_STYLE


def own_style(page: str) -> str:
    """What a page adds to the two stylesheets it is served."""
    head = page.split("</style>")[0]
    for shared in (CSS, MAP_STYLE):
        head = head.replace(shared, "")
    return head


def body_of(page: str) -> str:
    return page[page.rindex("</style>") :]


def rule(selector: str, sheet: str = CSS) -> str:
    at = re.compile(r"(?:^|[,}])\s*" + re.escape(selector) + r"\s*(?=[,{])", re.M)
    for found in at.finditer(sheet):
        brace = sheet.index("{", found.end())
        return sheet[brace + 1 : sheet.index("}", brace)]
    raise AssertionError(f"{selector} is not in the stylesheet")


def declarations(text: str) -> str:
    """CSS with its comments taken out. Every measurement this phase made is written down
    beside the rule it explains, and a sweep that read `3,750px tall` as a declaration would
    forbid recording what was measured."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


# ----------------------------------------------------------------- every name


def test_no_type_size_anywhere_is_a_bare_length() -> None:
    """The sheet's own claim - *two scales, and nothing off them* - was enforced on the
    pages and never on the sheet. The one exception is the fluid root, which is a `clamp`
    in pixels because that is the thing the whole scale is measured from."""
    stray = []
    for name, text in (("the theme", CSS), ("the map", MAP_STYLE)):
        for found in re.finditer(r"font(?:-size)?\s*:\s*([^;}]+)", declarations(text)):
            value = found.group(1)
            if "clamp(" in value:
                continue
            size = re.search(r"(?<![\w(-])\d*\.?\d+(px|rem|em)\b", value)
            if size:
                stray.append(f"{name}: {value.strip()[:60]}")
    assert stray == [], "a type size is chosen by eye rather than named:\n" + "\n".join(stray)


def test_the_scale_has_no_dead_step_and_the_headings_share_one() -> None:
    """`--t-title` was declared and used nowhere, while a panel's heading took 1.24rem, a
    dialog's 1.32 and the wordmark 1.3. A scale with a dead step and three live sizes outside
    it is the same thing as having no scale."""
    for step in ("t-display", "t-title", "t-subtitle", "t-body", "t-sm", "t-xs", "t-label"):
        assert f"--{step}:" in CSS, step
        assert f"var(--{step})" in SHEETS, f"--{step} is declared and worn by nothing"
    for selector in (".card h2", ".modal>.card h2", ".brand b"):
        assert "var(--t-title)" in rule(selector), f"{selector} chooses its own heading size"


def test_the_one_size_off_the_text_ratio_says_why_it_is_off_it() -> None:
    """`--t-figure` is deliberate and the sheet has to say so, because the next person to
    find a size outside the scale will copy whichever answer is written down."""
    assert "--t-figure:" in CSS and "var(--t-figure)" in CSS
    assert "subject of a page rather than text on it" in CSS


@pytest.mark.parametrize("name", sorted(PAGES))
def test_no_page_sets_a_type_size_or_a_bare_pixel_length(name: str) -> None:
    """Eight bare pixel lengths sat in the Analytics board's own markup - `padding:9px 0`,
    `margin:0 0 8px` - on a page whose root is fluid. P81 wrote down exactly this defect:
    a length in pixels does not follow the type, so it gets *proportionally smaller* on the
    bigger monitor it had more room on."""
    page = PAGES[name]
    for where, text in (("its own rules", own_style(page)), ("an element", body_of(page))):
        text = declarations(text)
        assert not re.search(r"style=\"[^\"]*font-size", text), (
            f"{name} sets a type size on {where}"
        )
        stray = [
            found.group(0)
            for found in re.finditer(r"style=\"[^\"]*?(?<![\w(-])\d+px[^\"]*\"", text)
        ]
        assert stray == [], f"{name} writes a pixel length on {where}: {stray[:3]}"


# ------------------------------------------------------------------ every box


def test_a_row_that_holds_a_sentence_wraps_it() -> None:
    """The defect, said as a property. `.sub` is the one place a row puts text beside the
    label, and it held `white-space:nowrap` from the day the first thing in it was a
    timestamp."""
    declared = rule(".r .sub")
    assert "nowrap" not in declared, "a sub is held to one line again"
    assert "overflow-wrap" in declared, "a sub with no break opportunity in it still overflows"


@pytest.mark.parametrize("name", sorted(PAGES))
def test_no_page_is_still_overriding_the_sheet_by_hand(name: str) -> None:
    """Nine `white-space:normal` written on elements, in two files, were the sheet's default
    being fought one element at a time. A tenth would mean the default drifted back."""
    assert "white-space:normal" not in body_of(PAGES[name]), (
        f"{name} overrides the sheet's wrapping on an element"
    )


def test_the_check_list_has_the_same_shape_as_the_findings_above_it() -> None:
    """One kind of thing, one row shape: what it is in bold, what it says underneath, one
    pill on the right. The check list put the detail *beside* the label instead."""
    js = page_code(SETUP)
    rows = js[js.index("All ${p.checks.length} checks") :]
    rows = rows[: rows.index("</details>")]
    assert '<span class="d">' in rows, "a check's detail is still beside its label"
    assert '<span class="sub">' not in rows, "a check's detail is still in a sub"
    assert rows.count('class="pill') == 1, "a check row carries more than one pill"


def test_the_clients_name_is_the_thing_that_keeps_its_width() -> None:
    """Three items shared a 285px column and the one that lost was the client's name -
    squeezed to 55px and set three lines tall, one word each. It is the reason anybody is
    reading the row."""
    head = rule(".grp-head")
    assert "flex-wrap:wrap" in head, "the meta cannot move to a second line, so the name gives way"
    name = rule(".grp-head b")
    assert "flex:0 0 auto" in name, "the name can be squeezed again"
    assert "text-overflow:ellipsis" in name and "nowrap" in name, (
        "a name too long for the column should end in an ellipsis, not break mid-word"
    )


# --------------------------------------------------------------- every target


def test_the_target_size_is_one_token_and_the_base_control_wears_it() -> None:
    """Set on the base rather than on the variants, so a variant cannot be born too small -
    which is how `.small` and `.quiet` came to be 20px while the control they modify was 33.
    """
    assert "--hit:24px" in CSS
    base = rule("button")
    assert "min-height:var(--hit)" in base and "min-width:var(--hit)" in base
    assert "inline-flex" in base, (
        "a minimum height on an inline-block leaves the label at the top of the extra space"
    )
    assert "ergonomic constant" in CSS, "the one reason this is in pixels is not written down"


def test_a_control_the_page_hides_is_still_hidden() -> None:
    """The regression that came with the line above, found by looking at the board: `[hidden]`
    is a `display:none` the user-agent sheet makes, and a `display` of our own outranks it.
    Three buttons the pages hide by attribute came back the moment controls got one."""
    assert "button[hidden],.btn[hidden]{display:none}" in CSS
    assert CSS.index("display:inline-flex", CSS.index("button,.btn{")) < CSS.index(
        "button[hidden]"
    ), "the restoring rule has to come after the display that broke it"


def test_a_line_that_is_only_a_link_is_a_target_too() -> None:
    """`profile: 3 things missing` is the only way to reach the profile from that row, and it
    is the whole line rather than a link inside a sentence - which is the case the target-size
    exception does not cover. It measured 13px."""
    assert "min-height:var(--hit)" in rule(".r .why-line a")


def test_the_one_live_control_in_the_chrome_is_big_enough_to_press() -> None:
    assert "min-height:var(--hit)" in rule(".chip")
    assert "border-bottom" in rule(".chip>span"), (
        "the rule that marks it pressable should stay under the word rather than around the "
        "reach the minimum height adds"
    )


# ------------------------------------------------- nothing a person reads is faint


def test_the_quiet_ink_is_worn_only_by_things_nobody_reads() -> None:
    """`--ink-4` measures 2.86:1 and the sheet keeps it for a placeholder, a disabled control
    and a decorative marker. A node of the design is none of those: reading which parts a run
    went through is the whole purpose of the panel that draws them."""
    worn = []
    for text in (CSS, MAP_STYLE):
        for found in re.finditer(r"([^{}]+)\{([^}]*var\(--ink-4\)[^}]*)\}", declarations(text)):
            worn.append(found.group(1).strip().replace("\n", " "))
    allowed = ("::placeholder", "summary::before", "#dmap.focused", "aria-pressed")
    stray = [s for s in worn if not any(ok in s for ok in allowed)]
    assert stray == [], "the placeholder ink is carrying text a person has to read:\n" + "\n".join(
        stray
    )
    assert "color:var(--ink-3)" in rule(".node"), "an unreached node is faint again"


def test_what_tells_an_unreached_node_apart_was_never_the_ink() -> None:
    """The distinction this whole panel exists to make survives the change because it was
    never carried by how faint the name was: every other state has a wash and a hairline, and
    an unreached node has neither."""
    assert "background:transparent" in rule(".node") and "box-shadow:none" in rule(".node")
    for state in (".node.used", ".node.passed", ".node.failed", ".node.active"):
        declared = rule(state)
        assert "background:" in declared and "box-shadow:inset" in declared, state


# ------------------------------------------------------------- said once, and well


def test_a_diagnostic_leads_with_what_happened() -> None:
    """Two internal identifiers set in plum and bold above the one line that said anything a
    person could act on. The plum rule down the left is what marks this as a diagnostic."""
    js = page_code(ACTIVITY)
    row = js[js.index("function diagRows(") :]
    row = row[: row.index(".join('');")]
    assert row.index('class="msg"') < row.index('class="code"'), "the codes still come first"
    assert "color:var(--ink)" in rule(".diag .d-row .msg")
    assert "var(--bad)" not in rule(".diag .d-row .code"), "the code is still shouting"
    assert "var(--bad)" in rule(".diag .d-row"), "and the rule that marks it is gone"


def test_a_quarantined_run_says_the_word_once() -> None:
    """The pill, then `quarantined: qc`, then the diagnostic's own `step.quarantined` - three
    vocabularies for one fact in sixty pixels, and only the last named a cause."""
    js = page_code(ACTIVITY)
    block = js[js.index("const diagnostic = whyItStopped(run);") :]
    block = block[: block.index("<dl class=")]
    assert "if (diagnostic) return says + diagnostic;" in block, (
        "the state reason is drawn beside the diagnostic again"
    )
    assert "run.state_reason" in block, "a run with no diagnostic has to fall back to it"


def test_a_row_carries_one_pill() -> None:
    """The sheet's own note. `no verdict` and `in progress` are notes about the scorecard
    rather than facts about the run, and both are already said where the scorecard is."""
    js = page_code(ACTIVITY)
    body = js[js.index("function scorecardPill(") :]
    body = body[: body.index("\n}")]
    assert "if (c.in_progress) return `<span class=\"quiet-note\"" in body
    assert body.count('class="pill') == 1, "there is more than one way out of this that is a pill"


def test_an_empty_panel_is_composed() -> None:
    """Six panels across the three boards are empty on a quiet machine, and each was a
    sentence of small grey text adrift in three hundred pixels of white - which reads as a
    page that has not finished loading."""
    mark = rule(".empty::before")
    # `content` first, because a pseudo-element without it is not drawn at all - and the
    # revert harness caught this guard passing with the mark switched off.
    assert 'content:""' in mark, "the mark is declared and never rendered"
    assert "border-radius:99px" in mark and "var(--s6)" in mark
    # `border-radius:99px` is this sheet's idiom for *fully round* - the pills, the dot and
    # the bar all use it - and a radius is a shape rather than a step in a rhythm, so it is
    # taken out before asking whether the mark picked a length of its own.
    sized = re.sub(r"border-radius:[^;]*;?", "", mark)
    for value in re.findall(r"(?<![\w(-])(\d*\.?\d+)(px|rem)\b", sized):
        assert value[1] == "px" and float(value[0]) <= 3, f"the mark picks its own {''.join(value)}"
    assert "var(--line)" in mark, "the mark is not drawn in a token"


def test_the_components_the_pages_were_spelling_out_are_in_the_sheet() -> None:
    """A component lives here or it does not exist. Each of these was being written on the
    element, in one or both of two files."""
    for selector in (".measure", ".measure>.r", ".audit", ".reasons", ".said", ".r .sub.line"):
        assert rule(selector), selector
    worn: set[str] = set()
    for page in PAGES.values():
        worn |= {
            token
            for value in re.findall(r'class="([^"]*)"', body_of(page))
            for token in re.sub(r"\$\{[^}]*\}", " ", value).split()
        }
    for component in ("measure", "audit", "reasons", "said", "line"):
        assert component in worn, f".{component} is in the sheet and no page wears it"
