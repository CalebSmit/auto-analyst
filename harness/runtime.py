"""The Guarded Tool Runtime: executes approved actions and nothing else.

A thin interceptor around every registered tool. A skill is constructed with the wrapped
functions only - `bound()` hands back closures for exactly the caller's allowlist, each
of which builds a `ProposedAction` and goes through the gate. The unwrapped callables are
not in scope, so bypassing the gate is not a configuration mistake anyone can make; there
is nothing to configure.

**Call-time caps are applied here, from the registry, never trusted from the caller.** A
caller that asks for ten thousand rows is denied by the gate's row-cap predicate; a tool
that *returns* ten thousand rows when its cap is five hundred is refused here. The
per-step call count is something the caller cannot even see, and it is enforced.

**A gated read is authorised exactly as a write is.** There is one path, `call`, and every
tool goes through it. A read that named another engagement would return perfectly valid
data, which is why reads are not the cheap case.

Every call is recorded - allowed or refused, with its cost and its row count - so "what
did this step actually do" is the event stream rather than a guess.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from harness.policy import Decision, PolicyDenied, PolicyGate, ProposedAction, RunScope
from ops.events import EventBus
from registries.constraints import ConstraintRegistry, ToolSpec
from registries.errors import CAP_EXCEEDED, UNKNOWN_TOOL, DiagnosticError, RegistryError, diagnose

__all__ = ["BoundTools", "CapExceeded", "GuardedRuntime", "Tool", "ToolResult"]

# What a registered tool looks like: keyword arguments in, anything out. The runtime
# passes `caps` alongside the caller's arguments, so a tool that respects its cap has the
# number in hand rather than having to know the registry.
Tool = Callable[..., Any]


@dataclass(frozen=True)
class ToolResult:
    """What came back, and what it cost. Rows counted so the cap can be checked."""

    tool: str
    value: Any
    rows: int
    cost_usd: float
    decision: Decision


class CapExceeded(DiagnosticError):
    """A call-time cap was hit. Not a denial - the action was allowed - but a refusal."""


class GuardedRuntime:
    """The only way a tool gets called."""

    def __init__(
        self,
        gate: PolicyGate,
        constraints: ConstraintRegistry,
        bus: EventBus,
        tools: Mapping[str, Tool],
    ) -> None:
        self.gate = gate
        self.constraints = constraints
        self.bus = bus
        self._tools: dict[str, Tool] = {}
        for name, implementation in tools.items():
            if name not in constraints.tools:
                raise RegistryError(
                    diagnose(
                        UNKNOWN_TOOL,
                        f"{name!r} cannot be registered; the namespace is "
                        f"{', '.join(sorted(constraints.tools))}",
                        locator="harness/runtime.py",
                    )
                )
            self._tools[name] = implementation
        self._calls: Counter[tuple[str, str, str]] = Counter()

    def registered(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    # -- the one path

    def call(self, action: ProposedAction, run: RunScope) -> ToolResult:
        """Decide, cap, execute, record. In that order, and the first two cannot be
        skipped by anything the caller passes."""
        decision = self.gate.decide(action, run)
        if not decision:
            raise PolicyDenied(decision)

        spec = self.constraints.tools[action.tool]
        implementation = self._tools.get(action.tool)
        if implementation is None:
            raise RegistryError(
                diagnose(
                    UNKNOWN_TOOL,
                    f"{action.tool} is in the namespace but nothing is registered to answer it",
                    locator=action.tool,
                )
            )

        key = (run.run_id, action.step_id, action.tool)
        self._calls[key] += 1
        per_step = spec.caps.get("max_calls_per_step")
        if per_step is not None and self._calls[key] > int(per_step):
            self._refuse(
                action,
                run,
                spec,
                f"call {self._calls[key]} of {action.tool} in step {action.step_id!r}; "
                f"the cap is {per_step} per step",
            )

        # The caller's limit is already within the cap or the gate refused it. The cap
        # goes to the tool regardless, so the tool has the number in hand.
        caps = dict(spec.caps)
        args = dict(action.args)
        if "max_rows" in caps:
            args["limit"] = min(int(args.get("limit", caps["max_rows"])), int(caps["max_rows"]))

        value = implementation(**args, caps=caps)
        rows = _count_rows(value)
        if "max_rows" in caps and rows > int(caps["max_rows"]):
            self._refuse(
                action,
                run,
                spec,
                f"{action.tool} returned {rows} rows against a cap of {caps['max_rows']}; "
                f"a tool that ignores its cap is broken rather than generous",
            )

        result = ToolResult(
            tool=action.tool,
            value=value,
            rows=rows,
            cost_usd=action.estimated_cost_usd,
            decision=decision,
        )
        self.bus.emit(
            run_id=run.run_id,
            engagement_id=run.engagement_id,
            node_id="guarded_runtime",
            type="tool.called",
            message=f"{action.caller} called {action.tool}: {rows} rows",
            step_id=action.step_id or None,
            cost_usd=action.estimated_cost_usd,
            payload={
                "tool": action.tool,
                "kind": spec.kind,
                "read_only": spec.read_only,
                "rows": rows,
                "call_in_step": self._calls[key],
            },
        )
        return result

    # -- what a skill is constructed with

    def bound(self, run: RunScope, caller: str, step_id: str) -> BoundTools:
        """Closures for exactly the caller's allowlist, each routed through `call`.

        This is what the dispatcher hands a skill. There is no method here that returns
        an unwrapped tool, and the allowlist is read from the registry rather than from
        the caller - a skill cannot ask for more than it declared.
        """
        skill = caller.split("@", 1)[0]
        names = self.constraints.tools_for(skill)
        return BoundTools(self, run, caller, step_id, names)

    # -- refusal

    def _refuse(self, action: ProposedAction, run: RunScope, spec: ToolSpec, reason: str) -> None:
        self.bus.emit(
            run_id=run.run_id,
            engagement_id=run.engagement_id,
            node_id="guarded_runtime",
            type="tool.cap_exceeded",
            level="warn",
            message=f"{action.caller} -> {action.tool}: {reason}",
            step_id=action.step_id or None,
            diagnostic_code=CAP_EXCEEDED,
            payload={"tool": action.tool, "caps": dict(spec.caps)},
        )
        raise CapExceeded(diagnose(CAP_EXCEEDED, reason, locator=action.tool))


class BoundTools:
    """The tool surface one skill invocation sees. Names from its allowlist, nothing else."""

    def __init__(
        self,
        runtime: GuardedRuntime,
        run: RunScope,
        caller: str,
        step_id: str,
        names: tuple[str, ...],
    ) -> None:
        self._runtime = runtime
        self._run = run
        self._caller = caller
        self._step_id = step_id
        self._names = names

    def names(self) -> tuple[str, ...]:
        return self._names

    def __contains__(self, name: object) -> bool:
        return name in self._names

    @property
    def engagement_id(self) -> str:
        """The run's engagement, for the `engagement_scoped` predicate every call must
        satisfy. A procedure passes it back; it cannot pass another."""
        return self._run.engagement_id

    @property
    def scope_path(self) -> str:
        """The run's resolved scope path, for the `precedent_scope_declared` predicate.
        A procedure passes it back; it cannot pass a wider one."""
        return self._run.scope_path

    def pinned(self, tool: str) -> str | None:
        """The version this run pinned for a tool - the taxonomy the chart-of-accounts
        lookup must read. A procedure asks for exactly this, or the gate refuses it."""
        return self._run.versions.get(tool)

    def __getitem__(self, name: str) -> Callable[..., ToolResult]:
        # A name outside the allowlist is not hidden - it is looked up, proposed, and
        # denied on the record. The skill learns it was refused; nobody learns it later.
        def invoke(**args: Any) -> ToolResult:
            spec = self._runtime.constraints.tools.get(name)
            mode: Literal["read", "write"] = "read" if spec is None or spec.read_only else "write"
            action = ProposedAction(
                tool=name,
                args=args,
                caller=self._caller,
                engagement=self._run.engagement_id,
                mode=mode,
                estimated_cost_usd=float(args.pop("estimated_cost_usd", 0.0)),
                step_id=self._step_id,
            )
            return self._runtime.call(action, self._run)

        return invoke


def _count_rows(value: Any) -> int:
    if isinstance(value, list | tuple):
        return len(value)
    if isinstance(value, dict) and isinstance(value.get("rows"), list | tuple):
        return len(value["rows"])
    return 1 if value is not None else 0
