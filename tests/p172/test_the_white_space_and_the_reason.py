"""P172 - the white space, the reason, and the word you do not know.

Four findings from walking the consoles with three real runs on them. Every one of them was
invisible to the suite, which was green through all four, and three of them are about the
same mechanism.

**The white space.** On a grid, every panel in a row is stretched to that row's height -
which is the whole reason a band of panels reads as one shelf. A panel that spans *two*
rows takes that away from everything beside it, because its own height is then shared out
across rows nothing else is in. Measured on the Activity board at 1366px with the rehearsal
loaded: the run-detail panel was 3,018px tall, so the Runs panel beside it was stretched to
3,108px around 259px of content, Waiting on a person to 1,557px around 92, and the page was
3,750px. The Setup board's top band ended at three different heights - 892px, 756px and
620px. The Analytics board, whose areas are plain rows with no spans, was already right and
is what both now look like.

**The bound under it.** The detail panel was 3,018px because it drew one row per decision a
person made on the run, three lines each, and the Analytics board reports 34 as the
*median*. P149 had classified it `ours` - *"one run at a time, and its shape is fixed"* -
which was true of the steps and false of everything under them. It is the firm's length,
and `tests/p149` now says so.

**The reason.** `qc: "no procedure for 'qc-tieout'; the skill has no mechanical half yet"`
was in `/api/runs/{id}` all along, and the only thing that drew it was the Run trace panel
two bands down the page. At four in the afternoon with a stopped run, the quickest way to
read the one sentence that says what to do was to open the whole-design view and press *Go
to the stop*. It is drawn on the run now, by the renderer that already existed rather than
by a second one.

**The word you do not know.** The glossary is in the order you meet the words, which is the
right order to read it in and the wrong one to look one up in.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from admin.page import PAGE as SETUP
from ops.console.analytics_page import PAGE as ANALYTICS
from ops.console.app import PAGE as ACTIVITY
from ops.console.help_page import GLOSSARY
from ops.console.help_page import PAGE as HELP
from ops.console.map_view import MAP_HTML, MAP_JS, MAP_STYLE
from tests.p149.test_the_panels_whose_length_is_not_ours import WHOSE
from tests.reading import inline_handlers
from ui.theme import CSS, SHELL

BOARDS = ((ACTIVITY, "Activity"), (SETUP, "Setup"), (ANALYTICS, "Analytics"))
PAGE_OF = {name: page for page, name in BOARDS}


def script(page: str) -> str:
    """Every script a page carries, with the shared shell left in - a page is served the
    shell too, and the thing being asked is what the browser ends up running.

    The whole-design view's script is taken back out of the Activity page. It is embedded
    there, it draws a diagnostic of its own on a node panel, and that is a different
    question asked in a different view - leaving it in would make every count below read
    the map's answer as the console's.
    """
    own = page.replace(MAP_HTML, "").replace(MAP_JS, "")
    return "\n".join(re.findall(r"<script>(.*?)</script>", own, re.S))


def bands(page: str) -> list[list[str]]:
    """Each `grid-template-areas` on the page, as a list of rows of area names.

    A page may declare more than one - the Setup board has a second for the state where
    setup is finished - and a layout that is right until the checklist is ticked is a
    layout that is wrong on every machine that has been used for a week.
    """
    found = []
    for declaration in re.findall(r"grid-template-areas:([^;}]*)", page):
        rows = [row.split() for row in re.findall(r'"([^"]*)"', declaration)]
        if rows:
            found.append(rows)
    return found


# ---------------------------------------------------------------- the bands


@pytest.mark.parametrize("board", sorted(PAGE_OF))
def test_no_panel_spans_more_than_one_band(board: str) -> None:
    """The property the white space came from, said as a question about the source.

    It is checkable without a browser, which is what makes it worth having: the measurement
    that found this needed a simulated firm and a running server, and a property that can
    only be seen that way is one nobody will check again.

    Spanning *columns* is free and both boards still do it - `trace` takes two of them and
    so does `report`. It is spanning rows that breaks the band for every panel beside it.
    """
    for layout in bands(PAGE_OF[board]):
        rows_of: dict[str, set[int]] = {}
        for n, row in enumerate(layout):
            for area in row:
                if area != ".":
                    rows_of.setdefault(area, set()).add(n)
        spanning = {area: sorted(rows) for area, rows in rows_of.items() if len(rows) > 1}
        assert spanning == {}, (
            f"{board} has a panel in more than one band, so every panel beside it is "
            f"stretched to a height nothing in that band asked for: {spanning}"
        )


def test_a_band_is_still_a_row_of_the_grid_rather_than_a_share_of_the_screen() -> None:
    """P142's half, which the bands rest on. If a row were a share of the viewport again,
    the band's height would stop being decided by what is in it and the grouping below
    would mean nothing."""
    for page, board in BOARDS:
        rows = re.search(r"grid-template-rows:([^;]*);", page)
        assert rows, f"{board} names no rows"
        assert "fr" not in rows.group(1), f"{board} is back to a share of the screen"
        assert "min-content" in rows.group(1), f"{board} no longer sizes a band to its band"


def test_every_board_declares_as_many_bands_as_it_lays_out() -> None:
    """A `repeat(6,min-content)` over three bands is three rows of nothing, and a panel
    dropped into one of them later would be in a band by itself without anybody noticing."""
    for page, board in BOARDS:
        rows = re.search(r"grid-template-rows:\s*repeat\((\d+),", page)
        assert rows, f"{board} does not declare its rows as a repeat"
        for layout in bands(page):
            assert len(layout) == int(rows.group(1)), (
                f"{board} declares {rows.group(1)} rows and lays out {len(layout)} bands"
            )


# ----------------------------------------------------- the bound under the white space


def test_the_run_detail_is_bounded_like_every_other_panel() -> None:
    """It was the one panel on the three boards fed by a list nothing here can count, and
    the only one that was not capped. The classification and the markup are held together
    by `tests/p149`; this says the thing that was actually wrong."""
    assert '<section class="card stream" style="grid-area:detail">' in ACTIVITY
    assert WHOSE["detail"][0] == "firm", (
        "the run detail draws one row per decision a person made, and nothing here knows "
        "how many of those there will be"
    )


def test_the_decisions_are_a_count_and_a_disclosure_rather_than_a_transcript() -> None:
    """2,400 of the panel's 3,018px were 34 rows carrying the same two sentences. Nothing is
    removed - the rows are still drawn inside the disclosure - but the shape of the answer
    is one line, and the counts on it are what a reviewer asks for afterwards."""
    js = script(ACTIVITY)
    body = js[js.index("async function decisions(") :]
    body = body[: body.index("\nasync function deliverables(")]
    assert "<details>" in body and "</details>" in body, "the decisions are still a flat list"
    assert "Decided on this run" in body
    assert "rows.length" in body, "the summary does not say how many there were"
    assert "!d.revealed_at" in body, (
        "how many were answered without the proposal being looked at is the one count in "
        "here that is a quality signal, and it was invisible when it was repeated 34 times"
    )


# --------------------------------------------------------------- the reason, on the run


def test_a_diagnostic_is_drawn_by_one_renderer_and_filtered_by_its_caller() -> None:
    """The map panel wants every diagnostic a run recorded and the run detail wants the one
    belonging to the step it stopped on. Writing the second one out beside the state would
    be B-046's defect: one failure, described two ways a click apart, drifting the first
    time either is edited."""
    js = script(ACTIVITY)
    assert js.count("function diagRows(") == 1, "there is more than one way to draw one"
    assert js.count('<div class="d-row">') == 1, (
        "the console draws a diagnostic in two places, which is how one failure comes to "
        "be described two ways"
    )
    assert "diagRows(trace.diagnostics)" in js, "the trace panel stopped using it"
    body = js[js.index("function whyItStopped(") :]
    body = body[: body.index("\n}", body.index("return rows"))]
    assert "diagRows((run.trace || {}).diagnostics, stopped.step_id)" in body, (
        "the run detail draws every diagnostic rather than the one that stopped it"
    )
    assert "'quarantined'" in body and "'failed'" in body, (
        "a step stops a run by being quarantined or by failing, and both have to be found"
    )
    assert "if (!stopped) return ''" in body, (
        "a run that did not stop would get an empty rule beside its state"
    )


def test_the_run_detail_actually_calls_it() -> None:
    """The defect this build is named for: built, and wired to nothing."""
    js = script(ACTIVITY)
    card = js[js.index("$('card').innerHTML =") :]
    card = card[: card.index("actions(row.run_id")]
    assert "${whyItStopped(run)}" in card
    assert card.index("whyItStopped") < card.index("<dl class=\"kv\""), (
        "the reason a run stopped belongs above when it started and what it cost"
    )


def test_the_payload_the_page_reads_it_out_of_carries_the_step_it_belongs_to(
    store, bus
) -> None:
    """The half of this that is not about markup. `whyItStopped` matches a diagnostic to the
    step that stopped, so a diagnostic recorded without a `step_id` would silently draw
    nothing - and the run would be back to saying `quarantined: qc` and no more."""
    from ops.console.app import Console
    from tests.p23.conftest import ENGAGEMENT, Clock, halted_run

    halted_run(store, bus, run_id="run_q", engagement=ENGAGEMENT)
    console = Console(store, bus, clock=Clock(), label_of=lambda _: None)
    run = console.run("run_q")

    stopped = [s for s in run["steps"] if s["status"] in ("quarantined", "failed")]
    assert stopped, "the fixture no longer stops on a step"
    diagnostics = run["trace"]["diagnostics"]
    assert diagnostics, "a stopped run records nothing to say why"
    matching = [d for d in diagnostics.values() if d.get("step_id") == stopped[0]["step_id"]]
    assert matching, (
        f"nothing the run recorded names step {stopped[0]['step_id']!r}, so the sentence "
        "that says why it stopped cannot be put beside the step that stopped"
    )
    assert matching[0].get("message"), "the diagnostic has no sentence in it"


# ------------------------------------------------------------------- the find box


def test_one_key_goes_to_a_find_box_and_it_is_written_once() -> None:
    """The whole-design view has answered `/` since P49 and says so in its own legend; the
    two consoles with a find box answered nothing, so the same keystroke meant *find* in
    one view and typed a slash into the next."""
    assert SHELL.count("e.key !== '/'") == 1, "the shortcut is declared more than once"
    rule = SHELL[SHELL.index("e.key !== '/'") :]
    rule = rule[: rule.index("box.select();")]
    assert "input,textarea,select,[contenteditable]" in rule, "it fires while somebody types"
    assert "'.modal'" in rule, "it reaches the page behind an open dialog"
    assert "'#dmap.on'" in rule, "it fights the map's own handler for the same key"
    assert "document.querySelector('.filter input')" in rule, (
        "it is bound to one page's box rather than to whatever box the page has"
    )


def test_a_page_with_a_find_box_advertises_the_key() -> None:
    """A shortcut nobody is told about is a shortcut nobody uses. The map says so in its
    legend; a console says so in the box itself, which is where somebody looking for it is
    already looking."""
    for page, where in ((ACTIVITY, "Activity"), (HELP, "Help")):
        assert '<div class="filter">' in page, f"{where} has no find box"
    assert "press /" in HELP, "the glossary's box does not say which key"


def test_the_glossary_is_searched_by_what_a_word_means_as_well_as_its_name() -> None:
    """The person using it mostly does not know the term. Somebody who has just read
    *stopped on itself* on a run types that, and the word they need is Quarantined - which
    a search over the headings alone would never find.

    Asserted over the glossary's own text rather than over the script, because the thing
    that can rot here is the wording: a rewrite of Quarantined that drops the phrase the
    console prints would quietly break the lookup it is here for.
    """
    text = {term: f"{term} {means}".lower() for term, means in GLOSSARY}
    for phrase, expected in (
        ("stopped on itself", "Quarantined"),
        ("quiet period", "Quiet period"),
        ("masked", "Precedent"),
    ):
        hits = [term for term, blob in text.items() if phrase in blob]
        assert expected in hits, (
            f"{phrase!r} is a phrase the consoles print and no glossary entry contains it"
        )
    assert "stopped on itself" not in "quarantined", "the heading alone would have found it"

    js = script(HELP)
    assert "row.textContent.toLowerCase().includes(needle)" in js, (
        "the box searches something other than the whole row"
    )


def test_a_search_that_matches_nothing_says_so_and_a_filtered_row_actually_goes() -> None:
    """`[hidden]` is a display rule the user-agent sheet makes, and `.gl .r{display:block}`
    outranks it - so without the rule that puts it back, every row of a filtered glossary
    would stay exactly where it was and the box would do nothing visible at all."""
    assert ".gl .r[hidden]{display:none}" in HELP
    assert 'id="gq-none"' in HELP and "No word here says that" in HELP
    js = script(HELP)
    assert "none.hidden = shown > 0" in js, "the empty state is drawn and never shown"
    assert "shown + ' of ' + WORDS.length" in js, (
        "a filtered list that does not say how much it is hiding is a short glossary"
    )


def test_the_find_box_reaches_a_handler_the_way_this_product_wires_one() -> None:
    """No page here builds a handler out of data. The box goes through `ACTIONS`, and
    `input` is one of the events the shell's own table lets a field use - which is the
    reason that table exists."""
    assert 'data-act="findWord"' in HELP and "ACTIONS.findWord" in HELP
    # Asked through `tests.reading` rather than spelled out as `"oninput=" not in page`.
    # C80 exists because six guards said it the second way and all six were wrong in the
    # same direction - a page's own prose contains the attribute it is explaining - and it
    # caught this test saying it the seventh time.
    assert inline_handlers(HELP) == [], "a handler is wired in the markup"
    assert "input: false" in SHELL, "an input event climbs again, so a row would act on a keystroke"


# ------------------------------------------------- somewhere to put the files, on day one


def test_an_engagement_gets_its_folder_when_it_is_made(console, environment, tmp_path) -> None:
    """The **files** button shows the path on this machine so a client's documents can be
    dragged into it, `aa stage` copies into it, and a Box connector saves into it. All three
    were pointed at a folder that did not exist until somebody had already dropped a file
    through the page - on the first day of every engagement, which is the day they are most
    likely to be used."""
    from intake.roster import RosterEntry, RosterState

    console.register_engagement(
        RosterEntry(
            engagement_id="NEWC-2026-01",
            client="New Client Co",
            scope_path="valuation/non-esop/non-repeat",
            watch_id="w-val",
            destination_id="d-local",
            state=RosterState.PAUSED,
            folder="New Client Co/2026 Valuation",
        ),
        profile=None,
        who="C. Smit",
        reason="engagement letter signed",
    )
    made = environment["inbox"] / "Clients" / "New Client Co" / "2026 Valuation"
    assert made.is_dir(), f"{made} was not made, so there is nowhere to drag anything"

    files = console.engagement_files("NEWC-2026-01")
    assert Path(files["absolute"]) == made, (
        "the page shows a path that is not the one that was made, which is worse than "
        "making none"
    )
    assert files["files"] == [], "making the folder put something in it"


def test_making_it_is_recorded_against_the_person_who_made_the_engagement(
    console, environment
) -> None:
    """Everything this console does to a machine is on the record under a name and a
    reason. A directory appearing on somebody's disk is not an exception."""
    from intake.roster import RosterEntry, RosterState

    console.register_engagement(
        RosterEntry(
            engagement_id="RECD-2026-01",
            client="Recorded Co",
            scope_path="valuation/non-esop/non-repeat",
            watch_id="w-val",
            destination_id="d-local",
            state=RosterState.PAUSED,
            folder="Recorded Co/2026 Valuation",
        ),
        profile=None,
        who="C. Smit",
        reason="engagement letter signed",
    )
    changes = [c for c in console.config.changes() if "folder_created" in (c.new or {})]
    assert changes, "a folder was made on this machine and nothing says who did it or why"
    assert changes[0].field == "files/RECD-2026-01"
    assert changes[0].who == "C. Smit"
    assert changes[0].reason == "engagement letter signed"


def test_a_folder_that_climbs_out_of_the_watch_root_makes_nothing(
    console, environment, tmp_path
) -> None:
    """`folder` is typed on a form, so the containment check is the same one a file gets.

    Registering such an engagement is refused before this runs - the depth check sees that
    `../../../escaped/here` is five levels below a watch that sweeps two - and that refusal
    is the right one and arrives with a better sentence. It is also not this guard. Two
    checks that each catch the same input is what defence in depth is, and the way to find
    out whether the second one works is to ask it directly, because the day it matters is
    the day the first one has been changed.
    """
    from intake.roster import RosterEntry, RosterState

    escapee = RosterEntry(
        engagement_id="ESC-2026-01",
        client="Escapee",
        scope_path="valuation/non-esop/non-repeat",
        watch_id="w-val",
        destination_id="d-local",
        state=RosterState.PAUSED,
        folder="../../../escaped/here",
    )
    assert console._make_folder(escapee, who="C. Smit", reason="test") is None
    assert not (tmp_path.parent / "escaped").exists()
    assert not (tmp_path / "escaped").exists()
    assert not (environment["inbox"] / "escaped").exists()


def test_a_folder_that_is_already_there_is_left_exactly_as_it_is(
    console, environment
) -> None:
    """The ordinary case on a repeat client: last year's folder is already on the disk with
    last year's files in it, and registering this year's engagement against it must not be
    the thing that touches them."""
    from intake.roster import RosterEntry, RosterState

    folder = environment["inbox"] / "Clients" / "Henderson Manufacturing" / "2026 ESOP"
    (folder / "last-year.txt").write_text("kept", encoding="utf-8")

    console.register_engagement(
        RosterEntry(
            engagement_id="HEND-2026-99",
            client="Henderson Manufacturing",
            scope_path="valuation/esop/repeat",
            watch_id="w-val",
            destination_id="d-local",
            state=RosterState.PAUSED,
            folder="Henderson Manufacturing/2026 ESOP",
        ),
        profile=None,
        who="C. Smit",
        reason="rolled forward",
    )
    assert (folder / "last-year.txt").read_text(encoding="utf-8") == "kept"
    changes = [
        c
        for c in console.config.changes()
        if c.field == "files/HEND-2026-99" and "folder_created" in (c.new or {})
    ]
    assert changes == [], "a folder nobody made was recorded as made"


# ------------------------------------------------------- and the language is still one


def test_nothing_added_chose_a_colour_or_a_length_of_its_own() -> None:
    """The rule the whole sheet rests on, re-asked over what this phase wrote: the page's
    own rules and the sheet's additions name tokens, so any sweep over the tokens is a
    sweep over the product."""
    def own(page: str) -> str:
        head = page.split("</style>")[0]
        for shared in (CSS, MAP_STYLE):
            head = head.replace(shared, "")
        # Comments out: a measurement written down beside the rule it explains is prose,
        # and a sweep that reads "3,750px tall" as a declaration is a sweep that forbids
        # recording what was measured - which is most of why these rules are readable.
        return re.sub(r"/\*.*?\*/", "", head, flags=re.S)

    added = "\n".join(own(page) for page, _ in ((HELP, "Help"), *BOARDS))
    assert re.findall(r"#[0-9a-fA-F]{3,8}\b", added) == [], "a page writes a colour of its own"
    for length in re.findall(r"(?<![\w(-])(\d*\.?\d+)px\b", added):
        assert float(length) <= 3, f"{length}px is a length chosen by eye, not a hairline"


def test_the_one_reduced_motion_rule_still_covers_everything() -> None:
    """P171's property. This phase added no animation, and the check is cheap enough that
    the next phase to add one inherits it."""
    block = re.search(r"@media \(prefers-reduced-motion:reduce\)\{(.*?)\n\}", CSS, re.S)
    assert block and block.group(1).lstrip().startswith("*,*::before,*::after{")
