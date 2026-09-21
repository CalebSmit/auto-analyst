"""P86: three kinds of wrong.

The evals said how often a skill agreed with the gold set and nothing about how it was
wrong when it did not. Two of the ways need repairing in different places: a cited locator
that does not resolve is an extraction problem, and a total that does not re-add is an
arithmetic one. One number cannot say which happened.

LAVA (arXiv 2608.16763) separates the same two on financial documents and reports the
second at nearly zero by having the model produce a formula and a deterministic engine
execute it - which is what this build already does and had never measured.

Underneath that was B-041. `evals.metrics.provenance_of` ran the real Provenance Gate and
**nothing called it**: the one entry on P82's allowlist that was a defect rather than a
decision. Provenance was measured on `line-item-tagging` by a hand-rolled check on whether
a description had changed, and on `ebitda-normalization` - the skill whose every figure
carries a locator - not at all. A candidate skill could promote while faulting the gate
that decides whether a figure is really in the document it cites.

The tests that matter are the ones that make each kind actually happen. All three numbers
are zero on a healthy fixture, so a measurement that always returned zero would pass every
test written against the fixture alone, which is the shape of defect this repo is named
for. Each is therefore shown catching a fault built for it.
"""

from __future__ import annotations

import copy

import pytest
import yaml

from evals.harness import GATES_FILE, EvalHarness
from evals.metrics import ebitda_metrics, kinds_of_wrong, provenance_of
from evals.world import EvalWorld

KINDS = ("fabricated_evidence", "numeric_infidelity", "sent_to_a_person")


@pytest.fixture(scope="module")
def world():
    """Closed rather than left to the garbage collector. A module-scoped world holds an
    open sqlite handle, and on Windows the temporary directory's own finaliser cannot
    delete a file that is still open - which surfaces as an unraisable exception at
    interpreter exit and would become a failure the first time the suite runs with
    warnings as errors."""
    built = EvalWorld()
    yield built
    built.close()


@pytest.fixture(scope="module")
def measured(world) -> dict[str, float]:
    return ebitda_metrics(world)


# ------------------------------------------------------------ the three are reported


@pytest.mark.parametrize("kind", KINDS)
def test_each_kind_is_reported_beside_the_agreement_rate(measured, kind: str) -> None:
    assert kind in measured
    assert f"{kind}_rate" in measured


def test_the_healthy_fixture_fabricates_nothing_and_foots(measured) -> None:
    """Which is also why every test below builds its own fault: on this fixture the two
    failure counts are zero, so a metric that always answered zero would be
    indistinguishable from one that works."""
    assert measured["fabricated_evidence"] == 0.0
    assert measured["numeric_infidelity"] == 0.0


def test_how_much_still_goes_to_a_person_is_measured(measured) -> None:
    """The number nobody was reporting. A skill can score well on recall by routing
    everything and answering nothing, so this belongs beside it."""
    assert measured["sent_to_a_person"] == 11.0
    assert measured["items"] == 18.0
    assert round(measured["sent_to_a_person_rate"], 2) == 0.61


# ------------------------------------------ and each one catches a fault built for it


def test_fabricated_evidence_is_seen_when_a_locator_does_not_resolve(world) -> None:
    """The failure the Provenance Gate exists for, and the one the evals never asked it
    about. A locator nothing resolves is not a lower agreement rate - the figure is not in
    the document it claims to be in."""
    from evals.metrics import _henderson  # noqa: PLC0415

    case, _, inputs, _ = _henderson(world)
    from harness.procedures.ebitda_normalization import EbitdaNormalization  # noqa: PLC0415

    out = EbitdaNormalization().apply(
        case["proposal"], world.tools_for("ebitda-normalization@0.1.0", "ebitda"), inputs, "eval"
    )
    versions = {f["source_id"]: f.get("source_version", 1) for f in case["case"]["files"]}
    assert provenance_of(world, out, versions, run_id="eval_henderson") == 0

    spoiled = copy.deepcopy(out)
    spoiled["addback_schedule"][0]["amount"]["locator"] = "TB_FY25!ZZ999"
    assert provenance_of(world, spoiled, versions, run_id="eval_henderson") >= 1


def test_numeric_infidelity_is_seen_when_a_total_does_not_re_add(world) -> None:
    """Evidence that resolves and arithmetic that does not. Counted from the Tie-Out
    Gate's mismatches rather than from its pass flag, which said only that something
    somewhere disagreed and could not say how much of the output was affected."""
    from evals.metrics import _henderson  # noqa: PLC0415
    from harness.procedures.ebitda_normalization import EbitdaNormalization  # noqa: PLC0415

    case, _, inputs, _ = _henderson(world)
    out = EbitdaNormalization().apply(
        case["proposal"], world.tools_for("ebitda-normalization@0.1.0", "ebitda"), inputs, "eval"
    )
    versions = {f["source_id"]: f.get("source_version", 1) for f in case["case"]["files"]}

    spoiled = copy.deepcopy(out)
    moved = next(
        i for i in spoiled["addback_schedule"] if i["amount"].get("derivation")
    )
    moved["amount"]["value"] = float(moved["amount"]["value"]) + 1_000_000.0

    faulted = kinds_of_wrong(
        world, spoiled, versions, "eval_henderson", sent_to_a_person=0, items=1
    )
    assert faulted["numeric_infidelity"] >= 1


def test_the_two_failures_are_told_apart(world) -> None:
    """The whole point. A run of these numbers where fabricated_evidence moved and
    numeric_infidelity did not sends somebody to the reader; the other way round sends
    them to the arithmetic. A single rate sends them nowhere."""
    from evals.metrics import _henderson  # noqa: PLC0415
    from harness.procedures.ebitda_normalization import EbitdaNormalization  # noqa: PLC0415

    case, _, inputs, _ = _henderson(world)
    out = EbitdaNormalization().apply(
        case["proposal"], world.tools_for("ebitda-normalization@0.1.0", "ebitda"), inputs, "eval"
    )
    versions = {f["source_id"]: f.get("source_version", 1) for f in case["case"]["files"]}

    bad_locator = copy.deepcopy(out)
    bad_locator["addback_schedule"][0]["amount"]["locator"] = "TB_FY25!ZZ999"
    only_evidence = kinds_of_wrong(
        world, bad_locator, versions, "eval_henderson", sent_to_a_person=0, items=18
    )
    assert only_evidence["fabricated_evidence"] >= 1
    assert only_evidence["numeric_infidelity"] == 0.0


# ------------------------------------------------------------ B-041 is closed


def test_the_real_gate_is_what_decides(world, measured) -> None:
    """Not a second opinion written beside it. `provenance_of` builds a ProvenanceGate over
    the world's own parse store, which is the object a run uses."""
    import inspect

    from evals import metrics

    source = inspect.getsource(metrics.provenance_of)
    assert "ProvenanceGate(" in source
    assert "world.parse_store" in source


def test_provenance_of_is_called_by_something_that_is_not_a_test() -> None:
    """B-041, and the reason it was on P82's allowlist. This is the check that the
    allowlist entry can now be removed - and P82's own decay test is what removes it."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    callers = set()
    for path in (root / "evals").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "provenance_of":
                callers.add(path.name)
    assert callers, "provenance_of is still called by nothing in evals/"
    assert callers != {"metrics.py"} or "kinds_of_wrong" in (
        root / "evals" / "metrics.py"
    ).read_text(encoding="utf-8")


def test_the_allowlist_no_longer_excuses_it() -> None:
    """The excuse lived in P71's list - the function-level scan - not P82's, and the first
    version of this checked P82's, where it had never been. It passed by looking in the
    wrong place, which is the defect it was written about.

    P71's decay test refused the entry the moment `provenance_of` was called, which is
    what a decay check is for. The list is empty now."""
    from tests.p71.test_nothing_is_unwired import ALLOWED as FUNCTIONS
    from tests.p82.test_nothing_a_run_cannot_reach import ALLOWED as MODULES

    assert "evals.metrics.provenance_of" not in FUNCTIONS
    assert FUNCTIONS == {}, "an entry was added back without being read here"
    assert "evals.metrics" not in MODULES


# ------------------------------------------------------ and no threshold was invented


def test_the_two_invariants_are_gated_at_zero() -> None:
    """Not a practice decision: a figure whose locator does not resolve is not a worse
    figure, it is not a figure, and a recompute either falls inside the tolerance the
    practice already set or it does not."""
    spec = yaml.safe_load(GATES_FILE.read_text(encoding="utf-8"))
    gates = {g["metric"]: g for g in spec["skills"]["ebitda-normalization"]["gates"]}
    for metric in ("fabricated_evidence", "numeric_infidelity"):
        assert gates[metric]["op"] == "<="
        assert gates[metric]["threshold"] == 0
        assert gates[metric]["note"], f"{metric} is gated without saying why zero"


def test_the_number_that_belongs_to_the_practice_is_not_gated() -> None:
    """How much review is the right amount is the pilot's question. A threshold typed into
    the file that decides whether a skill may register would be a number nobody decided."""
    spec = yaml.safe_load(GATES_FILE.read_text(encoding="utf-8"))
    gates = {g["metric"] for g in spec["skills"]["ebitda-normalization"]["gates"]}
    assert "sent_to_a_person_rate" not in gates


def test_the_ungated_number_is_owed_somewhere_a_person_reads() -> None:
    """Reported and not gated is only honest if somebody is told it is waiting on them."""
    from pathlib import Path

    open_md = (Path(__file__).resolve().parents[2] / "BUILD" / "OPEN.md").read_text(
        encoding="utf-8"
    )
    assert "sent_to_a_person_rate" in open_md
    assert "How much review is the right amount" in open_md


def test_the_skill_still_clears_its_gates(world) -> None:
    """Two gates were added to a shipped skill. If they had not held, this would be a
    phase that stopped a skill registering rather than one that measured it."""
    card = EvalHarness().evaluate("ebitda-normalization", world)
    assert card.passed, [m.gate.metric for m in card.metrics if m.passed is False]


def test_the_new_gates_are_measured_rather_than_owed(world) -> None:
    """A gate the harness cannot compute is listed as owed. These two it can, and a gate
    that silently reported itself as owed would pass a skill without checking anything."""
    card = EvalHarness().evaluate("ebitda-normalization", world)
    named = {m.gate.metric: m for m in card.metrics}
    for metric in ("fabricated_evidence", "numeric_infidelity"):
        assert named[metric].gate.measured_by == "eval_harness"
        assert named[metric].value is not None
        assert named[metric].passed is True, "owed reads as neither passed nor failed"


def test_a_metric_reported_and_not_gated_is_still_on_the_scorecard(world) -> None:
    """Otherwise "reported" means it is computed and thrown away."""
    card = EvalHarness().evaluate("ebitda-normalization", world)
    assert "sent_to_a_person_rate" in card.extras
    assert card.extras["sent_to_a_person_rate"] > 0
