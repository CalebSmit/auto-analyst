"""A proposal becomes a recipe, a recipe becomes a compiled plan, and the plan is written
down before any of it runs.

Three things live here, in the order they happen.

**`recipe_from_proposal`** turns what the model returned into a `Recipe` - the same
dataclass `recipes/*.yaml` loads into. That is the whole trick of this phase: there is no
second compiler and no second set of assertions for a proposed plan, because by the time
anything is compiled there is nothing to tell it apart from a named recipe. What the
model supplies is which skills run and what each one needs. What it does not supply, and
has no field for:

* **output contracts** - pinned from the skill by the contract registry;
* **skill versions and model pins** - from the resolved scope, at compile time;
* **timeouts and retries** - the recipe defaults;
* **loop regions and their ceilings** - `REQUIRED_LOOPS` below, with every maximum read
  from `constraints.yaml`. The graph owns every loop: no agent decides for itself whether
  to try again, so the ability to ask is not withheld by a rule, it is absent.

**`RunPlanner.plan`** compiles a proposal and falls back to the named recipe when the
compiler or the plan assertions refuse it. A refusal is not an error the caller handles -
it is an ordinary outcome, recorded with its diagnostic, and the run proceeds on the
recipe. The alternative, a run that stops because a model proposed a bad plan, would make
the orchestrator a single point of failure for work that has a perfectly good default.

**`run_plan_document`** is the artifact: steps, inputs, loops, order, plan hash, where it
came from and what was refused. Written to the blob store and recorded on the run before
execution begins, which is what makes "what is it doing?" answerable in advance.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from graph.compile import RUN_BOUNDARY, CompiledGraph, PlanContext, compile_recipe
from graph.recipes import (
    DEFAULT_MAX_TURNS,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT_S,
    LoopDeclaration,
    Recipe,
    RecipeInput,
    RecipeStep,
    load_recipe,
)
from ops.blobs import ContentStore, put_json
from ops.events import EventBus
from ops.run_store import RunStore
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.errors import Diagnostic, DiagnosticError

__all__ = [
    "PLAN_CONTRACT",
    "PROPOSED_RECIPE",
    "REQUIRED_LOOPS",
    "Planned",
    "RunPlanner",
    "recipe_from_proposal",
    "run_plan_document",
]

PLAN_CONTRACT = "run_plan@1.0.0"
PROPOSED_RECIPE = "proposed"
"""What a composed plan is called. Distinct from every name in `recipes/`, so the plan
hash of a proposal can never collide with a recipe's even if the steps are identical, and
the run manifest says plainly which one ran."""

NODE = "run_plan"

# Which loop regions a step gets, by the skill it runs. Code, not configuration and not
# the model's: `constraints.yaml` declares each loop and its ceiling, this table says
# where each one applies, and a region is added only when every member is in the plan.
# Members read from the head outwards, as the compiler requires.
REQUIRED_LOOPS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("self_verification", ("line-item-tagging",), "every tagging pass is checked by a separate "
     "invocation that sees the source excerpt and the proposal, never the first pass's reasoning"),
    ("self_verification", ("ebitda-normalization",), "every EBITDA output, always: the verifier "
     "sees the schedule, the cited rows and the excerpts, and never the rationale"),
    ("guard_repair", ("ebitda-normalization",), "the guard's structured failure is appended to "
     "the step input and the skill runs again; then a quarantine record and a review item"),
    ("tieout_repair", ("qc-tieout",), "the recomputed value and the cited source rows are handed "
     "back once; if the two still disagree a review item carries both numbers and the delta"),
    ("conflict_resolution", ("line-item-tagging", "ebitda-normalization"), "reconciliation "
     "surfaces a cross-skill disagreement and each skill is re-invoked with the other's position"),
)


@dataclass(frozen=True)
class Planned:
    """The plan that will run, and the account of how it was arrived at."""

    plan: CompiledGraph
    source: str
    """`recipe` or `proposal`. A refused proposal leaves `recipe` here."""
    document: dict[str, Any]
    refusal: Diagnostic | None = None
    proposal: dict[str, Any] | None = None

    @property
    def from_proposal(self) -> bool:
        return self.source == "proposal"

    @property
    def plan_hash(self) -> str:
        return self.plan.plan_hash


def recipe_from_proposal(
    proposal: Mapping[str, Any],
    *,
    contracts: ContractRegistry,
    constraints: ConstraintRegistry,
    run_inputs: Sequence[RecipeInput] = (),
    name: str = PROPOSED_RECIPE,
) -> Recipe:
    """The proposal as a `Recipe`, so the same compiler and assertions can have it.

    Deterministic in every particular: the step order is the proposal's, the loops come
    from `REQUIRED_LOOPS` in the order that table declares them, and nothing here reads a
    clock, a counter or the environment. Same proposal, same recipe, same plan hash.
    """
    steps = tuple(
        RecipeStep(
            id=str(entry["id"]),
            kind=str(entry["kind"]),
            label=str(entry.get("label") or entry["id"]),
            skill=entry.get("skill") or None,
            needs=tuple(str(n) for n in entry.get("needs") or ()),
            run_inputs=tuple(str(n) for n in entry.get("run_inputs") or ()),
            output_schema=_contract_for(entry, contracts),
            on_failure=str(entry.get("on_failure") or "quarantine"),
            timeout_s=DEFAULT_TIMEOUT_S,
            retries=DEFAULT_RETRIES,
            max_turns=DEFAULT_MAX_TURNS,
        )
        for entry in proposal.get("steps") or ()
    )
    return Recipe(
        name=name,
        version=1,
        title="Orchestrator proposal",
        description=" ".join(str(proposal.get("rationale", "")).split()),
        steps=steps,
        inputs=tuple(run_inputs),
        loops=_loops_for(steps, constraints),
        path=f"{name} (orchestrator proposal)",
        _by_id={s.id: s for s in steps},
    )


def _contract_for(entry: Mapping[str, Any], contracts: ContractRegistry) -> str | None:
    """The output contract for a proposed step, pinned from the skill.

    The proposal has no field for this on purpose. A step that names a skill gets that
    skill's registered output contract; a skill with none registered is left unpinned and
    the compiler refuses the plan, which is the right answer - an unpinned version is
    never resolved to a guess.
    """
    if entry.get("kind") != "skill" or not entry.get("skill"):
        return None
    key = contracts.skill_output_key(str(entry["skill"]))
    return key if key in contracts.ids() else None


def _loops_for(
    steps: tuple[RecipeStep, ...], constraints: ConstraintRegistry
) -> tuple[LoopDeclaration, ...]:
    """Every declared region whose members are all in this plan, with the ceiling the
    constraint registry gives it. Nothing the model said is consulted.

    A region spanning two steps is added only when the members are exactly the steps
    between them. A plan that put something else in between - a guard, a second skill -
    is a different shape, and a region that does not enclose the path is one the compiler
    would refuse. Skipping it is the safe direction: a loop only ever permits an extra
    iteration, so a plan without one iterates less, never more.
    """
    ceilings = {spec.name: spec.max_iterations for spec in constraints.in_run_loops()}
    by_skill: dict[str, str] = {}
    for step in steps:
        if step.kind == "skill" and step.skill and step.skill not in by_skill:
            by_skill[step.skill] = step.id
    needs = {step.id: set(step.needs) for step in steps}
    declarations: list[LoopDeclaration] = []
    for loop, skills, why in REQUIRED_LOOPS:
        if not all(skill in by_skill for skill in skills):
            continue
        maximum = ceilings.get(loop)
        if maximum is None:
            continue  # not an in-run loop, or declared without a ceiling: not a region
        members = tuple(by_skill[skill] for skill in skills)
        if len(members) > 1 and _between(members[0], members[-1], needs) != set(members):
            continue
        declarations.append(
            LoopDeclaration(
                loop=loop, head=members[0], members=members, max_iterations=maximum, why=why
            )
        )
    return tuple(declarations)


def _between(head: str, tail: str, needs: Mapping[str, set[str]]) -> set[str]:
    """Every step on some dependency path from `head` up to `tail`, both included.

    The intersection of two closures rather than an enumeration of paths: what `tail`
    transitively needs, and what transitively needs `head`. Empty when there is no path,
    which is the answer that makes a region no region at all.
    """
    upstream = _closure({tail}, lambda step: needs.get(step, set()))
    downstream = _closure({head}, lambda step: {s for s, ns in needs.items() if step in ns})
    return upstream & downstream if head in upstream else set()


def _closure(start: set[str], neighbours: Callable[[str], set[str]]) -> set[str]:
    seen = set(start)
    stack = list(start)
    while stack:
        for nxt in neighbours(stack.pop()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def run_plan_document(
    plan: CompiledGraph,
    *,
    run_id: str,
    source: str,
    rationale: str = "",
    proposal_ref: str | None = None,
    request_hash: str | None = None,
    refusal: Diagnostic | None = None,
) -> dict[str, Any]:
    """The Run Plan artifact: the compiled plan as data, plus where it came from."""
    return {
        "schema_version": PLAN_CONTRACT,
        "run_id": run_id,
        "engagement_id": plan.engagement_id,
        "source": source,
        "recipe": f"{plan.recipe}@v{plan.recipe_version}",
        "plan_hash": plan.plan_hash,
        "rationale": rationale,
        "proposal_ref": proposal_ref,
        "request_hash": request_hash,
        "order": list(plan.order),
        "steps": [
            {
                "id": step.id,
                "kind": step.kind,
                "label": step.label,
                "skill": step.skill,
                "model_pin": step.model_pin,
                "output_schema": step.output_schema,
                "inputs": [
                    {
                        "name": ref.name,
                        "producer": RUN_BOUNDARY if ref.from_run else ref.producer,
                        "schema": ref.schema,
                    }
                    for ref in step.inputs
                ],
                "loops": list(step.loops),
                "on_failure": step.on_failure,
                "timeout_s": step.timeout_s,
                "retries": step.retries,
                "max_turns": step.max_turns,
            }
            for step in plan.steps
        ],
        "loops": [
            {
                "loop": region.loop,
                "head": region.head,
                "members": list(region.members),
                "max_iterations": region.max_iterations,
                "why": region.why,
            }
            for region in plan.loops
        ],
        "refusal": None
        if refusal is None
        else {
            "code": refusal.code,
            "detail": refusal.detail,
            "locator": refusal.locator,
            "what_now": refusal.what_now,
        },
    }


class RunPlanner:
    """Compile the plan a run will execute, and write it down before it starts."""

    def __init__(
        self,
        store: RunStore,
        bus: EventBus,
        blobs: ContentStore,
        contracts: ContractRegistry | None = None,
        constraints: ConstraintRegistry | None = None,
    ) -> None:
        self.store = store
        self.bus = bus
        self.blobs = blobs
        self.contracts = contracts or ContractRegistry.load()
        self.constraints = constraints or ConstraintRegistry.load()

    def from_recipe(self, recipe_name: str, context: PlanContext, run_id: str) -> Planned:
        """The named path. What every run did before this phase, and still does when the
        orchestrator is not asked or its proposal does not survive."""
        plan = compile_recipe(
            load_recipe(recipe_name),
            context,
            contracts=self.contracts,
            constraints=self.constraints,
        )
        return self._record(plan, run_id=run_id, source="recipe")

    def from_proposal(
        self,
        proposal: Mapping[str, Any],
        context: PlanContext,
        run_id: str,
        *,
        fallback_recipe: str,
        run_inputs: Sequence[RecipeInput] = (),
        proposal_ref: str | None = None,
        request_hash: str | None = None,
    ) -> Planned:
        """Compile what was proposed; use the recipe if it does not survive.

        `match: recipe` is not a shortcut into the model's own steps - the named recipe
        is loaded from disk and its steps are used. A proposal saying "this is the
        monthly refresh" is a routing answer, not a licence to restate what the monthly
        refresh contains.
        """
        rationale = " ".join(str(proposal.get("rationale", "")).split())
        named = proposal.get("recipe") if proposal.get("match") == "recipe" else None
        if named:
            try:
                plan = compile_recipe(
                    load_recipe(str(named)),
                    context,
                    contracts=self.contracts,
                    constraints=self.constraints,
                )
            except DiagnosticError as refused:
                return self._fallback(
                    refused.diagnostic, context, run_id,
                    fallback_recipe=fallback_recipe, proposal=proposal,
                    rationale=rationale, proposal_ref=proposal_ref, request_hash=request_hash,
                )
            return self._record(
                plan, run_id=run_id, source="proposal", rationale=rationale,
                proposal=dict(proposal), proposal_ref=proposal_ref, request_hash=request_hash,
            )

        try:
            recipe = recipe_from_proposal(
                proposal,
                contracts=self.contracts,
                constraints=self.constraints,
                run_inputs=run_inputs,
            )
            plan = compile_recipe(
                recipe, context, contracts=self.contracts, constraints=self.constraints
            )
        except DiagnosticError as refused:
            # The compiler and the plan assertions refuse the same way, and both are
            # ordinary here: a proposal that does not survive is a proposal that does not
            # run, and the recipe is what the run was always going to fall back to.
            return self._fallback(
                refused.diagnostic, context, run_id,
                fallback_recipe=fallback_recipe, proposal=proposal,
                rationale=rationale, proposal_ref=proposal_ref, request_hash=request_hash,
            )
        return self._record(
            plan, run_id=run_id, source="proposal", rationale=rationale,
            proposal=dict(proposal), proposal_ref=proposal_ref, request_hash=request_hash,
        )

    # -- writing it down

    def _fallback(
        self,
        refusal: Diagnostic,
        context: PlanContext,
        run_id: str,
        *,
        fallback_recipe: str,
        proposal: Mapping[str, Any],
        rationale: str,
        proposal_ref: str | None,
        request_hash: str | None,
    ) -> Planned:
        self.bus.emit(
            run_id=run_id,
            engagement_id=context.engagement_id,
            node_id="orchestrator",
            type="plan.refused",
            message=f"the proposed plan does not run: {refusal.detail}",
            level="warn",
            diagnostic_code=refusal.code,
            payload={
                "locator": refusal.locator,
                "what_now": refusal.what_now,
                "fallback_recipe": fallback_recipe,
                "proposal_ref": proposal_ref,
            },
        )
        plan = compile_recipe(
            load_recipe(fallback_recipe),
            context,
            contracts=self.contracts,
            constraints=self.constraints,
        )
        return self._record(
            plan, run_id=run_id, source="recipe", rationale=rationale, proposal=dict(proposal),
            proposal_ref=proposal_ref, request_hash=request_hash, refusal=refusal,
        )

    def _record(
        self,
        plan: CompiledGraph,
        *,
        run_id: str,
        source: str,
        rationale: str = "",
        proposal: dict[str, Any] | None = None,
        proposal_ref: str | None = None,
        request_hash: str | None = None,
        refusal: Diagnostic | None = None,
    ) -> Planned:
        document = run_plan_document(
            plan,
            run_id=run_id,
            source=source,
            rationale=rationale,
            proposal_ref=proposal_ref,
            request_hash=request_hash,
            refusal=refusal,
        )
        self.contracts.validate(PLAN_CONTRACT, document)
        ref = put_json(self.blobs, document, name="run_plan")
        self.store.record_artifact(run_id, "run_plan", ref.content_hash)
        self.bus.emit(
            run_id=run_id,
            engagement_id=plan.engagement_id,
            node_id=NODE,
            type="plan.compiled",
            message=(
                f"{document['recipe']} from {source}: {len(plan.steps)} steps, "
                f"{len(plan.loops)} declared loop(s)"
            ),
            payload={
                "plan_hash": plan.plan_hash,
                "source": source,
                "recipe": document["recipe"],
                "steps": list(plan.order),
                "run_plan_ref": ref.content_hash,
                "refused": None if refusal is None else refusal.code,
            },
        )
        return Planned(
            plan=plan, source=source, document=document, refusal=refusal, proposal=proposal
        )
