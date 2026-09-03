"""The Numeric Integrity Lock: nothing numeric changes between checked and written.

Tokenizes every numeric value and citation marker before and after a transform - the
unmasking, the template writing - and the multiset difference must be empty. Any change
stops the run. Rounding to the nearest thousand, a swapped scale, a dropped cell: the
lock does not care which, because a transform that changes a figure is not a transform.

Built as its own node rather than folded into either transform, so it can be tested
independently of the step it checks: hand it two strings and it answers.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from guards import GuardResult, report
from ops.events import EventBus
from registries.errors import NUMERIC_DRIFT

__all__ = ["NumericLock", "numeric_tokens"]

# A number as it appears in a document: optional sign, thousands separators, decimals,
# optional percent. Years and account codes count too - a lock that guessed which
# numbers matter would be the thing it exists to replace.
NUMBER = re.compile(
    r"(?<![\w.])[-(]?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?\)?|(?<![\w.])[-(]?\d+(?:\.\d+)?%?\)?"
)
# Citation markers: a content hash, a sheet range, a page/table/row triple, a mask token.
CITATION = re.compile(
    r"sha256:[0-9a-f]{64}|(?:'[^']+'|[A-Za-z_]\w*)![A-Z]+\d+(?::[A-Z]+\d+)?"
    r"|p\d+/t\d+/r\d+|\[\[[A-Z]+_\d+\]\]"
)


def numeric_tokens(text: str) -> Counter[str]:
    """Every number and every citation marker, as a multiset. Normalised so that
    `1,234.50` and `1234.5` are the same token - the lock is about values, not typography.
    """
    tokens: Counter[str] = Counter()
    for match in NUMBER.finditer(text):
        raw = match.group(0)
        negative = raw.startswith("(") and raw.endswith(")") or raw.startswith("-")
        digits = raw.strip("()-%").replace(",", "")
        try:
            value = float(digits)
        except ValueError:
            continue
        if negative:
            value = -value
        tokens[f"{value:g}{'%' if raw.endswith('%') or raw.endswith('%)') else ''}"] += 1
    for match in CITATION.finditer(text):
        tokens[match.group(0)] += 1
    return tokens


class NumericLock:
    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus

    @staticmethod
    def check(before: str, after: str) -> GuardResult:
        """The pure half. Two strings in, the set difference out."""
        expected = numeric_tokens(before)
        found = numeric_tokens(after)
        missing = expected - found
        extra = found - expected
        drift = bool(missing or extra)
        return GuardResult(
            guard="numeric_lock",
            passed=not drift,
            checked=sum(expected.values()),
            failed=sum(missing.values()) + sum(extra.values()),
            code=NUMERIC_DRIFT if drift else None,
            reasons=tuple(
                ([f"{sum(missing.values())} token(s) changed or vanished: "
                  + ", ".join(sorted(missing.elements())[:8])] if missing else [])
                + ([f"{sum(extra.values())} token(s) appeared: "
                    + ", ".join(sorted(extra.elements())[:8])] if extra else [])
            ),
            detail={
                "missing": sorted(missing.elements())[:32],
                "extra": sorted(extra.elements())[:32],
            },
        )

    def run(
        self,
        before: str,
        after: str,
        run_id: str,
        engagement_id: str,
        step_id: str | None = None,
    ) -> GuardResult:
        return report(self.bus, self.check(before, after), "numeric_lock", run_id,
                      engagement_id, step_id)


def as_text(value: Any) -> str:
    """A structured output, flattened to the string the lock reads. Deterministic."""
    import json

    return json.dumps(value, sort_keys=True, ensure_ascii=False)
