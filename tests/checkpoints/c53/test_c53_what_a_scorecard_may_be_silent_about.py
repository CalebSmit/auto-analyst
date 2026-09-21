"""C53 - What a scorecard is allowed to be silent about.

P86 added two gates to a shipped skill and emptied P71's allowlist. Both change what
stops a skill registering, and neither is visible from the phase's own tests.

A gate can be silent in three ways and only one of them is honest. It can be *owed* -
the offline harness cannot measure it, which is `shadow_disagreement` and is written down
as such. It can be *absent* - nobody wrote it, which is `sent_to_a_person_rate` and is
deliberate, because what that number is allowed to be is the pilot's decision. Or it can
be **present and not actually measured**, which is a skill promoting on a check that ran
nothing, and is the failure this exists to catch.

The same shape applies to the allowlist. It held one entry, and the entry was a defect
rather than a decision: `provenance_of` ran the real Provenance Gate and nothing called
it, so a candidate skill could promote while faulting the gate that decides whether a
figure is really in the document it cites. P71's decay test refused the excuse the moment
P86 wired it. An empty allowlist is not a weaker check - it is the check having nothing
left to excuse, and this is where that stays true.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from evals.harness import GATES_FILE, EvalHarness
from evals.metrics import METRICS, kinds_of_wrong
from evals.world import EvalWorld

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def world():
    built = EvalWorld()
    yield built
    built.close()


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return yaml.safe_load(GATES_FILE.read_text(encoding="utf-8"))


# ------------------------------------------------- every gate is one of three things


def test_every_gate_is_measured_or_says_who_measures_it(spec) -> None:
    """The three states, and no fourth. A gate with a threshold the harness computes, or
    one named as owed to something else - never one that is present and answers nothing."""
    for skill, entry in spec["skills"].items():
        for gate in entry.get("gates", []):
            assert "op" in gate and "threshold" in gate, f"{skill}/{gate['metric']}"
            if gate.get("measured_by", "eval_harness") != "eval_harness":
                assert gate.get("note"), f"{skill}/{gate['metric']} is owed without saying why"


def test_a_gate_the_harness_claims_to_measure_really_produces_a_number(world, spec) -> None:
    """The dishonest silence. A gate listed as measured by the harness, whose metric the
    harness does not compute, would read as passing on a scorecard while checking nothing."""
    for skill, entry in spec["skills"].items():
        if entry.get("status") != "shipped" or skill not in METRICS:
            continue
        card = EvalHarness().evaluate(skill, world)
        for metric in card.metrics:
            if metric.gate.measured_by == "eval_harness":
                assert metric.value is not None, f"{skill}/{metric.gate.metric} measured nothing"
                assert metric.passed is not None


def test_the_two_new_gates_are_measured_on_the_skill_they_were_added_to(world) -> None:
    card = EvalHarness().evaluate("ebitda-normalization", world)
    named = {m.gate.metric: m for m in card.metrics}
    for metric in ("fabricated_evidence", "numeric_infidelity"):
        assert named[metric].value == 0.0
        assert named[metric].passed is True


def test_a_gate_at_zero_says_why_zero(spec) -> None:
    """Zero is either an invariant or a threshold somebody should have been asked about,
    and the difference has to be written down. A figure whose locator does not resolve is
    not a worse figure - it is not a figure; that is an invariant. How many add-backs may
    go to a person is not."""
    for skill, entry in spec["skills"].items():
        for gate in entry.get("gates", []):
            if gate.get("threshold") == 0 and gate.get("op") == "<=":
                assert gate.get("blueprint") or gate.get("note"), f"{skill}/{gate['metric']}"


# ------------------------------------------------- and the silence that is deliberate


def test_the_practice_s_number_is_reported_and_not_gated(world, spec) -> None:
    """Absent from the gates, present on the scorecard, and owed in writing. Any two of
    those three without the third is either a number nobody decided or a measurement
    nobody sees."""
    gates = {g["metric"] for g in spec["skills"]["ebitda-normalization"]["gates"]}
    assert "sent_to_a_person_rate" not in gates

    card = EvalHarness().evaluate("ebitda-normalization", world)
    assert card.extras["sent_to_a_person_rate"] > 0

    owed = (ROOT / "BUILD" / "OPEN.md").read_text(encoding="utf-8")
    assert "sent_to_a_person_rate" in owed


def test_a_skill_that_answered_nothing_would_not_look_good(world) -> None:
    """Why that number is worth carrying beside recall. Routing everything to a person is
    a way to be wrong about nothing, and an agreement rate cannot tell it from being
    right."""
    card = EvalHarness().evaluate("ebitda-normalization", world)
    assert 0.0 < card.extras["sent_to_a_person_rate"] < 1.0, (
        "either everything or nothing is routed, and this fixture can say neither"
    )


# ------------------------------------------------- the kinds really are told apart


def test_the_two_failures_move_independently(world) -> None:
    """Through the real gates, on real output, with one fault at a time. If both numbers
    moved together they would be one number wearing two names."""
    from evals.metrics import _henderson
    from harness.procedures.ebitda_normalization import EbitdaNormalization

    case, _, inputs, _ = _henderson(world)
    out = EbitdaNormalization().apply(
        case["proposal"], world.tools_for("ebitda-normalization@0.1.0", "ebitda"), inputs, "eval"
    )
    versions = {f["source_id"]: f.get("source_version", 1) for f in case["case"]["files"]}

    def kinds(output: dict[str, Any]) -> tuple[float, float]:
        found = kinds_of_wrong(
            world, output, versions, "eval_henderson", sent_to_a_person=0, items=18
        )
        return found["fabricated_evidence"], found["numeric_infidelity"]

    assert kinds(out) == (0.0, 0.0)

    bad_locator = copy.deepcopy(out)
    bad_locator["addback_schedule"][0]["amount"]["locator"] = "TB_FY25!ZZ999"
    evidence_only = kinds(bad_locator)
    assert evidence_only[0] >= 1 and evidence_only[1] == 0.0

    bad_sum = copy.deepcopy(out)
    moved = next(i for i in bad_sum["addback_schedule"] if i["amount"].get("derivation"))
    moved["amount"]["value"] = float(moved["amount"]["value"]) + 1_000_000.0
    arithmetic_only = kinds(bad_sum)
    assert arithmetic_only[1] >= 1


def test_a_fabricated_figure_would_stop_the_skill_registering(world) -> None:
    """The gate, not only the metric. Measuring a thing and letting it through is the
    silence this checkpoint is named for."""
    harness = EvalHarness()
    gates = {g.metric: g for g in harness.gates_for("ebitda-normalization")}
    fabricated = gates["fabricated_evidence"]
    assert fabricated.op == "<=" and fabricated.threshold == 0

    # one fabricated figure is one more than zero, so the gate would not hold
    assert not _holds(fabricated.op, 1.0, fabricated.threshold)
    assert _holds(fabricated.op, 0.0, fabricated.threshold)


def _holds(op: str, value: float, threshold: float) -> bool:
    return {"<=": value <= threshold, ">=": value >= threshold,
            "<": value < threshold, ">": value > threshold}[op]


# ------------------------------------------------- and nothing is excused any more


def test_the_unwired_allowlists_are_both_empty() -> None:
    """P71 excuses functions and P82 excuses modules. P71's one entry was a defect rather
    than a decision and P86 closed it; P82's are decisions, each citing a live backlog
    item. If P71's ever refills, the entry is either a real seam - which belongs in the
    backlog - or a defect somebody excused instead of fixing."""
    from tests.p71.test_nothing_is_unwired import ALLOWED as FUNCTIONS

    assert FUNCTIONS == {}, f"a function is excused again: {sorted(FUNCTIONS)}"


def test_the_scan_still_reports_something_so_the_empty_list_means_something(world) -> None:
    """An empty allowlist beside a scan that has stopped looking is indistinguishable from
    an empty allowlist beside a clean tree."""
    from tests.p71.test_nothing_is_unwired import public_functions
    from tests.p82.test_nothing_a_run_cannot_reach import ALLOWED as MODULES
    from tests.p82.test_nothing_a_run_cannot_reach import unreachable

    # 169 when this was written. The floor is a long way below that because the number
    # moves with every phase; what it is here for is a scan that has stopped reading the
    # tree at all, which is the only way an empty allowlist stops meaning anything.
    assert len(public_functions()) > 100, "the function scan has stopped seeing the tree"
    assert set(unreachable()) == set(MODULES), "the module scan and its excuses disagree"


def test_every_module_still_excused_cites_a_live_backlog_item() -> None:
    """P82's rule, re-run here because P86 closed one of the items it cites and a closed
    item excusing a live gap is the record disagreeing with the code."""
    from tests.p82.test_nothing_a_run_cannot_reach import ALLOWED, backlog_items

    items = backlog_items()
    for module, (cited, _) in sorted(ALLOWED.items()):
        assert cited in items, f"{module} cites {cited}, which is not in the backlog"
        assert not items[cited].startswith("built ("), f"{cited} is closed and {module} is not"


def test_the_backlog_says_b041_is_built() -> None:
    from tests.p82.test_nothing_a_run_cannot_reach import backlog_items

    assert backlog_items()["B-041"].startswith("built (2026-09-20, P86)")
