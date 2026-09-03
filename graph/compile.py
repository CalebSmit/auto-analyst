"""The Graph Compiler: a recipe becomes a typed DAG with a plan hash, or it does not run.

Nothing executes that has not been through here. The compiler emits
`{nodes, edges, loops, plan_hash}` and refuses anything it cannot vouch for, which is
what turns the properties in the blueprint's left rail from claims about a picture into
checks that run before a single step does.

Three refusals carry most of the weight.

**An undeclared cycle.** Loops are declared regions with an integer ceiling - never
implicit cycles. The dependency graph on its own must be acyclic, and every declared
region must close a real cycle over exactly the steps its back edge returns over. The
error names the steps, because "there is a cycle somewhere" is not a thing anyone can
act on.

**A ceiling nobody agreed to.** A declared region's `max_iterations` is checked against
`constraints.yaml`, and only in-run loops may appear in a plan at all. Run-spanning
(human clarification) and cross-run (drift re-review) loops are not cycles here; a plan
that tried to contain one would be a plan that never terminates on its own.

**More than one model turn.** A skill invocation is one model turn. If a skill needs a
tool result, that is another step in the plan - compiled, keyed and visible - not a
hidden turn inside one.

**What plan_hash promises**, and it is worth being precise: two runs with the same hash
had identical inputs and identical configuration - same skill versions, same model pins
and effort, same schemas, same constraints, same retrieved precedents. It does *not*
promise identical output. Models are not deterministic. What the hash promises is that a
difference between two runs is attributable to the model rather than to something that
quietly changed underneath, which is the property a workfile actually needs.

The precedent-store snapshot is in the hash because retrieved precedents change with
every approved correction. Without it two runs could share a hash, see different examples
and legitimately disagree.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from graph.recipes import Recipe, RecipeStep
from graph.resolve import ResolvedScope
from ports.llm import Effort, ModelPin
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.errors import (
    LOOP_CEILING_EXCEEDED,
    MULTI_TURN_STEP,
    RECIPE_INVALID,
    UNDECLARED_CYCLE,
    RegistryError,
    diagnose,
)

# The blueprint's own ceiling on an in-run loop, independent of what any one region asks
# for. `assert_all_loops_bounded` checks it too; the compiler checks it first so a plan
# that would fail that assertion never gets built.
MAX_IN_RUN_ITERATIONS = 3

RUN_BOUNDARY = "__run__"

__all__ = [
    "CompiledGraph",
    "Edge",
    "LoopRegion",
    "MAX_IN_RUN_ITERATIONS",
    "PlanContext",
    "Ref",
    "Step",
    "compile_recipe",
]


@dataclass(frozen=True)
class Ref:
    """One input to a step: what produced it, and what schema crosses the edge.

    Content-addressed at execution time. At compile time a ref is symbolic - the
    producer and the contract - because content hashes do not exist until something has
    run. P08 completes the idempotency key with them.
    """

    name: str
    producer: str
    """A step id, or `__run__` for something that arrived from outside the plan."""
    schema: str | None = None

    @property
    def from_run(self) -> bool:
        return self.producer == RUN_BOUNDARY


@dataclass(frozen=True)
class Edge:
    """Typed, and directed. A back edge is the return leg of a declared loop."""

    src: str
    dst: str
    name: str
    schema: str | None = None
    loop: str | None = None

    @property
    def is_back_edge(self) -> bool:
        return self.loop is not None


@dataclass(frozen=True)
class Step:
    """Every node in a compiled run graph is one of these.

    `loops` is plural where the blueprint's Step contract had a single `loop`. A step can
    genuinely sit in two declared regions at once - self-verification applies to every
    EBITDA output, and guard repair applies when that output fails its schema check - and
    a single field cannot say so. Recorded as an amendment on P06.
    """

    id: str
    kind: Literal["skill", "tool", "guard", "human", "io"]
    skill: str | None
    inputs: tuple[Ref, ...]
    output_schema: str | None
    timeout_s: int
    retries: int
    loops: tuple[str, ...]
    on_failure: Literal["halt", "quarantine", "review"]
    label: str = ""
    model_pin: str | None = None
    max_turns: int = 1

    @property
    def needs(self) -> tuple[str, ...]:
        """The steps this one depends on, in declaration order, without duplicates."""
        seen: list[str] = []
        for ref in self.inputs:
            if not ref.from_run and ref.producer not in seen:
                seen.append(ref.producer)
        return tuple(seen)

    def key_material(self) -> tuple[str, ...]:
        """The static half of the idempotency key.

        P08 completes it with the input content hashes and the context_ref, which is
        where retrieved precedents enter. Kept separate rather than pretending to a key
        the compiler cannot compute: a key that quietly omitted the runtime half would
        make a retry and a re-run look identical when they are not.
        """
        return (
            self.id,
            self.skill or "-",
            self.model_pin or "-",
            self.output_schema or "-",
        )


@dataclass(frozen=True)
class LoopRegion:
    """A declared, bounded loop. The only kind of cycle a plan may contain."""

    loop: str
    head: str
    members: tuple[str, ...]
    max_iterations: int
    scope: str = "in_run"
    why: str = ""

    @property
    def id(self) -> str:
        """Two regions can be instances of the same loop on different steps."""
        return f"{self.loop}:{self.head}"

    @property
    def tail(self) -> str:
        """Where the back edge starts. The deepest member."""
        return self.members[-1]


@dataclass(frozen=True)
class PlanContext:
    """Everything outside the recipe that the plan hash has to cover.

    Each field is something that can change under a run without the recipe changing, and
    every one of them has changed the answer at least once in somebody's system.
    """

    engagement_id: str
    scope: ResolvedScope
    taxonomy_version: str
    precedent_snapshot: str
    """The precedent-store snapshot id. In the hash because retrieved precedents change
    with every approved correction."""

    effort: Effort = "high"
    contracts_version: str = ""
    constraints_version: str = ""


@dataclass(frozen=True)
class CompiledGraph:
    """`{nodes, edges, loops, plan_hash}` - and nothing runs without one."""

    recipe: str
    recipe_version: int
    engagement_id: str
    steps: tuple[Step, ...]
    edges: tuple[Edge, ...]
    loops: tuple[LoopRegion, ...]
    order: tuple[str, ...]
    levels: tuple[tuple[str, ...], ...]
    plan_hash: str
    context: PlanContext = field(repr=False, default=None)  # type: ignore[assignment]

    def __len__(self) -> int:
        return len(self.steps)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(s.id for s in self.steps)

    def step(self, step_id: str) -> Step:
        found = next((s for s in self.steps if s.id == step_id), None)
        if found is None:
            raise KeyError(f"{step_id!r} is not in this plan")
        return found

    def steps_where(self, **match: Any) -> tuple[Step, ...]:
        return tuple(
            s for s in self.steps if all(getattr(s, k) == v for k, v in match.items())
        )

    def forward_edges(self) -> tuple[Edge, ...]:
        return tuple(e for e in self.edges if not e.is_back_edge)

    def back_edges(self) -> tuple[Edge, ...]:
        return tuple(e for e in self.edges if e.is_back_edge)

    def untyped_edges(self) -> tuple[Edge, ...]:
        """Edges carrying no contract.

        Only from steps whose kind has no typed output yet - the intake manifest is
        P16's and the delivery record is P21's. Exposed rather than hidden so P07's
        assertion suite can watch the number go to zero rather than take it on trust.
        """
        return tuple(e for e in self.forward_edges() if e.schema is None)

    def parallel_branches(self) -> tuple[tuple[str, ...], ...]:
        """Levels with more than one step in them: what could run at the same time."""
        return tuple(level for level in self.levels if len(level) > 1)


# --------------------------------------------------------------- compilation


def compile_recipe(
    recipe: Recipe,
    context: PlanContext,
    *,
    contracts: ContractRegistry | None = None,
    constraints: ConstraintRegistry | None = None,
) -> CompiledGraph:
    """Compile a recipe against a resolved scope. Refuses rather than warns."""
    contract_registry = contracts or ContractRegistry.load()
    constraint_registry = constraints or ConstraintRegistry.load()

    _check_steps_are_in_scope(recipe, context)
    regions = _regions(recipe, constraint_registry)
    membership = _membership(regions)

    steps = tuple(
        _step(entry, recipe, context, contract_registry, membership) for entry in recipe.steps
    )
    by_id = {s.id: s for s in steps}
    edges = _edges(steps, regions, by_id)

    _refuse_undeclared_cycles(steps, regions, edges)

    order = _topological(steps)
    levels = _levels(steps, order)

    plan_hash = _plan_hash(recipe, context, steps, edges, regions, contract_registry,
                           constraint_registry)
    return CompiledGraph(
        recipe=recipe.name,
        recipe_version=recipe.version,
        engagement_id=context.engagement_id,
        steps=steps,
        edges=edges,
        loops=regions,
        order=order,
        levels=levels,
        plan_hash=plan_hash,
        context=context,
    )


def _fail(code: str, detail: str, locator: str) -> None:
    raise RegistryError(diagnose(code, detail, locator=locator))


def _check_steps_are_in_scope(recipe: Recipe, context: PlanContext) -> None:
    """A recipe may only name skills the engagement's scope resolved to.

    This is the Scope Resolver's control made real. A Corporate Finance skill is not
    something an ESOP run declines to use - it is something that run never had, and a
    recipe asking for one is a recipe for a different engagement.
    """
    available = set(context.scope.names)
    for step in recipe.steps:
        if step.kind == "skill" and step.skill not in available:
            _fail(
                RECIPE_INVALID,
                f"{step.id}: {step.skill!r} did not resolve into {context.scope.scope}. "
                f"That scope has: {', '.join(sorted(available))}",
                recipe.path,
            )


def _regions(recipe: Recipe, constraints: ConstraintRegistry) -> tuple[LoopRegion, ...]:
    """Declared loops, checked against the constraint registry before anything is built."""
    declared = {spec.name: spec for spec in constraints.in_run_loops()}
    regions: list[LoopRegion] = []
    for entry in recipe.loops:
        spec = declared.get(entry.loop)
        if spec is None:
            _fail(
                LOOP_CEILING_EXCEEDED,
                f"{entry.loop!r} is not an in-run loop in constraints.yaml "
                f"(have: {', '.join(sorted(declared))}). Run-spanning and cross-run "
                f"loops are not cycles in a plan - a plan containing one would never "
                f"terminate on its own.",
                recipe.path,
            )
            raise AssertionError  # unreachable; _fail always raises
        if spec.max_iterations is None:
            _fail(
                LOOP_CEILING_EXCEEDED,
                f"constraints.yaml declares {entry.loop!r} as in-run but gives it no "
                f"ceiling. An in-run loop without an integer maximum is the thing the "
                f"compiler exists to refuse.",
                recipe.path,
            )
            raise AssertionError  # unreachable
        if entry.max_iterations > spec.max_iterations:
            _fail(
                LOOP_CEILING_EXCEEDED,
                f"{entry.loop} asks for {entry.max_iterations} iterations; "
                f"constraints.yaml allows {spec.max_iterations}. Ceilings are raised "
                f"there, deliberately, never in the recipe that wants the extra go.",
                recipe.path,
            )
        if entry.max_iterations > MAX_IN_RUN_ITERATIONS:
            _fail(
                LOOP_CEILING_EXCEEDED,
                f"{entry.loop} asks for {entry.max_iterations}; no in-run loop may "
                f"exceed {MAX_IN_RUN_ITERATIONS}",
                recipe.path,
            )
        if entry.max_iterations < 1:
            _fail(
                LOOP_CEILING_EXCEEDED,
                f"{entry.loop} declares {entry.max_iterations} iterations. A region "
                f"that cannot iterate is not a loop; remove it.",
                recipe.path,
            )
        _check_members(recipe, entry.loop, entry.head, entry.members)
        regions.append(
            LoopRegion(
                loop=entry.loop,
                head=entry.head,
                members=tuple(entry.members),
                max_iterations=entry.max_iterations,
                scope=spec.scope,
                why=entry.why,
            )
        )
    ids = [r.id for r in regions]
    if len(set(ids)) != len(ids):
        _fail(RECIPE_INVALID, "two loop regions share an id", recipe.path)
    return tuple(regions)


def _check_members(recipe: Recipe, loop: str, head: str, members: tuple[str, ...]) -> None:
    known = {s.id for s in recipe.steps}
    unknown = [m for m in (*members, head) if m not in known]
    if unknown:
        _fail(
            RECIPE_INVALID,
            f"loop {loop} names {', '.join(unknown)}, which the recipe has no step for",
            recipe.path,
        )
    if head not in members:
        _fail(
            RECIPE_INVALID,
            f"loop {loop} declares head {head!r}, which is not among its members. "
            f"Iteration restarts at the head, so it has to be inside the region.",
            recipe.path,
        )
    if members[0] != head:
        _fail(
            RECIPE_INVALID,
            f"loop {loop} lists {members[0]!r} first but declares {head!r} as its head. "
            f"Members read from the head outwards, so the back edge is visible in the "
            f"declaration rather than derived from a rule somebody has to remember.",
            recipe.path,
        )
    if len(set(members)) != len(members):
        _fail(RECIPE_INVALID, f"loop {loop} lists a member twice", recipe.path)


def _membership(regions: tuple[LoopRegion, ...]) -> dict[str, tuple[str, ...]]:
    found: dict[str, list[str]] = {}
    for region in regions:
        for member in region.members:
            found.setdefault(member, []).append(region.id)
    return {step: tuple(ids) for step, ids in found.items()}


def _step(
    entry: RecipeStep,
    recipe: Recipe,
    context: PlanContext,
    contracts: ContractRegistry,
    membership: dict[str, tuple[str, ...]],
) -> Step:
    if entry.max_turns != 1:
        _fail(
            MULTI_TURN_STEP,
            f"{entry.id} declares max_turns={entry.max_turns}. A skill invocation is "
            f"one model turn; a skill that needs a tool result takes another step in "
            f"the plan, compiled and keyed and visible.",
            recipe.path,
        )
    if entry.kind in ("skill", "tool") and not entry.output_schema:
        _fail(
            RECIPE_INVALID,
            f"{entry.id}: a {entry.kind} step declares no output_schema. Every edge "
            f"declares the schema and version of the data crossing it.",
            recipe.path,
        )
    if entry.output_schema and entry.output_schema not in contracts.ids():
        _fail(
            RECIPE_INVALID,
            f"{entry.id}: {entry.output_schema!r} is not pinned in the contract "
            f"registry. An unpinned version is never resolved to a guess.",
            recipe.path,
        )

    known = {s.id for s in recipe.steps}
    inputs: list[Ref] = []
    for producer in entry.needs:
        if producer not in known:
            _fail(
                RECIPE_INVALID,
                f"{entry.id} needs {producer!r}, which the recipe has no step for",
                recipe.path,
            )
        if producer == entry.id:
            _fail(
                RECIPE_INVALID,
                f"{entry.id} needs itself. A step that repeats is a declared loop "
                f"region, not a dependency on its own output.",
                recipe.path,
            )
        upstream = recipe.step(producer)
        inputs.append(Ref(name=producer, producer=producer, schema=upstream.output_schema))
    for name in entry.run_inputs:
        declared = recipe.input(name)
        if declared is None:
            _fail(
                RECIPE_INVALID,
                f"{entry.id} takes run input {name!r}, which the recipe's inputs block "
                f"does not declare. Nothing enters a plan undeclared.",
                recipe.path,
            )
            raise AssertionError  # unreachable
        inputs.append(Ref(name=name, producer=RUN_BOUNDARY, schema=declared.schema))

    pin: str | None = None
    if entry.kind == "skill" and entry.skill:
        resolved = context.scope.skill(entry.skill)
        pin = str(ModelPin.for_tier(resolved.skill.tier, effort=context.effort))

    return Step(
        id=entry.id,
        kind=entry.kind,  # type: ignore[arg-type]
        skill=_pinned(entry, context),
        inputs=tuple(inputs),
        output_schema=entry.output_schema,
        timeout_s=entry.timeout_s,
        retries=entry.retries,
        loops=membership.get(entry.id, ()),
        on_failure=entry.on_failure,  # type: ignore[arg-type]
        label=entry.label,
        model_pin=pin,
        max_turns=entry.max_turns,
    )


def _pinned(entry: RecipeStep, context: PlanContext) -> str | None:
    """`name@version`, from the resolved scope rather than from the recipe.

    A recipe names a skill; the scope decides which version of it this engagement has.
    Pinning here is what makes the plan hash change when a skill is revised, without
    every recipe having to be edited.
    """
    if entry.kind != "skill" or not entry.skill:
        return None
    return context.scope.skill(entry.skill).skill.key


def _edges(
    steps: tuple[Step, ...],
    regions: tuple[LoopRegion, ...],
    by_id: dict[str, Step],
) -> tuple[Edge, ...]:
    edges: list[Edge] = []
    for step in steps:
        for ref in step.inputs:
            if ref.from_run:
                continue
            edges.append(
                Edge(src=ref.producer, dst=step.id, name=ref.name, schema=ref.schema)
            )
    for region in regions:
        edges.append(
            Edge(
                src=region.tail,
                dst=region.head,
                name=region.loop,
                schema=by_id[region.tail].output_schema,
                loop=region.id,
            )
        )
    return tuple(edges)


# ------------------------------------------------------------------- cycles


def _refuse_undeclared_cycles(
    steps: tuple[Step, ...],
    regions: tuple[LoopRegion, ...],
    edges: tuple[Edge, ...],
) -> None:
    """Every cycle in the plan is a declared, bounded region - or it does not compile.

    Checked as two halves, because a single strongly-connected-components pass over the
    whole graph cannot do it: regions nest. Self-verification repeats one step that sits
    inside the span of conflict resolution, and both are legitimate, but they live in one
    component and SCC would only ever see the outer one.

    So: **the dependency graph alone must be acyclic** - any cycle there is one nobody
    declared, whether it was authored by accident or on purpose. And **every declared
    region must close a real cycle**, its members being exactly the steps its back edge
    returns over. A ceiling that bounds nothing reads like a control and is not one.
    """
    forward: dict[str, list[str]] = {s.id: [] for s in steps}
    for step in steps:
        for producer in step.needs:
            forward[producer].append(step.id)

    for component in _strongly_connected(forward):
        if len(component) == 1 and next(iter(component)) not in forward[next(iter(component))]:
            continue  # a step, not a cycle
        named = ", ".join(sorted(component))
        declared = "; ".join(f"{r.id} over {sorted(r.members)}" for r in regions) or "none"
        _fail(
            UNDECLARED_CYCLE,
            f"the dependencies cycle through {named}. Every loop is a declared region "
            f"with an integer ceiling, so a dependency that closes a cycle has nothing "
            f"bounding it. Declared regions: {declared}",
            named,
        )

    for region in regions:
        spanned = _nodes_between(region.head, region.tail, forward)
        if spanned is None:
            _fail(
                RECIPE_INVALID,
                f"loop region {region.id} returns from {region.tail!r} to "
                f"{region.head!r}, but nothing in the plan runs from the head to the "
                f"tail. Its back edge would close a cycle over steps that never reach "
                f"each other.",
                region.id,
            )
            raise AssertionError  # unreachable
        if spanned != set(region.members):
            missing = sorted(spanned - set(region.members))
            extra = sorted(set(region.members) - spanned)
            complaint = []
            if missing:
                complaint.append(
                    f"every path from {region.head} to {region.tail} also passes through "
                    f"{', '.join(missing)}, which the region does not list - those steps "
                    f"would iterate without being inside a declared loop"
                )
            if extra:
                complaint.append(f"{', '.join(extra)} is listed but is not on that path")
            _fail(RECIPE_INVALID, f"loop region {region.id}: {'; '.join(complaint)}", region.id)


def _nodes_between(head: str, tail: str, forward: dict[str, list[str]]) -> set[str] | None:
    """Every step on some path from head to tail, head and tail included.

    None when the tail is not reachable from the head at all. A self-loop region - head
    and tail the same step - spans exactly that step.
    """
    if head == tail:
        return {head}
    reachable_from_head = _reachable(head, forward)
    if tail not in reachable_from_head:
        return None
    backward: dict[str, list[str]] = {node: [] for node in forward}
    for node, targets in forward.items():
        for target in targets:
            backward[target].append(node)
    return reachable_from_head & _reachable(tail, backward)


def _reachable(start: str, adjacency: dict[str, list[str]]) -> set[str]:
    seen = {start}
    stack = [start]
    while stack:
        for nxt in adjacency[stack.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _strongly_connected(adjacency: dict[str, list[str]]) -> list[set[str]]:
    """Tarjan, iterative. Recursion depth is not a property a plan should have to have."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[set[str]] = []
    counter = 0

    for root in adjacency:
        if root in index:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, child = work[-1]
            if child == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            if child < len(adjacency[node]):
                work[-1] = (node, child + 1)
                nxt = adjacency[node][child]
                if nxt not in index:
                    work.append((nxt, 0))
                elif nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            else:
                if low[node] == index[node]:
                    component: set[str] = set()
                    while True:
                        popped = stack.pop()
                        on_stack.discard(popped)
                        component.add(popped)
                        if popped == node:
                            break
                    components.append(component)
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
    return components


# --------------------------------------------------------------- ordering


def _topological(steps: tuple[Step, ...]) -> tuple[str, ...]:
    """Execution order over the forward edges. Back edges are the loop's business.

    Ties break on the recipe's own order, so the ordering is stable and a plan reads the
    way it was written.
    """
    position = {s.id: n for n, s in enumerate(steps)}
    pending = {s.id: set(s.needs) for s in steps}
    ordered: list[str] = []
    while pending:
        ready = sorted((sid for sid, needs in pending.items() if not needs), key=position.get)  # type: ignore[arg-type]
        if not ready:
            # Unreachable: undeclared cycles are refused before this runs, and a
            # declared region's back edge is not a dependency.
            raise RegistryError(
                diagnose(UNDECLARED_CYCLE, f"cannot order {sorted(pending)}", locator="plan")
            )
        for sid in ready:
            ordered.append(sid)
            del pending[sid]
        for needs in pending.values():
            needs.difference_update(ready)
    return tuple(ordered)


def _levels(steps: tuple[Step, ...], order: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """Steps grouped by dependency depth: what could run at the same time.

    The Engagement Lock serialises within one deal, so this is not a promise that a run
    will fan out. It is the compiler saying which steps have no reason not to, which is
    what the worker pool needs from P25 and what the console draws today.
    """
    depth: dict[str, int] = {}
    by_id = {s.id: s for s in steps}
    for sid in order:
        needs = by_id[sid].needs
        depth[sid] = 1 + max((depth[n] for n in needs), default=-1)
    grouped: dict[int, list[str]] = {}
    for sid in order:
        grouped.setdefault(depth[sid], []).append(sid)
    return tuple(tuple(grouped[d]) for d in sorted(grouped))


# ------------------------------------------------------------------- hashing


def _plan_hash(
    recipe: Recipe,
    context: PlanContext,
    steps: tuple[Step, ...],
    edges: tuple[Edge, ...],
    regions: tuple[LoopRegion, ...],
    contracts: ContractRegistry,
    constraints: ConstraintRegistry,
) -> str:
    """Structure, versions, pins, schemas, template, taxonomy and the precedent snapshot.

    Every field here is something that can change under a run without the recipe
    changing. Leave one out and two runs can share a hash, differ underneath, and
    legitimately disagree - which is exactly what happened in review with the precedent
    snapshot before it was added.
    """
    scope = context.scope
    payload: dict[str, Any] = {
        "recipe": [recipe.name, recipe.version],
        "engagement_id": context.engagement_id,
        "structure": [
            {
                "id": s.id,
                "kind": s.kind,
                "skill": s.skill,
                "inputs": [[r.name, r.producer, r.schema] for r in s.inputs],
                "output_schema": s.output_schema,
                "timeout_s": s.timeout_s,
                "retries": s.retries,
                "loops": list(s.loops),
                "on_failure": s.on_failure,
                "max_turns": s.max_turns,
                "model_pin": s.model_pin,
            }
            for s in steps
        ],
        "edges": sorted([e.src, e.dst, e.name, e.schema or "", e.loop or ""] for e in edges),
        "loops": sorted(
            [r.loop, r.head, list(r.members), r.max_iterations, r.scope] for r in regions
        ),
        "scope": str(scope.scope),
        "resolution_hash": scope.resolution_hash,
        "template": None
        if scope.template is None
        else [scope.template.file, scope.template.template_version],
        "taxonomy_version": context.taxonomy_version,
        "precedent_snapshot": context.precedent_snapshot,
        "contracts_version": context.contracts_version or contracts.version,
        "constraints_version": context.constraints_version or constraints.version,
        "scopes_version": scope.scopes_version,
        "effort": context.effort,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(body).hexdigest()}"
