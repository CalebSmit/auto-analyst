"""P52: the map, answering what a person asks.

The fifth review read this screen as the two people who use it - a managing director with
thirty seconds, and a three-month analyst in front of a halted run at seven in the evening -
and its finding was one sentence: the screen is about the design, and both of them came to
it about a run.

Six questions get asked in front of a stopped run. Where did it stop, why, what had it
done, what would have happened next, what do I do now, and is the work so far usable. It
answered two and a half. These are the rest.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ops.console.map_view import MAP_HTML, MAP_JS, MAP_STYLE

ROOT = Path(__file__).resolve().parents[2]
GRAPH = json.loads((ROOT / "graph" / "architecture.json").read_text(encoding="utf-8"))

# ------------------------------------------------------------------ whose run, and what happened


def test_the_headline_names_the_run_and_not_the_diagram() -> None:
    """It said "The whole design" over "20 of 118 touched" - which an MD reads, correctly
    for the words used, as ten per cent complete. The denominator is a census of the
    architecture, including every connector, port and authoring bench no run ever goes
    near, presented where a completion rate would go.
    """
    assert '<span id="dmap-title">' in MAP_HTML
    assert "$('dmap-title').textContent = run.client || detail.engagement_id || runId;" in MAP_JS
    # The count is now the plan's own steps, which is a denominator that means something.
    assert "const done = steps.filter(st => st.status === 'completed').length;" in MAP_JS
    assert "`${done} of ${steps.length} steps done`" in MAP_JS


def test_the_line_under_it_says_what_happened_how_long_and_what_it_cost() -> None:
    """None of the verdict, the elapsed time or the spend was on this screen - and this
    screen covers the panel they were on."""
    assert "MAP_RUN_DETAIL = await get(`/api/runs/${encodeURIComponent(runId)}`)" in MAP_JS
    assert "if (STATE_SAYS[detail.state]) parts.push(STATE_SAYS[detail.state]);" in MAP_JS
    assert "mapFor(spend.active_seconds) + ' of work'" in MAP_JS
    assert "usd(spend.usd)" in MAP_JS


def test_the_census_of_the_drawing_moves_out_of_the_headline() -> None:
    """It is a fact about the picture, not a score for the run, so it goes with the key."""
    assert '<span class="hidden-note" id="dmap-drawn"></span>' in MAP_HTML
    assert "`${touched} of ${drawn} parts used`" in MAP_JS
    assert "not in this drawing" in MAP_JS


# ------------------------------------------------------------------ where did it stop


def test_it_opens_on_the_stop() -> None:
    """The single most likely reason to open this view, and it opened on a wide shot and
    left the reader to hunt for the plum one among a hundred and eighteen."""
    assert "MAP_STATES[id] === 'failed' && $('mn-' + id)" in MAP_JS
    assert "pickNode(nodeId && $('mn-' + nodeId) ? nodeId : (stopped || null));" in MAP_JS
    assert 'data-act="mapStop"' in MAP_HTML and "Go to the stop" in MAP_HTML
    assert "ACTIONS.mapStop" in MAP_JS
    assert "Nothing failed on this run." in MAP_JS, "and it says so when nothing did"


# ------------------------------------------------------------------ what would have come next


def test_a_run_blocked_from_a_part_is_not_the_same_as_a_part_nothing_uses() -> None:
    """Both were one dashed outline, for all ninety-nine of them. For a halted run "three
    steps I'll never get" and "not part of this job" are completely different facts, and
    telling them apart is the second question an analyst asks."""
    assert "function blockedBy(states)" in MAP_JS
    assert "const stopped = Object.keys(states).filter(id => states[id] === 'failed');" in MAP_JS
    assert "#dmap .mn.blocked{" in MAP_STYLE
    assert "blocked.has(id) ? 'blocked' : 'notreached'" in MAP_JS
    # And it is its own thing in the key, with its own filter.
    assert 'data-state="blocked"' in MAP_HTML and "never got to" in MAP_HTML
    assert "#dmap.hide-blocked .mn.blocked" in MAP_STYLE


def test_blocked_is_derived_from_the_blueprints_own_edges() -> None:
    """No new endpoint and no second source: what would have come next is downstream of
    where it stopped, and the edges are already in hand."""
    walk = MAP_JS[MAP_JS.index("function blockedBy(states)") :]
    assert "for (const next of MAP_OUT[queue.shift()] || [])" in walk[:900]
    # The graph it walks really is directed and really does have successors to walk to.
    out = {e["from"] for e in GRAPH["edges"]}
    assert len(out) > 40, "a blueprint with no outbound edges could not answer this"


# ------------------------------------------------------------------ what it actually did


def test_no_line_claims_a_flow_the_run_did_not_take() -> None:
    """Liveness was decided by both ends having been touched. On the canonical scripted run
    that lit thirteen edges, eight of which were never traversed - including a declared loop
    edge and three separate lines into the dispatcher. The strongest colour on the canvas
    was asserting flow that did not happen about sixty per cent of the time.
    """
    assert "const crossed = new Set();" in MAP_JS
    assert "crossed.add(MAP_ORDER[i] + '>' + MAP_ORDER[i + 1]);" in MAP_JS
    assert "const live = crossed.has(p.dataset.from + '>' + p.dataset.to);" in MAP_JS
    # The old adjacency test is gone entirely.
    assert "a !== 'notreached' && b !== 'notreached'" not in MAP_JS


def test_the_hops_the_blueprint_has_no_edge_for_are_drawn_rather_than_dropped() -> None:
    """Most of what a run does is not a blueprint edge - measured, twelve of nineteen
    transitions, including its two longest. Leaving them undrawn leaves the biggest thing
    the run did off the picture; drawing them as edges would be a lie. They are a trail."""
    assert "function drawPath()" in MAP_JS
    assert "const known = (MAP_OUT[from] || []).includes(to);" in MAP_JS
    assert "if (known) continue;" in MAP_JS, "an edge that exists is left to say it itself"
    assert "#dmap #dmap-path path{" in MAP_STYLE
    assert "stroke-dasharray:1 7" in MAP_STYLE, "dotted, so it is never read as an edge"
    assert "drawPath();" in MAP_JS


# ------------------------------------------------------------------ what do I do now


def test_it_says_what_to_do_and_carries_the_button_that_does_it() -> None:
    """Resume and Halt are on the run panel, which this overlay covers - so the path was
    read the map, close the map, find the run again, click Resume."""
    assert "function mapVerdict()" in MAP_JS
    assert "Fix the cause, then resume" in MAP_JS
    assert 'data-act="runAction"' in MAP_JS, "the console's own action, not a second one"
    assert "data-do=\"${esc(next[1])}\"" in MAP_JS


def test_there_is_a_link_to_send() -> None:
    """The deep-link plumbing existed and was invisible on screen; only USING.md knew."""
    assert "ACTIONS.mapCopy" in MAP_JS
    assert "navigator.clipboard.writeText(link)" in MAP_JS
    assert "Link copied. It opens this run at this place." in MAP_JS
    assert "Copy a link to this" in MAP_JS


def test_the_first_screen_is_the_answer_and_then_the_list() -> None:
    """Nothing picked is what a person sees first, so it was the view's real opening
    statement - and it was the console's trace panel and steps list a third time."""
    assert "box.innerHTML = mapVerdict() + (went.length" in MAP_JS
    order = MAP_JS.index("function mapVerdict()")
    for line in ("Got through", "Never got to", "<dt>Time</dt>", "<dt>Cost</dt>"):
        assert line in MAP_JS[order : order + 3000], line


# ------------------------------------------------------------------ how long it took


def test_the_panel_subtracts_the_two_timestamps_it_was_already_printing() -> None:
    """"Where do the hours go" is the analyst's own recorded question, and the view printed
    the first and last time against a node and left the arithmetic to the reader."""
    assert "function mapTook(events)" in MAP_JS
    both = "const first = Date.parse(events[0].ts), last = Date.parse(events"
    assert both in MAP_JS
    assert "esc(mapTook(events)) + ' here'" in MAP_JS
    assert "function mapFor(seconds)" in MAP_JS


# ------------------------------------------------------------------ the words


def test_the_machines_event_names_are_translated_with_the_raw_one_kept() -> None:
    """`guard.tieout.fail`, `hitl.pass.paused`, `step.quarantined` - the console already
    does this for run states and scorecard verdicts."""
    assert "const MAP_EVENT_SAYS = {" in MAP_JS
    assert "function mapSays(type)" in MAP_JS
    assert "MAP_EVENT_SAYS[type] || String(type).replace(/[._]/g, ' ')" in MAP_JS, (
        "an event added tomorrow is readable tomorrow, not when somebody updates a table"
    )
    assert '<span class="t" title="${esc(e.type)}">${esc(mapSays(e.type))}</span>' in MAP_JS


def test_two_different_things_are_not_both_called_a_step() -> None:
    """The console's run detail has Steps - the plan's, seven of them, with attempt counts.
    This view's stepper counted places touched, twenty-one of them. Same word, two panels,
    one run; a reader will assume they correspond, and they do not."""
    assert "aria-label=\"Walk the places this run went, in order\"" in MAP_HTML
    assert ">in order<" in MAP_HTML
    assert "Where it went, in order" in MAP_JS
    assert "places &middot; pick one for what happened there" in MAP_JS
    # The plan's steps keep the word, and only in the header, where they are the plan's.
    assert MAP_JS.count("steps done") == 1


def test_one_table_of_words_serves_the_canvas_the_panel_and_the_announcement() -> None:
    """The announced state used the raw vocabulary while the node's own label used the
    friendly one: the same node said "used" to a screen reader and "ran" on the canvas."""
    assert "const MAP_SAYS = {" in MAP_JS
    assert "const says = MAP_SAYS;" in MAP_JS
    assert "MAP_SAYS[MAP_STATES[id]] || 'not used on this run'" in MAP_JS


def test_deselecting_is_announced() -> None:
    """Clicking the paper means "the whole run again", and the live region was left holding
    the sentence about the node just left."""
    assert "Nothing picked. The whole run, ${MAP_ORDER.length} places." in MAP_JS


def test_the_engineers_words_are_off_the_screen() -> None:
    """Every visible string, against the two readers: an MD with thirty seconds and an
    analyst three months into the job."""
    visible = re.findall(r">([^<>{}$]{4,})<", MAP_HTML)
    text = " ".join(visible).lower()
    for word in ("node", "blueprint"):
        assert word not in text, f"'{word}' is still on the screen: {text[:200]}"
    assert "Find a part of the system" in MAP_HTML
    assert "Show everything" in MAP_HTML, "not 'Fit all'"
    assert "not used here" in MAP_HTML, "not 'never reached', which conflated two things"


def test_the_unexported_blueprint_message_is_not_addressed_to_whoever_built_it() -> None:
    """"re-export it with tools/export_architecture.py", shown to an analyst at 7pm."""
    assert "tools/export_architecture.py" not in MAP_JS
    assert "This picture is not available on this build." in MAP_JS
    assert "under Run trace" in MAP_JS, "and it says where the answer still is"
