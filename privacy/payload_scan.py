"""The Outbound Payload Scan: the proof the masker worked.

The Masking Engine is the control; this is the check on it. Two nodes rather than one,
deliberately, so the check can be tested independently of the thing it checks - a masker
that silently no-ops and a scanner that silently passes are the same bug, and splitting
them is what makes it findable. The exit criterion for this phase is exactly that case: a
stubbed masker that does nothing, and the scan catching it.

Deterministic. String and pattern matching against the engagement's identifier list, plus
a check that every token the masker was expected to substitute actually appears - a
missed substitution is an identifier that left unmasked, whichever way you read it. No
model is involved anywhere in this module, which is the point: the one step where a
plausible mistake is indistinguishable from correctness is not a step to be plausible in.

Passes are recorded as well as failures. A guard that only speaks when it fires is, on a
quiet day, indistinguishable from a guard that never ran.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from ops.events import EventBus
from registries.errors import UNMASKED_IDENTIFIER, DiagnosticError, diagnose

__all__ = ["IdentifierList", "PayloadScan", "ScanFailed", "ScanResult"]

# What a mask token looks like. The masker (P12) produces these; the scan only needs to
# recognise them, and the shape is fixed here so the two cannot disagree about it.
TOKEN_PATTERN = re.compile(r"\[\[[A-Z]+_[0-9]+\]\]")


@dataclass(frozen=True)
class IdentifierList:
    """What must not leave, and what must be there instead.

    `identifiers` are the raw strings from the engagement's vault - names, account
    labels, anything that re-identifies. `expected_tokens` are the substitutes the masker
    said it made. Both come from the vault in P12; until then a caller supplies them, and
    the scan is exactly as good as the list it is given.
    """

    engagement_id: str
    identifiers: tuple[str, ...]
    expected_tokens: tuple[str, ...] = ()

    @classmethod
    def of(
        cls, engagement_id: str, identifiers: Iterable[str], expected_tokens: Iterable[str] = ()
    ) -> IdentifierList:
        return cls(
            engagement_id=engagement_id,
            identifiers=tuple(sorted({i for i in identifiers if i.strip()}, key=len, reverse=True)),
            expected_tokens=tuple(sorted(set(expected_tokens))),
        )


@dataclass(frozen=True)
class ScanResult:
    passed: bool
    checked: int
    """Identifiers looked for plus tokens expected. The count the manifest records."""
    hits: tuple[str, ...] = ()
    missing_tokens: tuple[str, ...] = ()
    tokens_seen: int = 0
    reasons: tuple[str, ...] = field(default_factory=tuple)


class ScanFailed(DiagnosticError):
    """Something re-identifying would have left. Nothing did."""

    def __init__(self, result: ScanResult, engagement_id: str) -> None:
        super().__init__(
            diagnose(UNMASKED_IDENTIFIER, "; ".join(result.reasons), locator=engagement_id)
        )
        self.result = result


class PayloadScan:
    """Scan text bound for a model. Raise if anything re-identifying is in it."""

    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus

    def scan(
        self,
        text: str,
        identifiers: IdentifierList,
        run_id: str = "",
        step_id: str | None = None,
    ) -> ScanResult:
        result = self.check(text, identifiers)
        if self.bus is not None and run_id:
            self.bus.emit_guard(
                run_id=run_id,
                engagement_id=identifiers.engagement_id,
                node_id="payload_scan",
                guard="payload_scan",
                passed=result.passed,
                checked=result.checked,
                failed=len(result.hits) + len(result.missing_tokens),
                step_id=step_id,
                diagnostic_code=None if result.passed else UNMASKED_IDENTIFIER,
                payload={
                    "hits": len(result.hits),
                    "missing_tokens": list(result.missing_tokens),
                    "tokens_seen": result.tokens_seen,
                },
            )
        if not result.passed:
            raise ScanFailed(result, identifiers.engagement_id)
        return result

    def check(self, text: str, identifiers: IdentifierList) -> ScanResult:
        """The pure half. No bus, no raise - what a test of the matching wants."""
        lowered = text.lower()
        hits = tuple(
            ident for ident in identifiers.identifiers if ident.lower() in lowered
        )
        missing = tuple(t for t in identifiers.expected_tokens if t not in text)
        seen = len(TOKEN_PATTERN.findall(text))
        reasons: list[str] = []
        if hits:
            # Never echo the identifier itself into an event or an error - that would
            # be the leak the scan exists to prevent, one level up.
            reasons.append(f"{len(hits)} identifier(s) from the vault appear unmasked")
        if missing:
            reasons.append(f"{len(missing)} expected token(s) were never substituted")
        return ScanResult(
            passed=not hits and not missing,
            checked=len(identifiers.identifiers) + len(identifiers.expected_tokens),
            hits=hits,
            missing_tokens=missing,
            tokens_seen=seen,
            reasons=tuple(reasons),
        )
