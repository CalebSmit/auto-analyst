"""P112 - the waiver the refusal already promised.

The writer refuses to write anything while a required input has no source, and says so:
*"nothing is written until a person supplies or waives them."* There was no way to waive.
A person accepted the review item, the step re-ran, recomputed the same list and asked
again - the same livelock P104 fixed for timing, in the one step that produces the
deliverable. The first real client folder blocked on eighteen inputs and blocked again on
the identical eighteen after the item was answered.

So every run whose mapping was not total ended with no workbook at all, and a mapping over
a real client's folder is rarely total.

The waiver is an acceptance of an item whose id carries a digest of the exact list that was
shown, so a list that changed between the question and the answer is a new question. And a
waived input is *written*, with the word `not found` in its own cell: this workbook is read
and copied into a valuation model, and a blank cell among forty filled ones reads as a
zero, which is a number, and the wrong one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from deliver.builder import NOT_FOUND, waiver_for
from graph.execute import Blocked
from tests.p21.conftest import mapping_for
from tools.write_template import read_named

ROOT = Path(__file__).resolve().parents[2]
RUN, ENG = "run_p112", "ENG-2026-01"




# ============================================================ the id


def test_the_waiver_names_the_exact_list() -> None:
    """Not just the step. An id of `unmapped:release` would let a waiver given yesterday
    cover a different set of unfilled inputs today, silently."""
    one = waiver_for("release", ["Revenue_FY1", "COGS_FY1"])
    same = waiver_for("release", ["COGS_FY1", "Revenue_FY1"])
    other = waiver_for("release", ["Revenue_FY1"])
    assert one == same, "order is not part of the question"
    assert one != other
    assert one.startswith("unmapped:release:")


def test_a_different_step_is_a_different_question() -> None:
    assert waiver_for("release", ["A"]) != waiver_for("model", ["A"])


# ============================================================ blocking, and not


def build(world: Any, *, waived: tuple[str, ...] = (), drop: tuple[str, ...] = ()) -> Any:
    """Build the P21 world's workbook, optionally with some bindings removed."""
    mapping = mapping_for(world)
    if drop:
        mapping = {
            **mapping,
            "template_mapping": {
                **mapping["template_mapping"],
                "bindings": [
                    b
                    for b in mapping["template_mapping"]["bindings"]
                    if b["named_range"] not in drop
                ],
            },
        }
    return world["builder"].build(
        mapping,
        world["inputs"].figures(),
        world["template"],
        run_id=RUN,
        engagement_id=ENG,
        step_id="release",
        waived=waived,
    )


def test_an_unwaived_list_still_blocks(world: Any) -> None:
    """The refusal is the default and stays the default. Nothing is written because a
    mapping was incomplete and nobody looked."""
    dropped = (world["template"].inputs.required[0],)
    with pytest.raises(Blocked) as blocked:
        build(world, drop=dropped)
    assert blocked.value.item_id == waiver_for("release", dropped)
    assert dropped[0] in blocked.value.subject


def test_the_refusal_says_how_to_answer_it() -> None:
    """The old message promised a waiver that did not exist. This one says what accepting
    does and what the cell will say."""
    source = (ROOT / "deliver" / "builder.py").read_text(encoding="utf-8")
    assert "accept this to write the workbook without them" in source
    assert "or supply them and run again" in source


def test_a_waived_list_writes(world: Any) -> None:
    """The whole phase. A person answered, and a workbook exists."""
    dropped = (world["template"].inputs.required[0],)
    built = build(world, drop=dropped, waived=(waiver_for("release", dropped),))
    assert built.data
    assert built.waived == dropped


def test_a_waiver_for_a_different_list_does_not_cover_this_one(world: Any) -> None:
    """The property the digest exists for. A person waived two inputs; the mapping then
    lost a third. That is a question nobody has answered."""
    dropped = tuple(world["template"].inputs.required[:2])
    stale = waiver_for("release", dropped[:1])
    with pytest.raises(Blocked):
        build(world, drop=dropped, waived=(stale,))


def test_a_total_mapping_needs_no_waiver(world: Any) -> None:
    built = build(world)
    assert built.waived == ()


# ============================================================ what the cell says


def test_a_waived_input_says_so_in_its_own_cell(world: Any) -> None:
    """Not left blank. This is the part that matters when somebody opens the file: a blank
    among forty filled cells reads as a zero, and in a valuation a zero is a number."""
    dropped = (world["template"].inputs.required[0],)
    built = build(world, drop=dropped, waived=(waiver_for("release", dropped),))
    assert built.writes[dropped[0]] == NOT_FOUND
    assert read_named(built.data, [dropped[0]])[dropped[0]] == NOT_FOUND


def test_the_marker_is_not_a_number(world: Any) -> None:
    """It cannot be summed by accident, and it cannot be mistaken for a figure that was
    read off a page."""
    assert isinstance(NOT_FOUND, str)
    with pytest.raises(ValueError, match="could not convert"):
        float(NOT_FOUND)


def test_the_bound_inputs_are_still_written_as_figures(world: Any) -> None:
    """A partial workbook is still a workbook. Waiving one input must not turn the other
    forty into text."""
    dropped = (world["template"].inputs.required[0],)
    built = build(world, drop=dropped, waived=(waiver_for("release", dropped),))
    numbers = [v for name, v in built.writes.items() if name not in dropped]
    assert numbers and all(isinstance(v, float) for v in numbers)


# ============================================================ the lock still holds


def test_the_lock_still_brackets_the_write(world: Any) -> None:
    """Marker cells included. The lock is the evidence the write was faithful, and a write
    it does not cover is a write nobody checked."""
    dropped = (world["template"].inputs.required[0],)
    built = build(world, drop=dropped, waived=(waiver_for("release", dropped),))
    assert built.lock.passed
    assert dropped[0] in built.locked_text
    assert NOT_FOUND in built.locked_text


# ============================================================ the record


def test_what_was_waived_is_named_rather_than_counted() -> None:
    """"Three inputs waived" is not an answer anybody can act on. Which three is."""
    source = (ROOT / "deliver" / "builder.py").read_text(encoding="utf-8")
    assert '"waived": sorted(unmapped),' in source
    driver = (ROOT / "workers" / "driver.py").read_text(encoding="utf-8")
    assert '"waived": list(built.waived),' in driver


def test_the_driver_reads_acceptances_and_nothing_else() -> None:
    """A rejection is not a waiver, and neither is an escalation. Only a person saying
    yes to this exact question lets the write happen.

    Asked of `_waivers` by calling it. This sliced the source and asserted
    `"DecisionKind.ACCEPTED" in body` with `REJECTED` and `ESCALATED` absent - and
    inverting the comparison to `!=` satisfies all three, which would make a review item
    somebody *refused* waive the inputs they refused, and an acceptance stop waiving.
    That is the delivery path's last human gate and it had no behavioural cover at all."""
    from ops.models import DecisionKind
    from workers.driver import RunDriver

    decided = [
        type("D", (), {"item_id": "unmapped:release:yes", "decision": DecisionKind.ACCEPTED})(),
        type("D", (), {"item_id": "unmapped:release:no", "decision": DecisionKind.REJECTED})(),
        type("D", (), {"item_id": "unmapped:release:up", "decision": DecisionKind.ESCALATED})(),
        type("D", (), {"item_id": "unmapped:release:fix", "decision": DecisionKind.CORRECTED})(),
    ]
    driver = RunDriver.__new__(RunDriver)
    driver.wiring = type(  # type: ignore[attr-defined]
        "W", (), {"store": type("S", (), {"decisions": lambda self, r: decided})()}
    )()
    assert driver._waivers("run-1") == frozenset({"unmapped:release:yes"})  # noqa: SLF001


def test_the_release_step_passes_its_own_id(world: Any) -> None:
    """The waiver id contains the step id, so a release that told the builder it was
    called something else would raise an item nobody could answer."""
    source = (ROOT / "workers" / "driver.py").read_text(encoding="utf-8")
    body = source[source.index("def _release") : source.index("def _waivers")]
    assert "step_id=attempt.step.id," in body
    assert "waived=self._waivers(context.run_id)," in body
