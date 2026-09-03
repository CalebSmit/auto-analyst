"""The Unmask Integrity Check: a separate node, so it can be tested apart from the masker.

Three assertions, as set comparisons between the tokens issued for this engagement, the
tokens found in the input, and the tokens resolved:

    1. every token present in the input resolved to a real value
    2. no token survives into the output
    3. no token resolved that was never issued for this engagement

Any of the three failing stops the run. The third is the one that matters most: a token
resolving to a value from another engagement is the cross-client failure this whole band
exists to prevent, and it is exactly the kind of bug that would otherwise surface in a
client's hands.

Separate from the unmasker on purpose. A masker that silently no-ops and a checker that
silently passes are the same bug, and splitting them is what makes it findable - this
module takes sets and a string, and can be handed a wrong set to prove it notices.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from ops.events import EventBus
from privacy.payload_scan import TOKEN_PATTERN
from privacy.unmask import Unmasked
from registries.errors import (
    TOKEN_CROSS_ENGAGEMENT,
    UNMASK_RESIDUAL,
    DiagnosticError,
    diagnose,
)

__all__ = ["IntegrityFailed", "UnmaskVerify", "VerifyResult"]


@dataclass(frozen=True)
class VerifyResult:
    passed: bool
    checked: int
    """Tokens found plus tokens resolved: everything the three assertions looked at."""
    unresolved: tuple[str, ...] = ()
    residual: tuple[str, ...] = ()
    foreign: tuple[str, ...] = ()
    code: str | None = None
    reasons: tuple[str, ...] = ()


class IntegrityFailed(DiagnosticError):
    def __init__(self, result: VerifyResult, engagement_id: str) -> None:
        assert result.code is not None
        super().__init__(diagnose(result.code, "; ".join(result.reasons), locator=engagement_id))
        self.result = result


class UnmaskVerify:
    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus

    def verify(
        self,
        unmasked: Unmasked,
        issued: Collection[str],
        run_id: str = "",
        step_id: str | None = None,
    ) -> VerifyResult:
        result = self.check(unmasked, issued)
        if self.bus is not None and run_id:
            self.bus.emit_guard(
                run_id=run_id,
                engagement_id=unmasked.engagement_id,
                node_id="unmask_verify",
                guard="unmask_verify",
                passed=result.passed,
                checked=result.checked,
                failed=len(result.unresolved) + len(result.residual) + len(result.foreign),
                step_id=step_id,
                diagnostic_code=result.code,
                payload={
                    "unresolved": len(result.unresolved),
                    "residual": len(result.residual),
                    "foreign": len(result.foreign),
                },
            )
        if not result.passed:
            raise IntegrityFailed(result, unmasked.engagement_id)
        return result

    @staticmethod
    def check(unmasked: Unmasked, issued: Collection[str]) -> VerifyResult:
        """The pure half. Sets in, verdict out, nothing recorded."""
        issued_set = frozenset(issued)
        unresolved = tuple(sorted(unmasked.found - unmasked.resolved))
        residual = tuple(sorted(set(TOKEN_PATTERN.findall(unmasked.text))))
        foreign = tuple(sorted(unmasked.resolved - issued_set))
        # A token found in the input that this engagement never issued is foreign whether
        # or not something resolved it - the cross-engagement case is the one to name.
        foreign_in_input = tuple(sorted(unmasked.found - issued_set))

        reasons: list[str] = []
        code: str | None = None
        if foreign or foreign_in_input:
            code = TOKEN_CROSS_ENGAGEMENT
            reasons.append(
                f"{len(set(foreign) | set(foreign_in_input))} token(s) were never issued "
                f"under this engagement"
            )
        if residual:
            code = code or UNMASK_RESIDUAL
            reasons.append(f"{len(residual)} mask token(s) survive in the output")
        if unresolved:
            code = code or UNMASK_RESIDUAL
            reasons.append(f"{len(unresolved)} token(s) in the input never resolved")

        return VerifyResult(
            passed=code is None,
            checked=len(unmasked.found) + len(unmasked.resolved),
            unresolved=unresolved,
            residual=residual,
            foreign=tuple(sorted(set(foreign) | set(foreign_in_input))),
            code=code,
            reasons=tuple(reasons),
        )
