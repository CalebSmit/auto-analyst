"""C36 - Finding one client, and what the screen may claim about them.

P63 gave Activity the unit an analyst actually works in. A checkpoint is not a second run
of that phase's tests: it asks whether the phase agrees with everything around it. Three
ways it could disagree, and each is asked here.

1. **The two lists could drift.** The engagement fold and the runs panel read the same
   rows on purpose. If they could disagree, one of the screens would be wrong and nothing
   on the page would say which.
2. **The screen could claim something the record has not got.** B-026 asked for a
   valuation date and no such field exists. What stops it appearing later is a test plus a
   question in the register, and a question that quietly vanishes is one somebody asks
   again from scratch.
3. **The register could go stale again**, which is the rule C35 set and which this build
   had to keep while settling a row and adding a question.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from ops.console.app import NEEDS_ATTENTION, Console
from ops.console.app import PAGE as ACTIVITY
from ops.events import EventBus
from ops.run_store import SqlRunStore
from tests.conftest import needs_a_checkout
from tests.p23.conftest import ENGAGEMENT, OTHER_ENGAGEMENT, Clock, clean_run, reviewed_run

ROOT = Path(__file__).resolve().parents[3]


def plan() -> dict:
    return json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))


def register() -> str:
    return (ROOT / "BUILD" / "OPEN.md").read_text(encoding="utf-8")


@pytest.fixture
def console(store: SqlRunStore, bus: EventBus) -> Console:
    return Console(
        store,
        bus,
        clock=Clock(),
        label_of={
            ENGAGEMENT: {"client": "Henderson Manufacturing", "scope_path": "valuation/non-esop"},
            OTHER_ENGAGEMENT: {"client": "Mercer Dental", "scope_path": "esop/annual"},
        }.get,
    )


# ------------------------------------------------- the two lists cannot disagree


def test_every_run_on_the_panel_is_behind_exactly_one_engagement_line(
    console: Console, store: SqlRunStore, bus: EventBus
) -> None:
    """A run that belonged to no line, or to two, would be a run a person could not reach
    by looking for the client - which is the whole point of the fold."""
    clean_run(store, bus, run_id="run_a1", engagement=ENGAGEMENT)
    reviewed_run(store, bus, run_id="run_a2", engagement=ENGAGEMENT)
    clean_run(store, bus, run_id="run_b1", engagement=OTHER_ENGAGEMENT)

    on_panel = [row["run_id"] for row in console.runs()]
    folded: list[str] = []
    for line in console.engagements():
        folded.extend(line["run_ids"])

    assert sorted(folded) == sorted(on_panel), "a run is missing from the fold, or counted twice"
    assert len(set(folded)) == len(folded)


def test_what_the_line_says_is_open_is_what_the_queue_says_is_open(
    console: Console, store: SqlRunStore, bus: EventBus
) -> None:
    """The engagement line and the "waiting on a person" panel are two readings of one
    queue. A person who trusts the first and works from the second must not find them
    disagreeing about the same client."""
    for run_id in ("run_a1", "run_a2"):
        script = reviewed_run(store, bus, run_id=run_id, engagement=ENGAGEMENT)
        script.review(f"{run_id}_open", "line-item-tagging@0.1.0", confidence=0.4)
    clean_run(store, bus, run_id="run_b1", engagement=OTHER_ENGAGEMENT)

    from_inbox: dict[str, int] = {}
    for item in console.inbox():
        key = str(item["engagement_id"])
        from_inbox[key] = from_inbox.get(key, 0) + 1

    for line in console.engagements():
        expected = from_inbox.get(line["engagement_id"], 0)
        assert line["open_review_items"] == expected, line["engagement_id"]


def test_every_state_the_page_names_is_one_a_run_can_actually_be_in() -> None:
    """`engagements()` counts the attention states and the page paints every state. Both
    were naming states no run can hold - `blocked` is an `Outcome` a halted run carries,
    and the delivered state has never been called `released` - so the entries were dead
    and read as coverage they had not got. Nothing counted them, because nothing could,
    which is exactly why they survived three reviews of this page.

    Asked of the whole table rather than of the two that were wrong: the next dead key
    should fail here rather than wait for somebody to notice a colour that never appears.
    """
    from ops.models import RunState

    real = {str(state) for state in RunState}
    assert set(NEEDS_ATTENTION) <= real, "a state that wants a person is not a state"

    body = "\n".join(
        re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S)
    )
    for table in ("STATE_TONE", "STATE_SAYS"):
        declared = re.search(rf"const {table} = \{{(.*?)\}};", body, re.S)
        assert declared, table
        named = set(re.findall(r"(\w+):", declared.group(1)))
        assert named <= real, f"{table} paints a state no run can be in: {sorted(named - real)}"


# ------------------------------------------------- the screen claims nothing it has not got


def test_no_engagement_line_carries_a_valuation_date(
    console: Console, store: SqlRunStore, bus: EventBus
) -> None:
    clean_run(store, bus, run_id="run_a1", engagement=ENGAGEMENT)
    for line in console.engagements():
        assert not [key for key in line if "valuation" in key or key == "as_of"]


def test_the_question_that_refusal_opened_is_still_in_the_register() -> None:
    """The date was not invented; a question was recorded instead. If the question goes
    and the field has not arrived, the next person to read B-026 builds the invented one.
    """
    text = register()
    assert "valuation date" in text
    assert re.search(r"##\s*5\.\s*Questions I am holding", text), "section 5 is gone"


def test_the_questions_i_am_holding_are_numbered_without_a_repeat() -> None:
    """A list that gained an entry mid-build is the easy place for two sevens."""
    text = register()
    section = text.split("## 5. Questions I am holding", 1)[1].split("\n---", 1)[0]
    numbers = [int(n) for n in re.findall(r"^(\d+)\.\s+\*\*", section, re.M)]
    assert numbers == list(range(1, len(numbers) + 1)), numbers


# ------------------------------------------------- and the register is still current


def test_the_settled_row_for_the_engagement_view_says_when_and_what() -> None:
    settled = [line for line in register().splitlines() if line.startswith("| ~~")]
    engagement_view = [line for line in settled if "engagement view" in line.lower()]
    assert engagement_view, "the row B-026 answered was not settled"
    for line in engagement_view:
        assert re.search(r"20\d\d-\d\d-\d\d", line), line[:120]
        assert "P63" in line


def test_no_live_row_asks_for_a_phase_that_is_closed() -> None:
    """C35's rule, kept while this build settled a row and added a question."""
    done = {p["id"] for p in plan()["phases"] if p["status"] == "done"}
    green = {c["id"] for c in plan()["checkpoints"] if c["status"] == "done"}
    live = [
        line
        for line in register().splitlines()
        if line.startswith("|") and not line.startswith(("| ~~", "|--", "| |"))
    ]
    for row in live:
        assert not (set(re.findall(r"close (P\d+)", row)) & done), row[:100]
        assert not (set(re.findall(r"checkpoint (C\d+)", row)) & green), row[:100]


def test_the_backlog_item_this_closed_is_marked_built() -> None:
    needs_a_checkout("the backlog item this closed")
    backlog = (ROOT / "knowledge" / "backlog.md").read_text(encoding="utf-8")
    item = backlog.split("## B-026", 1)[1].split("\n## ", 1)[0]
    assert "status: built" in item, "B-026 is built and the backlog still says proposed"
    assert "P63" in item
