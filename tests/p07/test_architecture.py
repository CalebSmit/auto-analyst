"""All 25 invariants are executable and pass against the current architecture.

The first exit criterion, and the least interesting test in the phase: it is the one that
would pass if every assertion were `pass`. The tests that make it mean something are in
`test_edge_deletion.py`, where each assertion has to catch its own violation and nothing
else's.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph.architecture_assertions import (
    ALL,
    OUTSIDE_THE_RUN_GRAPH,
    ArchGraph,
    check_all,
)
from tools.export_architecture import ARRAYS, build, rendered, source_block

ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT = ROOT / "docs" / "architecture.html"
GRAPH_FILE = ROOT / "graph" / "architecture.json"


def test_all_twenty_five_invariants_pass(graph: ArchGraph) -> None:
    failures = check_all(graph)
    assert not failures, "\n".join(
        f"{inv.number}. {inv.name}: {err}" for inv, err in failures
    )


def test_there_are_exactly_twenty_five(graph: ArchGraph) -> None:
    """The blueprint declares 25 and the suite implements 25. A suite that had drifted to
    24 would still pass the test above."""
    assert len(ALL) == 25
    assert len(graph.invariant_texts) == 25


def test_every_invariant_is_numbered_in_order() -> None:
    assert [inv.number for inv in ALL] == list(range(1, 26))


def test_every_assertion_names_its_invariant_number() -> None:
    """The docstring starts with the number, so a failure report can be read against the
    blueprint's own list without a lookup table."""
    for inv in ALL:
        first = (inv.check.__doc__ or "").strip()
        assert first.startswith(f"{inv.number}. "), f"{inv.name} does not open with its number"


def test_every_assertion_explains_itself() -> None:
    """Each one says what it checks and why, because the person reading a failure is
    deciding whether the design changed or the assertion is wrong."""
    for inv in ALL:
        assert len(inv.check.__doc__ or "") > 200, f"{inv.name} is under-documented"


def test_the_graph_is_the_size_the_project_claims(graph: ArchGraph) -> None:
    """118 nodes, 240 edges, 25 invariants - the numbers in CLAUDE.md and in the
    blueprint's own header."""
    raw = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
    assert raw["counts"] == {"nodes": 118, "edges": 240, "invariants": 25}
    assert len(graph) == 118


# ------------------------------------------------------------------- drift


def test_the_exported_graph_is_current() -> None:
    """The exported JSON matches the blueprint it came from.

    Editing docs/architecture.html without re-exporting would leave the assertions
    running against a design nobody has any more, and passing. This is the check that
    makes the export a mirror rather than a snapshot.
    """
    current = GRAPH_FILE.read_text(encoding="utf-8")
    assert current == rendered(build()), (
        "graph/architecture.json is out of date with docs/architecture.html.\n"
        "Run: python tools/export_architecture.py"
    )


def test_the_digest_covers_the_source_blocks(graph: ArchGraph) -> None:
    """The recorded digest is of the exact JS the export was taken from."""
    import hashlib

    html = BLUEPRINT.read_text(encoding="utf-8")
    digest = hashlib.sha256()
    for name in ARRAYS:
        digest.update(source_block(html, name).encode("utf-8"))
    assert graph.source_digest == f"sha256:{digest.hexdigest()}"


def test_the_reader_round_trips_every_node(graph: ArchGraph) -> None:
    """Every node came out with the fields the blueprint gives it. A parser that silently
    dropped a field on one node would leave an assertion quietly checking nothing."""
    for node_id, node in graph.nodes.items():
        assert node["id"] == node_id
        for required in ("label", "plain", "group", "exec", "runtime", "desc", "impl", "full"):
            assert node.get(required), f"{node_id} has no {required}"


# -------------------------------------------------------- the exception list


def test_every_exemption_from_the_one_door_rule_gives_a_reason(graph: ArchGraph) -> None:
    """A model node the LLM Port does not serve has to be listed with a written reason.
    The assertion itself checks the list is exactly right; this checks the reasons are
    real sentences rather than a word somebody typed to make a test pass."""
    for node_id, reason in OUTSIDE_THE_RUN_GRAPH.items():
        assert node_id in graph, f"{node_id} is exempted and does not exist"
        assert node_id in graph.llm_nodes, f"{node_id} is exempted and runs no model"
        assert len(reason) > 40, f"{node_id}'s exemption is not explained"


def test_the_exemption_list_is_as_short_as_it_looks(graph: ArchGraph) -> None:
    """Seven of nineteen model nodes would be a bad sign. Four is the intake path plus
    the analyst chat, and if that grows somebody should have to argue for it."""
    assert len(OUTSIDE_THE_RUN_GRAPH) <= 5


# ----------------------------------------------------- the graph model itself


def test_dominance_is_computed_over_content_edges_by_default(graph: ArchGraph) -> None:
    """The default matters more than it looks. Over all ten edge kinds the graph is so
    connected that almost nothing dominates anything, and every assertion built on it
    would be false for reasons unrelated to the design."""
    assert graph.dominated_by("sharefile", "sweep_planner")
    assert not graph.dominated_by("sharefile", "sweep_planner", kinds=None)


def test_a_route_is_offered_when_dominance_fails(graph: ArchGraph) -> None:
    """A failure message that says "it is reachable" sends somebody to the graph. One
    that names the route sends them to the edge."""
    route = graph.route_avoiding("file_fingerprint", "engagement_lock")
    assert route
    assert "engagement_lock" not in route
    assert route[-1] == "file_fingerprint"


def test_skills_and_tools_are_told_apart(graph: ArchGraph) -> None:
    """`skill_contract` is in the skill group and is a schema; the registries are in the
    tool group and are resources. Both distinctions carry an assertion."""
    assert "skill_contract" not in graph.skill_nodes
    assert len(graph.skill_nodes) == 9
    assert set(graph.tool_nodes) == {"t_timing", "t_recompute", "t_template"}


def test_hybrid_nodes_count_as_model_nodes(graph: ArchGraph) -> None:
    """A node that is code most of the time and a model call sometimes is a model node
    for every invariant here: the guarantee has to hold on the branch where it runs."""
    assert "email_watcher" in graph.llm_nodes
    assert graph["email_watcher"]["exec"] == "hybrid"


@pytest.mark.parametrize("node_id", ["mask_vault", "unmask_engine", "release_gate"])
def test_the_graph_knows_the_nodes_the_invariants_name(graph: ArchGraph, node_id: str) -> None:
    assert node_id in graph


def test_every_node_an_invariant_names_exists(graph: ArchGraph) -> None:
    """The blueprint's invariants each list the nodes they concern. One naming a node
    that does not exist would be an invariant about nothing."""
    raw = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
    for n, invariant in enumerate(raw["invariants"], 1):
        for node_id in invariant["nodes"]:
            assert node_id in graph, f"invariant {n} names {node_id}, which is not a node"
