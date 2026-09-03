"""The Checkpoint Policy: it can raise the bar, never lower the floor."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.errors import ContractViolation
from registries.scopes import ScopeRegistry
from review import CheckpointPolicy, Money, PolicyRefused
from tests.p15.conftest import DECLARED, EBITDA, ENGAGEMENT, OWNER, ROOT, TAGGING, profile


def test_a_policy_lowering_a_skills_review_floor_is_rejected(
    constraints: ConstraintRegistry, scopes: ScopeRegistry
) -> None:
    """The exit criterion. ebitda-normalization declares material add-backs go to a
    person (rank 20); a policy asking for rank 10 would review less than the skill
    requires, and is refused with the same code an overlay would be."""
    policy = CheckpointPolicy.from_profile(
        profile(
            checkpoint_policy={
                "owner": OWNER,
                "sla_hours": 48,
                "review_floors": {EBITDA: "confidence_below_threshold_requires_review"},
            }
        ),
        constraints,
    )
    with pytest.raises(PolicyRefused) as refused:
        policy.check_against_floors(constraints, DECLARED, scopes)
    d = refused.value.diagnostic
    assert d.code == "POLICY.OVERLAY_LOOSENS"
    assert d.skill == EBITDA and "never lower" in d.detail
    assert d.expected == "rank >= 20" and d.found == "rank 10"


def test_a_policy_raising_a_floor_is_accepted_and_wins(
    constraints: ConstraintRegistry, scopes: ScopeRegistry
) -> None:
    policy = CheckpointPolicy.from_profile(
        profile(
            checkpoint_policy={
                "owner": OWNER,
                "sla_hours": 48,
                "review_floors": {TAGGING: "material_addbacks_require_review"},
            }
        ),
        constraints,
    )
    policy.check_against_floors(constraints, DECLARED, scopes)
    assert (
        policy.effective_review(TAGGING, DECLARED[TAGGING], scopes)
        == "material_addbacks_require_review"
    )
    assert policy.effective_review(EBITDA, DECLARED[EBITDA], scopes) == DECLARED[EBITDA]


def test_a_floor_naming_an_unranked_level_is_refused(
    constraints: ConstraintRegistry, scopes: ScopeRegistry
) -> None:
    """A level nobody placed on the ladder cannot be compared, so it cannot be a floor."""
    policy = CheckpointPolicy.from_profile(
        profile(
            checkpoint_policy={
                "owner": OWNER,
                "sla_hours": 48,
                "review_floors": {TAGGING: "sometimes_review"},
            }
        ),
        constraints,
    )
    with pytest.raises(Exception, match="review ladder"):
        policy.check_against_floors(constraints, DECLARED, scopes)


def test_materiality_above_the_firm_floor_is_refused(constraints: ConstraintRegistry) -> None:
    amount, currency = constraints.materiality_floor()
    with pytest.raises(PolicyRefused) as refused:
        CheckpointPolicy.from_profile(
            profile(materiality_threshold={"amount": amount + 1, "currency": currency}),
            constraints,
        )
    assert refused.value.diagnostic.code == "POLICY.OVERLAY_LOOSENS"
    assert "reviews less" in refused.value.diagnostic.detail


def test_materiality_at_or_below_the_floor_is_accepted(constraints: ConstraintRegistry) -> None:
    amount, currency = constraints.materiality_floor()
    at = CheckpointPolicy.from_profile(
        profile(materiality_threshold={"amount": amount, "currency": currency}), constraints
    )
    below = CheckpointPolicy.from_profile(
        profile(materiality_threshold={"amount": 5000, "currency": currency}), constraints
    )
    assert at.materiality == Money(amount, currency)
    assert below.materiality.amount == 5000


def test_no_threshold_means_the_firm_floor_not_a_looser_default(
    constraints: ConstraintRegistry,
) -> None:
    body = profile()
    del body["materiality_threshold"]
    policy = CheckpointPolicy.from_profile(body, constraints)
    assert policy.materiality == Money(*constraints.materiality_floor())


def test_a_threshold_in_another_currency_is_refused(constraints: ConstraintRegistry) -> None:
    with pytest.raises(PolicyRefused, match="cannot be compared"):
        CheckpointPolicy.from_profile(
            profile(materiality_threshold={"amount": 1, "currency": "GBP"}), constraints
        )


def test_there_is_no_auto_accept_default(constraints: ConstraintRegistry) -> None:
    """The blueprint's open question, as code: the bar has no default the firm can
    safely inherit from us. Absent means nothing is auto-accepted."""
    policy = CheckpointPolicy.from_profile(
        profile(checkpoint_policy={"owner": OWNER, "sla_hours": 48}), constraints
    )
    assert policy.auto_accept_confidence is None


def test_an_owner_and_a_positive_sla_are_required(constraints: ConstraintRegistry) -> None:
    with pytest.raises(ValueError, match="owner"):
        CheckpointPolicy.from_profile(
            profile(checkpoint_policy={"owner": " ", "sla_hours": 48}), constraints
        )
    with pytest.raises(ValueError, match="SLA"):
        CheckpointPolicy.from_profile(
            profile(checkpoint_policy={"owner": OWNER, "sla_hours": 0}), constraints
        )
    with pytest.raises(ValueError, match="confidence"):
        CheckpointPolicy(ENGAGEMENT, OWNER, 48, Money(1, "USD"), auto_accept_confidence=1.5)


def test_material_means_at_or_above_and_foreign_currency_is_never_immaterial(
    policy: CheckpointPolicy,
) -> None:
    assert policy.is_material(Money(20000, "USD"))
    assert not policy.is_material(Money(19999.99, "USD"))
    assert policy.is_material(Money(1, "EUR")), (
        "a figure that cannot be compared is not quietly small"
    )
    assert not policy.is_material(None)


# ------------------------------------------------------------- the contract


def test_the_engagement_profile_contract_carries_the_policy(contracts: ContractRegistry) -> None:
    assert contracts.check("engagement_profile@1.0.0", profile()) == ()
    bad = profile(checkpoint_policy={"owner": OWNER, "sla_hours": 48, "disable_guards": True})
    with pytest.raises(ContractViolation):
        contracts.validate("engagement_profile@1.0.0", bad)


def test_the_policy_reaches_exactly_one_node() -> None:
    """Drawn with a single downstream reader on purpose. No guard, no harness stage and
    no graph module imports the policy; the router does."""
    readers: set[str] = set()
    for folder in ("guards", "harness", "graph", "privacy", "ops", "tools", "review"):
        for path in (ROOT / folder).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "review.policy":
                    readers.add(path.relative_to(ROOT).as_posix())
    assert "guards" not in {r.split("/")[0] for r in readers}
    assert not any(
        r.startswith(("harness/", "graph/", "privacy/", "ops/", "tools/")) for r in readers
    )
    assert "review/router.py" in readers
    assert readers - {"review/router.py", "review/queue.py", "review/__init__.py"} == set()


def test_the_policy_has_no_way_to_touch_a_guard() -> None:
    """No import of guards/, and no name on the policy that could reach a tolerance, a
    schema or a fail-closed check. The prose may mention guards; the code cannot."""
    tree = ast.parse((Path(ROOT) / "review" / "policy.py").read_text(encoding="utf-8"))
    imported = {
        (n.module or "") if isinstance(n, ast.ImportFrom) else n.names[0].name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
    }
    assert not any(m == "guards" or m.startswith("guards.") for m in imported)
    assert not any(m.startswith("tools") or m.startswith("harness") for m in imported)
    for forbidden in ("tolerance", "schema", "disable", "fail_closed", "skip"):
        assert not any(forbidden in name for name in dir(CheckpointPolicy)), forbidden
