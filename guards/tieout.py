"""The Tie-Out Check: every derived figure, recomputed from the rows it cites.

Calls the Recompute Engine on every figure that claims to be a sum, subtotal or derived
value, and compares to the stated figure within a tolerance recorded in the manifest. A
mismatch stops the run and writes both values, the delta and the cited rows, so a
reviewer sees what disagreed rather than just that something did.

The tolerance is the run's. A figure may carry a tighter one in its derivation and never
a looser one - a repair loop may change the input to a step, never the guard, the
tolerance or the schema.

Tie-out proves arithmetic, not selection. Eight wrong rows added correctly still pass
here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from guards import GuardResult, figures_in, report
from ops.events import EventBus
from ops.source_parse import SourceParseStore
from registries.errors import TIEOUT_MISMATCH, UNKNOWN_SOURCE

__all__ = ["Recompute", "TieoutGate"]

# The shape of the engine, as the guard sees it. `tools.recompute.recompute` satisfies
# it; a runtime-bound version does too. The guard imports neither, because binding a tool
# implementation is the runtime's job and a test says so.
Recompute = Callable[..., Any]


class TieoutGate:
    def __init__(
        self,
        parse_store: SourceParseStore,
        recompute: Recompute,
        tolerance: float,
        bus: EventBus | None = None,
    ) -> None:
        if tolerance < 0:
            raise ValueError("a tolerance is zero or positive")
        self.parse_store = parse_store
        self.recompute = recompute
        self.tolerance = tolerance
        self.bus = bus

    def check(self, output: Any, run_id: str) -> GuardResult:
        checked = 0
        mismatches: list[dict[str, Any]] = []
        reasons: list[str] = []
        code: str | None = None

        for path, figure in figures_in(output):
            derivation = figure.get("derivation")
            if not derivation:
                continue  # read off the page; provenance's business, not arithmetic's
            checked += 1
            tolerance = min(self.tolerance, float(derivation.get("tolerance", self.tolerance)))
            operands: list[Sequence[float]] = []
            missing = []
            for locator in derivation["of"]:
                rows = self.parse_store.rows(run_id, figure["source_id"], locator)
                if not rows:
                    missing.append(locator)
                    continue
                operands.append([r.value for r in rows if r.value is not None])
            if missing:
                code = code or UNKNOWN_SOURCE
                reasons.append(f"{path}: no rows in the parse store for {missing}")
                continue

            result = self.recompute(
                derivation["op"], operands, float(figure["value"]), tolerance=tolerance
            )
            if not result.matches:
                code = TIEOUT_MISMATCH if code is None or code == UNKNOWN_SOURCE else code
                mismatches.append(
                    {
                        "at": path,
                        "stated": result.stated,
                        "recomputed": result.recomputed,
                        "delta": result.delta,
                        "tolerance": tolerance,
                        "op": result.op,
                        "rows": derivation["of"],
                    }
                )
                reasons.append(
                    f"{path}: stated {result.stated:g}, recomputed {result.recomputed:g} "
                    f"(delta {result.delta:+g}, tolerance {tolerance:g})"
                )

        return GuardResult(
            guard="tieout",
            passed=code is None,
            checked=checked,
            failed=len(reasons),
            code=code,
            reasons=tuple(reasons),
            detail={"tolerance": self.tolerance, "mismatches": mismatches},
        )

    def run(
        self, output: Any, run_id: str, engagement_id: str, step_id: str | None = None
    ) -> GuardResult:
        return report(
            self.bus, self.check(output, run_id), "tieout_gate", run_id, engagement_id, step_id
        )
