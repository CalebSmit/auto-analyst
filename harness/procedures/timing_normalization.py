"""The mechanical half of timing-normalization.

What the model sees is labels and locators - never values. What comes back is a mapping.
What the tool does with it is every piece of arithmetic. This module is the glue and
nothing more: it neither matches nor sums.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from harness.runtime import BoundTools
from review.router import Item

__all__ = [
    "NO_CALENDAR",
    "NOT_HISTORICAL",
    "FiscalCalendar",
    "SourceFile",
    "TimingInputs",
    "TimingNormalization",
    "historical",
]

PROPOSAL_CONTRACT = "skills/timing-normalization-proposal@1.0.0"

# How the timing normalizer marks a disagreement the analyst's precedence rules settled. Kept
# here rather than imported: nothing in the harness imports a tool module (tests/p10). A test
# holds the two copies equal.
SETTLED_BY_RULE = " - taken by rule: "

# Document types that are never history, whatever they look like. A client forecast carries
# every statement label a historical file does; aligned into the historical table, its
# projected years would sit beside the real ones as if they had happened (P38). Held out
# here, in code, rather than left to the model to notice from a document_type field.
NOT_HISTORICAL = frozenset({"forecast"})

NO_CALENDAR = (
    "this engagement's profile records no fiscal calendar; take the year end from the "
    "statements themselves and say which one you took"
)


@dataclass(frozen=True)
class SourceFile:
    """One classified statement file, as the readers left it."""

    source_id: str
    filename: str
    document_type: str
    blocks: dict[str, list[dict[str, Any]]]
    """block locator -> rows (label, value, raw, ordinal)."""
    scale: int | None
    currency: str | None
    period_type: str | None
    period_ends: tuple[str, ...]
    ambiguous: tuple[str, ...] = ()
    source_version: int = 1
    block_periods: dict[str, str] = field(default_factory=dict)
    """block locator -> the period label the detector read for that block, if it
    could. A hint for the model, not a decision."""
    audited: bool = False
    """Whether the reader found an audit opinion - audited sources win a disagreement."""
    received_at: str = ""
    """When intake first saw the file - the more recent wins a disagreement of one kind."""


@dataclass(frozen=True)
class FiscalCalendar:
    """When this engagement's year ends, as a person recorded it at setup."""

    basis: str
    year_end_month: int
    year_end_day: int

    @property
    def month_day(self) -> str:
        return f"{self.year_end_month:02d}-{self.year_end_day:02d}"

    def end_of(self, year: int) -> str:
        """The date the fiscal year labelled `year` ends on."""
        return f"{year:04d}-{self.month_day}"

    def as_row(self) -> dict[str, Any]:
        return {
            "basis": self.basis,
            "year_end_month": self.year_end_month,
            "year_end_day": self.year_end_day,
            "fiscal_year_ends": self.month_day,
        }


@dataclass(frozen=True)
class TimingInputs:
    files: tuple[SourceFile, ...]
    calendar: FiscalCalendar | None = None
    """The engagement's fiscal calendar, or None where no profile recorded one.

    It is here because the payload was `{"files": [...]}` and nothing else: the model was
    handed twelve documents, asked to type and date every period in them, and never told
    when this company's year ends - though a person had filled that in at setup. Then the
    guard refused the answer for saying FY2023 two ways. The guard was right and the
    question was unanswerable: a June year end on one statement and a bare "2023" on
    another page cannot be reconciled by anybody who has not been told which the company
    uses.

    Optional because the profile is a person's and may be silent. A silence is said out
    loud in the payload rather than filled in with December, which would be the same
    guess wearing a system's confidence."""


def historical(inputs: TimingInputs) -> tuple[SourceFile, ...]:
    """The files that may enter the historical table."""
    return tuple(f for f in inputs.files if f.document_type not in NOT_HISTORICAL)


class TimingNormalization:
    name = "timing-normalization"
    proposal_contract = PROPOSAL_CONTRACT

    def terms(self, inputs: TimingInputs) -> tuple[str, ...]:
        """Alignment retrieves no precedents; there is nothing to rank by."""
        return ()

    def escalate(self, inputs: TimingInputs) -> str | None:
        """A file flagged ambiguous on scale or period type stops here, before the model. So
        does a set with no historical file in it: forecasts alone are not a history."""
        if inputs.files and not historical(inputs):
            names = ", ".join(f.filename for f in inputs.files)
            return f"no historical statements to align, only forecasts: {names}"
        for f in historical(inputs):
            # `columns` joins scale and period_type: a row carrying two figures holds two
            # periods, and a store with one value per row cannot say which one it kept. It
            # kept the last, which on a comparative statement is the prior year - so the
            # alternative to stopping here is a run whose every figure is a year out and
            # which passes provenance and footing on the way through.
            flags = [a for a in f.ambiguous if a.startswith(("scale", "period_type", "columns"))]
            if flags:
                return f"{f.filename} is ambiguous: " + "; ".join(flags)
            if f.scale not in (1, 1000, 1_000_000):
                return f"{f.filename} has no settled scale"
            if not f.currency:
                # Nothing stated one and the profile declared none. A figure without a
                # currency is not a figure; a person settles it, not a default.
                return f"{f.filename} has no settled currency"
        return None

    def review_items(self, output: dict[str, Any], inputs: dict[str, Any]) -> list[Item]:
        """A line with no counterpart, and sources that disagree: a person places them."""
        report = output.get("alignment_report") or {}
        items: list[Item] = []
        for u in report.get("unmatched", ()):
            loc = str(u.get("locator") or "")
            label = str(u.get("label") or loc)
            items.append(
                Item(
                    item_id=f"unmatched:{loc or label}",
                    skill=self.name,
                    question=(
                        f"{label} ({loc}) has no counterpart: {u.get('reason') or 'unmatched'}. "
                        f"A new line, a rename, or left out?"
                    ),
                    source_excerpt=f"{loc} {label}".strip(),
                    proposal={"treatment": "unmatched", "reason": u.get("reason")},
                    confidence=None,
                    review_required=True,
                    locator=loc,
                )
            )
        for c in report.get("conflicts", ()):
            if SETTLED_BY_RULE in str(c.get("detail") or ""):
                continue  # settled by the analyst's precedence rules; listed in the report
            label = str(c.get("canonical_label") or c.get("label") or "conflict")
            items.append(
                Item(
                    item_id=f"conflict:{label}",
                    skill=self.name,
                    question=(
                        f"{label}: the sources disagree. {c.get('why') or c.get('reason') or ''}"
                    ).strip(),
                    source_excerpt=label,
                    proposal=dict(c),
                    confidence=None,
                    review_required=True,
                    locator=str(c.get("locator") or ""),
                )
            )
        return items

    def payload(self, inputs: TimingInputs) -> str:
        """Labels, locators and the fiscal calendar. No values: the model matches, it does
        not read figures.

        The calendar is the only fact here that is not read off a page, and it is the one
        that makes the question answerable: every period label in the answer has to end on
        a date, and which date a fiscal year ends on is a property of the company rather
        than of the page it was printed on."""
        entries = []
        for f in historical(inputs):
            entries.append(
                {
                    "source_id": f.source_id,
                    "filename": f.filename,
                    "document_type": f.document_type,
                    "scale": f.scale,
                    "currency": f.currency,
                    "period_type": f.period_type,
                    "period_ends": list(f.period_ends),
                    "blocks": {
                        block: {
                            "period_hint": f.block_periods.get(block),
                            "rows": [
                                f"{_row_locator(block, int(r['ordinal']))}: {r['label']}"
                                for r in rows
                                if r.get("value") is not None
                            ],
                        }
                        for block, rows in f.blocks.items()
                    },
                }
            )
        body: dict[str, Any] = {"files": entries}
        # Stated once, at the top, rather than left to be inferred twelve times.
        body["fiscal_calendar"] = (
            inputs.calendar.as_row()
            if inputs.calendar is not None
            else {"recorded": False, "note": NO_CALENDAR}
        )
        return json.dumps(body, indent=1)

    def parse(self, text: str) -> dict[str, Any]:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("the model returned no JSON object")
        body = json.loads(text[start : end + 1])
        if not isinstance(body, dict):
            raise ValueError("the proposal is not an object")
        return body

    def apply(
        self, proposal: dict[str, Any], tools: BoundTools, inputs: TimingInputs, pin: str
    ) -> dict[str, Any]:
        sources = {f.source_id: f.blocks for f in historical(inputs)}
        files = {
            f.source_id: {
                "scale": f.scale,
                "currency": f.currency,
                "source_version": f.source_version,
                "audited": f.audited,
                "received_at": f.received_at,
            }
            for f in historical(inputs)
        }
        result = tools["timing_normalizer"](
            engagement_id=tools.engagement_id,
            mapping=proposal,
            sources=sources,
            files=files,
            model_pin=pin,
        )
        output: dict[str, Any] = result.value["output"]
        return output

    def summary(self, output: dict[str, Any]) -> dict[str, Any]:
        """What the scorecard reads for period coverage: the periods the table spans
        and every gap the skill reported. Labels and counts only, never a figure."""
        table = output.get("normalized_historicals") or {}
        report = output.get("alignment_report") or {}
        return {
            "periods": [str(p.get("label", p)) for p in table.get("periods", ())],
            "period_gaps": [
                {"period_label": g.get("period_label"), "why": g.get("why")}
                for g in report.get("period_gaps", ())
            ],
            "unmatched": len(report.get("unmatched", ())),
            "line_items": len(table.get("line_items", ())),
        }


def _row_locator(block: str, ordinal: int) -> str:
    if "!" in block and ":" in block:
        sheet, span = block.split("!", 1)
        col = "".join(ch for ch in span.split(":")[0] if ch.isalpha())
        return f"{sheet}!{col}{ordinal}"
    return f"{block}/r{ordinal}"
