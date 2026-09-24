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

__all__ = ["IdentifierList", "PayloadScan", "ScanFailed", "ScanResult", "loosely"]

# What a mask token looks like. The masker (P12) produces these; the scan only needs to
# recognise them, and the shape is fixed here so the two cannot disagree about it.
TOKEN_PATTERN = re.compile(r"\[\[[A-Z]+_[0-9]+\]\]")

# Two shapes that re-identify a person or a business on their own, whichever engagement
# they belong to, and that no identifier list would ever contain because nobody typed them
# into a profile: a social security number and an employer identification number. Both
# are precise enough to fail closed on. The account-number pattern the draft scanner uses
# is not - it would match every `2025-12` period label - so it stays where it is.
SHAPED_LIKE_PII: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("social security number", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("employer identification number", re.compile(r"\b\d{2}-\d{7}\b")),
)


def loosely(value: str) -> re.Pattern[str]:
    """A declared identifier, matched however the page spaced it.

    `John Smith` matches `John Smith`, `John  Smith`, `John\nSmith` and `JohnSmith`.

    The last one is why this exists. OCR reads a scanned page at high confidence and
    still runs words together - the first real client folder came back with
    `BOARDMEETINGMINUTES` at 0.97 - and it does so unpredictably, so nothing downstream
    can assume either spacing. Until P97 both the masker and the scan matched on a plain
    substring, so a name a scanner had joined to its neighbour was masked by neither, and
    the scan could not catch the masker's miss because it shared the miss.

    **The error has a direction.** `\\s*` can match more than was meant - a two-letter
    identifier `A B` will now also match `AB` wherever it appears - and that masks text
    nobody needed masked. That is the survivable failure. The other direction, a name
    leaving unmasked, is the one this module exists to prevent, and a control that fails
    towards doing its job too often is the right way round.

    **What it does not cover.** A scanner that drops or mistakes a *letter* rather than a
    space - `Smlth` for `Smith` - defeats this as completely as it defeated the substring.
    Fuzzy matching on characters is a different instrument with a different error
    direction, and guessing that two names are the same name is not something this module
    is allowed to do. That case is a person's, and `interview.py register` is where they
    record it.
    """
    pieces = [re.escape(piece) for piece in value.split() if piece]
    if not pieces:  # `Identifier` forbids this; `IdentifierList` takes raw strings.
        return re.compile(re.escape(value), re.IGNORECASE)
    return re.compile(r"\s*".join(pieces), re.IGNORECASE)


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
        # `loosely`, not `ident.lower() in text.lower()`. The scan is the check on the
        # masker and the two must not differ about what counts as finding a name: a scan
        # that matched more loosely would fail runs the masker had handled correctly, and
        # one that matched more strictly would pass the leak it exists to catch.
        hits = tuple(ident for ident in identifiers.identifiers if loosely(ident).search(text))
        missing = tuple(t for t in identifiers.expected_tokens if t not in text)
        seen = len(TOKEN_PATTERN.findall(text))
        shaped = tuple(
            f"{kind} x{len(found)}"
            for kind, pattern in SHAPED_LIKE_PII
            if (found := pattern.findall(text))
        )
        reasons: list[str] = []
        if hits:
            # Never echo the identifier itself into an event or an error - that would
            # be the leak the scan exists to prevent, one level up.
            reasons.append(f"{len(hits)} identifier(s) from the vault appear unmasked")
        if shaped:
            # Counted and named by kind, never quoted, for the same reason.
            reasons.append("something shaped like a " + ", ".join(shaped) + " is in the payload")
        if missing:
            reasons.append(f"{len(missing)} expected token(s) were never substituted")
        return ScanResult(
            passed=not hits and not missing and not shaped,
            checked=len(identifiers.identifiers) + len(identifiers.expected_tokens),
            hits=hits + shaped,
            missing_tokens=missing,
            tokens_seen=seen,
            reasons=tuple(reasons),
        )
