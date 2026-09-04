"""constraints.yaml - the predicates the Policy Gate evaluates.

Contracts say what shapes are legal; constraints say what actions are legal. This suite
checks the second registry loads, pins, refuses, and agrees with the blueprint about who
may call what. It does not check evaluation - the Policy Gate arrives in P10, and
splitting the decision from its data is exactly what lets that be tested on its own.
"""

from __future__ import annotations

import pytest

from registries.constraints import ConstraintRegistry
from registries.errors import UNKNOWN_CONSTRAINTS, RegistryError

TOOL_NAMESPACE = {
    "recompute",
    "timing_normalizer",
    "chart_of_accounts_lookup",
    "precedent_lookup",
    "index_lookup",
    "template_schema_lookup",
}
COMPUTE_TOOLS = {"recompute", "timing_normalizer"}


def test_the_registry_loads_and_pins(constraints: ConstraintRegistry) -> None:
    assert constraints.version == "1.0.0"
    constraints.require_version("1.0.0")


def test_a_run_pinned_to_another_version_is_refused(constraints: ConstraintRegistry) -> None:
    """The plan hash was computed over these predicates. A different version is not a
    detail to shrug at."""
    with pytest.raises(RegistryError) as raised:
        constraints.require_version("0.9.0")
    assert raised.value.diagnostic.code == UNKNOWN_CONSTRAINTS


def test_the_tool_namespace_is_six_names(constraints: ConstraintRegistry) -> None:
    """Finding F3: six declared names, and only two of them are compute tools. Building
    the runtime for compute tools alone would have left the other four unpoliced."""
    assert set(constraints.tools) == TOOL_NAMESPACE
    assert {name for name, spec in constraints.tools.items() if spec.computes} == COMPUTE_TOOLS


def test_every_gated_read_is_marked_read_only(constraints: ConstraintRegistry) -> None:
    for name, spec in constraints.tools.items():
        assert spec.read_only is (name not in COMPUTE_TOOLS), name


def test_every_tool_has_a_call_time_cap(constraints: ConstraintRegistry) -> None:
    """The Guarded Tool Runtime applies these. An approved action with no ceiling is an
    approved action that can still run away."""
    for name, spec in constraints.tools.items():
        assert spec.caps, f"{name} has no caps"
        assert "max_rows" in spec.caps, f"{name} has no row cap"


def test_the_allowlists_match_the_blueprints_skill_frontmatter(
    constraints: ConstraintRegistry, blueprint_skills: dict[str, dict[str, tuple[str, ...]]]
) -> None:
    """The frontmatter is what a skill declares; this file is what the Policy Gate
    enforces. If they disagree, one of them is wrong and the run finds out at the worst
    possible moment."""
    for skill, fields in blueprint_skills.items():
        declared = set(fields.get("tools", ()))
        enforced = set(constraints.tools_for(skill))
        assert enforced == declared, f"{skill}: constraints {enforced}, blueprint {declared}"


def test_an_undeclared_tool_call_is_not_permitted(constraints: ConstraintRegistry) -> None:
    assert constraints.may_call("ebitda-normalization", "recompute")
    assert not constraints.may_call("ebitda-normalization", "index_lookup")
    assert not constraints.may_call("ddr-tagging", "recompute")


def test_a_skill_with_no_allowlist_is_refused_rather_than_defaulted(
    constraints: ConstraintRegistry,
) -> None:
    """An empty allowlist and an absent one are different facts. Defaulting the second
    to the first is how a skill nobody registered ends up permitted to call nothing
    quietly instead of failing loudly."""
    with pytest.raises(RegistryError):
        constraints.tools_for("skill-that-does-not-exist")


def test_every_predicate_names_the_diagnostic_it_raises(constraints: ConstraintRegistry) -> None:
    for predicate in constraints.predicates:
        assert predicate.diagnostic.startswith("POLICY."), predicate.id
        assert predicate.rule


def test_the_engagement_scope_predicate_exists_and_applies_to_everything(
    constraints: ConstraintRegistry,
) -> None:
    """Reading another engagement's folder returns perfectly valid data, which is why
    only a pre-execution check catches it."""
    scoped = [p for p in constraints.predicates if p.id == "engagement_scoped"]
    assert len(scoped) == 1
    assert scoped[0].applies_to == ("all",)
    assert scoped[0].why


def test_every_in_run_loop_has_an_integer_maximum(constraints: ConstraintRegistry) -> None:
    """The compiler rejects any cycle that is not a declared, bounded loop. No agent
    decides for itself whether to try again."""
    loops = constraints.in_run_loops()
    assert len(loops) == 4
    for loop in loops:
        assert isinstance(loop.max_iterations, int)
        assert 1 <= loop.max_iterations <= 3


def test_the_run_ceiling_is_above_every_local_maximum(constraints: ConstraintRegistry) -> None:
    """Several loops must not be able to conspire to run long, and the global ceiling
    must not be so tight that one legal loop trips it."""
    local_total = sum(loop.max_iterations or 0 for loop in constraints.in_run_loops())
    assert local_total <= constraints.loop_ceiling()


def test_a_retry_ceiling_exists_for_transport_only(constraints: ConstraintRegistry) -> None:
    """A guard failure is not a transport failure and must not be retried like one."""
    assert constraints.ceilings["per_step"]["transport_retries_max"] <= 3
    assert "transport failures only" in constraints.ceilings["note"]


def test_an_unchanged_retry_is_refused(constraints: ConstraintRegistry) -> None:
    """A retry with byte-identical input is not a retry - it is the same call again at
    the same price, and it is the single most common way these systems waste money."""
    rules = " ".join(constraints.rules).lower()
    assert "byte-identical" in rules
    assert "refused" in rules
    assert "never the guard, the tolerance or the schema" in rules


def test_the_firm_materiality_floor_is_declared(constraints: ConstraintRegistry) -> None:
    amount, currency = constraints.materiality_floor()
    assert amount > 0
    assert currency == "USD"


def test_some_things_force_review_whatever_the_confidence_says(
    constraints: ConstraintRegistry,
) -> None:
    """Confidence is a model's self-report. It routes review; it never overrides it."""
    forced = constraints.materiality["forces_review_regardless_of_confidence"]
    assert len(forced) >= 4
    assert any("company-specific" in item for item in forced)


def test_guards_are_not_configurable(constraints: ConstraintRegistry) -> None:
    """An admin may raise a review requirement, never lower one, and never disable a
    guard that fails closed. A guarantee with a dial on it is not a guarantee."""
    rules = constraints.immutability
    never = " ".join(rules["admin_may_never"]).lower()
    assert "disable a guard" in never
    assert "lower a review requirement" in never
    assert set(rules["fail_closed_nodes"]) >= {
        "policy_gate",
        "schema_gate",
        "provenance_gate",
        "tieout_gate",
        "numeric_lock",
    }


def test_an_inconsistent_constraints_file_fails_to_load(tmp_path: object) -> None:
    """The self-check is not decoration: a skill declaring a tool the namespace does not
    contain must fail at load, not at the moment a run tries to call it."""
    raw = {
        "version": "1.0.0",
        "tools": {
            "recompute": {
                "kind": "computes",
                "node": "t_recompute",
                "read_only": False,
                "caps": {"max_rows": 10},
            }
        },
        "tool_allowlists": {"ebitda-normalization": ["recompute", "invented_tool"]},
        "predicates": [
            {
                "id": "x",
                "applies_to": ["all"],
                "rule": "true",
                "diagnostic": "POLICY.ARG_OUT_OF_SCOPE",
            }
        ],
        "loops": {"guard_repair": {"scope": "in_run", "max_iterations": 2}},
        "ceilings": {"per_run": {"loop_iterations_max": 8}},
        "materiality": {"firm_floor": {"amount": 1, "currency": "USD"}},
        "immutability": {},
    }
    with pytest.raises(RegistryError):
        ConstraintRegistry(raw)._self_check()


# ------------------------------------------------------ blueprint agreement
#
# The blueprint is the design of record and it has to keep saying what is actually
# built. These are the checks that make a divergence a failing test rather than
# something somebody notices in month four.


def test_the_tool_namespace_matches_the_blueprints_table(
    constraints: ConstraintRegistry, blueprint_tool_namespace: dict[str, dict[str, object]]
) -> None:
    assert set(blueprint_tool_namespace) == set(constraints.tools)
    for name, row in blueprint_tool_namespace.items():
        spec = constraints.tools[name]
        assert spec.node == row["node"], f"{name}: node disagrees"
        assert spec.kind == row["kind"], f"{name}: kind disagrees"


def test_the_blueprints_usage_counts_are_not_stale(
    constraints: ConstraintRegistry, blueprint_tool_namespace: dict[str, dict[str, object]]
) -> None:
    """The blueprint's tool table states how many skills use each tool. It said five for
    recompute while its own skill frontmatter said six - the same class of drift as the
    stale node counts the pre-build review caught. Counted here so it cannot recur."""
    for name, row in blueprint_tool_namespace.items():
        actual = len(constraints.skills_using(name))
        assert row["used_by"] == actual, (
            f"blueprint says {name} is used by {row['used_by']} skills, allowlists say {actual}"
        )


def test_every_directory_the_build_created_is_on_the_blueprints_repo_listing(
    blueprint_repo_listing: str,
) -> None:
    """A package that exists and is not in the listing is a divergence. registries/ is
    here because the listing placed the contract and constraint data but named no home
    for the code that loads it."""
    for directory in (
        "contracts/",
        "constraints/",
        "scope/",
        "registries/",
        "skills/",
        "harness/",
        "graph/",
        "privacy/",
        "tools/",
        "guards/",
        "ports/",
        "ops/",
        "fixtures/",
        "precedent/",
        "taxonomy/",
        "deliver/",
        "templates/",
        "evals/",
        "admin/",
        "workers/",
        "orchestrate/",
        "governance/",
    ):
        assert directory in blueprint_repo_listing, f"{directory} is not on the repo listing"
