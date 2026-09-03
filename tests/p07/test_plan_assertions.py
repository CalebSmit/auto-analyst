"""Plan assertions run before execute, and refuse a plan that violates one.

The other suite answers "is the design intact" over 118 nodes in CI. This one answers "is
this run legal" over about eight typed steps, every time a plan is compiled. Conflating
them is what made three assertions unsatisfiable in the blueprint's first draft, and the
first test here is about that: the architecture graph would fail the plan suite's own
rule, which is exactly why they are two files.

`check_plan` is wired into `compile_recipe`, so these do not need to be remembered. The
tests below prove the wiring as well as the assertions - an assertion nobody calls is a
comment.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

import pytest

from graph import plan_assertions
from graph.compile import CompiledGraph, compile_recipe
from graph.plan_assertions import (
    ALL,
    MAX_IN_RUN_ITERATIONS,
    PlanRefused,
    check_plan,
)
from graph.recipes import load_recipe


def altered(plan: CompiledGraph, **fields: Any) -> CompiledGraph:
    """A compiled plan with one thing changed, to violate one assertion at a time.

    Built by replacing fields on the frozen result rather than by compiling something
    invalid, because most of these cannot be compiled at all - the compiler refuses them
    first. That overlap is deliberate: the compiler refuses while building, and the plan
    suite re-checks what came out, and they are different claims.
    """
    return dataclasses.replace(plan, **fields)


# ----------------------------------------------------------------- wiring


def test_compiling_a_plan_runs_the_assertions(monkeypatch: pytest.MonkeyPatch, plan) -> None:
    """The wiring, proved rather than assumed. There is no flag to skip it: a compiler
    that could be asked not to check is one nobody can rely on having checked."""
    called: list[str] = []
    monkeypatch.setattr(
        "graph.compile.check_plan", lambda p: called.append(p.recipe)
    )
    compile_recipe(load_recipe("monthly-refresh"), plan.context)
    assert called == ["monthly-refresh"]


def test_a_real_plan_passes_every_assertion(plan: CompiledGraph) -> None:
    check_plan(plan)
    assert len(ALL) == 7


def test_every_plan_assertion_explains_itself() -> None:
    for assertion in ALL:
        assert len(assertion.check.__doc__ or "") > 150, f"{assertion.name} is under-documented"


# -------------------------------------------------------- max_turns == 1


def test_assert_all_loops_bounded_covers_max_turns(plan: CompiledGraph) -> None:
    """The exit criterion names `assert_all_loops_bounded` and `max_turns == 1` in one
    breath, and the blueprint's own pseudocode puts them in one function. They are two
    functions here, and this is the test that says so out loud rather than leaving a
    reader to wonder whether the second half was forgotten.

    The intra-step agent loop is the one a graph cannot see, so it is bounded at the call
    site instead of in the cycle check - different mechanism, same invariant.
    """
    names = {a.name for a in ALL}
    assert "assert_all_loops_bounded" in names
    assert "assert_every_skill_step_takes_one_turn" in names
    assert {s.max_turns for s in plan.steps} == {1}


@pytest.mark.parametrize("turns", [0, 2, 7])
def test_a_step_taking_more_than_one_turn_is_refused(plan: CompiledGraph, turns: int) -> None:
    """A skill proposes; if it needs a tool result, that is another step in the plan -
    compiled, keyed and visible - not a hidden turn inside one."""
    steps = (dataclasses.replace(plan.steps[2], max_turns=turns), *plan.steps[3:])
    with pytest.raises(PlanRefused) as raised:
        check_plan(altered(plan, steps=steps))
    assert raised.value.diagnostic.code == "POLICY.MULTI_TURN_STEP"


# ------------------------------------------------------------- the loops


def test_an_undeclared_back_edge_is_refused(plan: CompiledGraph) -> None:
    edges = (*plan.edges[:-1], dataclasses.replace(plan.edges[-1], loop="not_declared"))
    with pytest.raises(PlanRefused) as raised:
        check_plan(altered(plan, edges=edges))
    assert raised.value.diagnostic.code == "LOOP.UNDECLARED_CYCLE"


def test_a_run_spanning_loop_in_a_plan_is_refused(plan: CompiledGraph) -> None:
    """The run checkpoints, the process exits, and a person's answer restarts it at the
    frontier. That is not a cycle - it is an ending followed by a beginning, and a plan
    that contained one would never terminate on its own."""
    loops = (dataclasses.replace(plan.loops[0], scope="run_spanning"), *plan.loops[1:])
    with pytest.raises(PlanRefused, match="in-run"):
        check_plan(altered(plan, loops=loops))


@pytest.mark.parametrize("ceiling", [0, MAX_IN_RUN_ITERATIONS + 1, 99])
def test_a_ceiling_outside_the_range_is_refused(plan: CompiledGraph, ceiling: int) -> None:
    loops = (dataclasses.replace(plan.loops[0], max_iterations=ceiling), *plan.loops[1:])
    with pytest.raises(PlanRefused, match="LOOP.UNDECLARED_CYCLE"):
        check_plan(altered(plan, loops=loops))


def test_a_declared_region_at_the_ceiling_is_allowed(plan: CompiledGraph) -> None:
    """The other side. A rule that refuses everything is not a rule."""
    loops = (
        dataclasses.replace(plan.loops[0], max_iterations=MAX_IN_RUN_ITERATIONS),
        *plan.loops[1:],
    )
    check_plan(altered(plan, loops=loops))


# ------------------------------------------------------------ the rest


def test_an_order_that_misses_a_step_is_refused(plan: CompiledGraph) -> None:
    """A step missing from the order would never run, and nothing else would notice."""
    with pytest.raises(PlanRefused, match="does not cover"):
        check_plan(altered(plan, order=plan.order[:-1]))


def test_an_order_that_puts_a_step_before_its_producer_is_refused(
    plan: CompiledGraph,
) -> None:
    reversed_order = tuple(reversed(plan.order))
    with pytest.raises(PlanRefused, match="ordered before"):
        check_plan(altered(plan, order=reversed_order))


def test_an_edge_carrying_an_unpinned_contract_is_refused(plan: CompiledGraph) -> None:
    forward = next(e for e in plan.edges if e.schema)
    edges = tuple(
        dataclasses.replace(e, schema="skills/made-up@9.9.9") if e is forward else e
        for e in plan.edges
    )
    with pytest.raises(PlanRefused, match="does not pin"):
        check_plan(altered(plan, edges=edges))


def test_a_plan_with_no_hash_is_refused(plan: CompiledGraph) -> None:
    with pytest.raises(PlanRefused, match="plan_hash"):
        check_plan(altered(plan, plan_hash="not-a-hash"))


def test_a_plan_with_no_precedent_snapshot_is_refused(plan: CompiledGraph) -> None:
    """Two runs could otherwise share a hash, see different examples and legitimately
    disagree - which is what a review found before the snapshot was added."""
    thin = dataclasses.replace(plan.context, precedent_snapshot="")
    with pytest.raises(PlanRefused, match="precedent"):
        check_plan(altered(plan, context=thin))


def test_a_step_with_no_failure_policy_is_refused(plan: CompiledGraph) -> None:
    """There is no implicit 'carry on regardless'."""
    steps = (dataclasses.replace(plan.steps[0], on_failure="ignore"), *plan.steps[1:])  # type: ignore[arg-type]
    with pytest.raises(PlanRefused, match="on_failure"):
        check_plan(altered(plan, steps=steps))


# -------------------------------------------------- the two graphs stay apart


def test_the_plan_suite_would_reject_the_architecture_graph() -> None:
    """The phase note, as a test.

    "No model step downstream of a guard" is unsatisfiable on the architecture graph -
    the untrusted boundary and the payload scan are guards and are ancestors of every
    model call by construction. The plan suite's version is about *writes*, not ancestry,
    and it is scoped to a compiled plan. Neither suite imports the other's graph, and
    this asserts that they cannot: the plan assertions take a CompiledGraph and an
    ArchGraph has none of what they read.
    """
    from graph.architecture_assertions import load_graph

    arch = load_graph()
    assert not hasattr(arch, "plan_hash")
    assert not hasattr(arch, "loops")
    assert not hasattr(arch, "order")


def test_the_verification_guards_are_the_narrow_set() -> None:
    """Invariant 5 is about generation after *verification*, not after any guard. The
    boundary guards are deliberately excluded, because including them is precisely the
    mistake that made the assertion unsatisfiable."""
    assert "untrusted_boundary" not in plan_assertions.VERIFICATION_GUARDS
    assert "payload_scan" not in plan_assertions.VERIFICATION_GUARDS
    assert "tieout_gate" in plan_assertions.VERIFICATION_GUARDS


def test_a_skill_after_verification_may_not_emit_figures(plan: CompiledGraph) -> None:
    """qc-tieout runs after the tie-out gate in a real plan. Its contract is allowed to
    emit figures today because the gate is not a step in this recipe - so the assertion
    is exercised here by putting one there."""
    checker: Callable[[CompiledGraph], None] = (
        plan_assertions.assert_no_generation_writes_a_verified_figure
    )
    checker(plan)  # the real plan is clean

    # A two-step plan, built rather than mutated: a tie-out guard, then a skill whose
    # contract has a figures field. That is a value written after it was meant to be
    # checked, which is the whole of the invariant.
    guard_step = dataclasses.replace(
        plan.step("timing"), id="tieout_gate", kind="guard", skill=None,
        output_schema=None, inputs=(),
    )
    ebitda = plan.step("ebitda")
    after_the_guard = dataclasses.replace(
        ebitda, inputs=(dataclasses.replace(ebitda.inputs[0], name="tieout_gate",
                                            producer="tieout_gate", schema=None),),
    )
    illegal = altered(
        plan,
        steps=(guard_step, after_the_guard),
        edges=(),
        order=("tieout_gate", "ebitda"),
        levels=(("tieout_gate",), ("ebitda",)),
    )
    with pytest.raises(PlanRefused, match="emits figures"):
        checker(illegal)
