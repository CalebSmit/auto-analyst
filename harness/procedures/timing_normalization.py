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

__all__ = ["SourceFile", "TimingInputs", "TimingNormalization"]

PROPOSAL_CONTRACT = "skills/timing-normalization-proposal@1.0.0"


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


@dataclass(frozen=True)
class TimingInputs:
    files: tuple[SourceFile, ...]


class TimingNormalization:
    name = "timing-normalization"
    proposal_contract = PROPOSAL_CONTRACT

    def escalate(self, inputs: TimingInputs) -> str | None:
        """A file flagged ambiguous on scale or period type stops here, before the model."""
        for f in inputs.files:
            flags = [a for a in f.ambiguous if a.startswith(("scale", "period_type"))]
            if flags:
                return f"{f.filename} is ambiguous: " + "; ".join(flags)
            if f.scale not in (1, 1000, 1_000_000):
                return f"{f.filename} has no settled scale"
        return None

    def payload(self, inputs: TimingInputs) -> str:
        """Labels and locators. No values: the model matches, it does not read figures."""
        entries = []
        for f in inputs.files:
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
        return json.dumps({"files": entries}, indent=1)

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
        sources = {f.source_id: f.blocks for f in inputs.files}
        files = {
            f.source_id: {
                "scale": f.scale,
                "currency": f.currency,
                "source_version": f.source_version,
            }
            for f in inputs.files
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


def _row_locator(block: str, ordinal: int) -> str:
    if "!" in block and ":" in block:
        sheet, span = block.split("!", 1)
        col = "".join(ch for ch in span.split(":")[0] if ch.isalpha())
        return f"{sheet}!{col}{ordinal}"
    return f"{block}/r{ordinal}"
