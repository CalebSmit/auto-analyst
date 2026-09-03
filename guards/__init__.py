"""Guards: assertions about a result. Every one emits on pass as well as on failure.

Five of them here - schema, provenance, tie-out, reconcile, numeric lock - each with a
fixture built specifically to defeat it, because a guard with no adversarial fixture is
an assumption. The unmask integrity check is the sixth and lives in `privacy/verify.py`,
beside the thing it checks.

A guard reports; the Loop Controller decides what happens next. Nothing here repairs.

What they share: a result shape, a failure type, and the walk that finds every figure in
an output. A figure is any object carrying the envelope's provenance fields and a value,
wherever it sits in a skill's output.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from ops.events import EventBus
from registries.errors import DiagnosticError, diagnose

__all__ = ["GuardFailed", "GuardResult", "figures_in", "report"]

PROVENANCE_FIELDS = ("source_id", "locator", "source_version")


@dataclass(frozen=True)
class GuardResult:
    """One guard's verdict, in the shape the manifest and the loop controller read."""

    guard: str
    passed: bool
    checked: int
    failed: int = 0
    code: str | None = None
    reasons: tuple[str, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)
    """Both values, the delta, the cited rows - whatever a reviewer needs to see what
    disagreed rather than just that something did."""


class GuardFailed(DiagnosticError):
    def __init__(self, result: GuardResult, locator: str = "") -> None:
        assert result.code is not None
        super().__init__(diagnose(result.code, "; ".join(result.reasons), locator=locator))
        self.result = result


def figures_in(value: Any, path: str = "$") -> Iterator[tuple[str, dict[str, Any]]]:
    """Every figure envelope in an output, with where it was found."""
    if isinstance(value, dict):
        if all(k in value for k in PROVENANCE_FIELDS) and "value" in value:
            yield path, value
            return
        for key, inner in value.items():
            yield from figures_in(inner, f"{path}.{key}")
    elif isinstance(value, list):
        for n, inner in enumerate(value):
            yield from figures_in(inner, f"{path}[{n}]")


def report(
    bus: EventBus | None,
    result: GuardResult,
    node_id: str,
    run_id: str,
    engagement_id: str,
    step_id: str | None,
) -> GuardResult:
    """Emit the verdict, pass or fail, and raise on fail.

    Passes are recorded. A guard that only speaks when it fires is, on a quiet day,
    indistinguishable from a guard that never ran.
    """
    if bus is not None and run_id:
        bus.emit_guard(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=node_id,
            guard=result.guard,
            passed=result.passed,
            checked=result.checked,
            failed=result.failed,
            step_id=step_id,
            diagnostic_code=result.code,
            payload={k: v for k, v in result.detail.items() if _small(v)},
        )
    if not result.passed:
        raise GuardFailed(result, locator=step_id or node_id)
    return result


def _small(value: Any) -> bool:
    return len(str(value)) < 2000
