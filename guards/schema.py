"""The Output Schema Validator: every skill output against its declared contract.

Forbidden fields are part of the schema - `additionalProperties: false` and the P02 rule
that no state field may say approved, certified or concluded - so "the skill wrote a
conclusion into a field that should not exist" is caught structurally rather than by a
list somebody maintains beside the schema.

A violation stops the run. Fix the skill, not the schema: a validator that bends is worse
than no validator.
"""

from __future__ import annotations

from typing import Any

from guards import GuardResult, report
from ops.events import EventBus
from registries.contracts import ContractRegistry
from registries.errors import FABRICATED_SOURCE, NO_PROVENANCE, SCHEMA_INVALID

__all__ = ["SchemaGate"]


class SchemaGate:
    def __init__(self, contracts: ContractRegistry, bus: EventBus | None = None) -> None:
        self.contracts = contracts
        self.bus = bus

    def check(self, output: Any, contract: str) -> GuardResult:
        """The pure half: is this output what the contract says one looks like."""
        diagnostics = self.contracts.check(contract, output)
        if not diagnostics:
            return GuardResult(guard="schema", passed=True, checked=1)
        worst = min((d.code for d in diagnostics), key=_severity)
        return GuardResult(
            guard="schema",
            passed=False,
            checked=1,
            failed=len(diagnostics),
            code=worst if worst.startswith("SKILL.") else SCHEMA_INVALID,
            reasons=tuple(f"{d.locator}: {d.detail}" for d in diagnostics[:8]),
            detail={"contract": contract, "violations": len(diagnostics)},
        )

    def run(
        self,
        output: Any,
        contract: str,
        run_id: str,
        engagement_id: str,
        step_id: str | None = None,
    ) -> GuardResult:
        return report(
            self.bus, self.check(output, contract), "schema_gate", run_id, engagement_id, step_id
        )


def _severity(code: str) -> int:
    """Fabricated provenance outranks a missing source, which outranks a bad shape. The
    registry reports in path order; the gate names the worst thing it found."""
    order = {FABRICATED_SOURCE: 0, NO_PROVENANCE: 1}
    return order.get(code, 2)
