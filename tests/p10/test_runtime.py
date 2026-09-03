"""The Guarded Tool Runtime: one path, caps from the registry, every call recorded.

Two exit criteria. A gated read is authorised exactly as a write is - there is one path
and every tool goes through it. And call-time caps are applied by the runtime rather than
trusted from the caller, which is a different claim from the gate's row-cap predicate: the
gate refuses a caller who asks for too much, the runtime refuses a tool that returns too
much.
"""

from __future__ import annotations

import pytest

from harness.policy import PolicyDenied, RunScope
from harness.runtime import CapExceeded, GuardedRuntime
from ops.run_store import SqlRunStore
from registries.constraints import ConstraintRegistry
from registries.errors import RegistryError
from tests.p10.conftest import CALLER, ENGAGEMENT, OTHER, Fakes, action

# --------------------------------------------------------------- the path


def test_an_allowed_call_executes_and_is_recorded(
    runtime: GuardedRuntime, run: RunScope, fakes: Fakes, store: SqlRunStore, started: str
) -> None:
    result = runtime.call(action(), run)
    assert result.tool == "recompute"
    assert result.rows == 3
    assert result.decision.allowed
    assert [name for name, _ in fakes.calls] == ["recompute"]

    called = [e for e in store.events(started) if e.type == "tool.called"]
    assert len(called) == 1
    assert called[0].node_id == "guarded_runtime"
    assert called[0].payload["rows"] == 3
    assert called[0].cost_usd == 0.05


def test_a_denied_call_never_reaches_the_tool(
    runtime: GuardedRuntime, run: RunScope, fakes: Fakes
) -> None:
    with pytest.raises(PolicyDenied) as raised:
        runtime.call(action("index_lookup"), run)
    assert raised.value.diagnostic.code == "POLICY.TOOL_NOT_DECLARED"
    assert fakes.calls == [], "the tool ran anyway"


def test_a_gated_read_is_authorised_exactly_as_a_write_is(
    runtime: GuardedRuntime, run: RunScope, fakes: Fakes, store: SqlRunStore, started: str
) -> None:
    """The exit criterion. A read naming another engagement is refused by the same code,
    through the same path, and leaves the same record as a write would."""
    write = action("recompute", args={"engagement_id": OTHER, "limit": 5})
    read = action("precedent_lookup", args={
        "engagement_id": OTHER, "scope": "valuation/esop/repeat", "limit": 5,
    })

    for proposal in (write, read):
        with pytest.raises(PolicyDenied) as raised:
            runtime.call(proposal, run)
        assert raised.value.diagnostic.code == "POLICY.ARG_OUT_OF_SCOPE"
        assert raised.value.decision.predicate == "engagement_scoped"

    assert fakes.calls == []
    denials = [e for e in store.events(started) if e.type == "policy.deny"]
    assert [e.payload["mode"] for e in denials] == ["write", "read"]
    assert {e.diagnostic_code for e in denials} == {"POLICY.ARG_OUT_OF_SCOPE"}


def test_an_allowed_read_goes_through_the_same_path(
    runtime: GuardedRuntime, run: RunScope, fakes: Fakes
) -> None:
    result = runtime.call(action("precedent_lookup", args={
        "engagement_id": ENGAGEMENT, "scope": "valuation/esop/repeat", "limit": 5,
    }), run)
    assert result.decision.allowed
    assert fakes.calls[0][0] == "precedent_lookup"


# --------------------------------------------------------------- the caps


def test_the_cap_is_handed_to_the_tool_from_the_registry(
    runtime: GuardedRuntime, run: RunScope, fakes: Fakes, constraints: ConstraintRegistry
) -> None:
    """The tool has the number in hand rather than having to know the registry."""
    runtime.call(action(), run)
    _, kwargs = fakes.calls[0]
    assert kwargs["caps"] == constraints.tools["recompute"].caps
    assert kwargs["limit"] == 100


def test_the_callers_limit_is_clamped_not_trusted(
    runtime: GuardedRuntime, run: RunScope, fakes: Fakes, constraints: ConstraintRegistry
) -> None:
    """A caller passing no limit gets the cap, not unlimited."""
    runtime.call(action(args={"engagement_id": ENGAGEMENT}), run)
    _, kwargs = fakes.calls[0]
    assert kwargs["limit"] == constraints.tools["recompute"].caps["max_rows"]


def test_a_tool_that_returns_more_rows_than_its_cap_is_refused(
    runtime: GuardedRuntime, run: RunScope, fakes: Fakes, constraints: ConstraintRegistry,
    store: SqlRunStore, started: str,
) -> None:
    """The exit criterion. The gate cannot see what a tool returns; the runtime can. A
    tool that ignores its cap is broken rather than generous."""
    cap = constraints.tools["precedent_lookup"].caps["max_rows"]
    fakes.answer_rows = cap + 1
    with pytest.raises(CapExceeded) as raised:
        runtime.call(action("precedent_lookup", args={
            "engagement_id": ENGAGEMENT, "scope": "valuation/esop/repeat",
        }), run)
    assert raised.value.diagnostic.code == "POLICY.CAP_EXCEEDED"
    refusals = [e for e in store.events(started) if e.type == "tool.cap_exceeded"]
    assert len(refusals) == 1
    assert refusals[0].diagnostic_code == "POLICY.CAP_EXCEEDED"


def test_calls_per_step_are_counted_and_capped(
    runtime: GuardedRuntime, run: RunScope, constraints: ConstraintRegistry, fakes: Fakes
) -> None:
    """Something the caller cannot even see, and it is enforced."""
    per_step = constraints.tools["timing_normalizer"].caps["max_calls_per_step"]
    proposal = action("timing_normalizer", caller="timing-normalization@0.1.0", step_id="timing",
                      mode="write", args={"engagement_id": ENGAGEMENT, "limit": 10})
    for _ in range(per_step):
        runtime.call(proposal, run)
    with pytest.raises(CapExceeded, match="per step"):
        runtime.call(proposal, run)
    assert len(fakes.calls) == per_step


def test_the_count_is_per_step_not_per_run(
    runtime: GuardedRuntime, run: RunScope, constraints: ConstraintRegistry
) -> None:
    per_step = constraints.tools["timing_normalizer"].caps["max_calls_per_step"]
    base = dict(caller="timing-normalization@0.1.0", mode="write",
                args={"engagement_id": ENGAGEMENT, "limit": 10})
    for _ in range(per_step):
        runtime.call(action("timing_normalizer", step_id="timing", **base), run)
    # A different step starts its own count.
    runtime.call(action("timing_normalizer", step_id="timing_repair", **base), run)


# ----------------------------------------------------- bound, not unwrapped


def test_a_skill_is_constructed_with_its_allowlist_and_nothing_else(
    runtime: GuardedRuntime, run: RunScope, constraints: ConstraintRegistry
) -> None:
    tools = runtime.bound(run, CALLER, "ebitda")
    assert set(tools.names()) == set(constraints.tools_for("ebitda-normalization"))
    assert "recompute" in tools
    assert "index_lookup" not in tools


def test_a_bound_tool_goes_through_the_gate(
    runtime: GuardedRuntime, run: RunScope, fakes: Fakes
) -> None:
    tools = runtime.bound(run, CALLER, "ebitda")
    result = tools["recompute"](engagement_id=ENGAGEMENT, limit=20)
    assert result.decision.allowed
    assert fakes.calls[0][1]["limit"] == 20


def test_a_bound_tool_cannot_name_another_engagement(
    runtime: GuardedRuntime, run: RunScope, fakes: Fakes
) -> None:
    """The engagement is bound at construction. A skill cannot pass a different one -
    the argument is checked against the run, and the action's own field is the run's."""
    tools = runtime.bound(run, CALLER, "ebitda")
    with pytest.raises(PolicyDenied):
        tools["recompute"](engagement_id=OTHER, limit=20)
    assert fakes.calls == []


def test_asking_for_an_undeclared_tool_is_denied_on_the_record(
    runtime: GuardedRuntime, run: RunScope, store: SqlRunStore, started: str
) -> None:
    """Not hidden. Looked up, proposed, denied, recorded. The skill learns it was refused
    and nobody has to discover later that it tried."""
    tools = runtime.bound(run, CALLER, "ebitda")
    with pytest.raises(PolicyDenied) as raised:
        tools["index_lookup"](engagement_id=ENGAGEMENT)
    assert raised.value.diagnostic.code == "POLICY.TOOL_NOT_DECLARED"
    assert any(e.type == "policy.deny" for e in store.events(started))


def test_there_is_no_way_to_get_an_unwrapped_tool(runtime: GuardedRuntime) -> None:
    """The unwrapped callables are not in scope. No attribute, no method, no accident."""
    public = [n for n in dir(runtime) if not n.startswith("_")]
    for name in public:
        assert name not in ("tools", "implementations", "raw", "unwrapped")
    assert runtime.registered() == tuple(sorted(runtime.constraints.tools))


def test_registering_a_name_outside_the_namespace_is_refused(
    gate: object, constraints: ConstraintRegistry, bus: object
) -> None:
    """Six names, declared in constraints.yaml. A seventh is not a tool nobody has
    written yet; it is a name nothing will ever answer to."""
    with pytest.raises(RegistryError) as raised:
        GuardedRuntime(gate, constraints, bus, {"send_email": lambda **k: None})  # type: ignore[arg-type]
    assert raised.value.diagnostic.code == "SCOPE.UNKNOWN_TOOL"


def test_the_namespace_is_the_six_the_blueprint_names(constraints: ConstraintRegistry) -> None:
    """Finding F3. Two compute, four read, and t_template is in no skill's allowlist: a
    skill that could write cells could write one the mapping never declared."""
    assert set(constraints.tools) == {
        "recompute", "timing_normalizer", "chart_of_accounts_lookup",
        "precedent_lookup", "index_lookup", "template_schema_lookup",
    }
    assert {n for n, t in constraints.tools.items() if t.computes} == {
        "recompute", "timing_normalizer"
    }
    assert all(t.read_only for n, t in constraints.tools.items() if not t.computes)
    for skill in constraints.tool_allowlists.values():
        assert "t_template" not in skill and "write_template" not in skill
