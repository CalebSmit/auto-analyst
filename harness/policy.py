"""The Policy Gate: every tool call a skill proposes is decided before it executes.

A wrong action can produce a right-looking result. Verification catches a wrong result;
only a decision taken *before* execution catches a wrong act. Reading another
engagement's folder returns perfectly valid data, which is exactly why no guard on the
output would ever notice.

A proposed action is allowed iff **all** of:

    1. the tool is on the caller's declared allowlist
    2. the arguments satisfy every predicate in constraints.yaml that applies
    3. the engagement is this run's engagement
    4. the estimated cost is within what remains of the budget

Anything else is a denial, and denials are recorded - with a code and an owner, because
"denied" on its own tells nobody what to do. There is no "allow with a warning": a
warning nobody reads is an allow.

**Predicates are evaluated, not interpreted.** `constraints.yaml` states each rule in
words, and each rule's `id` binds to a Python function here. The words are the
documentation a reviewer reads; the function is what runs. The gate refuses to construct
if a predicate in the registry has no evaluator, so a rule cannot be added to the file
and silently never enforced.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from ops.events import EventBus
from registries.constraints import ConstraintRegistry, Predicate
from registries.errors import (
    ARG_OUT_OF_SCOPE,
    BUDGET_EXCEEDED,
    TOOL_NOT_DECLARED,
    UNKNOWN_TOOL,
    UNRESOLVED_SCOPE,
    WHAT_NOW,
    DiagnosticError,
    RegistryError,
    diagnose,
)

__all__ = [
    "EVALUATORS",
    "Decision",
    "PolicyDenied",
    "PolicyGate",
    "ProposedAction",
    "RunScope",
]

Mode = Literal["read", "write"]


@dataclass(frozen=True)
class ProposedAction:
    """What the Policy Gate decides on, before anything runs."""

    tool: str
    args: Mapping[str, Any]
    caller: str
    """skill@version."""
    engagement: str
    mode: Mode = "read"
    estimated_cost_usd: float = 0.0
    step_id: str = ""

    @property
    def skill(self) -> str:
        return self.caller.split("@", 1)[0]


@dataclass(frozen=True)
class RunScope:
    """The facts about this run the predicates are evaluated against.

    `versions` is tool name to the version this run pinned - the taxonomy version the
    chart-of-accounts lookup must read, the template version the schema lookup must read.
    A run that read two taxonomy versions cannot say which one it tagged against.
    """

    run_id: str
    engagement_id: str
    engagement_root: str
    scope_path: str
    versions: Mapping[str, str]
    budget_remaining_usd: float

    @property
    def practice(self) -> str:
        return self.scope_path.split("/", 1)[0]


@dataclass(frozen=True)
class Decision:
    """Allow or deny. Nothing in between."""

    allowed: bool
    action: ProposedAction
    reason: str
    code: str | None = None
    owner: str | None = None
    predicate: str | None = None

    def __bool__(self) -> bool:
        return self.allowed


class PolicyDenied(DiagnosticError):
    """The gate said no. Carries the decision, so the caller can record it too."""

    def __init__(self, decision: Decision) -> None:
        assert decision.code is not None
        super().__init__(diagnose(decision.code, decision.reason, locator=decision.action.tool))
        self.decision = decision


# ---------------------------------------------------------------- evaluators
#
# One function per predicate id in constraints.yaml. Each returns None when the rule holds
# and a reason when it does not. The gate maps the reason to the predicate's declared
# diagnostic code, so the code is the file's decision and the check is this module's.

Evaluator = Callable[[ProposedAction, RunScope, ConstraintRegistry], str | None]


def _engagement_scoped(a: ProposedAction, run: RunScope, _: ConstraintRegistry) -> str | None:
    named = a.args.get("engagement_id", a.engagement)
    if named != run.engagement_id or a.engagement != run.engagement_id:
        return f"names engagement {named!r}; this run is {run.engagement_id!r}"
    return None


def _path_within_engagement(a: ProposedAction, run: RunScope, _: ConstraintRegistry) -> str | None:
    root = run.engagement_root.rstrip("/") + "/"
    for name, value in a.args.items():
        if not isinstance(value, str) or not _looks_like_a_path(name, value):
            continue
        normalised = value.replace("\\", "/")
        if ".." in normalised.split("/") or not (normalised + "/").startswith(root):
            return f"{name}={value!r} is outside {run.engagement_root!r}"
    return None


def _looks_like_a_path(name: str, value: str) -> bool:
    """By the argument's *name*, never by its shape. A scope path and a pinned version
    both contain slashes and neither is a location on disk; inferring from the value
    would refuse them for being outside a folder they were never inside."""
    return name.endswith(("path", "file", "folder", "dir", "root"))


def _read_only_tools_write_nothing(
    a: ProposedAction, _: RunScope, constraints: ConstraintRegistry
) -> str | None:
    spec = constraints.tools[a.tool]
    if spec.read_only and a.mode != "read":
        return f"{a.tool} is read-only and the action is mode={a.mode!r}"
    return None


def _row_cap(a: ProposedAction, _: RunScope, constraints: ConstraintRegistry) -> str | None:
    cap = constraints.tools[a.tool].caps.get("max_rows")
    limit = a.args.get("limit")
    if cap is not None and limit is not None and int(limit) > int(cap):
        return f"limit={limit} exceeds {a.tool}'s cap of {cap} rows"
    return None


def _precedent_scope_declared(
    a: ProposedAction, run: RunScope, _: ConstraintRegistry
) -> str | None:
    scope = a.args.get("scope")
    if not scope:
        return "precedent_lookup declares no scope; retrieval is scope-built or it is not done"
    if str(scope).split("/", 1)[0] != run.practice:
        return f"scope {scope!r} is outside this run's {run.scope_path!r}"
    return None


def _pinned_versions_only(a: ProposedAction, run: RunScope, _: ConstraintRegistry) -> str | None:
    pinned = run.versions.get(a.tool)
    asked = a.args.get("version")
    if pinned is None:
        return f"this run pinned no version for {a.tool}"
    if asked != pinned:
        return f"asks for version {asked!r}; this run pinned {pinned!r}"
    return None


def _budget_remaining(a: ProposedAction, run: RunScope, _: ConstraintRegistry) -> str | None:
    if a.estimated_cost_usd > run.budget_remaining_usd:
        return (
            f"estimated ${a.estimated_cost_usd:.2f} exceeds the "
            f"${run.budget_remaining_usd:.2f} remaining"
        )
    return None


EVALUATORS: dict[str, Evaluator] = {
    "engagement_scoped": _engagement_scoped,
    "path_within_engagement": _path_within_engagement,
    "read_only_tools_write_nothing": _read_only_tools_write_nothing,
    "row_cap": _row_cap,
    "precedent_scope_declared": _precedent_scope_declared,
    "pinned_versions_only": _pinned_versions_only,
    "budget_remaining": _budget_remaining,
}


# ------------------------------------------------------------------- the gate


class PolicyGate:
    """Decides. Records. Never executes."""

    def __init__(
        self,
        constraints: ConstraintRegistry,
        bus: EventBus,
        evaluators: Mapping[str, Evaluator] | None = None,
    ) -> None:
        self.constraints = constraints
        self.bus = bus
        self.evaluators = dict(evaluators if evaluators is not None else EVALUATORS)
        self._require_every_predicate_is_evaluated()

    def decide(self, action: ProposedAction, run: RunScope) -> Decision:
        decision = self._decide(action, run)
        self.bus.emit(
            run_id=run.run_id,
            engagement_id=run.engagement_id,
            node_id="policy_gate",
            type="policy.allow" if decision.allowed else "policy.deny",
            level="info" if decision.allowed else "warn",
            message=f"{action.caller} -> {action.tool}: {decision.reason}",
            step_id=action.step_id or None,
            diagnostic_code=decision.code,
            payload={
                "tool": action.tool,
                "caller": action.caller,
                "mode": action.mode,
                "owner": decision.owner,
                "predicate": decision.predicate,
                "estimated_cost_usd": action.estimated_cost_usd,
            },
        )
        return decision

    def _decide(self, action: ProposedAction, run: RunScope) -> Decision:
        if action.tool not in self.constraints.tools:
            return self._deny(action, UNKNOWN_TOOL, f"{action.tool!r} is not in the tool namespace")

        # 1. Declared. A skill reaches the tools it declares and no others.
        if not self.constraints.may_call(action.skill, action.tool):
            declared = ", ".join(self.constraints.tools_for(action.skill)) or "nothing"
            return self._deny(
                action, TOOL_NOT_DECLARED,
                f"{action.skill} does not declare {action.tool} (it declares: {declared})",
            )

        # 3. This engagement. Checked before the predicates run, and again by the
        # engagement_scoped predicate: cross-client bleed is the failure that ends the
        # project, and it is worth being caught twice.
        if action.engagement != run.engagement_id:
            return self._deny(
                action, ARG_OUT_OF_SCOPE,
                f"proposed for {action.engagement!r}; this run is {run.engagement_id!r}",
            )

        # 2 and 4. Every applicable predicate, the budget among them.
        for predicate in self._applicable(action.tool):
            reason = self.evaluators[predicate.id](action, run, self.constraints)
            if reason is not None:
                return self._deny(action, predicate.diagnostic, reason, predicate.id)

        return Decision(allowed=True, action=action, reason="every condition held")

    def _applicable(self, tool: str) -> tuple[Predicate, ...]:
        return tuple(
            p for p in self.constraints.predicates
            if "all" in p.applies_to or tool in p.applies_to
        )

    def _deny(
        self, action: ProposedAction, code: str, reason: str, predicate: str | None = None
    ) -> Decision:
        owner, _ = WHAT_NOW[code]
        return Decision(
            allowed=False, action=action, reason=reason, code=code, owner=owner,
            predicate=predicate,
        )

    def _require_every_predicate_is_evaluated(self) -> None:
        """A rule in the file with no function behind it would be documented and never
        enforced, which is worse than absent: it reads as a control."""
        missing = [p.id for p in self.constraints.predicates if p.id not in self.evaluators]
        if missing:
            raise RegistryError(
                diagnose(
                    UNRESOLVED_SCOPE,
                    f"constraints.yaml declares predicate(s) {', '.join(missing)} and the "
                    f"policy gate has no evaluator for them. A rule that is written down "
                    f"and never run is a control that does not exist.",
                    locator="harness/policy.py",
                )
            )
        for predicate in self.constraints.predicates:
            if predicate.diagnostic not in (ARG_OUT_OF_SCOPE, BUDGET_EXCEEDED):
                raise RegistryError(
                    diagnose(
                        UNRESOLVED_SCOPE,
                        f"predicate {predicate.id} names diagnostic {predicate.diagnostic!r}, "
                        f"which is not a policy denial code",
                        locator="constraints/constraints.yaml",
                    )
                )
