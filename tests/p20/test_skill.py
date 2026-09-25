"""The first pass through the dispatcher: every amount ties, recall against the analyst,
the officer-compensation test with its benchmark cited, and what escalates."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from graph.compile import Step
from graph.execute import Blocked
from graph.resolve import ResolvedScope
from guards.provenance import ProvenanceGate
from guards.tieout import TieoutGate
from guards.untrusted import BEGIN, SENTINEL_RULE
from harness.policy import PolicyDenied
from harness.procedures.ebitda_normalization import ProposalRefused
from harness.procedures.line_item_tagging import line_item_ref
from ops.models import DecisionKind
from ops.run_store import SqlRunStore
from registries.contracts import ContractRegistry
from registries.skills import SkillTree
from review import ConfidenceRouter, Item, Money, ReviewQueue, ReviewSurface
from tests.messages import anywhere
from tests.p15.conftest import profile
from tests.p20.conftest import (
    CLIENT,
    HITL,
    SCOPE_PATH,
    SKILL,
    ProposalPort,
    dispatch,
    events_of,
    first_pass,
    inputs_for,
)
from tools.recompute import recompute

CONTRACT = "skills/ebitda-normalization@1.0.0"


def test_the_skill_runs_end_to_end_and_every_amount_ties(
    world: dict[str, Any],
    ebitda_step: Step,
    scope: ResolvedScope,
    case: dict[str, Any],
    store: SqlRunStore,
    contracts: ContractRegistry,
) -> None:
    """The exit criterion: 100% of proposed add-backs tie via recompute. Twice over -
    the procedure's own call through the gated tool, and the tie-out guard re-deriving
    every figure independently from the parse store."""
    done = first_pass(world, ebitda_step, scope, case)
    schedule = done.output["addback_schedule"]

    assert done.skill == SKILL
    assert contracts.check(CONTRACT, done.output) == ()
    assert len(schedule) == case["expected"]["schedule_items"]
    assert all(item["recomputed"] for item in schedule)
    assert all(item["amount"]["derivation"] for item in schedule)

    tieout = TieoutGate(world["parse_store"], recompute, 0.0).check(done.output, world["run_id"])
    assert tieout.passed and tieout.checked == len(schedule)
    versions = {f["source_id"]: 1 for f in case["case"]["files"]}
    provenance = ProvenanceGate(contracts, world["parse_store"]).check(
        done.output, world["run_id"], versions
    )
    assert provenance.passed and provenance.checked == len(schedule)

    called = [e.payload["tool"] for e in events_of(store, world["run_id"], "tool.called")]
    assert called.count("recompute") >= len(schedule), "recompute on every proposed amount"
    assert done.model_calls == 1 and store.run(world["run_id"]).model_calls == 1


def test_recall_against_the_analysts_add_backs_is_at_least_90_percent(
    world: dict[str, Any], ebitda_step: Step, scope: ResolvedScope, case: dict[str, Any]
) -> None:
    done = first_pass(world, ebitda_step, scope, case)
    proposed = {
        (item["line_item_ref"], item["amount"]["period"]["end"][:4], item["category"])
        for item in done.output["addback_schedule"]
        if not item["recurs_in_all_periods"] or item["category"] != "non_recurring"
    }
    gold = {(line_item_ref(g["label"]), g["period"][2:], g["category"]) for g in case["gold"]}
    recalled = gold & proposed
    assert len(gold) == case["expected"]["gold"]
    assert len(recalled) / len(gold) >= 0.9, f"{len(recalled)}/{len(gold)}"
    missed = {g for g in gold if g not in proposed}
    assert missed == {(line_item_ref(case["expected"]["missed"]), "2023", "non_recurring")}


def test_the_model_sees_lines_tags_and_periods_never_a_value(
    world: dict[str, Any], ebitda_step: Step, scope: ResolvedScope, case: dict[str, Any]
) -> None:
    port = ProposalPort(case["proposal"])
    dispatch(world, ebitda_step, scope, port, world["inputs"])
    (request,) = port.requests
    user = request.messages[0].content
    assert user.startswith(BEGIN)
    assert "Legal settlement" in user and '"periods_present"' in user
    # The provenance, asked of the message's content rather than of its spelling - this
    # read `'"basis": "survey_median"' in user` until P124 (tests/messages.py).
    assert anywhere(user, "basis", "survey_median"), "the benchmark's provenance, not its amount"
    # The engagement profile is its own context section and carries the benchmark's
    # amount by design; the payload - what this skill chose to send - carries no value.
    payload = user.split("=== payload:", 1)[1]
    for value in ("85,000", "85000", "285000", "285,000", "4,020,000", "4020000", '"value"'):
        assert value not in payload, f"a value reached the model: {value}"
    assert SENTINEL_RULE in request.system
    flat = " ".join(request.system.lower().split())
    assert "you never apply one, and you never state its amount" in flat


def test_officer_pay_is_tested_against_the_profiles_benchmark_and_the_benchmark_is_cited(
    world: dict[str, Any], ebitda_step: Step, scope: ResolvedScope, case: dict[str, Any]
) -> None:
    """The F1 contract consumed: the benchmark comes from engagement_profile, is cited
    on every officer-pay item, and every such item is reviewed."""
    done = first_pass(world, ebitda_step, scope, case)
    officer = [i for i in done.output["addback_schedule"] if i["officer_comp_benchmark"]]
    assert len(officer) == 6
    baseline = profile()["owner_compensation_baseline"]
    for item in officer:
        assert item["officer_comp_benchmark"] == {
            "basis": baseline["basis"],
            "source": baseline["source"],
            "as_of": baseline["as_of"],
        }
        assert item["category"] == "owner_related" and item["review_required"]
        assert "officer comp test" in item["rationale"]
        assert "the benchmark of 285,000" in item["rationale"]
    fy23 = [i for i in officer if i["amount"]["period"]["end"] == "2023-12-31"]
    assert all("at or below" in i["rationale"] for i in fy23), "FY2023 total is exactly 285,000"
    fy25 = [i for i in officer if i["amount"]["period"]["end"] == "2025-12-31"]
    assert all("is above" in i["rationale"] for i in fy25)
    others = [i for i in done.output["addback_schedule"] if not i["officer_comp_benchmark"]]
    assert all(i["officer_comp_benchmark"] is None for i in others)


def test_a_candidate_recurring_across_all_periods_is_flagged_and_reviewed_not_proposed(
    world: dict[str, Any], ebitda_step: Step, scope: ResolvedScope, case: dict[str, Any]
) -> None:
    """The exit criterion. Repairs and maintenance is in every period; called
    non-recurring anyway, it reaches a person as flagged rather than the model as an
    add-back."""
    done = first_pass(world, ebitda_step, scope, case)
    trap = next(
        i
        for i in done.output["addback_schedule"]
        if i["candidate_id"] == case["expected"]["recurring_trap"]
    )
    assert trap["recurs_in_all_periods"] and trap["review_required"]
    assert "present in every period" in trap["rationale"]
    genuine = [
        i
        for i in done.output["addback_schedule"]
        if i["category"] == "non_recurring" and i["candidate_id"] != trap["candidate_id"]
    ]
    assert genuine and not any(i["recurs_in_all_periods"] for i in genuine)


def test_an_add_back_that_depends_on_a_fact_not_in_the_documents_is_reviewed(
    world: dict[str, Any], ebitda_step: Step, scope: ResolvedScope, case: dict[str, Any]
) -> None:
    done = first_pass(world, ebitda_step, scope, case)
    rent = [i for i in done.output["addback_schedule"] if i["category"] == "related_party"]
    assert len(rent) == 3
    for item in rent:
        assert item["review_required"]
        assert "depends on a fact not in the documents: market rent" in item["rationale"]


def test_no_benchmark_escalates_before_any_model_call(
    world: dict[str, Any],
    ebitda_step: Step,
    scope: ResolvedScope,
    case: dict[str, Any],
    store: SqlRunStore,
) -> None:
    """The profile that forgot its baseline is exactly how the officer test gets
    skipped, so the run blocks on a person with the skill's own hitl kind."""
    body = profile()
    del body["owner_compensation_baseline"]
    inputs = inputs_for(case, world["policy"], profile_body=body)
    assert inputs.benchmark is None
    port = ProposalPort(case["proposal"])
    with pytest.raises(Blocked) as blocked:
        dispatch(world, ebitda_step, scope, port, inputs)
    # The ESOP overlay tightens this skill's review level; the block carries the
    # resolved kind, which is at least as tight as the frontmatter's.
    resolved = scope.skill("ebitda-normalization").hitl
    assert blocked.value.kind == resolved == "all_addbacks_require_review"
    assert resolved != HITL, "the overlay raised the bar, and the block reflects it"
    assert "no benchmark" in blocked.value.subject
    assert port.requests == []
    kinds = {e.type for e in store.events(world["run_id"])}
    assert "skill.escalated" in kinds
    assert not kinds & {"model.called", "context.assembled", "tool.called"}


@pytest.mark.parametrize("how", ["unknown_line", "absent_period", "duplicate_id"])
def test_a_candidate_naming_what_the_step_was_not_given_is_refused(
    world: dict[str, Any], case: dict[str, Any], how: str
) -> None:
    proposal = copy.deepcopy(case["proposal"])
    first = proposal["candidates"][0]
    if how == "unknown_line":
        first["line_item_ref"] = "li_not_a_line"
    elif how == "absent_period":
        settlement = next(
            c for c in proposal["candidates"] if c["candidate_id"] == "ADD-settlement"
        )
        settlement["periods"] = ["FY2023"]
    else:
        proposal["candidates"][1]["candidate_id"] = first["candidate_id"]
    with pytest.raises(ProposalRefused) as refused:
        world["procedure"].apply(proposal, world["tools_for"](), world["inputs"], "pin")
    assert refused.value.diagnostic.code == "SKILL.UNKNOWN_LINE_ITEM"


def test_a_proposal_carrying_an_amount_is_refused_before_any_tool_runs(
    world: dict[str, Any],
    ebitda_step: Step,
    scope: ResolvedScope,
    case: dict[str, Any],
    store: SqlRunStore,
) -> None:
    """The proposal is refused, and - because `ebitda` declares `guard_repair` - the
    refusal is offered to the loop controller rather than ending the step outright.

    This asserted `GuardFailed` until P59, when the declared loops started being reachable.
    The claim it was making is unchanged and now stronger: the guard still refuses, still
    with `SKILL.SCHEMA_INVALID`, still before any tool runs - and the region the recipe has
    declared on this step since P14 is named rather than ignored.
    """
    from harness.loops import RepairNeeded

    numeric = copy.deepcopy(case["proposal"])
    numeric["candidates"][0]["amount"] = 285000
    with pytest.raises(RepairNeeded) as refused:
        dispatch(world, ebitda_step, scope, ProposalPort(numeric), world["inputs"])
    assert refused.value.diagnostic.code == "SKILL.SCHEMA_INVALID"
    assert refused.value.loop == "guard_repair"
    assert refused.value.feedback is not None, "the next pass has to be given what was wrong"
    assert events_of(store, world["run_id"], "tool.called") == []


def test_the_skill_may_only_call_the_three_tools_it_declared(world: dict[str, Any]) -> None:
    tools = world["tools_for"]()
    assert tools.names() == ("recompute", "chart_of_accounts_lookup", "precedent_lookup")
    with pytest.raises(PolicyDenied):
        tools["timing_normalizer"](engagement_id=tools.engagement_id)


def test_the_output_has_no_field_a_concluded_value_could_enter(
    contracts: ContractRegistry,
) -> None:
    """Never applies an add-back. The schedule is items with evidence; there is no
    normalized EBITDA, no total, no adjusted anything."""
    schema = contracts.get(CONTRACT)
    assert set(schema["properties"]) == {"schema_version", "produced_by", "addback_schedule"}
    item = schema["properties"]["addback_schedule"]["items"]["properties"]
    for banned in ("normalized", "adjusted", "total", "applied", "ebitda"):
        assert not [k for k in item if banned in k.lower()], banned


def test_an_approved_add_back_becomes_a_precedent_without_its_amount(
    world: dict[str, Any],
    ebitda_step: Step,
    scope: ResolvedScope,
    case: dict[str, Any],
    router: ConfidenceRouter,
    queue: ReviewQueue,
    surface: ReviewSurface,
) -> None:
    done = first_pass(world, ebitda_step, scope, case)
    settlement = next(
        i for i in done.output["addback_schedule"] if i["candidate_id"] == "ADD-settlement"
    )
    figure = settlement["amount"]
    item = Item(
        item_id=settlement["candidate_id"],
        skill=SKILL,
        question="Legal settlement FY2024: non-recurring?",
        source_excerpt=settlement["evidence"][0]["excerpt"],
        proposal={**settlement, "description": "Legal settlement"},
        confidence=figure["confidence"],
        amount=Money(float(figure["value"]) * int(figure["scale"]), figure["currency"]),
        category=settlement["category"],
        review_required=settlement["review_required"],
    )
    routing = router.route(item, HITL, run_id=world["run_id"], engagement_id="HEND-2026-04")
    queue.enqueue(world["run_id"], "HEND-2026-04", item, routing, step_id="ebitda")
    surface.decide(
        world["run_id"],
        item.item_id,
        decided_by="Dana Whitfield",
        decision=DecisionKind.ACCEPTED,
        expected_version=1,
    )
    written = world["writeback"].write(
        world["run_id"], item.item_id, client_id=CLIENT, scope_path=SCOPE_PATH, identifiers=()
    )
    assert written.example["category"] == "non_recurring"
    assert written.example["description"] == "Legal settlement"
    assert "amount" not in written.example and "85" not in str(written.example)


def test_the_skill_file_is_written_and_says_it_never_applies(tree: SkillTree) -> None:
    skill = next(s for s in tree.all() if s.name == "ebitda-normalization")
    assert skill.status == "draft"
    assert skill.scripts == (), "no Python under skills/"
    body = tree.body(skill)
    for heading in (
        "## When to use",
        "## When not to use",
        "## Procedure",
        "## Verification pass",
        "## Escalate when",
    ):
        assert heading in body
    assert "Skeleton" not in body
    flat = " ".join(body.lower().split())
    assert "you never apply one, and you never state its amount" in flat
    assert "goes to a person whatever your confidence says" in flat
    for ref in ("addback-taxonomy.md", "officer-comp-tests.md", "worked-examples.md"):
        text = tree.reference(skill, ref)
        assert "Placeholder" not in text and len(text.splitlines()) > 20
