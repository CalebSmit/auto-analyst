"""The Checkpoint Policy: how much a human reviews. It can raise the bar - never lower it.

A per-engagement setting, read by exactly one node downstream (the Confidence Router).
No guard subscribes to it: fails-closed guards are outside its reach by construction,
not by policy.

Three things it may set, and the direction each may move:

* **The auto-accept confidence bar.** There is no firm default - the blueprint records
  that the bar "has no default the firm can safely inherit from us". A policy that sets
  none auto-accepts nothing: every item a skill was unsure about goes to a person.
* **The materiality threshold.** At or below the firm floor in `constraints.yaml`.
  A lower threshold reviews more; a higher one would be an engagement quietly reviewing
  less than the firm requires, and is refused.
* **A review floor per skill.** At or above the level the skill declares (after its
  scope overlays). The review ladder in `scopes.yaml` says which values are tighter;
  a policy naming a lower rung is refused with the same code an overlay would be.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from registries.constraints import ConstraintRegistry
from registries.errors import OVERLAY_LOOSENS, DiagnosticError, diagnose
from registries.scopes import ScopeRegistry

__all__ = ["CheckpointPolicy", "Money", "PolicyRefused"]


class PolicyRefused(DiagnosticError):
    """A policy tried to review less than the floor requires."""


@dataclass(frozen=True)
class Money:
    amount: float
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("a threshold cannot be negative")
        if len(self.currency) != 3 or not self.currency.isupper():
            raise ValueError(f"{self.currency!r} is not an ISO currency code")


@dataclass(frozen=True)
class CheckpointPolicy:
    """What the engagement asks a person to look at, over and above the floors."""

    engagement_id: str
    owner: str
    """The named person the queue escalates to. Required: an item with no owner is an
    item nobody works, which the blueprint ranks as its second-highest risk."""
    sla_hours: float
    materiality: Money
    auto_accept_confidence: float | None = None
    """Items at or above this confidence, and material to nobody, go straight through.
    None means nothing is auto-accepted."""
    always_review_categories: frozenset[str] = frozenset()
    review_floors: dict[str, str] = field(default_factory=dict)
    """skill name -> hitl value on the review ladder. Each must be at or above the level
    the skill itself declares."""

    def __post_init__(self) -> None:
        if not self.owner.strip():
            raise ValueError("a checkpoint policy names an owner")
        if self.sla_hours <= 0:
            raise ValueError("the review SLA is a positive number of hours")
        if self.auto_accept_confidence is not None and not 0 < self.auto_accept_confidence <= 1:
            raise ValueError("the auto-accept bar is a confidence in (0, 1]")

    # -- construction

    @classmethod
    def from_profile(
        cls,
        profile: dict[str, Any],
        constraints: ConstraintRegistry,
    ) -> CheckpointPolicy:
        """From an engagement profile (`engagement_profile@1.0.0`). The profile's
        `materiality_threshold` and `checkpoint_policy` blocks are optional; what is
        absent falls to the floor, never to a looser default."""
        floor = _firm_floor(constraints)
        raw = dict(profile.get("checkpoint_policy") or {})
        threshold = profile.get("materiality_threshold")
        materiality = (
            Money(float(threshold["amount"]), str(threshold["currency"])) if threshold else floor
        )
        policy = cls(
            engagement_id=str(profile["engagement_id"]),
            owner=str(raw.get("owner", "")),
            sla_hours=float(raw.get("sla_hours", 0)),
            materiality=materiality,
            auto_accept_confidence=raw.get("auto_accept_confidence"),
            always_review_categories=frozenset(raw.get("always_review_categories") or ()),
            review_floors=dict(raw.get("review_floors") or {}),
        )
        policy.check_against_floors(constraints)
        return policy

    # -- the one direction

    def check_against_floors(
        self,
        constraints: ConstraintRegistry,
        declared: dict[str, str] | None = None,
        scopes: ScopeRegistry | None = None,
    ) -> None:
        """Refuse anything looser than a floor. `declared` is skill -> the hitl value the
        skill carries after its scope overlays; every review floor in the policy must sit
        at or above it on the ladder."""
        floor = _firm_floor(constraints)
        if self.materiality.currency != floor.currency:
            raise PolicyRefused(
                diagnose(
                    OVERLAY_LOOSENS,
                    f"the materiality threshold is in {self.materiality.currency}; the firm "
                    f"floor is in {floor.currency}, and the two cannot be compared",
                    locator=f"checkpoint_policy/{self.engagement_id}",
                )
            )
        if self.materiality.amount > floor.amount:
            raise PolicyRefused(
                diagnose(
                    OVERLAY_LOOSENS,
                    f"materiality {self.materiality.amount:,.0f} {self.materiality.currency} is "
                    f"above the firm floor of {floor.amount:,.0f} {floor.currency}. A higher "
                    f"threshold reviews less; an engagement may only lower it.",
                    locator=f"checkpoint_policy/{self.engagement_id}",
                    expected=f"<= {floor.amount:,.0f}",
                    found=f"{self.materiality.amount:,.0f}",
                )
            )
        if declared:
            ladder = scopes or ScopeRegistry.load()
            for skill, level in self.review_floors.items():
                if skill not in declared:
                    continue
                have, want = ladder.review_rank(declared[skill]), ladder.review_rank(level)
                if want < have:
                    raise PolicyRefused(
                        diagnose(
                            OVERLAY_LOOSENS,
                            f"the policy sets {skill} to {level!r} (rank {want}); the skill "
                            f"declares {declared[skill]!r} (rank {have}). A policy may raise "
                            f"a review floor, never lower one.",
                            locator=f"checkpoint_policy/{self.engagement_id}/{skill}",
                            expected=f"rank >= {have}",
                            found=f"rank {want}",
                            skill=skill,
                        )
                    )

    def effective_review(self, skill: str, declared: str, scopes: ScopeRegistry) -> str:
        """The tighter of what the skill declares and what the policy asks for."""
        asked = self.review_floors.get(skill)
        if asked is None:
            return declared
        return asked if scopes.review_rank(asked) > scopes.review_rank(declared) else declared

    def is_material(self, amount: Money | None) -> bool:
        if amount is None:
            return False
        if amount.currency != self.materiality.currency:
            # A figure in another currency cannot be compared to the threshold, and a
            # figure that cannot be compared is not one that is quietly immaterial.
            return True
        return amount.amount >= self.materiality.amount


def _firm_floor(constraints: ConstraintRegistry) -> Money:
    amount, currency = constraints.materiality_floor()
    return Money(float(amount), str(currency))
