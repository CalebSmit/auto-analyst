"""Fixtures for P07.

`broken` is the important one. It hands back a copy of the architecture graph with one
edge removed or one node field changed, so a test can ask the question that actually
matters about an assertion suite: does each assertion catch its own violation, and only
its own? A suite where every assertion fails whenever anything breaks is not 25 checks,
it is one check with 25 names.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from graph.architecture_assertions import ArchGraph, Edge, load_graph
from graph.compile import PlanContext, compile_recipe
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver

ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT = ROOT / "docs" / "architecture.html"
GRAPH_FILE = ROOT / "graph" / "architecture.json"


@pytest.fixture(scope="session")
def graph() -> ArchGraph:
    return load_graph()


@pytest.fixture
def without_edge(graph: ArchGraph) -> Callable[[str, str], ArchGraph]:
    """The graph with one edge deleted, by endpoints."""

    def build(src: str, dst: str) -> ArchGraph:
        remaining = tuple(e for e in graph.edges if not (e.src == src and e.dst == dst))
        if len(remaining) == len(graph.edges):
            raise AssertionError(f"there is no {src} -> {dst} edge to delete")
        return ArchGraph(nodes=copy.deepcopy(graph.nodes), edges=remaining)

    return build


@pytest.fixture
def with_edge(graph: ArchGraph) -> Callable[..., ArchGraph]:
    """The graph with one edge added. Some invariants are broken by adding, not removing:
    a config edge into a guard is a new arrow, never a missing one."""

    def build(src: str, dst: str, kind: str = "flow", label: str = "") -> ArchGraph:
        return ArchGraph(
            nodes=copy.deepcopy(graph.nodes),
            edges=(*graph.edges, Edge(src=src, dst=dst, kind=kind, label=label)),
        )

    return build


@pytest.fixture
def with_node_change(graph: ArchGraph) -> Callable[[str, str, Any], ArchGraph]:
    """The graph with one node field changed - turning a code node into a model node,
    say, which is how several of these invariants are actually violated in practice."""

    def build(node_id: str, field: str, value: Any) -> ArchGraph:
        nodes = copy.deepcopy(graph.nodes)
        nodes[node_id][field] = value
        return ArchGraph(nodes=nodes, edges=graph.edges)

    return build


@pytest.fixture(scope="session")
def plan() -> Any:
    """A real compiled plan. The plan assertions have already run on it - they are wired
    into the compiler - so its existence is itself part of the evidence."""
    scope = ScopeResolver().resolve("valuation/esop/repeat")
    context = PlanContext(
        engagement_id="HEND-2026-04",
        scope=scope,
        taxonomy_version="coa-taxonomy@1.0.0",
        precedent_snapshot="precedent_snapshot_2026_09_01",
    )
    return compile_recipe(load_recipe("monthly-refresh"), context)
