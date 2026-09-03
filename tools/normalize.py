"""The Timing Normalizer: does the actual arithmetic of lining up periods.

Given a line-item mapping (the model's proposal) and the source rows (from the Source
Parse Store), produces the combined historical table and the alignment report. All
summation and period alignment happens here - never in a model. Pure function: mapping
plus rows in, table plus a full derivation trail out.

What it refuses to do:

* **Interpolate.** A period no block covers is a gap in the report and an absence in the
  table. Not a zero, not an average, not last year.
* **Choose between two files.** Two blocks claiming one period: where they agree the
  figure carries both locators; where they disagree there is no figure and the report
  carries the conflict with both values.
* **Restate scale.** Each figure carries the scale its file was read at.
* **Drop a row.** Every row in every block the mapping names ends up under a canonical
  label or in `unmatched`; a row the proposal forgot is reported as such.

Every figure it emits has a derivation - `sum` over the locators it came from - so the
tie-out guard re-derives every number in this table from the parse store.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

__all__ = ["Normalized", "timing_normalizer"]

PRODUCED_BY = "timing-normalization@0.1.0"
CONTRACT = "skills/timing-normalization@1.0.0"
CONFIDENCE = {"exact": 1.0, "rename": 0.9, "split": 0.8, "merge": 0.8}

_SHEET_ROW = re.compile(r"^(?P<sheet>'[^']+'|[^!']+)!(?P<col>[A-Z]{1,3})(?P<row>\d+)$")
_SHEET_BLOCK = re.compile(
    r"^(?P<sheet>'[^']+'|[^!']+)!(?P<col>[A-Z]{1,3})(?P<r1>\d+):(?P=col)(?P<r2>\d+)$"
)
_DOC_ROW = re.compile(r"^(?P<block>p\d+/t\d+)/r(?P<row>\d+)$")


@dataclass(frozen=True)
class Normalized:
    output: dict[str, Any]
    """skills/timing-normalization@1.0.0."""
    trail: list[dict[str, Any]] = field(default_factory=list)
    """One entry per figure: what was summed, from where, to what."""

    @property
    def rows(self) -> list[dict[str, Any]]:
        return self.trail


def timing_normalizer(
    mapping: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
    files: Mapping[str, Mapping[str, Any]],
    model_pin: str,
    engagement_id: str | None = None,
    limit: int | None = None,
    caps: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a proposal.

    `engagement_id` is the Policy Gate's, passed through so the `engagement_scoped`
    predicate has something to check; the tool has no use for it. `limit` and `caps`
    are the runtime's, and the row cap is checked on the trail this returns.

    `sources` is source_id -> block locator -> rows (label, value, raw, ordinal), as the
    readers wrote them. `files` is source_id -> {scale, currency, source_version}. `limit`
    and `caps` are the runtime's; the row cap is checked on the trail this returns.
    """
    periods = [dict(p) for p in mapping["periods"]]
    _check_periods(periods)
    max_periods = int((caps or {}).get("max_periods", 40))
    if len(periods) > max_periods:
        raise ValueError(f"{len(periods)} periods against a cap of {max_periods}")

    by_block = {(p["source_id"], p["block"]): p for p in periods}
    claimed: set[tuple[str, str]] = set()
    trail: list[dict[str, Any]] = []
    line_items: list[dict[str, Any]] = []
    matched: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for item in mapping["line_items"]:
        label = item["canonical_label"]
        kind = item.get("kind", "exact")
        per_period: dict[str, list[tuple[dict[str, Any], dict[str, Any], str]]] = {}
        source_labels: list[str] = []
        for src in item["sources"]:
            key = (src["source_id"], src["locator"])
            if key in claimed:
                raise ValueError(f"{src['locator']} in {src['source_id'][:19]} is claimed twice")
            claimed.add(key)
            block, row = _row_for(src["source_id"], src["locator"], sources)
            period = by_block.get((src["source_id"], block))
            if period is None:
                raise ValueError(
                    f"{src['locator']} sits in block {block}, which no period in the "
                    f"proposal covers"
                )
            per_period.setdefault(period["label"], []).append((period, row, src["locator"]))
            if src["label"] not in source_labels:
                source_labels.append(src["label"])

        values: list[dict[str, Any]] = []
        for period_label, hits in per_period.items():
            period = hits[0][0]
            by_file: dict[str, list[tuple[dict[str, Any], str]]] = {}
            for hit_period, row, locator in hits:
                by_file.setdefault(hit_period["source_id"], []).append((row, locator))
            # Sources for one period from different files must agree; from one file they sum.
            file_totals = {
                sid: (round(sum(float(r["value"]) for r, _ in rows), 6), [loc for _, loc in rows])
                for sid, rows in by_file.items()
            }
            file_sources = {loc_sid for loc_sid, _ in by_file.items()}
            claimants = {p["source_id"] for p in periods if p["label"] == period_label}
            totals = {sid: t for sid, (t, _) in file_totals.items()}
            if len(claimants) > 1 and len(set(totals.values())) > 1:
                conflicts.append(
                    {
                        "period_label": period_label,
                        "source_ids": sorted(totals),
                        "detail": (
                            f"{label}: "
                            + "; ".join(
                                f"{sid[:19]}... says {t:,.2f}" for sid, t in sorted(totals.items())
                            )
                            + " - no figure taken"
                        ),
                    }
                )
                continue
            # The figure cites one file. Where two files agree, the other's rows are on
            # the trail; the derivation names rows the figure's own source holds, so the
            # tie-out guard can resolve every locator under the figure's source_id.
            value = next(iter(totals.values()))
            first_sid = sorted(file_sources)[0]
            locators = list(file_totals[first_sid][1])
            meta = files[first_sid]
            if meta.get("scale") not in (1, 1000, 1_000_000):
                raise ValueError(
                    f"{first_sid[:19]}... has no settled scale; the period detector flagged it "
                    f"and it should have escalated before this tool ran"
                )
            figure: dict[str, Any] = {
                "value": value,
                "unit": "currency",
                "scale": int(meta["scale"]),
                "period": {"type": period["type"], "end": period["end"]},
                "source_id": first_sid,
                "locator": locators[0],
                "source_version": int(meta.get("source_version", 1)),
                "derivation": {"op": "sum", "of": locators},
                "masked": True,
                "confidence": CONFIDENCE.get(kind, 0.8),
                "produced_by": PRODUCED_BY,
                "model_pin": model_pin,
            }
            if meta.get("currency"):
                figure["currency"] = str(meta["currency"])
            values.append(figure)
            trail.append(
                {
                    "canonical_label": label,
                    "period_label": period_label,
                    "op": "sum",
                    "of": locators,
                    "rows": [
                        {"locator": loc, "label": r["label"], "value": float(r["value"])}
                        for _, r, loc in hits
                    ],
                    "value": value,
                }
            )
        line_items.append(
            {"canonical_label": label, "source_labels": source_labels, "values": values}
        )
        matched.append({"canonical_label": label, "source_labels": source_labels, "kind": kind})

    unmatched = [
        {"source_label": u["label"], "file_source_id": u["source_id"], "reason": u["reason"]}
        for u in mapping.get("unmatched", [])
    ]
    for u in mapping.get("unmatched", []):
        claimed.add((u["source_id"], u["locator"]))

    # Every row in every block a period names is accounted for, or reported.
    for period in periods:
        for stray in sources[period["source_id"]][period["block"]]:
            locator = _row_locator(period["block"], int(stray["ordinal"]))
            if (period["source_id"], locator) not in claimed and stray.get("value") is not None:
                unmatched.append(
                    {
                        "source_label": str(stray["label"]),
                        "file_source_id": period["source_id"],
                        "reason": f"not in the proposal ({locator})",
                    }
                )

    output = {
        "schema_version": CONTRACT,
        "produced_by": PRODUCED_BY,
        "normalized_historicals": {
            "periods": [
                {
                    "label": p["label"],
                    "type": p["type"],
                    "end": p["end"],
                    "source_id": p["source_id"],
                }
                for p in _distinct_periods(periods)
            ],
            "line_items": line_items,
        },
        "alignment_report": {
            "matched": matched,
            "unmatched": unmatched,
            "period_gaps": _gaps(periods),
            "conflicts": conflicts,
        },
    }
    frame = _frame(line_items)
    return {"output": output, "rows": trail, "table": frame.to_dict(orient="index")}


# ------------------------------------------------------------------ periods


def _check_periods(periods: list[dict[str, Any]]) -> None:
    seen: dict[str, tuple[str, str]] = {}
    for p in periods:
        date.fromisoformat(p["end"])
        key = p["label"]
        if key in seen and seen[key] != (p["type"], p["end"]):
            raise ValueError(f"period {key!r} is typed or ended two ways")
        seen[key] = (p["type"], p["end"])


def _distinct_periods(periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(periods, key=lambda p: (p["end"], p["label"])):
        out.setdefault(p["label"], p)
    return list(out.values())


def _gaps(periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Months or years between the earliest and latest that no block covers."""
    gaps: list[dict[str, Any]] = []
    for kind in ("M", "FY", "CY"):
        ends = sorted({date.fromisoformat(p["end"]) for p in periods if p["type"] == kind})
        if len(ends) < 2:
            continue
        if kind == "M":
            cursor = ends[0]
            have = set(ends)
            while cursor < ends[-1]:
                cursor = _next_month_end(cursor)
                if (
                    cursor not in have
                    and cursor < ends[-1]
                    or (cursor not in have and cursor == ends[-1])
                ):
                    gaps.append(
                        {"period_label": f"M{cursor.isoformat()[:7]}", "why": "no block covers it"}
                    )
        else:
            years = {e.year for e in ends}
            for year in range(ends[0].year + 1, ends[-1].year):
                if year not in years:
                    gaps.append({"period_label": f"{kind}{year}", "why": "no block covers it"})
    return gaps


def _next_month_end(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    following = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return date.fromordinal(following.toordinal() - 1)


# --------------------------------------------------------------------- rows


def _row_for(
    source_id: str,
    locator: str,
    sources: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
) -> tuple[str, dict[str, Any]]:
    """The block a row locator sits in, and the row itself."""
    blocks = sources.get(source_id)
    if not blocks:
        raise ValueError(f"no rows for {source_id[:19]}...")
    sheet = _SHEET_ROW.match(locator)
    doc = _DOC_ROW.match(locator)
    if sheet:
        row_no = int(sheet.group("row"))
        for block, rows in blocks.items():
            m = _SHEET_BLOCK.match(block)
            if (
                m
                and m.group("sheet") == sheet.group("sheet")
                and m.group("col") == sheet.group("col")
                and int(m.group("r1")) <= row_no <= int(m.group("r2"))
            ):
                for row in rows:
                    if int(row["ordinal"]) == row_no:
                        return block, dict(row)
    elif doc:
        block = doc.group("block")
        for row in blocks.get(block, ()):
            if int(row["ordinal"]) == int(doc.group("row")):
                return block, dict(row)
    raise ValueError(f"{locator} resolves to no row in {source_id[:19]}...")


def _row_locator(block: str, ordinal: int) -> str:
    m = _SHEET_BLOCK.match(block)
    if m:
        return f"{m.group('sheet')}!{m.group('col')}{ordinal}"
    return f"{block}/r{ordinal}"


def _frame(line_items: list[dict[str, Any]]) -> pd.DataFrame:
    """The table a person would look at: line items down, periods across. Built from
    the figures, so it can never disagree with them."""
    cells: dict[str, dict[str, float]] = {}
    for item in line_items:
        for figure in item["values"]:
            cells.setdefault(item["canonical_label"], {})[figure["period"]["end"]] = figure["value"]
    frame = pd.DataFrame.from_dict(cells, orient="index")
    return frame.reindex(sorted(frame.columns), axis=1) if not frame.empty else frame
