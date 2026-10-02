"""P81: the setup surface, composed rather than assembled.

P80 fixed what this screen says. This is about how it looks while saying it, and the
findings were about hierarchy rather than taste:

Seven panels of equal weight, so nothing on the screen was the subject. Seven disconnected
marks in the checklist, so a sequence read as a list. A finished step costing the same
three lines as the one you have to act on, so five done steps crowded out the two left. No
figure anywhere, so the eye had nowhere to land on the one page a beginner starts at.
Three pills on every row of the practice groups, which the stylesheet's own note calls the
thing that makes a tool look like a toy. And the checklist holding the best position on
the screen permanently, including on a machine where every box had been ticked for months.

Underneath that, values chosen by eye: `.55rem` four times, and `14px` and `10px` in a page
whose root is `clamp(12px,.55vw + 5.5px,14.5px)` - so those two gaps got *proportionally
smaller* on a larger monitor, which is backwards. And eight `onclick=` attributes on a page
that documents one way to wire a control and used two.

The tests here are the parts of that which are facts. "It looks expensive" is not one, so
nothing below asserts it: what they hold is that the sequence is drawn as a sequence, that
the finished checklist yields its space, that emphasis is spent once, that every length
comes from the scale, and that nothing the page could do before it cannot do now.
"""

from __future__ import annotations

import re

from admin.page import PAGE
from ui.theme import CSS


def script() -> str:
    """The page's JavaScript, with the f-string doubling undone so it reads as it ships."""
    return "\n".join(re.findall(r"<script>(.*?)</script>", PAGE, re.S)).replace(
        "{{", "{"
    ).replace("}}", "}")


def page_style() -> str:
    """The page's own <style> block - its layout, which is the one thing a page may set."""
    blocks = re.findall(r"<style>(.*?)</style>", PAGE, re.S)
    return "\n".join(blocks).replace("{{", "{").replace("}}", "}")


def inline_styles() -> list[str]:
    return re.findall(r'style="([^"]*)"', PAGE.replace("{{", "{").replace("}}", "}"))


# ------------------------------------------------------------ the steps are a sequence


def test_the_marks_are_joined() -> None:
    """Seven circles in a column are a list of unrelated things until a rule joins them.
    The rail is the whole difference between "here are seven tasks" and "here is where you
    are in one sequence", and it is one pseudo-element."""
    assert ".step::before" in CSS
    assert ".step:last-child::before{display:none}" in CSS, "the rail runs past the last mark"
    # Centred by construction. Two literals that happened to agree would read as aligned
    # today and drift the first time the mark changed size.
    assert "--mark:1.6rem" in CSS
    assert "left:calc(var(--s3) + var(--mark) / 2)" in CSS
    assert ".step .mark{width:var(--mark);height:var(--mark)" in CSS


def test_the_rail_carries_how_far_along_it_is() -> None:
    """A rail drawn in one colour is a decoration. Drawn in two it is a measure."""
    assert ".step.done::before{background:var(--good-line)}" in CSS


def test_the_mark_sits_on_top_of_the_rail_rather_than_being_crossed_by_it() -> None:
    assert re.search(r"\.step \.mark\{[^}]*z-index:1", CSS, re.S), "the rail would draw through it"


def test_the_step_being_worked_on_is_the_subject() -> None:
    """Given a wash and nothing else it was one of seven equal rows with a tint."""
    assert ".step.now .t{font-size:var(--t-subtitle)" in CSS, "its title is not set apart"
    ringed = r"\.step\.now \.mark\{[^}]*box-shadow:0 0 0 3px var\(--accent-soft\)"
    assert re.search(ringed, CSS, re.S), "the current mark is not lifted off the wash"


def test_a_finished_step_costs_one_line() -> None:
    """Five done and two left filled the panel evenly, which put most of the ink on the
    part nobody has to read again. What a finished step says is confirmation, not
    instruction, and confirmation is worth one line.

    P136 made it cost one line rather than two: the title and the detail share a line, and
    the truncation moved from the detail to the row around it - or the title would be
    clipped by a rule meant for the sentence after it. The property is the same and this
    asserts it where it now lives.
    """
    assert re.search(r"\.step\.done>span:not\(\.mark\):not\(\.go\)\{[^}]*ellipsis", CSS, re.S)
    assert ".step.done .t{display:inline}" in CSS
    assert ".step.done .d{display:inline" in CSS


# ------------------------------------------------------------ and the panel has an anchor


def test_the_panel_carries_a_figure() -> None:
    """Its largest element was a heading, so the eye had nowhere to land and the screen
    read as reference material rather than as the thing to do next."""
    assert ".progress .n{font:400 var(--t-display)/1 var(--serif)" in CSS
    assert '<span class="n">' in script()


def test_the_figure_counts_what_is_left_rather_than_what_is_done() -> None:
    """"5 of 7 done" is a score. "2 steps left" is the thing somebody is holding in their
    head, and it counts down to a word."""
    body = script()
    assert "const left = steps.length - done;" in body
    assert "'step left' : 'steps left'" in body
    assert "Ready to run" in body, "it has to land on a word, not on zero"


def test_the_score_is_still_there_for_whoever_wants_it() -> None:
    assert "${done} of ${steps.length}" in script()


# ------------------------------------------------- the finished checklist yields the screen


def test_a_finished_checklist_gives_its_rows_to_the_panels() -> None:
    """It is the reason a first-time reader is on this page and dead weight to everybody
    else, and it was holding three rows of the first column permanently."""
    style = page_style()
    # The page inlines the whole stylesheet, which has a `.board{` of its own. The page's
    # two are the rules that name areas.
    areas = dict(re.findall(r"([\w.\- ]*\.board)\{[^}]*grid-template-areas:([^}]*)\}", style))
    assert set(areas) == {".board", "body.all-done .board"}, sorted(areas)
    normal, done = areas[".board"], areas["body.all-done .board"]
    # How many rows it holds while there is work in it is a design decision that has moved
    # once already - P136 gave it a fourth, having measured the panel at a laptop's
    # viewport. What this test is about is that finishing gives them back, so it asserts
    # the relation rather than either number.
    assert normal.count("steps") > done.count("steps"), "the checklist no longer leads the board"
    assert done.count("steps") == 1, "a finished checklist still holds more than one row"
    assert done.count("eng") > normal.count("eng"), "nothing gained the space it gave up"
    assert set(re.findall(r"\w+", normal)) == set(re.findall(r"\w+", done)), (
        "a panel appears in one layout and not the other"
    )


def test_the_page_says_when_it_is_finished_in_one_place() -> None:
    """On the wrapper, so the layout is decided by the stylesheet rather than by rebuilding
    a grid in script."""
    assert "document.body.classList.toggle('all-done', next === -1);" in script()


def test_the_steps_stay_reachable_after_they_are_done() -> None:
    """"How did this get set up" is a real question, and the answer should not be "read the
    code". Collapsed, not removed."""
    body = script()
    assert "<details><summary>What was done, in order</summary>${drawn}</details>" in body


def test_the_steps_are_drawn_once_however_they_are_shown() -> None:
    """Two copies of the same markup is how a collapsed one stops matching the open one."""
    body = script()
    assert body.count('<span class="mark">') == 1, "the steps are rendered in two places"


# ------------------------------------------------------------ emphasis is spent once


def test_a_practice_group_carries_one_pill_and_not_three() -> None:
    """focus, parked, firm layer only and defined put a row of badges beside every line -
    which is the thing the stylesheet's own note says makes a tool look like a toy. Only
    one of the four is ever the reason somebody is reading the row."""
    body = script()
    scopes = body[body.index("async function scopes()") : body.index("function methodology()")]
    assert scopes.count('class="pill') == 1, "more than one pill per row"
    assert "const standing = p =>" in scopes, "the one that matters is not chosen anywhere"


def test_the_pill_is_the_most_particular_thing_true_of_the_row() -> None:
    """Which one it keeps is the whole decision, and the order is not alphabetical. Parked
    outranks everything, because a parked group is not somewhere work goes however well
    defined it is; `defined` is last, because it is what is left when nothing more
    particular is true."""
    body = script()
    chain = body[body.index("const standing = p =>") :][:400]
    assert re.findall(r"p\.(\w+) \?", chain) == ["parked", "firm_layer_only", "focus"]
    assert re.findall(r"\['([^']+)',", chain) == [
        "parked",
        "firm layer only",
        "focus",
        "defined",
    ]


def test_a_parked_group_that_is_also_the_focus_says_both() -> None:
    """Dropping to one pill loses something real in exactly one case - the focus division's
    own parked segment - so that case says it in words under the name rather than having it
    silently dropped."""
    assert "p.focus && p.parked ?" in script()
    assert "the focus division" in script()


def test_the_skill_count_is_a_column_rather_than_a_sentence() -> None:
    """A column of figures is read down. Ragged numbers are the difference between a table
    and a list of facts, and the stylesheet already has the class for it."""
    body = script()
    scopes = body[body.index("async function scopes()") : body.index("function methodology()")]
    assert '<span class="num">${p.skills}</span>' in scopes


# ------------------------------------------------------------ nothing chosen by eye


def test_no_length_on_the_page_was_chosen_by_eye() -> None:
    """The spacing scale is `--s1` to `--s7`. A page that reaches past it does not follow
    the next change to the rhythm, and the two `px` values were worse than off-scale: the
    root is `clamp(12px,.55vw + 5.5px,14.5px)`, so a gap in pixels gets *proportionally
    smaller* on a larger monitor, which is the opposite of what it was set for."""
    found = [
        f"{prop}:{''.join(length)}  in  {style[:70]}"
        for style in inline_styles()
        for prop, value in re.findall(r"([\w-]+)\s*:\s*([^;]+)", style)
        for length in re.findall(r"(?<![\w(-])(\d*\.?\d+)(px|rem|em)\b", value)
    ]
    assert found == [], "lengths off both scales: " + "; ".join(found)


def test_the_page_still_sets_its_own_layout() -> None:
    """The rule is about values, not about placement: which panel goes where is the page's
    business and belongs nowhere else. A test that banned every inline style would have
    been passed by moving the same hand-picked values into the style block."""
    assert 'style="grid-area:steps"' in PAGE
    assert "grid-template-areas:" in page_style()


def test_every_control_is_wired_one_way() -> None:
    """The page documents ACTIONS and had eight `onclick=` attributes beside it. Not a way
    in - nothing was ever interpolated into one - but two mechanisms for one job, and the
    one the page documents is the one that survives a content-security policy."""
    assert re.findall(r"\son(?:click|input|change|submit)=", PAGE) == []


def test_the_controls_that_lost_an_attribute_gained_a_binding() -> None:
    """Deleting `oninput="suggest()"` and stopping there would leave a form that no longer
    suggests anything, and every test above would still pass."""
    body = script()
    assert "$('e_client').addEventListener('input', suggest);" in body
    assert "$('e_id').addEventListener('input', wasTyped);" in body
    assert "$('e_folder').addEventListener('input', wasTyped);" in body
    assert "function wasTyped(e)" in body, "the handler it names does not exist"


def test_the_bindings_are_named_functions_rather_than_written_out_each_time() -> None:
    """`showAdd` runs again every time the dialog opens. An identical named listener is
    added once; an arrow function written inline would stack a new one on every open."""
    body = script()
    for call in re.findall(r"addEventListener\('input', ([^)]+)\)", body):
        assert re.fullmatch(r"\w+", call), f"input listener {call!r} is not a named function"


# ------------------------------------------------------------ and it still does everything


def test_every_control_the_dialog_needs_still_exists() -> None:
    """The dialog was regrouped into three sections. Regrouping a form is exactly how a
    field goes missing, and the id is what `addEngagement` reads."""
    fields = ("e_client", "e_id", "e_scope", "e_kind", "e_watch", "e_dest", "e_folder", "e_pin")
    for field in fields:
        assert f'id="{field}"' in PAGE, f"{field} was lost in the regrouping"
        assert f"$('{field}')" in script(), f"{field} is on the page and nothing reads it"


def test_the_dialog_asks_in_three_sections_rather_than_one_stack() -> None:
    """Eight controls in a column is a form. The same eight under three rules is a thing
    with a shape, and the shape is what says how much is left before you start."""
    asked = re.findall(r'<p class="section-label">([^<]+)</p>', PAGE)
    assert asked == ["Who it is", "Where its files are", "How it runs"], asked


def test_the_sections_are_laid_out_on_the_scale() -> None:
    assert ".cols.two.ask{gap:0 var(--s5)" in CSS
    assert ".cols.two.ask>.field.wide{grid-column:1 / -1}" in CSS


def test_a_qualifier_on_a_label_is_not_shouted() -> None:
    """Labels are uppercase and letterspaced. "EXCEL MODEL TEMPLATE - OPTIONAL, AND NOT THE
    AI MODEL" is a label nobody finishes reading."""
    assert ".aside{text-transform:none;letter-spacing:0" in CSS
    assert '<span class="aside">&mdash; optional, and not the AI model</span>' in PAGE


def test_every_style_promoted_into_the_sheet_is_still_worn_by_something() -> None:
    """Seven hand-styled elements became seven classes. A class in the sheet that nothing
    wears is a rule styling nothing, and the element that lost its inline style is then
    sitting there unstyled - which is the failure this whole change could produce and the
    one nothing else here would notice, because the page would still render.

    `.excerpt.said` and `.note.tight` are worn by `ask()` rather than by the page's own
    markup, so they are looked for in the whole document the page ships, which is where
    the shared dialog builder ends up too."""
    # The selector, not the selector followed by a brace. A rule may serve more than one -
    # `button.primary.danger,.btn.primary.danger` is one rule for a button and for an anchor
    # that looks like one - and keying on `{` asked whether it was written alone.
    for selector, worn in (
        (".excerpt.path", 'class="excerpt path"'),
        (".excerpt.said", 'class="excerpt said"'),
        (".drop", 'class="drop"'),
        (".code-area", 'class="code-area"'),
        (".r.lede", 'class="r lede"'),
        (".note.tight", 'class="note tight"'),
        (".sm", 'class="sm"'),
        (".aside", 'class="aside"'),
        ("button.primary.danger", "class=\"primary${danger ? ' danger' : ''}\""),
    ):
        written = re.search(r"(?:^|[,}])\s*" + re.escape(selector) + r"\s*(?=[,{])", CSS, re.M)
        assert written, f"{selector} is not in the stylesheet"
        assert worn in PAGE, f"{selector} is in the sheet and nothing on the page wears it"
