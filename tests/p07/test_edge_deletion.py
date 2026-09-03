"""Breaking the design in one place fails exactly the right assertion.

The exit criterion, and the test that makes the other twenty-five mean something. An
assertion suite where everything fails whenever anything breaks is not 25 checks, it is
one check with 25 names - and one where nothing fails is 25 functions that say `pass` in
a complicated way.

So each case breaks the design in one specific place and asserts the **exact set** of
invariants that notice. Exact in both directions: the right one fires, and the others
stay quiet. Where two invariants genuinely share a piece of the design the expected set
says so, which is itself worth having written down.

Writing this found three assertions that passed *vacuously* - remove the edge they were
about and the loop they iterated had nothing in it, so silence read as success. All three
now check the thing exists before checking what guards it.
"""

from __future__ import annotations

import pytest

from graph.architecture_assertions import ArchGraph, check_all

# --------------------------------------------------------------- the cases
#
# Each row: the change, and every invariant number that should notice it. Held as module
# constants rather than inline, so the coverage test at the bottom can read them.

DELETIONS: tuple[tuple[str, str, set[int]], ...] = (
    # The release path. A release that skips the ledger is one that can happen twice.
    ("release_gate", "idempotency_ledger", {12}),
    # The only writer into the precedent store.
    ("precedent_writeback", "precedent_store", {9}),
    # The lock is how one deal gets one run.
    ("intake_window", "engagement_lock", {10}),
    # The resolver narrows the library, and the index is what the orchestrator reads.
    # Two invariants approach that from different ends.
    ("scope_resolver", "skill_index", {15, 22}),
    # Precedents reach a model only through the node that knows the scope.
    ("precedent_store", "context_builder", {16}),
    # Authorisation before execution, or it is not authorisation.
    ("policy_gate", "guarded_runtime", {17}),
    # The assembled context is what makes a call reconstructable - and cutting it also
    # cuts that skill's route to the LLM Port, which invariant 2 is right to notice.
    ("context_builder", "sk_ebitda", {2, 18}),
    # A verdict computed from the event stream, not an opinion after the fact.
    ("run_store", "run_scorecard", {19}),
    # The governance chain. Severing it also strands the sandbox's route to the port.
    ("skill_board", "shadow_run", {2, 21, 22}),
    # The roster is what makes an inactive engagement unreachable rather than filtered.
    ("project_roster", "sweep_planner", {24}),
    # One configuration source means one resolved destination.
    ("config_store", "delivery_port", {25}),
    # Figures enter a deliverable locked, or they do not enter.
    ("numeric_lock", "model_builder", {4}),
    # A loop edge whose source nothing reaches has no controller bounding it.
    ("tieout_gate", "reconcile", {11}),
    # The compiler is where a run's versions are fixed before anything executes.
    ("graph_compiler", "step_executor", {13}),
    # A failure surface with no diagnostics behind it produces a message nobody can act on.
    ("diagnostics", "quarantine", {20}),
)

ADDITIONS: tuple[tuple[str, str, str, str, set[int]], ...] = (
    # A dial on a guarantee. The whole point of invariant 23.
    ("config_store", "tieout_gate", "pref", "tolerance", {14, 23}),
    # A config edge into a guard that does not say it may only raise.
    ("checkpoint_policy", "schema_gate", "pref", "strictness", {14}),
    # A second way into the release gate.
    ("workpaper", "release_gate", "flow", "narrative", {6}),
    # Content reaching delivery from somewhere that is not the ledger or the manifest.
    ("model_builder", "delivery_port", "flow", "straight out", {6}),
    # Governance reading client content.
    ("run_store", "skill_board", "flow", "run data", {7}),
    # A second writer into the precedent store - the system learning from itself.
    ("sk_ebitda", "precedent_store", "flow", "learned", {9}),
    # The orchestrator reading the whole library instead of the resolved index.
    ("skill_tree", "orchestrator", "data", "everything", {15}),
    # A skill calling a tool around the gate.
    ("sk_ebitda", "t_recompute", "flow", "direct call", {17}),
    # Generation feeding content back into the figure path after the numbers are locked.
    ("workpaper", "tieout_gate", "flow", "narrative back", {5}),
)

NODE_CHANGES: tuple[tuple[str, str, object, set[int]], ...] = (
    # A privacy node that can guess. Two invariants are about exactly this.
    ("unmask_engine", "exec", "llm", {1, 3}),
    # A model node beside the vault - and one the port does not serve.
    ("mask_engine", "exec", "llm", {1, 2, 3}),
    # A new model node with no route to the port and no written exemption.
    ("file_fingerprint", "exec", "llm", {2}),
    # A guard that cannot reach the event bus, so its passes are silent.
    ("box_mcp", "group", "guard", {8}),
)


def failing(graph: ArchGraph) -> set[int]:
    return {inv.number for inv, _ in check_all(graph)}


# ------------------------------------------------------------ the controls


def test_the_intact_graph_fails_nothing(graph: ArchGraph) -> None:
    """Every case below has to fail *because of the change*. If the graph failed
    something already, none of them would prove anything."""
    assert failing(graph) == set()


# ------------------------------------------------------------ the cases


@pytest.mark.parametrize(("src", "dst", "expected"), DELETIONS)
def test_deleting_one_edge_fails_exactly_the_right_invariants(
    without_edge, src: str, dst: str, expected: set[int]
) -> None:
    assert failing(without_edge(src, dst)) == expected, (
        f"deleting {src} -> {dst} should fail exactly {sorted(expected)}"
    )


@pytest.mark.parametrize(("src", "dst", "kind", "label", "expected"), ADDITIONS)
def test_adding_one_bad_edge_fails_exactly_the_right_invariants(
    with_edge, src: str, dst: str, kind: str, label: str, expected: set[int]
) -> None:
    """Some invariants are broken by an arrow that should not exist rather than a missing
    one. A config edge into a guard is a new edge; so is a skill reaching a tool."""
    assert failing(with_edge(src, dst, kind, label)) == expected, (
        f"adding {src} -> {dst} ({kind}) should fail exactly {sorted(expected)}"
    )


@pytest.mark.parametrize(("node_id", "field", "value", "expected"), NODE_CHANGES)
def test_changing_a_node_fails_exactly_the_right_invariants(
    with_node_change, node_id: str, field: str, value: object, expected: set[int]
) -> None:
    assert failing(with_node_change(node_id, field, value)) == expected


def test_a_config_edge_into_a_guard_is_allowed_when_it_says_it_may_only_raise(
    with_edge,
) -> None:
    """The other half of invariant 14, and why the check reads the label. The one config
    path that legitimately reaches a guard is checkpoint_policy, whose rule is stated on
    the edge - so an edge carrying the same promise is not a violation."""
    allowed = with_edge(
        "checkpoint_policy", "schema_gate", "pref", "strictness - may only raise"
    )
    assert failing(allowed) == set()


# -------------------------------------------------------- guards over nothing


def test_an_assertion_over_no_intake_sources_refuses(with_node_change) -> None:
    """Invariant 24 covers the nodes marked `is_intake`. With none marked it would pass
    forever over an empty set, so it fails instead. A guard over nothing is worse than no
    guard, because it reads as enforcement.

    Three assertions in this suite were found passing this way while the deletion cases
    above were being written, which is the reason this test exists.
    """
    stripped = with_node_change("sharefile", "is_intake", None)
    for node_id in ("local_intake", "email_watcher"):
        stripped.nodes[node_id].pop("is_intake", None)
    stripped.nodes["sharefile"].pop("is_intake", None)
    assert 24 in failing(stripped)


def test_severing_the_governance_chain_is_not_mistaken_for_gating_it(without_edge) -> None:
    """Remove the last link and nothing reaches the tree - which an assertion phrased as
    "cannot reach without passing X" reads as success. Both governance invariants check
    the path exists before checking what guards it."""
    severed = without_edge("skill_registry", "skill_tree")
    assert {21, 22} <= failing(severed)


# ------------------------------------------------------------- independence


def test_no_single_change_fails_more_than_three_invariants() -> None:
    """A suite where one deletion fails half the invariants is one assertion wearing
    twenty-five hats. Three is the most any case here produces, and each of those is two
    or three invariants genuinely sharing a piece of the design."""
    for _, _, expected in DELETIONS:
        assert len(expected) <= 3
    for *_, expected in ADDITIONS:
        assert len(expected) <= 3
    for *_, expected in NODE_CHANGES:
        assert len(expected) <= 3


def test_every_invariant_can_be_broken() -> None:
    """The strongest statement this file makes.

    Each of the 25 is broken by at least one case above, so none of them is a function
    that passes because it checks nothing. Read off the tables rather than restated, so
    adding an invariant without a case that breaks it fails here.
    """
    covered: set[int] = set()
    for _, _, expected in DELETIONS:
        covered |= expected
    for *_, expected in ADDITIONS:
        covered |= expected
    for *_, expected in NODE_CHANGES:
        covered |= expected

    uncovered = sorted(set(range(1, 26)) - covered)
    assert not uncovered, (
        f"invariants {uncovered} have no case in this module that breaks them, so "
        f"nothing here proves they check anything"
    )
