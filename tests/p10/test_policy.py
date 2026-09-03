"""The Policy Gate: four conditions, evaluated before anything runs, denials recorded.

Two exit criteria live here - a tool outside the allowlist is denied and the denial is in
the event stream; an argument naming another engagement is denied - and the thing the
phase note is really about: a wrong action can produce a right-looking result, so the
only place to catch it is before it happens.
"""

from __future__ import annotations

import pytest

from harness.policy import EVALUATORS, PolicyGate, RunScope
from ops.run_store import SqlRunStore
from registries.constraints import ConstraintRegistry
from registries.errors import RegistryError
from tests.p10.conftest import CALLER, ENGAGEMENT, OTHER, ROOT, action

# ---------------------------------------------------------------- the four


def test_a_well_formed_proposal_is_allowed(gate: PolicyGate, run: RunScope) -> None:
    decision = gate.decide(action(), run)
    assert decision.allowed
    assert decision.code is None
    assert bool(decision)


def test_a_tool_not_on_the_allowlist_is_denied_and_recorded(
    gate: PolicyGate, run: RunScope, store: SqlRunStore, started: str
) -> None:
    """The exit criterion. ebitda-normalization declares recompute,
    chart_of_accounts_lookup and precedent_lookup. index_lookup is a real tool it may
    not call - and the denial names the code, the owner and what to do."""
    decision = gate.decide(action("index_lookup"), run)

    assert not decision.allowed
    assert decision.code == "POLICY.TOOL_NOT_DECLARED"
    assert decision.owner == "policy"
    assert "does not declare index_lookup" in decision.reason

    denials = [e for e in store.events(started) if e.type == "policy.deny"]
    assert len(denials) == 1
    assert denials[0].diagnostic_code == "POLICY.TOOL_NOT_DECLARED"
    assert denials[0].payload["owner"] == "policy"
    assert denials[0].node_id == "policy_gate"


def test_an_argument_naming_another_engagement_is_denied(
    gate: PolicyGate, run: RunScope, store: SqlRunStore, started: str
) -> None:
    """The exit criterion, and the failure that would end the project. Reading another
    engagement's folder returns perfectly valid data."""
    decision = gate.decide(action(args={"engagement_id": OTHER, "limit": 10}), run)

    assert not decision.allowed
    assert decision.code == "POLICY.ARG_OUT_OF_SCOPE"
    assert decision.predicate == "engagement_scoped"
    assert OTHER in decision.reason
    assert [e.diagnostic_code for e in store.events(started) if e.type == "policy.deny"] == [
        "POLICY.ARG_OUT_OF_SCOPE"
    ]


def test_a_proposal_for_another_engagement_is_denied_before_the_predicates(
    gate: PolicyGate, run: RunScope
) -> None:
    """Caught twice on purpose: the action's own engagement field, then the predicate
    over its arguments."""
    decision = gate.decide(action(engagement=OTHER), run)
    assert decision.code == "POLICY.ARG_OUT_OF_SCOPE"
    assert decision.predicate is None, "refused before any predicate ran"


def test_a_call_over_budget_is_denied(gate: PolicyGate, run: RunScope) -> None:
    decision = gate.decide(action(estimated_cost_usd=run.budget_remaining_usd + 0.01), run)
    assert decision.code == "POLICY.BUDGET_EXCEEDED"
    assert decision.predicate == "budget_remaining"
    assert decision.owner == "policy"


def test_a_call_exactly_at_budget_is_allowed(gate: PolicyGate, run: RunScope) -> None:
    """The boundary. A ceiling is inclusive or it is a different number."""
    assert gate.decide(action(estimated_cost_usd=run.budget_remaining_usd), run).allowed


# --------------------------------------------------------------- predicates


def test_a_path_outside_the_engagement_root_is_denied(gate: PolicyGate, run: RunScope) -> None:
    decision = gate.decide(
        action(args={"engagement_id": ENGAGEMENT, "path": "engagements/NOVK-2026-11/tb.xlsx"}),
        run,
    )
    assert decision.code == "POLICY.ARG_OUT_OF_SCOPE"
    assert decision.predicate == "path_within_engagement"


def test_a_path_that_climbs_out_is_denied(gate: PolicyGate, run: RunScope) -> None:
    """`..` inside the root is outside the root."""
    decision = gate.decide(
        action(args={"engagement_id": ENGAGEMENT, "path": f"{ROOT}/../NOVK-2026-11/x"}), run
    )
    assert decision.predicate == "path_within_engagement"


def test_a_path_inside_the_root_is_allowed(gate: PolicyGate, run: RunScope) -> None:
    assert gate.decide(
        action(args={"engagement_id": ENGAGEMENT, "path": f"{ROOT}/inbox/tb.xlsx"}), run
    ).allowed


def test_a_row_limit_above_the_cap_is_denied(
    gate: PolicyGate, run: RunScope, constraints: ConstraintRegistry
) -> None:
    cap = constraints.tools["recompute"].caps["max_rows"]
    decision = gate.decide(action(args={"engagement_id": ENGAGEMENT, "limit": cap + 1}), run)
    assert decision.predicate == "row_cap"
    assert gate.decide(action(args={"engagement_id": ENGAGEMENT, "limit": cap}), run).allowed


def test_a_write_on_a_read_only_tool_is_denied(gate: PolicyGate, run: RunScope) -> None:
    decision = gate.decide(action("precedent_lookup", mode="write", args={
        "engagement_id": ENGAGEMENT, "scope": "valuation/esop/repeat",
    }), run)
    assert decision.predicate == "read_only_tools_write_nothing"


def test_a_precedent_lookup_must_declare_a_scope(gate: PolicyGate, run: RunScope) -> None:
    """Retrieval is scope-built or it is not done."""
    decision = gate.decide(action("precedent_lookup", args={"engagement_id": ENGAGEMENT}), run)
    assert decision.predicate == "precedent_scope_declared"


def test_a_precedent_lookup_outside_the_practice_is_denied(
    gate: PolicyGate, run: RunScope
) -> None:
    """A Corporate Finance decision is never available to an ESOP valuation."""
    decision = gate.decide(action("precedent_lookup", args={
        "engagement_id": ENGAGEMENT, "scope": "corporate-finance/tbd/repeat",
    }), run)
    assert decision.predicate == "precedent_scope_declared"
    assert "corporate-finance" in decision.reason


def test_an_unpinned_taxonomy_version_is_denied(gate: PolicyGate, run: RunScope) -> None:
    """A run that read two taxonomy versions cannot say which one it tagged against."""
    decision = gate.decide(action("chart_of_accounts_lookup", args={
        "engagement_id": ENGAGEMENT, "version": "coa-taxonomy@2.0.0",
    }), run)
    assert decision.predicate == "pinned_versions_only"
    assert gate.decide(action("chart_of_accounts_lookup", args={
        "engagement_id": ENGAGEMENT, "version": "coa-taxonomy@1.0.0",
    }), run).allowed


def test_a_tool_outside_the_namespace_is_a_different_refusal(
    gate: PolicyGate, run: RunScope
) -> None:
    """Not "not declared" - not a tool at all. The owner is config, not policy, because
    the fix is in a file rather than in a skill's conduct."""
    decision = gate.decide(action("delete_everything"), run)
    assert decision.code == "SCOPE.UNKNOWN_TOOL"
    assert decision.owner == "config"


# ------------------------------------------------------- allow is recorded too


def test_an_allow_is_in_the_stream_as_well(
    gate: PolicyGate, run: RunScope, store: SqlRunStore, started: str
) -> None:
    """A gate that only speaks when it refuses is, on a quiet day, indistinguishable from
    a gate that never ran."""
    gate.decide(action(), run)
    allows = [e for e in store.events(started) if e.type == "policy.allow"]
    assert len(allows) == 1
    assert allows[0].payload["tool"] == "recompute"
    assert allows[0].payload["caller"] == CALLER
    assert allows[0].diagnostic_code is None


def test_there_is_no_allow_with_a_warning(gate: PolicyGate, run: RunScope) -> None:
    """Decisions are allow or deny. A warning nobody reads is an allow."""
    import dataclasses

    from harness.policy import Decision

    fields = {f.name for f in dataclasses.fields(Decision)}
    assert "warning" not in fields and "warnings" not in fields
    decision = gate.decide(action(), run)
    assert decision.allowed is True


# --------------------------------------------- evaluated, not interpreted


def test_every_predicate_in_the_file_has_an_evaluator(constraints: ConstraintRegistry) -> None:
    """The task says evaluated, not interpreted. The rule strings are documentation; the
    ids bind to code. A rule with no code is a control that does not exist."""
    assert {p.id for p in constraints.predicates} == set(EVALUATORS)


def test_a_predicate_with_no_evaluator_refuses_to_build_the_gate(
    constraints: ConstraintRegistry, bus: object
) -> None:
    thinner = {k: v for k, v in EVALUATORS.items() if k != "row_cap"}
    with pytest.raises(RegistryError) as raised:
        PolicyGate(constraints, bus, evaluators=thinner)  # type: ignore[arg-type]
    assert "row_cap" in str(raised.value)
    assert "never run" in str(raised.value)


def test_the_rule_text_is_not_executed(gate: PolicyGate, run: RunScope) -> None:
    """The words in constraints.yaml are for a reviewer. Nothing evals them - which is
    why a rule can say `every path argument resolves under run.engagement_root` in
    English and still be enforced."""
    import inspect

    from harness import policy

    source = inspect.getsource(policy)
    assert "eval(" not in source
    assert "exec(" not in source
    for predicate in gate.constraints.predicates:
        assert predicate.rule not in source, f"{predicate.id}'s rule text is in the code"
