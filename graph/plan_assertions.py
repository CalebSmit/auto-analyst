"""The plan assertions: is *this run* legal, checked before a single step executes.

The other suite runs over the architecture graph - 118 nodes, in CI, answering "is the
design intact". This one runs over a compiled plan of about eight typed steps, every time
one is compiled, and answers a different question. Conflating the two is what made three
assertions in the blueprint's first draft unsatisfiable: "no model step downstream of a
guard" is false by construction on the architecture graph, because the untrusted boundary
and the payload scan are guards and are ancestors of every model call there is.

So the assertions here are about a plan and only a plan. Where an invariant has both a
structural half and a runtime half, the structural half stays in the architecture suite
and this one takes the half a compiled plan can actually answer.

`check_plan` is called by `graph.compile.compile_recipe`, so nothing can execute a plan
that has not been through it. There is no flag to skip it: a compiler that could be asked
not to check is a compiler nobody can rely on having checked.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from registries.contracts import ContractRegistry
from registries.errors import (
    MULTI_TURN_STEP,
    PLAN_REFUSED,
    UNDECLARED_CYCLE,
    RegistryError,
    diagnose,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle at runtime, types only
    from graph.compile import CompiledGraph

# The blueprint's ceiling on any in-run loop, whatever an individual region asks for.
MAX_IN_RUN_ITERATIONS = 3

# Guards whose whole job is to verify a figure. A model step downstream of one of these
# is the thing invariant 5 is about - not the boundary guards, which are upstream of
# every model call by construction.
VERIFICATION_GUARDS = frozenset(
    {"schema_gate", "provenance_gate", "tieout_gate", "reconcile", "numeric_lock"}
)

__all__ = [
    "ALL",
    "MAX_IN_RUN_ITERATIONS",
    "PlanAssertion",
    "PlanRefused",
    "check_plan",
]


class PlanRefused(RegistryError):
    """A compiled plan violates an invariant. It does not execute."""


def _refuse(code: str, detail: str, locator: str) -> None:
    raise PlanRefused(diagnose(code, detail, locator=locator))


# ================================================================ assertions


def assert_all_loops_bounded(plan: CompiledGraph) -> None:
    """Every cycle in the plan is a declared region with an integer ceiling.

    Only in-run loops live in a plan. Run-spanning (human clarification) and cross-run
    (drift re-review) loops are not cycles here - the run checkpoints and the process
    exits, which is not a cycle, it is an ending followed by a beginning.

    The compiler refuses an undeclared cycle while building. This re-checks the built
    plan, because the two are different claims: one is about what the compiler did, the
    other is about what came out of it.
    """
    declared = {region.id for region in plan.loops}
    for edge in plan.back_edges():
        if edge.loop not in declared:
            _refuse(
                UNDECLARED_CYCLE,
                f"{edge.src} -> {edge.dst} closes a cycle and names loop {edge.loop!r}, "
                f"which the plan does not declare",
                plan.recipe,
            )
    for region in plan.loops:
        if region.scope != "in_run":
            _refuse(
                UNDECLARED_CYCLE,
                f"{region.id} is a {region.scope} loop. Only in-run loops are cycles in "
                f"a plan; a plan containing another kind would never terminate on its own.",
                region.id,
            )
        if not 1 <= region.max_iterations <= MAX_IN_RUN_ITERATIONS:
            _refuse(
                UNDECLARED_CYCLE,
                f"{region.id} declares {region.max_iterations} iterations, outside "
                f"1..{MAX_IN_RUN_ITERATIONS}",
                region.id,
            )


def assert_every_skill_step_takes_one_turn(plan: CompiledGraph) -> None:
    """A skill invocation is one model turn.

    The intra-step agent loop is the one a graph cannot see, so it is bounded at the call
    site instead. If a skill needs a tool result, that is another step in the plan -
    compiled, keyed and visible - not a hidden turn inside one.

    Checked on every step rather than only skill steps: a non-skill step that asked for
    more than one turn would be a model call the plan does not admit to making.
    """
    for step in plan.steps:
        if step.max_turns != 1:
            _refuse(
                MULTI_TURN_STEP,
                f"{step.id} declares max_turns={step.max_turns}",
                step.id,
            )


def assert_the_order_covers_every_step(plan: CompiledGraph) -> None:
    """Every step appears exactly once in the execution order, and after what it needs.

    An internal consistency check on the compiler's own output. A step missing from the
    order would never run and nothing else would notice; a step ordered before its
    producer would run on an input that does not exist yet.

    Deliberately *not* "every step is connected to something": a plan may legitimately
    have two independent branches, and an assertion that called that stranded would be
    the kind of false positive that gets a skip flag added.
    """
    if not plan.steps:
        _refuse(PLAN_REFUSED, "the plan has no steps", plan.recipe)
    if sorted(plan.order) != sorted(plan.ids):
        missing = sorted(set(plan.ids) - set(plan.order))
        _refuse(
            PLAN_REFUSED,
            f"the execution order does not cover {', '.join(missing) or 'every step once'}",
            plan.recipe,
        )
    position = {step_id: n for n, step_id in enumerate(plan.order)}
    for step in plan.steps:
        for producer in step.needs:
            if position[producer] >= position[step.id]:
                _refuse(
                    PLAN_REFUSED,
                    f"{step.id} is ordered before {producer}, which it needs",
                    step.id,
                )


def assert_every_typed_edge_names_a_registered_contract(plan: CompiledGraph) -> None:
    """Every edge between two steps declares the schema and version crossing it.

    The compiler already refuses an unpinned contract on a step. This asks the question
    of the assembled graph, which is where an edge could exist that no step's declaration
    accounted for.
    """
    contracts = ContractRegistry.load()
    known = set(contracts.ids())
    for edge in plan.forward_edges():
        if edge.schema is None:
            producer = plan.step(edge.src)
            if producer.kind in ("skill", "tool"):
                _refuse(
                    PLAN_REFUSED,
                    f"{edge.src} -> {edge.dst} carries no schema and {edge.src} is a "
                    f"{producer.kind} step",
                    edge.src,
                )
        elif edge.schema not in known:
            _refuse(
                PLAN_REFUSED,
                f"{edge.src} -> {edge.dst} carries {edge.schema!r}, which the contract "
                f"registry does not pin",
                edge.src,
            )


def assert_no_generation_writes_a_verified_figure(plan: CompiledGraph) -> None:
    """A skill step downstream of a verification guard may not emit figures.

    Deliberately *not* "no model step downstream of a guard" - that is unsatisfiable,
    because the untrusted boundary and the payload scan are guards and are ancestors of
    every model call by construction. The real property is about writes, not ancestry: if
    a step runs after the figures have been checked, its output contract must have no
    field a figure could enter through.
    """
    contracts = ContractRegistry.load()
    for step in plan.steps_where(kind="skill"):
        if not (VERIFICATION_GUARDS & _ancestors(plan, step.id)):
            continue
        if not step.output_schema:
            continue
        schema = contracts.get(step.output_schema)
        if schema.get("x-emits-figures"):
            _refuse(
                PLAN_REFUSED,
                f"{step.id} runs after verification and its contract "
                f"{step.output_schema} emits figures - a value written there would never "
                f"have been checked",
                step.id,
            )


def assert_every_step_says_what_happens_when_it_fails(plan: CompiledGraph) -> None:
    """There is no implicit 'carry on regardless'.

    Exhaustion always produces an artifact - a quarantine record or a review item. A step
    with no failure policy is a step that could fail silently and let the run continue as
    though nothing happened.
    """
    for step in plan.steps:
        if step.on_failure not in ("halt", "quarantine", "review"):
            _refuse(
                PLAN_REFUSED,
                f"{step.id} declares on_failure={step.on_failure!r}",
                step.id,
            )


def assert_the_plan_is_hashed(plan: CompiledGraph) -> None:
    """A plan carries the hash it was built under.

    Every guarantee about reproducibility rests on it, and a plan that reached execution
    without one would be a run nobody could attribute afterwards.
    """
    if not plan.plan_hash.startswith("sha256:") or len(plan.plan_hash) != 71:
        _refuse(PLAN_REFUSED, f"plan_hash is {plan.plan_hash!r}", plan.recipe)
    if not plan.context or not plan.context.precedent_snapshot:
        _refuse(
            PLAN_REFUSED,
            "the plan names no precedent-store snapshot, so two runs could share a hash, "
            "see different examples and legitimately disagree",
            plan.recipe,
        )


def _ancestors(plan: CompiledGraph, step_id: str) -> set[str]:
    """Everything upstream of a step over the forward edges."""
    seen: set[str] = set()
    stack = list(plan.step(step_id).needs)
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(plan.step(current).needs)
    return seen


# ================================================================== registry


@dataclass(frozen=True)
class PlanAssertion:
    check: Callable[[CompiledGraph], None]

    @property
    def name(self) -> str:
        return self.check.__name__

    @property
    def summary(self) -> str:
        return (self.check.__doc__ or "").strip().split("\n")[0]


ALL: tuple[PlanAssertion, ...] = tuple(
    PlanAssertion(check)
    for check in (
        assert_all_loops_bounded,
        assert_every_skill_step_takes_one_turn,
        assert_the_order_covers_every_step,
        assert_every_typed_edge_names_a_registered_contract,
        assert_no_generation_writes_a_verified_figure,
        assert_every_step_says_what_happens_when_it_fails,
        assert_the_plan_is_hashed,
    )
)


def check_plan(plan: CompiledGraph) -> None:
    """Run every plan assertion. Raises `PlanRefused` on the first violation.

    First rather than all of them, unlike the architecture suite: a plan that violates an
    invariant does not execute, so there is nothing to be gained by finding out how many
    ways it is illegal. The architecture suite reports everything because somebody is
    about to go and fix the design.
    """
    for assertion in ALL:
        assertion.check(plan)
