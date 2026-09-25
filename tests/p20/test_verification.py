"""The self-verification pass: a declared iteration, a separate invocation, and a
verifier that never sees the first pass's reasoning."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from graph.compile import CompiledGraph, Step
from graph.resolve import ResolvedScope
from harness.loops import LoopController
from harness.procedures import verifier_for
from harness.procedures.ebitda_normalization import ProposalRefused, VerificationInputs
from ops.run_store import SqlRunStore
from registries.contracts import ContractRegistry
from registries.errors import VERIFICATION_PASS, diagnose
from tests.messages import anywhere, sections_with, values_at
from tests.p20.conftest import ProposalPort, dispatch, events_of, first_pass


def test_self_verification_is_declared_on_the_ebitda_step_with_a_ceiling_of_one(
    plan: CompiledGraph, ebitda_step: Step
) -> None:
    assert "self_verification:ebitda" in ebitda_step.loops
    region = next(r for r in plan.loops if r.id == "self_verification:ebitda")
    assert region.max_iterations == 1 and region.members == ("ebitda",)


def test_the_pass_is_admitted_once_by_the_loop_controller_and_refused_a_second_time(
    world: dict[str, Any],
    plan: CompiledGraph,
    ebitda_step: Step,
    scope: ResolvedScope,
    case: dict[str, Any],
    controller: LoopController,
    store: SqlRunStore,
) -> None:
    done = first_pass(world, ebitda_step, scope, case)
    trigger = diagnose(VERIFICATION_PASS, "every EBITDA output", locator="ebitda", step_id="ebitda")
    first = controller.admit(
        world["run_id"],
        plan,
        ebitda_step,
        "self_verification",
        current_key=done.request_hash,
        next_key=f"verify:{done.request_hash}",
        next_inputs={"schedule": done.output_ref.content_hash},
        trigger=trigger,
    )
    assert first.allowed and first.iteration == 1 and first.ceiling == 1
    again = controller.admit(
        world["run_id"],
        plan,
        ebitda_step,
        "self_verification",
        current_key=f"verify:{done.request_hash}",
        next_key="verify:again",
        next_inputs={"schedule": "x"},
        trigger=trigger,
    )
    assert not again.allowed and again.code == "LOOP.EXHAUSTED"
    loop_events = [e for e in store.events(world["run_id"]) if e.level == "loop"]
    assert len(loop_events) == 1


def test_the_verifier_sees_amounts_citations_and_excerpts_and_never_the_reasoning(
    world: dict[str, Any], ebitda_step: Step, scope: ResolvedScope, case: dict[str, Any]
) -> None:
    done = first_pass(world, ebitda_step, scope, case)
    port = ProposalPort(case["verification"])
    verified = dispatch(
        world,
        ebitda_step,
        scope,
        port,
        VerificationInputs.from_pass(done.output, world["inputs"]),
        procedure=world["verifier"],
    )
    (request,) = port.requests
    user = request.messages[0].content
    # Asked of what was sent rather than of how it was punctuated. These read
    # `'"verification": true' in user` until P124 compacted the separators, at which point
    # three claims about what the verifier is handed failed over a space (tests/messages.py).
    (sent,) = sections_with(user, "verification", "items")
    assert sent["verification"] is True
    assert anywhere(user, "raw", "85,000"), "the cited excerpt, as the document wrote it"
    assert any(str(loc).startswith("IS!B") for loc in values_at(user, "locator")), (
        "the citation the verifier re-reads"
    )
    assert anywhere(user, "value", 85000), "the stated amount, for the verifier to check"
    for rationale in (c["rationale"] for c in case["proposal"]["candidates"]):
        assert rationale not in user, (
            f"the first pass's reasoning reached the verifier: {rationale}"
        )
    for item in done.output["addback_schedule"]:
        assert item["rationale"] not in user
    # The profile section carries the engagement's auto-accept bar by design; the
    # verifier's own payload carries no confidence and no review flag.
    payload = user.split("=== payload:", 1)[1]
    assert '"confidence"' not in payload and "review_required" not in payload
    assert "## Verification pass" in request.system
    assert verified.request_hash != done.request_hash


def test_an_unsupported_verdict_sends_the_item_to_a_person_and_nothing_else_changes(
    world: dict[str, Any],
    ebitda_step: Step,
    scope: ResolvedScope,
    case: dict[str, Any],
    contracts: ContractRegistry,
    store: SqlRunStore,
) -> None:
    done = first_pass(world, ebitda_step, scope, case)
    verified = dispatch(
        world,
        ebitda_step,
        scope,
        ProposalPort(case["verification"]),
        VerificationInputs.from_pass(done.output, world["inputs"]),
        procedure=world["verifier"],
    )
    assert contracts.check("skills/ebitda-normalization@1.0.0", verified.output) == ()
    before = {i["candidate_id"]: i for i in done.output["addback_schedule"]}
    after = {i["candidate_id"]: i for i in verified.output["addback_schedule"]}
    assert list(before) == list(after)
    target = case["expected"]["verifier_disagrees"]
    assert not before[target]["review_required"] and after[target]["review_required"]
    assert after[target]["rationale"].startswith("verification: not supported - ")
    for cid, item in after.items():
        if cid != target:
            assert item == before[cid]
    assert store.run(world["run_id"]).model_calls == 2, "two separate invocations"
    assert len(events_of(store, world["run_id"], "skill.completed")) == 2


def test_a_missing_verdict_is_a_review_and_an_unknown_one_is_refused(
    world: dict[str, Any], ebitda_step: Step, scope: ResolvedScope, case: dict[str, Any]
) -> None:
    done = first_pass(world, ebitda_step, scope, case)
    inputs = VerificationInputs.from_pass(done.output, world["inputs"])
    verifier = verifier_for("ebitda-normalization@0.1.0")

    partial = copy.deepcopy(case["verification"])
    dropped = partial["verdicts"].pop()
    out = verifier.apply(partial, world["tools_for"](), inputs, "pin")
    item = next(i for i in out["addback_schedule"] if i["candidate_id"] == dropped["candidate_id"])
    assert item["review_required"] and item["rationale"].startswith("verification: no verdict")

    invented = copy.deepcopy(case["verification"])
    invented["verdicts"].append({"candidate_id": "ADD-invented", "supported": True, "reason": "x"})
    with pytest.raises(ProposalRefused):
        verifier.apply(invented, world["tools_for"](), inputs, "pin")


def test_the_verification_contract_has_no_number_in_it(contracts: ContractRegistry) -> None:
    from tests.p02.conftest import walk_schemas

    schema = contracts.get("skills/ebitda-normalization-verification-proposal@1.0.0")
    for node in walk_schemas(schema):
        assert node.get("type") not in ("number", "integer"), node
