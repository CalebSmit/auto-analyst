"""The Replay Harness: a candidate over the recorded inputs of a past run, and a diff
against what was delivered and what a person later corrected."""

from __future__ import annotations

from typing import Any

import pytest

from evals import ReplayHarness
from evals.replay import json_diff, restore
from graph.compile import Step
from graph.resolve import ResolvedScope
from ops.blobs import LocalContentStore
from ops.models import DecisionKind
from ops.run_store import SqlRunStore
from review import ConfidenceRouter, ReviewQueue, ReviewSurface
from tests.p19.conftest import (
    ProposalPort,
    decide,
    dispatch,
    inputs_for,
    load_fixture,
    proposal_of,
    tag,
)


@pytest.fixture
def delivered(world: dict[str, Any], tagging_step: Step, scope: ResolvedScope) -> Any:
    """One real tagging step, dispatched: the three blobs replay reads are on the record."""
    items, _, batches = load_fixture()
    return dispatch(world, tagging_step, scope, ProposalPort(batches[0]), inputs_for(items[:20]))


def test_the_dispatcher_records_inputs_proposal_and_output_for_every_skill_step(
    world: dict[str, Any], delivered: Any, store: SqlRunStore, blobs: LocalContentStore
) -> None:
    harness = ReplayHarness(store, blobs)
    (record,) = harness.records(world["run_id"])
    assert record.step_id == "tagging" and record.skill == "line-item-tagging@0.1.0"
    assert record.output_ref == delivered.output_ref.content_hash
    assert record.inputs_ref == delivered.inputs_ref.content_hash
    assert record.proposal_ref == delivered.proposal_ref.content_hash
    assert harness.delivered(record) == delivered.output
    inputs = harness.inputs_of(record)
    assert len(inputs.items) == 20 and inputs.taxonomy_version == "coa-taxonomy@1.0.0"


def test_replay_produces_a_diff_not_a_pass_fail(
    world: dict[str, Any], delivered: Any, store: SqlRunStore, blobs: LocalContentStore
) -> None:
    """The exit criterion. A candidate that retags one line and leaves the rest alone
    shows exactly that: the changed paths on one item, and nothing else."""
    harness = ReplayHarness(store, blobs)
    items, _, batches = load_fixture()
    target = items[3].line_item_ref

    def candidate(inputs: Any) -> dict[str, Any]:
        proposal = proposal_of(
            [
                tag(target, "other_operating_expense", confidence=0.7)
                if item["line_item_ref"] == target
                else dict(item)
                for item in batches[0]["items"]
            ]
        )
        out: dict[str, Any] = world["procedure"].apply(
            proposal, world["tools_for"]("replay"), inputs, "candidate"
        )
        return out

    replay = harness.replay(
        world["run_id"], "tagging", candidate, candidate_skill="line-item-tagging@0.2.0"
    )
    assert not replay.unchanged
    paths = {c.path for c in replay.changes}
    assert all(f"[line_item_ref={target}]" in p for p in paths), paths
    assert any(p.endswith(".category") for p in paths)
    assert any(p.endswith(".review_required") for p in paths)
    assert f"line_item_ref={target}" in replay.report()
    assert replay.delivered == delivered.output


def test_a_candidate_that_changes_nothing_shows_an_empty_diff(
    world: dict[str, Any], delivered: Any, store: SqlRunStore, blobs: LocalContentStore
) -> None:
    harness = ReplayHarness(store, blobs)
    items, _, batches = load_fixture()

    def same(inputs: Any) -> dict[str, Any]:
        out: dict[str, Any] = world["procedure"].apply(
            batches[0], world["tools_for"]("replay"), inputs, "pin"
        )
        return out

    replay = harness.replay(
        world["run_id"], "tagging", same, candidate_skill="line-item-tagging@0.1.0"
    )
    assert replay.unchanged and replay.changes == ()


def test_replay_reports_whether_the_candidate_agrees_with_a_later_correction(
    world: dict[str, Any],
    delivered: Any,
    store: SqlRunStore,
    blobs: LocalContentStore,
    router: ConfidenceRouter,
    queue: ReviewQueue,
    surface: ReviewSurface,
) -> None:
    """Against what a human later corrected: the analyst moved one item to another
    category; a candidate that lands there agrees, one that does not is told so."""
    items, _, batches = load_fixture()
    first = delivered.output["tagged_line_items"][0]
    decide(
        router=router,
        queue=queue,
        surface=surface,
        run_id=world["run_id"],
        tagged=first,
        decision=DecisionKind.CORRECTED,
        answer={"category": "professional_fees"},
        rationale="it is a fee",
    )
    harness = ReplayHarness(store, blobs)

    def agreeing(inputs: Any) -> dict[str, Any]:
        proposal = proposal_of(
            [
                tag(first["line_item_ref"], "professional_fees", confidence=0.9)
                if item["line_item_ref"] == first["line_item_ref"]
                else dict(item)
                for item in batches[0]["items"]
            ]
        )
        out: dict[str, Any] = world["procedure"].apply(
            proposal, world["tools_for"]("replay"), inputs, "pin"
        )
        return out

    replay = harness.replay(world["run_id"], "tagging", agreeing, candidate_skill="x@0.2.0")
    (check,) = replay.corrections
    assert check.item_id == first["line_item_ref"] and check.decided_by == "Dana Whitfield"
    assert check.agrees and check.candidate is not None
    assert "candidate agrees" in replay.report()

    def disagreeing(inputs: Any) -> dict[str, Any]:
        out: dict[str, Any] = world["procedure"].apply(
            batches[0], world["tools_for"]("replay"), inputs, "pin"
        )
        return out

    (check,) = harness.replay(
        world["run_id"], "tagging", disagreeing, candidate_skill="x@0.1.0"
    ).corrections
    assert not check.agrees


def test_replay_reads_the_record_and_the_blobs_and_nothing_re_identified(
    world: dict[str, Any], delivered: Any, store: SqlRunStore, blobs: LocalContentStore
) -> None:
    """Masked payloads only: the harness is built from the run store and the content
    store, holds no vault, no delivery port and no unmasker, and the inputs it restores
    are the ones the skill was given."""
    import inspect

    import evals.replay as replay_module

    harness = ReplayHarness(store, blobs)
    assert set(inspect.signature(ReplayHarness.__init__).parameters) == {"self", "store", "blobs"}
    imports = [
        line
        for line in inspect.getsource(replay_module).splitlines()
        if line.startswith(("import ", "from "))
    ]
    for forbidden in ("privacy.vault", "privacy.unmask", "ports.delivery", "deliver"):
        assert not any(forbidden in line for line in imports), forbidden
    record = harness.record_for(world["run_id"], "tagging")
    assert (
        harness.inputs_of(record).items[0].description
        == delivered.output["tagged_line_items"][0]["description"]
    )


def test_every_shipped_skills_inputs_restore_from_what_the_dispatcher_records() -> None:
    from dataclasses import asdict

    from harness.procedures.ebitda_normalization import Benchmark, EbitdaInputs, Line
    from harness.procedures.model_load import FigureRef, ModelLoadInputs, TemplateInput
    from harness.procedures.timing_normalization import SourceFile, TimingInputs

    timing = TimingInputs(
        files=(
            SourceFile(
                "sha256:" + "a" * 64,
                "IS.xlsx",
                "financial_statements",
                {"IS!B2:B3": []},
                1,
                "USD",
                "FY",
                ("2025-12-31",),
            ),
        )
    )
    assert restore("timing-normalization@0.1.0", asdict(timing)) == timing
    ebitda = EbitdaInputs(
        periods=("FY2025",),
        lines=(Line("li_1", "Rent", "rent", False, False, ("Rent",), {"FY2025": {"value": 1.0}}),),
        blocks={},
        benchmark=Benchmark(1.0, "USD", "survey_median", "ERI", "2025-06-30"),
        materiality_amount=20000.0,
        materiality_currency="USD",
        always_review_categories=frozenset({"owner_related"}),
    )
    restored = restore("ebitda-normalization@0.1.0", _plain(asdict(ebitda)))
    assert restored == ebitda
    model = ModelLoadInputs(
        "T@1",
        "1",
        (TemplateInput("Revenue_FY1", "Revenue", "FY1", True),),
        (FigureRef("timing:Revenue:FY1", "timing", "Revenue", "FY1", {"value": 2.0}),),
        ("FY1",),
    )
    assert restore("model-load@0.1.0", asdict(model)) == model
    with pytest.raises(KeyError):
        restore("no-such-skill@0.1.0", {})


def _plain(value: Any) -> Any:
    """What the dispatcher's canonical JSON does to a frozenset."""
    if isinstance(value, frozenset | set):
        return sorted(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


def test_json_diff_aligns_keyed_lists_by_id_and_names_every_changed_path() -> None:
    before = {
        "items": [{"line_item_ref": "a", "category": "x"}, {"line_item_ref": "b", "category": "y"}]
    }
    after = {
        "items": [{"line_item_ref": "b", "category": "y"}, {"line_item_ref": "a", "category": "z"}]
    }
    assert [c.path for c in json_diff(before, after)] == ["$.items[line_item_ref=a].category"]
    assert json_diff({"n": [1, 2]}, {"n": [1, 3, 4]}) == json_diff({"n": [1, 2]}, {"n": [1, 3, 4]})
    assert [c.path for c in json_diff({"n": [1, 2]}, {"n": [1, 3, 4]})] == ["$.n[1]", "$.n[2]"]
    assert json_diff({"a": 1}, {"a": 1}) == ()
