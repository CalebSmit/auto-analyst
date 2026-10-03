"""The Workpaper Narrative: what was processed, what was adjusted, what remains open,
what a reviewer should look at first.

Renders figures; originates none. Written after the numbers are locked, from the
schedule, the mapping and the record - and the lock is checked again over the prose:
every number in the narrative is a number in the locked set, or the narrative does not
release. Counts are written in words so a count is never mistaken for a figure.

The blueprint positions this as a style-only model pass upstream of the QC gate.
Through P24 the build is local and keyless, so the narrative is rendered by code from
the same structured data a model would be handed; a style pass slots in before the lock
check without moving anything else. The contract, `workpaper@1.0.0`, has no numeric
field: a figure enters the prose only by being rendered from a locked value.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from guards import GuardResult
from guards.numeric_lock import numeric_tokens
from registries.errors import NUMERIC_DRIFT

__all__ = ["CONTRACT", "Narrative", "WorkpaperNarrative", "words"]

CONTRACT = "workpaper@1.0.0"
NODE = "workpaper"

_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def words(n: int) -> str:
    """A count in words, 0-999, so the narrative carries no number that is not a
    locked figure."""
    if n < 0:
        return "minus " + words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens - 2] + ("" if not ones else "-" + _ONES[ones])
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return _ONES[hundreds] + " hundred" + ("" if not rest else " and " + words(rest))
    return str(n)  # beyond the narrative's range; the lock will say so


@dataclass(frozen=True)
class Narrative:
    body: dict[str, Any]
    text: str
    lock: GuardResult


class WorkpaperNarrative:
    def render(
        self,
        *,
        engagement_id: str,
        run_id: str,
        template_key: str,
        periods: Iterable[str],
        sources: Iterable[Mapping[str, Any]],
        schedule: Iterable[Mapping[str, Any]],
        mapping: Mapping[str, Any],
        open_items: Iterable[Mapping[str, Any]],
        locked_text: str,
        currency: str = "USD",
    ) -> Narrative:
        periods = list(periods)
        sources = list(sources)
        schedule = list(schedule)
        open_items = list(open_items)
        bindings = mapping.get("bindings", [])
        unmapped = mapping.get("unmapped_template_inputs", [])

        processed = [
            f"{words(len(sources))} source file(s) were read for {engagement_id} and aligned "
            f"onto {words(len(periods))} period(s): {', '.join(periods)}.",
            f"{words(len(bindings))} template input(s) of {template_key} were written from "
            f"validated figures; {words(len(unmapped))} declared input(s) were left empty and "
            f"are listed in the mapping.",
        ]
        adjusted = [
            f"{_describe(item, currency)}"
            for item in schedule
            if not item.get("recurs_in_all_periods")
        ] or ["No add-backs were proposed."]
        flagged = [
            f"{_label(item)} was proposed as non-recurring but appears in every period; it is "
            f"flagged and not applied."
            for item in schedule
            if item.get("recurs_in_all_periods")
        ]
        review = [
            f"{_label(item)} ({_amount(item, currency)}) is waiting for a person: {_why(item)}"
            for item in schedule
            if item.get("review_required")
        ]
        look_first = [
            f"{words(len(review))} schedule item(s) are marked for review; "
            f"the material ones first.",
            *(f"{o.get('subject', o.get('item_id', 'an item'))}" for o in open_items),
        ]
        body = {
            "schema_version": CONTRACT,
            "engagement_id": engagement_id,
            "run_id": run_id,
            "processed": processed,
            "adjusted": adjusted + flagged,
            "open_items": review,
            "look_first": look_first,
        }
        text = "\n".join(
            line
            for section in ("processed", "adjusted", "open_items", "look_first")
            for line in body[section]
        )
        # Identifiers are not figures: the engagement, the run and the template key may
        # carry digits, and the narrative names them. Everything else numeric must be
        # a locked value.
        allowed = "\n".join([locked_text, engagement_id, run_id, template_key, *periods])
        lock = self.check_locked(text, allowed)
        return Narrative(body=body, text=text, lock=lock)

    @staticmethod
    def check_locked(narrative: str, locked_text: str) -> GuardResult:
        """Every number in the prose is a locked figure. The narrative renders; it does
        not originate, and this is where that is checked rather than hoped."""
        allowed = numeric_tokens(locked_text)
        found = numeric_tokens(narrative)
        strays = sorted(t for t in found if t not in allowed)
        return GuardResult(
            guard="numeric_lock",
            passed=not strays,
            checked=sum(found.values()),
            failed=len(strays),
            code=NUMERIC_DRIFT if strays else None,
            reasons=tuple(
                f"{t} appears in the narrative and is not a locked figure" for t in strays
            ),
            detail={"strays": strays},
        )


def _label(item: Mapping[str, Any]) -> str:
    return str(item.get("candidate_id", item.get("line_item_ref", "an item")))


def _amount(item: Mapping[str, Any], currency: str) -> str:
    """The figure as locked, and the period as a label - `FY2024`, never a date, so the
    only digits in the sentence are the figure's."""
    from harness.restate import amount_of

    figure = item.get("amount") or {}
    # Through the one multiplication, and printed as what it is: a count of shares reads
    # `135,361,000 shares`, never `135,361,000 USD` with the template's currency filled in
    # for a figure that has none because it is not money.
    said = amount_of({"value": 0, **figure}, _label(item))
    word = said.currency or (currency if said.unit == "currency" else said.unit)
    period = figure.get("period") or {}
    end = str(period.get("end", ""))
    label = f"{period.get('type', 'FY')}{end[:4]}" if end else ""
    return f"{said.number:,.0f} {word}" + (f" in {label}" if label else "")


def _describe(item: Mapping[str, Any], currency: str) -> str:
    return (
        f"{_label(item)}: {item.get('category', '').replace('_', ' ')} add-back of "
        f"{_amount(item, currency)}, proposed with evidence and not applied."
    )


def _why(item: Mapping[str, Any]) -> str:
    """From the item's structured flags, never its free-text rationale: the rationale
    can carry numbers the lock has not seen, and the narrative renders structure."""
    reasons = []
    if item.get("above_materiality"):
        reasons.append("above the materiality threshold")
    if item.get("officer_comp_benchmark"):
        reasons.append("officer pay, tested against the cited benchmark")
    if item.get("recurs_in_all_periods"):
        reasons.append("recurs in every period")
    if not item.get("recomputed", True):
        reasons.append("did not tie to its rows")
    category = str(item.get("category", "")).replace("_", " ")
    if category:
        reasons.append(f"{category} add-back")
    return "; ".join(reasons) or "review required"
