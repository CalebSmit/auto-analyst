"""The 25 invariants, as a suite that runs.

A diagram can be quietly wrong for months. An assertion that runs cannot. This is where
the properties in the blueprint's left rail stop being claims about a picture and become
checks over `graph/architecture.json`, exported from the blueprint itself.

**Two graphs, two suites, and conflating them is the mistake.** This one runs over the
*architecture* graph - 118 nodes, one per repo, asserted in CI on every commit. It
answers "is the design intact". The plan suite in `graph.plan_assertions` runs over a
compiled plan of about eight typed steps, before execution, and answers "is this run
legal". Three assertions in the blueprint's first draft were unsatisfiable because they
were written as though there were one graph.

**Why most of these walk content edges only.** The graph draws ten kinds of edge, and
only three of them move work: `flow`, `masked` and `guard`. A `record` edge reports what
happened, a `pref` edge carries a setting, a `port` edge binds an interface, a `human`
edge is a person acting. Walk all ten and the graph is so densely connected that the
Analyst Chat - a read-only surface - "reaches" the model builder in twenty-five hops, and
every dominance claim becomes false for reasons that have nothing to do with the design.
Walk the three that carry work and the questions get their real answers.

**What a graph can and cannot prove.** Reachability cannot always tell a figure's path
from a tool call: a skill reaches the recompute engine and the recompute engine reaches
the tie-out gate, but no figure travelled that way. Where that ambiguity bites, the
assertion tests specific edges instead of paths, and its docstring says which half of the
invariant is structural and which half is enforced at run time by a guard. An assertion
that overclaims is worse than one that is narrow and honest.

Each function is named for its invariant and carries its text. `ALL` is ordered:
`ALL[n - 1]` is invariant n as the blueprint numbers them.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
GRAPH_FILE = REPO_ROOT / "graph" / "architecture.json"

# The edges that move work. Everything else reports, configures, binds or is a person.
ARTIFACT_KINDS = frozenset({"flow", "masked", "guard"})

# The narrower set: an edge that can move a finished artifact. A `guard` edge hands work
# on after a check, which is movement; but for "what may write to the delivery port" the
# question is only about content leaving, so `flow` and `masked` are the carriers.
CONTENT_KINDS = frozenset({"flow", "masked"})

# Where a run's client work ends up.
DELIVERABLES = ("model_builder", "ddr_pack", "workpaper")

# Model nodes the LLM Port does not serve, each with the reason it is outside the run
# graph. The test asserts this mapping is exactly right, so a model node added without a
# port edge fails until somebody either wires it up or writes down why it is exempt.
OUTSIDE_THE_RUN_GRAPH = {
    "analyst_chat": (
        "Read-only over the run store, and deliberately the one model surface outside "
        "the masking path - the blueprint says so in prose rather than leaving it to be "
        "discovered in the graph."
    ),
    "doc_classifier": (
        "Intake. Reads a raw document inside the Untrusted Content Boundary, before "
        "masking, so it is on the intake path rather than the payload path. The port "
        "edge is not drawn; see the P07 note in BUILD/AMENDMENTS.md."
    ),
    "period_detector": "Intake, before masking. Same as doc_classifier.",
    "workbook_reader": "Intake, before masking. Same as doc_classifier.",
    "email_watcher": "Intake, before masking. Same as doc_classifier.",
}

__all__ = [
    "ALL",
    "ARTIFACT_KINDS",
    "ArchGraph",
    "AssertionFailed",
    "Edge",
    "Invariant",
    "check_all",
    "load_graph",
]


class AssertionFailed(AssertionError):
    """An invariant does not hold over the architecture graph."""


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str
    label: str = ""

    def __str__(self) -> str:
        head = f"{self.src} -> {self.dst} ({self.kind}"
        return f"{head}: {self.label})" if self.label else f"{head})"


@dataclass
class ArchGraph:
    """The blueprint's node and edge model, with the queries the invariants need."""

    nodes: dict[str, dict[str, Any]]
    edges: tuple[Edge, ...]
    invariant_texts: tuple[str, ...] = ()
    source_digest: str = ""
    _out: dict[str, list[Edge]] = field(default_factory=dict, repr=False)
    _in: dict[str, list[Edge]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for node_id in self.nodes:
            self._out[node_id] = []
            self._in[node_id] = []
        for edge in self.edges:
            self._out[edge.src].append(edge)
            self._in[edge.dst].append(edge)

    def __getitem__(self, node_id: str) -> dict[str, Any]:
        return self.nodes[node_id]

    def __contains__(self, node_id: object) -> bool:
        return node_id in self.nodes

    def __len__(self) -> int:
        return len(self.nodes)

    # -- neighbours

    def out(self, node_id: str, kinds: Iterable[str] | None = None) -> tuple[Edge, ...]:
        allowed = frozenset(kinds) if kinds is not None else None
        return tuple(e for e in self._out[node_id] if allowed is None or e.kind in allowed)

    def inbound(self, node_id: str, kinds: Iterable[str] | None = None) -> tuple[Edge, ...]:
        allowed = frozenset(kinds) if kinds is not None else None
        return tuple(e for e in self._in[node_id] if allowed is None or e.kind in allowed)

    def neighbours(self, node_id: str) -> tuple[str, ...]:
        """Both directions. "No model node can reach the vault" is not a question about
        which way the arrow points - an edge either way is contact."""
        return tuple(
            sorted({e.dst for e in self._out[node_id]} | {e.src for e in self._in[node_id]})
        )

    def nodes_where(self, **match: Any) -> tuple[str, ...]:
        return tuple(
            node_id
            for node_id, node in self.nodes.items()
            if all(node.get(k) == v for k, v in match.items())
        )

    def kind(self, *kinds: str) -> tuple[Edge, ...]:
        return tuple(e for e in self.edges if e.kind in kinds)

    # -- reachability

    def reachable(
        self,
        start: str,
        kinds: Iterable[str] | None = None,
        without: str | None = None,
    ) -> frozenset[str]:
        allowed = frozenset(kinds) if kinds is not None else None
        seen = {start}
        stack = [start]
        while stack:
            for edge in self._out[stack.pop()]:
                if allowed is not None and edge.kind not in allowed:
                    continue
                if edge.dst == without or edge.dst in seen:
                    continue
                seen.add(edge.dst)
                stack.append(edge.dst)
        return frozenset(seen)

    def ancestors(self, target: str, kinds: Iterable[str] | None = None) -> frozenset[str]:
        allowed = frozenset(kinds) if kinds is not None else None
        seen = {target}
        stack = [target]
        while stack:
            for edge in self._in[stack.pop()]:
                if allowed is not None and edge.kind not in allowed:
                    continue
                if edge.src not in seen:
                    seen.add(edge.src)
                    stack.append(edge.src)
        return frozenset(seen)

    def roots(self, kinds: Iterable[str] | None = None) -> tuple[str, ...]:
        """Nodes nothing flows into, within the given edge kinds."""
        return tuple(
            sorted(
                node_id
                for node_id in self.nodes
                if not self.inbound(node_id, kinds) and self.out(node_id, kinds)
            )
        )

    def dominated_by(
        self,
        target: str,
        gate: str,
        kinds: Iterable[str] | None = ARTIFACT_KINDS,
        roots: Iterable[str] | None = None,
    ) -> bool:
        """Does every path from a root to `target` pass through `gate`?

        Computed by deletion rather than a dominator tree: remove the gate and ask whether
        anything can still get there. That is the property the invariant claims, it stays
        correct on a graph with many roots, and the failure message can then show the
        route that got through.

        `roots` narrows the question to paths that start somewhere specific - "from a
        skill", say - which is what makes several of these assertions mean what their
        invariant means rather than something adjacent to it.
        """
        if target == gate:
            return True
        starts = list(roots) if roots is not None else list(self.roots(kinds))
        return not any(
            target in self.reachable(start, kinds, without=gate)
            for start in starts
            if start != gate
        )

    def route_avoiding(
        self,
        target: str,
        gate: str,
        kinds: Iterable[str] | None = ARTIFACT_KINDS,
        roots: Iterable[str] | None = None,
    ) -> tuple[str, ...]:
        """One concrete path that gets to `target` without `gate`, for the message.

        A person reading a failed assertion is trying to work out what changed. "It is
        reachable" sends them to the graph; a route sends them to the edge.
        """
        allowed = frozenset(kinds) if kinds is not None else None
        starts = list(roots) if roots is not None else list(self.roots(kinds))
        for start in starts:
            if start == gate:
                continue
            stack: list[tuple[str, tuple[str, ...]]] = [(start, (start,))]
            seen = {start}
            while stack:
                node, path = stack.pop()
                if node == target:
                    return path
                for edge in self._out[node]:
                    if allowed is not None and edge.kind not in allowed:
                        continue
                    if edge.dst == gate or edge.dst in seen:
                        continue
                    seen.add(edge.dst)
                    stack.append((edge.dst, (*path, edge.dst)))
        return ()

    @cached_property
    def llm_nodes(self) -> frozenset[str]:
        """Anything that runs a model, hybrid included.

        Hybrid counts. A node that is code most of the time and a model call sometimes is
        a model node for every invariant here - the guarantee has to hold on the branch
        where the model runs.
        """
        return frozenset(self.nodes_where(exec="llm") + self.nodes_where(exec="hybrid"))

    @cached_property
    def skill_nodes(self) -> tuple[str, ...]:
        """The nine dispatchable skills. `skill_contract` is in the group but is a
        schema, not something that runs."""
        return tuple(
            sorted(n for n in self.nodes_where(group="skill") if n.startswith("sk_"))
        )

    @cached_property
    def tool_nodes(self) -> tuple[str, ...]:
        """Tools that execute. A registry in the same band is a resource, not a tool -
        `runtime` is what separates them."""
        return tuple(
            sorted(
                n
                for n in self.nodes_where(group="tool", runtime="step")
                if n != "guarded_runtime"
            )
        )


def load_graph(path: Path = GRAPH_FILE) -> ArchGraph:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ArchGraph(
        nodes={n["id"]: n for n in raw["nodes"]},
        edges=tuple(
            Edge(src=e["from"], dst=e["to"], kind=e["kind"], label=e.get("label", ""))
            for e in raw["edges"]
        ),
        invariant_texts=tuple(i["t"] for i in raw["invariants"]),
        source_digest=raw.get("source_digest", ""),
    )


def fail(message: str) -> None:
    raise AssertionFailed(message)


def _with_route(message: str, route: tuple[str, ...]) -> str:
    return message + (f" - e.g. {' -> '.join(route)}" if route else "")


# ================================================================ invariants


def assert_no_model_reaches_the_vault(g: ArchGraph) -> None:
    """1. No model node can reach the Mask Vault.

    Re-identification is deterministic code, so a token can never be resolved by
    something that might guess. Neighbours in both directions: an edge either way is
    contact, and which way the arrow points is not the point.
    """
    for neighbour in g.neighbours("mask_vault"):
        if neighbour in g.llm_nodes:
            fail(
                f"{neighbour} touches mask_vault and runs a model "
                f"(exec={g[neighbour]['exec']}). Re-identification is code, or it is a guess."
            )


def assert_one_door_to_a_model(g: ArchGraph) -> None:
    """2. Every payload bound for a model passes through one door.

    One place to check what leaves and one place to record it. Every node that runs a
    model takes its model access from the LLM Port - except the ones listed in
    `OUTSIDE_THE_RUN_GRAPH`, each with a written reason, and the list is asserted to be
    exactly right so a new model node cannot join it by being forgotten.
    """
    served = {e.dst for e in g.out("llm_port")}
    unserved = {
        n for n in g.llm_nodes if n not in served and "llm_port" not in g.ancestors(n)
    }
    undeclared = sorted(unserved - set(OUTSIDE_THE_RUN_GRAPH))
    if undeclared:
        fail(
            f"{', '.join(undeclared)} run a model and cannot reach llm_port. Either wire "
            f"them to the port or record in OUTSIDE_THE_RUN_GRAPH why they are outside "
            f"the run graph - the one thing that must not happen is a model call nobody "
            f"has a place to scan."
        )
    stale = sorted(set(OUTSIDE_THE_RUN_GRAPH) - unserved)
    if stale:
        fail(f"{', '.join(stale)} are listed as outside the run graph but the port reaches them")
    if len(g.inbound("payload_scan", CONTENT_KINDS)) != 1:
        fail("payload_scan does not have exactly one content way in, so it is not one door")


def assert_only_code_touches_reidentification(g: ArchGraph) -> None:
    """3. Only CODE nodes touch re-identification.

    No skill has an unmask tool. It is the one step where a plausible mistake is
    indistinguishable from correctness, so there is nothing here able to be plausible.
    """
    for node_id in ("unmask_engine", "unmask_verify", "mask_vault", "mask_engine"):
        if g[node_id]["exec"] != "code":
            fail(f"{node_id} handles re-identification and is exec={g[node_id]['exec']}")
        for neighbour in g.neighbours(node_id):
            if neighbour in g.llm_nodes:
                fail(f"{neighbour} runs a model and touches {node_id}")


def assert_every_figure_cleared_provenance_and_tieout(g: ArchGraph) -> None:
    """4. Every figure in a deliverable cleared Provenance and was recomputed by Tie-Out.

    The structural half, and it is worth being exact about which half that is. Figures
    enter a deliverable through one door - `numeric_lock` is the only content edge into
    each - and no skill can reach a deliverable without the tie-out gate and the lock.
    Every skill's output leaves through the schema gate, which leads to provenance.

    What the graph cannot prove is that the *particular value* in a cell cleared the
    gates, because reachability cannot tell a figure's path from a tool call: a skill
    reaches the recompute engine and the recompute engine reaches the tie-out gate, but no
    figure travelled that way. That half is the provenance gate's own job at run time,
    in P13.
    """
    for deliverable in DELIVERABLES:
        sources = {e.src for e in g.inbound(deliverable, ARTIFACT_KINDS)}
        if sources != {"numeric_lock"}:
            fail(
                f"{deliverable} takes content from {sorted(sources)}; figures enter a "
                f"deliverable locked or they do not enter"
            )
    for gate in ("tieout_gate", "numeric_lock", "unmask_verify"):
        for deliverable in DELIVERABLES:
            if not g.dominated_by(deliverable, gate, roots=g.skill_nodes):
                route = g.route_avoiding(deliverable, gate, roots=g.skill_nodes)
                fail(_with_route(f"a skill reaches {deliverable} without {gate}", route))
    for skill in g.skill_nodes:
        if "schema_gate" not in {e.dst for e in g.out(skill, ARTIFACT_KINDS)}:
            fail(f"{skill} does not send its output through the schema gate")
    if "provenance_gate" not in {e.dst for e in g.out("schema_gate", ARTIFACT_KINDS)}:
        fail("the schema gate does not hand on to provenance")


def assert_generation_never_originates_a_figure(g: ArchGraph) -> None:
    """5. A generative step may render a verified figure but can never originate or alter
    one.

    The narrative is written after the numbers are locked. So a model node downstream of
    `numeric_lock` must not have any content edge back into the figure path - if it did,
    something written by a model could re-enter as a number.

    Its schema having no field a figure can enter through is the other half, and that is
    the contract registry's, not the graph's.
    """
    locked_side = g.reachable("numeric_lock", ARTIFACT_KINDS) - {"numeric_lock"}
    figure_path = g.ancestors("numeric_lock", ARTIFACT_KINDS)
    for node_id in sorted(locked_side & g.llm_nodes):
        for edge in g.out(node_id, ARTIFACT_KINDS):
            if edge.dst in figure_path:
                fail(
                    f"{edge} - {node_id} runs a model after the numbers are locked and "
                    f"feeds content back into the figure path"
                )


def assert_one_release_with_one_inbound_edge(g: ArchGraph) -> None:
    """6. One node releases client work, with one inbound edge.

    The run manifest is written separately and unconditionally, including when a run
    halts. Configuration selects the destination but carries no content: only a content
    edge can move an artifact, which is why `pref` is excluded below.
    """
    inbound = g.inbound("release_gate")
    if len(inbound) != 1:
        fail(
            f"release_gate has {len(inbound)} inbound edges "
            f"({', '.join(str(e) for e in inbound)}); one release means one way in"
        )
    carriers = {e.src for e in g.inbound("delivery_port", CONTENT_KINDS)}
    if carriers != {"idempotency_ledger", "run_manifest"}:
        fail(
            f"content reaches delivery_port from {sorted(carriers)}; expected the "
            f"released artifact and the run manifest, and nothing else"
        )


def assert_governance_never_reads_client_data(g: ArchGraph) -> None:
    """7. Governance never reads client-identifying data - only masked payloads.

    And its one edge back into the live system publishes a skill definition, never a
    file. Both halves: what crosses in, and what crosses out.
    """
    governance = set(g.nodes_where(group="gov"))
    for edge in g.kind("flow"):
        if edge.dst in governance and edge.src not in governance:
            fail(
                f"{edge} carries content into governance. Governance sees masked "
                f"payloads or it sees nothing."
            )
    returning = [e for e in g.kind("flow") if e.src in governance and e.dst not in governance]
    if len(returning) != 1:
        fail(
            f"governance has {len(returning)} content edges back into the live system "
            f"({', '.join(str(e) for e in returning)}); there is one, and it publishes a "
            f"skill definition"
        )
    if returning[0].dst != "skill_tree":
        fail(f"governance returns content to {returning[0].dst}, not to the skill tree")


def assert_every_guard_writes_to_the_record(g: ArchGraph) -> None:
    """8. Every guard writes to the record - passes included.

    A guard that only speaks when it fires is, on a quiet day, indistinguishable from a
    guard that never ran at all. Silence has to be unambiguous.
    """
    for guard in sorted(g.nodes_where(group="guard")):
        if "event_bus" not in g.reachable(guard, kinds=None):
            fail(f"{guard} is a guard and cannot reach event_bus, so its passes are silent")


def assert_only_a_human_writes_precedent(g: ArchGraph) -> None:
    """9. Only a human decision can write to the Precedent Store.

    A system that learns from its own unreviewed output drifts, and does it invisibly.
    One writer, and every path to that writer passes a recorded human decision.
    """
    writers = {e.src for e in g.inbound("precedent_store")}
    if writers != {"precedent_writeback"}:
        fail(f"the precedent store is written by {sorted(writers)}, not only the writeback")
    if not g.dominated_by("precedent_writeback", "decision_log"):
        route = g.route_avoiding("precedent_writeback", "decision_log")
        fail(
            _with_route(
                "precedent_writeback is reachable without decision_log, so something "
                "other than a human decision can write precedent",
                route,
            )
        )


def assert_nothing_runs_unscoped(g: ArchGraph) -> None:
    """10. Nothing runs unscoped, and never two runs at once on one deal.

    Cross-client bleed is the failure mode that ends the project. Every file is stamped
    with its deal before a run can start, and the only content way out of the intake
    window is through the lock - so two runs cannot race on one engagement.
    """
    if "engagement_bind" not in g.ancestors("intake_window", ARTIFACT_KINDS):
        fail("a file reaches the intake window without being bound to an engagement")
    onward = {e.dst for e in g.out("intake_window", ARTIFACT_KINDS)}
    if onward != {"engagement_lock"}:
        fail(
            f"the intake window hands on to {sorted(onward)}; the engagement lock is the "
            f"only way a run may start, or two runs can fight over one deal"
        )
    if "storage_port" not in {e.dst for e in g.out("engagement_lock", ARTIFACT_KINDS)}:
        fail("the engagement lock does not gate the storage port")


def assert_every_loop_is_declared(g: ArchGraph) -> None:
    """11. Every loop is declared with a maximum iteration count.

    Over the architecture graph this is the structural half: every loop edge in the
    design answers to a controller or the compiler. The executable half - a compiled plan
    containing no undeclared cycle - is `plan_assertions.assert_all_loops_bounded`, and
    that is where the enforcement is.
    """
    for edge in g.kind("loop"):
        upstream = g.ancestors(edge.src, kinds=None) | {edge.src}
        if not ({"loop_controller", "graph_compiler", "step_executor"} & upstream):
            fail(f"{edge} is a loop with no controller or compiler upstream of it")


def assert_every_step_is_keyed(g: ArchGraph) -> None:
    """12. Every step is keyed and idempotent.

    A retry, a resume and a manual re-run are the same operation. Structurally: the
    release goes through the ledger, so a repeated release is one release. The manifest
    reaches the delivery port on its own edge, which is invariant 6's business and is
    deliberately not keyed the same way - it is written unconditionally.
    """
    for node_id in ("step_executor", "checkpoint_store", "idempotency_ledger"):
        if node_id not in g:
            fail(f"{node_id} is missing; without it a retry is not a re-run")
    onward = {e.dst for e in g.out("release_gate", ARTIFACT_KINDS)}
    if onward != {"idempotency_ledger"}:
        fail(
            f"release_gate hands on to {sorted(onward)}; a release that skips the ledger "
            f"is a release that can happen twice"
        )
    if "delivery_port" not in {e.dst for e in g.out("idempotency_ledger", CONTENT_KINDS)}:
        fail("the idempotency ledger does not reach the delivery port")


def assert_every_run_records_its_versions(g: ArchGraph) -> None:
    """13. Every run records the exact model, prompt, skill, template, taxonomy and schema
    versions it used.

    A workfile that cannot say which model produced a figure is a workfile that cannot be
    defended.
    """
    for source in ("model_pin", "graph_compiler", "contract_registry", "t_registry"):
        if "run_manifest" not in g.reachable(source, kinds=None):
            fail(f"{source} cannot reach run_manifest, so its version is not recorded")


def assert_a_scope_overlay_can_only_tighten(g: ArchGraph) -> None:
    """14. A scope overlay can only tighten.

    Nothing deeper in the tree can loosen a review requirement or a privacy class. The
    graph half: the resolver reads a declared taxonomy rather than inferring one, and any
    configuration edge that does reach a guard says on its face that it may only raise.
    The enforcement half is `graph.resolve`, which refuses a loosening outright.
    """
    if not any(e.src == "scope_registry" for e in g.inbound("scope_resolver")):
        fail("scope_resolver does not read scope_registry, so the taxonomy is implicit")
    guards = set(g.nodes_where(group="guard"))
    for edge in g.kind("pref"):
        if edge.dst in guards and not _says_it_cannot_lower(edge.label):
            fail(
                f"{edge} is a configuration edge into a guard and its label does not say "
                f"it may only tighten. An admin may raise a review requirement, never "
                f"lower one, and the edge has to say so."
            )


def _says_it_cannot_lower(label: str) -> bool:
    lowered = label.lower()
    return any(phrase in lowered for phrase in ("cannot lower", "may only raise", "only raise"))


def assert_an_engagement_sees_only_its_scope(g: ArchGraph) -> None:
    """15. An engagement can only see the skills its scope resolves to.

    A Corporate Finance skill is not declined by an ESOP run - it was never in it. The
    orchestrator's view of the library is the resolved index, never the whole tree.
    """
    feeders = {e.src for e in g.inbound("skill_index")}
    if feeders != {"scope_resolver"}:
        fail(f"skill_index is fed by {sorted(feeders)}; the resolver is what narrows the field")
    for edge in g.inbound("orchestrator"):
        if edge.src == "skill_tree":
            fail("the orchestrator reads the whole skill tree rather than the resolved index")


def assert_precedents_stay_in_scope(g: ArchGraph) -> None:
    """16. Precedents are retrieved only from the engagement's own scope.

    A repeat client sees its own prior decisions first. Retrieval reaches a model only
    through the context builder, which is the node that knows the scope.
    """
    readers = {e.dst for e in g.out("precedent_store")}
    if readers != {"context_builder"}:
        fail(
            f"precedents go to {sorted(readers)}; the context builder is the node that "
            f"knows the scope, so it is the only one that may retrieve them"
        )
    if not any(e.src == "scope_resolver" for e in g.inbound("context_builder")):
        fail("context_builder does not receive the resolved scope, so retrieval is unscoped")


def assert_every_tool_call_is_authorised(g: ArchGraph) -> None:
    """17. Every tool call is authorised before it executes.

    No skill can reach a tool around the gate. Tested on edges rather than reachability:
    a skill can *reach* the template writer through the figure path, but that is a figure
    travelling, not a skill calling a tool. What must not exist is a direct edge from
    anything that runs a model to a tool - every such call goes through the policy gate
    and then the runtime.

    Code invoking a tool directly is not a violation and is not treated as one: the Model
    Builder calls the template writer, and neither of them can guess.
    """
    tools = set(g.tool_nodes)
    for skill in g.skill_nodes:
        direct = [e for e in g.out(skill) if e.dst in tools]
        if direct:
            fail(
                f"{', '.join(str(e) for e in direct)} - a skill calls a tool directly, "
                f"around the policy gate"
            )
    for tool in g.tool_nodes:
        model_callers = sorted({e.src for e in g.inbound(tool)} & g.llm_nodes)
        if model_callers:
            fail(f"{tool} is invoked directly by {', '.join(model_callers)}, which runs a model")
    if not any(e.src == "policy_gate" for e in g.inbound("guarded_runtime")):
        fail("the guarded runtime runs without the policy gate deciding first")


def assert_context_is_assembled_in_one_place(g: ArchGraph) -> None:
    """18. Everything a model is shown is assembled in one place and recorded.

    So any call can be reconstructed exactly. "What was in context?" should be a hash
    lookup rather than an archaeology exercise.
    """
    for skill in g.skill_nodes:
        if "context_builder" not in {e.src for e in g.inbound(skill, ARTIFACT_KINDS)}:
            fail(f"{skill} receives a payload from somewhere other than the context builder")
    if "event_bus" not in {e.dst for e in g.out("context_builder")}:
        fail("context_builder does not record what it assembled")


def assert_every_run_ends_with_a_computed_verdict(g: ArchGraph) -> None:
    """19. Every run ends with a computed verdict against versioned criteria.

    No run's outcome is a matter of opinion: the scorecard reads the event stream and
    writes the manifest, rather than a person deciding after the fact.
    """
    if not any(e.src == "run_store" for e in g.inbound("run_scorecard")):
        fail("run_scorecard does not read the run store, so its verdict is not computed")
    if "run_manifest" not in {e.dst for e in g.out("run_scorecard")}:
        fail("the scorecard's verdict never reaches the manifest")


def assert_every_failure_carries_a_code(g: ArchGraph) -> None:
    """20. Every failure carries a stable code, an owner and what to do next.

    A message nobody can act on is a defect. Direct edges rather than reachability: over
    all ten edge kinds this graph is connected enough that everything "reaches" everything,
    and the question is whether the registry actually feeds each surface. The Ops Console
    is not in the list because it takes its codes through the scorecard rather than from
    the registry itself.
    """
    if "diagnostics" not in g:
        fail("there is no diagnostics registry")
    served = {e.dst for e in g.out("diagnostics")}
    for surface in ("quarantine", "fixed_notice", "run_scorecard"):
        if surface not in served:
            fail(
                f"{surface} reports a failure to a person and takes no edge from the "
                f"diagnostics registry, so its message has no code, no owner and no next "
                f"action"
            )


def assert_a_dropped_draft_is_only_a_candidate(g: ArchGraph) -> None:
    """21. A dropped draft is a candidate, not a skill.

    No path from the drop folder to the tree skips fixtures, review or a shadow run.
    Remove any one gate and the folder can no longer reach the live tree - that is the
    assertion, not a promise. All seven are checked, individually.
    """
    if "skill_tree" not in g.reachable("skill_drop", ARTIFACT_KINDS):
        fail(
            "the drop folder cannot reach the skill tree at all. The governance chain is "
            "how a draft becomes a skill; a severed chain is not a safe one, it is a "
            "broken one, and every gate below would pass over nothing."
        )
    for gate in (
        "skill_conformance",
        "skill_adapt",
        "skill_sandbox",
        "sandbox_test",
        "eval_harness",
        "skill_board",
        "shadow_run",
        "skill_registry",
    ):
        if "skill_tree" in g.reachable("skill_drop", ARTIFACT_KINDS, without=gate):
            route = g.route_avoiding("skill_tree", gate, roots=["skill_drop"])
            fail(
                _with_route(f"a dropped draft reaches the skill tree without {gate}", route)
            )


def assert_nothing_reaches_the_index_untested(g: ArchGraph) -> None:
    """22. Nothing reaches the Skill Index without passing fixtures and a shadow run.

    Followed along the path a definition actually takes: drop, conformance, bench,
    sandbox, fixtures, board, shadow run, registry, tree - and only then the resolver,
    which builds the index.
    """
    if "skill_registry" not in g.reachable("skill_drop", ARTIFACT_KINDS):
        fail("nothing can reach the skill registry from the drop folder, so no skill is admitted")
    for gate in ("eval_harness", "shadow_run", "skill_board"):
        if "skill_registry" in g.reachable("skill_drop", ARTIFACT_KINDS, without=gate):
            fail(f"a skill reaches the registry without {gate}")
    admitting = {e.src for e in g.inbound("skill_tree", ARTIFACT_KINDS)}
    if admitting != {"skill_registry"}:
        fail(f"the skill tree admits content from {sorted(admitting)}, not only the registry")
    if {e.src for e in g.inbound("skill_index")} != {"scope_resolver"}:
        fail("the skill index is built from something other than the resolved scope")


def assert_config_cannot_reach_a_failclosed_node(g: ArchGraph) -> None:
    """23. No configuration edge reaches a node that can fail closed.

    Config writes the engagement record; guards read the run. A guarantee with a dial on
    it is not a guarantee.

    Direct edges out of the config store, which is what "a configuration edge" means. The
    one config path that does reach a guard goes through `checkpoint_policy`, whose rule
    is that it may only raise a requirement - stated on the edge, and checked by
    invariant 14 rather than dissolved into reachability here.
    """
    guards = set(g.nodes_where(group="guard"))
    for edge in g.out("config_store"):
        if edge.dst in guards:
            fail(
                f"{edge} - config reaches a node that fails closed. "
                f"That is a guarantee with a dial on it."
            )


def assert_the_roster_gates_every_source(g: ArchGraph) -> None:
    """24. An engagement not on the roster has no path from any intake source.

    Inactive is unreachable, not merely unchecked. An archived deal's folder has *no
    path* into the pipeline, which is a property of the graph rather than a filter
    somebody remembered to write.
    """
    sources = g.nodes_where(is_intake=True)
    if not sources:
        fail("no node is marked is_intake, so this assertion covers nothing")
    for source in sources:
        if not g.dominated_by(source, "sweep_planner"):
            route = g.route_avoiding(source, "sweep_planner")
            fail(_with_route(f"{source} is reachable without the sweep planner", route))
    if not any(e.src == "project_roster" for e in g.inbound("sweep_planner")):
        fail("the sweep planner does not read the roster, so it sweeps folders nobody listed")


def assert_one_destination_and_one_template(g: ArchGraph) -> None:
    """25. Every active engagement resolves to exactly one delivery destination and
    exactly one model template pin.

    Both come from configuration, and preflight checks they resolved before a run starts
    rather than after it has produced something with nowhere to go.
    """
    for target in ("delivery_port", "t_registry"):
        sources = {e.src for e in g.inbound(target, ["pref"])}
        if sources != {"config_store"}:
            fail(
                f"{target} takes its setting from {sorted(sources)}; exactly one "
                f"configuration source means exactly one resolved answer"
            )
    if "preflight" not in g:
        fail("nothing checks that an engagement resolves before a run starts")


# ================================================================== registry


@dataclass(frozen=True)
class Invariant:
    """One numbered invariant and the function that checks it."""

    number: int
    check: Callable[[ArchGraph], None]

    @property
    def name(self) -> str:
        return self.check.__name__

    @property
    def summary(self) -> str:
        first = (self.check.__doc__ or "").strip().split("\n")[0]
        return first.split(". ", 1)[-1] if ". " in first else first


# Ordered: ALL[n - 1] is invariant n as the blueprint numbers them. A test asserts this
# list and the blueprint's INVARIANTS array are the same length and in the same order.
ALL: tuple[Invariant, ...] = tuple(
    Invariant(number=n, check=check)
    for n, check in enumerate(
        (
            assert_no_model_reaches_the_vault,
            assert_one_door_to_a_model,
            assert_only_code_touches_reidentification,
            assert_every_figure_cleared_provenance_and_tieout,
            assert_generation_never_originates_a_figure,
            assert_one_release_with_one_inbound_edge,
            assert_governance_never_reads_client_data,
            assert_every_guard_writes_to_the_record,
            assert_only_a_human_writes_precedent,
            assert_nothing_runs_unscoped,
            assert_every_loop_is_declared,
            assert_every_step_is_keyed,
            assert_every_run_records_its_versions,
            assert_a_scope_overlay_can_only_tighten,
            assert_an_engagement_sees_only_its_scope,
            assert_precedents_stay_in_scope,
            assert_every_tool_call_is_authorised,
            assert_context_is_assembled_in_one_place,
            assert_every_run_ends_with_a_computed_verdict,
            assert_every_failure_carries_a_code,
            assert_a_dropped_draft_is_only_a_candidate,
            assert_nothing_reaches_the_index_untested,
            assert_config_cannot_reach_a_failclosed_node,
            assert_the_roster_gates_every_source,
            assert_one_destination_and_one_template,
        ),
        start=1,
    )
)


def check_all(graph: ArchGraph | None = None) -> list[tuple[Invariant, AssertionFailed]]:
    """Run every invariant. Returns the failures rather than raising on the first.

    All of them, because "the design broke in three places" and "the design broke" are
    different reports and only one of them is useful.
    """
    g = graph or load_graph()
    failures: list[tuple[Invariant, AssertionFailed]] = []
    for invariant in ALL:
        try:
            invariant.check(g)
        except AssertionFailed as failure:
            failures.append((invariant, failure))
    return failures
