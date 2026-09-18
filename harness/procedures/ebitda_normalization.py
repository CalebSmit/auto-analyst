"""The mechanical half of ebitda-normalization: two passes, two procedures.

**The first pass** (`EbitdaNormalization`) sends the tagged lines, the periods and the
benchmark's provenance - never a value - and gets back candidates: a line, its periods,
a category, a rationale, a confidence. Everything numeric happens here, through tools:

* the amount of a candidate-period is the line's own figure from the normalized
  historicals, and `recompute` re-derives it from the rows behind it before it becomes
  a schedule item - `recomputed` is the tool's answer, never the model's;
* the officer-compensation test sums the officer lines through `recompute` and compares
  the total to the engagement's benchmark, which the profile carried in (the F1
  contract) and which is cited on every such item;
* `above_materiality` is the figure against the engagement's threshold;
* `review_required` is set from rules a model cannot relax: material, officer pay, a
  category the policy always reviews, a fact not in the documents, a non-recurring
  candidate that fails the analyst's one-time test (more than two periods, or present in the
  earliest), a figure that did not tie, a confidence below
  the bar, a departure from a cited precedent.

**The verification pass** (`EbitdaVerification`) is a separate invocation of the same
skill. It sends the schedule's amounts, citations and excerpts and never the first
pass's rationale or confidence, and gets back a verdict per candidate. An unsupported
item goes to a person. It runs as an iteration of the plan's declared
`self_verification` region on the EBITDA step, admitted by the loop controller.

Nothing here applies an add-back, and nothing here has a field a concluded value could
be recorded in.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from harness.procedures.line_item_tagging import line_item_ref
from harness.runtime import BoundTools
from ops.source_parse import SheetRange, parse_locator
from registries.errors import UNKNOWN_LINE_ITEM, DiagnosticError, diagnose
from review import Money
from review.router import Item

__all__ = [
    "Benchmark",
    "CONTRACT",
    "EbitdaInputs",
    "EbitdaNormalization",
    "EbitdaVerification",
    "Line",
    "PROPOSAL_CONTRACT",
    "PRODUCED_BY",
    "ProposalRefused",
    "VERIFICATION_CONTRACT",
    "VerificationInputs",
    "one_time_doubts",
]

CONTRACT = "skills/ebitda-normalization@1.0.0"
PROPOSAL_CONTRACT = "skills/ebitda-normalization-proposal@1.0.0"
VERIFICATION_CONTRACT = "skills/ebitda-normalization-verification-proposal@1.0.0"
PRODUCED_BY = "ebitda-normalization@0.1.0"
RECOMPUTE = "recompute"
PRECEDENT_TOOL = "precedent_lookup"
NON_RECURRING = "non_recurring"
OWNER_RELATED = "owner_related"
# The most periods a one-time item may appear in (the analyst's rule, 2026-09-17-1).
ONE_TIME_MAX_PERIODS = 2
CONFIRM_WITH_MANAGEMENT = "confirm with management that it will not recur"


def one_time_doubts(periods: Sequence[str], present: Iterable[str]) -> list[str]:
    """Why an item proposed as non-recurring may not be, by the analyst's test.

    One-time means it appears in one or two periods and not in the years before; management
    then confirms (knowledge, 2026-09-17-1). `periods` are the table's, earliest first. The
    confirmation question is always last; any note before it sends the item to a person.
    """
    here = [p for p in periods if p in set(present)]
    doubts: list[str] = []
    if here and len(here) == len(periods):
        doubts.append("present in every period; probably not non-recurring")
    elif len(here) > ONE_TIME_MAX_PERIODS:
        doubts.append(
            f"present in {len(here)} of {len(periods)} periods; one-time means at most "
            f"{ONE_TIME_MAX_PERIODS}"
        )
    elif len(periods) > 1 and here and here[0] == periods[0]:
        doubts.append("present in the earliest period, so no earlier year shows it was absent")
    return [*doubts, CONFIRM_WITH_MANAGEMENT]


Rows = list[dict[str, Any]]


class ProposalRefused(DiagnosticError):
    """The proposal names something the step was not given."""


@dataclass(frozen=True)
class Benchmark:
    """The owner-compensation baseline, as the engagement profile recorded it."""

    amount: float
    currency: str
    basis: str
    source: str
    as_of: str

    def cited(self) -> dict[str, str]:
        return {"basis": self.basis, "source": self.source, "as_of": self.as_of}


@dataclass(frozen=True)
class Line:
    """One tagged line of the historical table, with its figure per period."""

    line_item_ref: str
    description: str
    category: str
    excluded_from_al: bool
    include_in_nwc: bool
    source_labels: tuple[str, ...]
    figures: dict[str, dict[str, Any]]
    """period label -> the figure envelope from the normalized historicals."""

    @property
    def periods(self) -> tuple[str, ...]:
        return tuple(self.figures)


@dataclass(frozen=True)
class EbitdaInputs:
    periods: tuple[str, ...]
    lines: tuple[Line, ...]
    blocks: Mapping[str, Mapping[str, Rows]]
    """source_id -> locator -> rows, as the readers left them. What recompute sums."""
    benchmark: Benchmark | None
    materiality_amount: float
    materiality_currency: str
    auto_accept_confidence: float | None = None
    always_review_categories: frozenset[str] = field(default_factory=frozenset)

    def line(self, ref: str) -> Line | None:
        return next((ln for ln in self.lines if ln.line_item_ref == ref), None)

    @classmethod
    def from_outputs(
        cls,
        timing_output: Mapping[str, Any],
        tagging_output: Mapping[str, Any],
        profile: Mapping[str, Any],
        blocks: Mapping[str, Mapping[str, Rows]],
        *,
        materiality_amount: float,
        materiality_currency: str,
        auto_accept_confidence: float | None = None,
        always_review_categories: Iterable[str] = (),
    ) -> EbitdaInputs:
        """From the two upstream skill outputs and the engagement profile. The
        materiality threshold is the checkpoint policy's - the tighter of the profile's
        and the firm floor - and comes from the caller for that reason."""
        table = timing_output["normalized_historicals"]
        by_end = {p["end"]: p["label"] for p in table["periods"]}
        tags = {t["line_item_ref"]: t for t in tagging_output["tagged_line_items"]}
        lines = []
        for entry in table["line_items"]:
            label = str(entry["canonical_label"])
            ref = line_item_ref(label)
            tag = tags.get(ref, {})
            figures = {
                by_end[f["period"]["end"]]: dict(f)
                for f in entry.get("values", [])
                if f.get("period", {}).get("end") in by_end
            }
            lines.append(
                Line(
                    line_item_ref=ref,
                    description=label,
                    category=str(tag.get("category", "unmapped")),
                    excluded_from_al=bool(tag.get("excluded_from_al", False)),
                    include_in_nwc=bool(tag.get("include_in_nwc", False)),
                    source_labels=tuple(str(s) for s in entry.get("source_labels", [])),
                    figures=figures,
                )
            )
        baseline = profile.get("owner_compensation_baseline")
        benchmark = (
            Benchmark(
                amount=float(baseline["amount"]),
                currency=str(baseline["currency"]),
                basis=str(baseline["basis"]),
                source=str(baseline["source"]),
                as_of=str(baseline["as_of"]),
            )
            if isinstance(baseline, Mapping) and baseline.get("amount") is not None
            else None
        )
        return cls(
            periods=tuple(p["label"] for p in table["periods"]),
            lines=tuple(lines),
            blocks=blocks,
            benchmark=benchmark,
            materiality_amount=float(materiality_amount),
            materiality_currency=str(materiality_currency),
            auto_accept_confidence=auto_accept_confidence,
            always_review_categories=frozenset(always_review_categories),
        )


# ------------------------------------------------------------------ pass one


class EbitdaNormalization:
    name = "ebitda-normalization"
    proposal_contract = PROPOSAL_CONTRACT

    def escalate(self, inputs: EbitdaInputs) -> str | None:
        """No benchmark, no run: the officer-compensation test cannot be skipped by a
        profile that forgot to say what the benchmark was."""
        if inputs.benchmark is None:
            return (
                "owner compensation has no benchmark: the engagement profile carries no "
                "owner_compensation_baseline"
            )
        if not inputs.lines:
            raise ValueError("ebitda-normalization was given no tagged lines")
        return None

    def terms(self, inputs: EbitdaInputs) -> tuple[str, ...]:
        return tuple(ln.description for ln in inputs.lines)

    def review_items(self, output: dict[str, Any], inputs: dict[str, Any]) -> list[Item]:
        """Every add-back the policy marked for a person: material, owner-related, below
        the confidence bar. The amount travels so the router can apply its thresholds."""
        items: list[Item] = []
        for s in output.get("addback_schedule", ()):
            if not s.get("review_required"):
                continue
            amount = dict(s.get("amount") or {})
            period = dict(amount.get("period") or {})
            money: Money | None
            try:
                money = Money(
                    abs(float(str(amount.get("value")))) * float(amount.get("scale") or 1),
                    str(amount.get("currency") or ""),
                )
            except (TypeError, ValueError):
                money = None
            cid = str(s["candidate_id"])
            what = str(s.get("description") or s.get("line_item_ref") or cid)
            when = str(period.get("label") or period.get("end") or "the period")
            items.append(
                Item(
                    item_id=f"addback:{cid}",
                    skill=self.name,
                    question=f"Add back {what} for {when}? ({s.get('category')})",
                    source_excerpt=" | ".join(
                        str(e.get("excerpt", "")) for e in (s.get("evidence") or [])[:2]
                    ),
                    proposal={
                        "description": what,
                        **{
                            k: s.get(k)
                            for k in (
                                "category",
                                "line_item_ref",
                                "recurs_in_all_periods",
                                "above_materiality",
                            )
                        },
                        "amount": amount,
                    },
                    confidence=amount.get("confidence"),
                    amount=money,
                    category=str(s.get("category") or "") or None,
                    review_required=True,
                    locator=str(amount.get("locator") or ""),
                )
            )
        return items

    def payload(self, inputs: EbitdaInputs) -> str:
        """Lines, tags, periods present, and the benchmark's provenance. No values: an
        add-back is decided by what a line is and when it occurs, not by its size."""
        assert inputs.benchmark is not None
        body = {
            "periods": list(inputs.periods),
            "benchmark": inputs.benchmark.cited(),
            "materiality_currency": inputs.materiality_currency,
            "lines": [
                {
                    "line_item_ref": ln.line_item_ref,
                    "description": ln.description,
                    "category": ln.category,
                    "excluded_from_al": ln.excluded_from_al,
                    "include_in_nwc": ln.include_in_nwc,
                    "source_labels": list(ln.source_labels),
                    "periods_present": list(ln.periods),
                }
                for ln in inputs.lines
            ],
        }
        return json.dumps(body, indent=1)

    def parse(self, text: str) -> dict[str, Any]:
        return _json_object(text)

    def apply(
        self, proposal: dict[str, Any], tools: BoundTools, inputs: EbitdaInputs, pin: str
    ) -> dict[str, Any]:
        assert inputs.benchmark is not None
        benchmark = inputs.benchmark
        candidates = proposal["candidates"]
        seen_ids: set[str] = set()
        for c in candidates:
            line = inputs.line(str(c["line_item_ref"]))
            if line is None:
                raise ProposalRefused(
                    diagnose(
                        UNKNOWN_LINE_ITEM,
                        f"{c['candidate_id']} names {c['line_item_ref']}, which is not a "
                        f"tagged line of this table",
                        locator=str(c["candidate_id"]),
                        skill=PRODUCED_BY,
                    )
                )
            absent = [p for p in c["periods"] if p not in line.figures]
            if absent:
                raise ProposalRefused(
                    diagnose(
                        UNKNOWN_LINE_ITEM,
                        f"{c['candidate_id']}: {line.description} has no figure in "
                        f"{', '.join(absent)}; the periods present were listed",
                        locator=str(c["candidate_id"]),
                        skill=PRODUCED_BY,
                    )
                )
            if c["candidate_id"] in seen_ids:
                raise ProposalRefused(
                    diagnose(
                        UNKNOWN_LINE_ITEM,
                        f"candidate_id {c['candidate_id']} is used twice",
                        locator=str(c["candidate_id"]),
                        skill=PRODUCED_BY,
                    )
                )
            seen_ids.add(str(c["candidate_id"]))

        known = _cited_precedents(candidates, tools)

        # The officer-compensation test, per period: the officer lines' total through
        # recompute, against the benchmark. Once per period, not once per item.
        officer_refs = [
            str(c["line_item_ref"]) for c in candidates if c.get("officer_compensation")
        ]
        officer_total: dict[str, float] = {}
        for period in inputs.periods:
            operands = []
            for ref in dict.fromkeys(officer_refs):
                line = inputs.line(ref)
                assert line is not None
                figure = line.figures.get(period)
                if figure is not None:
                    operands.append([float(figure["value"]) * int(figure["scale"])])
            if operands:
                total = tools[RECOMPUTE](
                    engagement_id=tools.engagement_id, op="sum", operands=operands, stated=0.0
                ).value
                officer_total[period] = float(total.recomputed)

        schedule: list[dict[str, Any]] = []
        for c in candidates:
            line = inputs.line(str(c["line_item_ref"]))
            assert line is not None
            for period in c["periods"]:
                schedule.append(
                    self._item(c, line, period, tools, inputs, pin, known, officer_total, benchmark)
                )
        order = {ln.line_item_ref: n for n, ln in enumerate(inputs.lines)}
        schedule.sort(key=lambda s: (order[s["line_item_ref"]], s["candidate_id"]))
        return {
            "schema_version": CONTRACT,
            "produced_by": PRODUCED_BY,
            "addback_schedule": schedule,
        }

    def _item(
        self,
        c: dict[str, Any],
        line: Line,
        period: str,
        tools: BoundTools,
        inputs: EbitdaInputs,
        pin: str,
        known: dict[str, dict[str, Any]],
        officer_total: dict[str, float],
        benchmark: Benchmark,
    ) -> dict[str, Any]:
        notes: list[str] = []
        review = False
        category = str(c["category"])
        confidence = float(c["confidence"])
        source = dict(line.figures[period])

        # The amount: the line's own figure, re-derived from its rows by the tool.
        figure = {
            **source,
            "confidence": confidence,
            "produced_by": PRODUCED_BY,
            "model_pin": pin,
            "masked": True,
        }
        recomputed, excerpt_rows = self._recompute(figure, tools, inputs)
        if not recomputed:
            notes.append("did not tie to its rows")
            review = True

        # Magnitude, not the signed amount. A statement is read as presented, so a
        # material line can arrive negative - an interest-income reversal, a credit-balance
        # expense, a contra account. Compared signed, a -$500,000 add-back scores below a
        # $250,000 threshold and materiality, the one trigger that is supposed to be
        # sign-blind, stops firing: with no other trigger the item auto-accepts and no
        # person ever sees it. `review_items` a few hundred lines up already takes `abs()`
        # for the reviewer's queue, so the two halves of this file used to disagree about
        # what "how big is it" means.
        absolute = abs(float(figure["value"]) * int(figure["scale"]))
        currency = str(figure.get("currency", ""))
        if currency != inputs.materiality_currency:
            above = True
            notes.append(f"{currency or 'no currency'} cannot be compared to the threshold")
        else:
            above = absolute >= inputs.materiality_amount
        if above:
            review = True

        recurs = set(inputs.periods) <= set(line.periods)
        if category == NON_RECURRING:
            doubts = one_time_doubts(inputs.periods, line.periods)
            notes.extend(doubts)
            review = review or len(doubts) > 1

        cited: dict[str, str] | None = None
        if c.get("officer_compensation"):
            cited = benchmark.cited()
            review = True
            total = officer_total.get(period)
            if benchmark.currency != currency:
                notes.append(f"benchmark is in {benchmark.currency}, the line in {currency or '?'}")
            elif total is not None:
                verdict = "above" if total > benchmark.amount else "at or below"
                notes.append(
                    f"officer comp test: {period} total {total:,.0f} {currency} is {verdict} "
                    f"the benchmark of {benchmark.amount:,.0f} ({benchmark.basis}, "
                    f"{benchmark.source}, as of {benchmark.as_of})"
                )

        fact = c.get("needs_fact")
        if fact:
            notes.append(f"depends on a fact not in the documents: {fact}")
            review = True

        precedent_ref = c.get("precedent_ref") or None
        if precedent_ref is not None:
            precedent = known.get(str(precedent_ref))
            if precedent is None:
                notes.append(f"cited precedent {precedent_ref} is not in this scope; dropped")
                precedent_ref, review = None, True
            elif precedent.get("category") != category:
                notes.append(f"departs from precedent {precedent_ref}")
                review = True

        if category in inputs.always_review_categories:
            review = True
        bar = inputs.auto_accept_confidence
        if bar is None or confidence < bar:
            review = True

        rationale = str(c["rationale"]).strip()
        if notes:
            rationale = "; ".join(notes) + " - " + rationale
        candidate_id = (
            f"{c['candidate_id']}-{period}" if len(c["periods"]) > 1 else str(c["candidate_id"])
        )
        return {
            "candidate_id": candidate_id,
            "line_item_ref": line.line_item_ref,
            "category": category,
            "amount": figure,
            "rationale": rationale,
            "evidence": [
                {
                    "source_id": figure["source_id"],
                    "locator": locator,
                    "excerpt": excerpt,
                }
                for locator, excerpt in excerpt_rows
            ]
            or [
                {
                    "source_id": figure["source_id"],
                    "locator": figure["locator"],
                    "excerpt": f"{line.description} ({period})",
                }
            ],
            "recomputed": recomputed,
            "above_materiality": above,
            "review_required": review,
            "officer_comp_benchmark": cited,
            "recurs_in_all_periods": recurs,
        }

    def _recompute(
        self, figure: dict[str, Any], tools: BoundTools, inputs: EbitdaInputs
    ) -> tuple[bool, list[tuple[str, str]]]:
        """Re-derive the figure from the rows behind its derivation, through the tool.
        A figure read off the page has nothing to re-derive and is trusted to the
        provenance gate; a derived one must tie."""
        derivation = figure.get("derivation")
        if not derivation:
            return True, []
        source_rows = inputs.blocks.get(str(figure["source_id"]), {})
        operands = []
        excerpts: list[tuple[str, str]] = []
        for locator in derivation["of"]:
            rows = rows_at(source_rows, str(locator))
            if not rows:
                return False, []
            operands.append([float(r["value"]) for r in rows if r.get("value") is not None])
            excerpts.append(
                (
                    str(locator),
                    "; ".join(
                        f"{r.get('label', '')} {r.get('raw') or r.get('value')}".strip()
                        for r in rows
                    ),
                )
            )
        result = tools[RECOMPUTE](
            engagement_id=tools.engagement_id,
            op=str(derivation["op"]),
            operands=operands,
            stated=float(figure["value"]),
            tolerance=float(derivation.get("tolerance", 0.0)),
        ).value
        return bool(result.matches), excerpts


# ------------------------------------------------------------------ pass two


@dataclass(frozen=True)
class VerificationInputs:
    """The first pass's schedule, and what the verifier may see of it."""

    schedule: dict[str, Any]
    descriptions: Mapping[str, str]
    """line_item_ref -> description, from the same inputs the first pass had."""
    blocks: Mapping[str, Mapping[str, Rows]]

    @classmethod
    def from_pass(cls, schedule: Mapping[str, Any], inputs: EbitdaInputs) -> VerificationInputs:
        return cls(
            schedule=dict(schedule),
            descriptions={ln.line_item_ref: ln.description for ln in inputs.lines},
            blocks=inputs.blocks,
        )


class EbitdaVerification:
    """The separate invocation. Same skill, different payload, different contract."""

    name = "ebitda-normalization"
    proposal_contract = VERIFICATION_CONTRACT

    def escalate(self, inputs: VerificationInputs) -> str | None:
        return None

    def terms(self, inputs: VerificationInputs) -> tuple[str, ...]:
        return ()

    def payload(self, inputs: VerificationInputs) -> str:
        """Amounts, citations, excerpts and the cited rows. Not the rationale, not the
        confidence, not the review flags: the verifier judges the evidence."""
        items = []
        for s in inputs.schedule["addback_schedule"]:
            figure = s["amount"]
            rows = []
            source_rows = inputs.blocks.get(str(figure["source_id"]), {})
            for locator in (figure.get("derivation") or {}).get("of", [figure["locator"]]):
                for r in rows_at(source_rows, str(locator)):
                    rows.append(
                        {
                            "locator": locator,
                            "label": r.get("label", ""),
                            "raw": r.get("raw") or r.get("value"),
                        }
                    )
            items.append(
                {
                    "candidate_id": s["candidate_id"],
                    "description": inputs.descriptions.get(s["line_item_ref"], s["line_item_ref"]),
                    "category": s["category"],
                    "period": figure["period"],
                    "amount": {
                        "value": figure["value"],
                        "currency": figure.get("currency"),
                        "scale": figure["scale"],
                    },
                    "evidence": [e["excerpt"] for e in s["evidence"]],
                    "cited_rows": rows,
                    "recurs_in_all_periods": s.get("recurs_in_all_periods", False),
                }
            )
        return json.dumps({"verification": True, "items": items}, indent=1)

    def parse(self, text: str) -> dict[str, Any]:
        return _json_object(text)

    def apply(
        self, proposal: dict[str, Any], tools: BoundTools, inputs: VerificationInputs, pin: str
    ) -> dict[str, Any]:
        """The schedule, with the verdicts applied. An unsupported item, or one the
        verifier did not answer for, goes to a person. Nothing else changes."""
        ids = {s["candidate_id"] for s in inputs.schedule["addback_schedule"]}
        verdicts: dict[str, dict[str, Any]] = {}
        for v in proposal["verdicts"]:
            if v["candidate_id"] not in ids:
                raise ProposalRefused(
                    diagnose(
                        UNKNOWN_LINE_ITEM,
                        f"the verifier answered for {v['candidate_id']}, which is not on "
                        f"the schedule",
                        locator=str(v["candidate_id"]),
                        skill=PRODUCED_BY,
                    )
                )
            verdicts[str(v["candidate_id"])] = v
        schedule = []
        for s in inputs.schedule["addback_schedule"]:
            item = dict(s)
            verdict = verdicts.get(str(s["candidate_id"]))
            if verdict is None:
                item["review_required"] = True
                item["rationale"] = "verification: no verdict - " + str(s["rationale"])
            elif not verdict["supported"]:
                item["review_required"] = True
                item["rationale"] = f"verification: not supported - {verdict['reason']} - " + str(
                    s["rationale"]
                )
            schedule.append(item)
        return {
            "schema_version": CONTRACT,
            "produced_by": PRODUCED_BY,
            "addback_schedule": schedule,
        }


# ------------------------------------------------------------------ helpers


def rows_at(source_rows: Mapping[str, Rows], locator: str) -> Rows:
    """The rows a locator names within one source's blocks, as the readers left them.

    The same resolution the Source Parse Store does, over the in-memory blocks the
    step was handed: a block locator is itself; a sheet cell or sub-range is the rows
    of the block containing it, by ordinal; a document row is that row of its table.
    Nothing resolves to a guess.
    """
    exact = source_rows.get(locator)
    if exact:
        return list(exact)
    try:
        want = parse_locator(locator)
    except ValueError:
        return []
    if isinstance(want, SheetRange):
        if not want.single_column:
            return []
        for block, rows in source_rows.items():
            try:
                have = parse_locator(block)
            except ValueError:
                continue
            if (
                isinstance(have, SheetRange)
                and have.sheet == want.sheet
                and have.column == want.column
                and have.row_start <= want.row_start
                and have.row_end >= want.row_end
            ):
                return [
                    r for r in rows if want.row_start <= int(r.get("ordinal", 0)) <= want.row_end
                ]
        return []
    for block, rows in source_rows.items():
        if locator.startswith(block + "/"):
            tail = locator[len(block) + 1 :]
            if tail.startswith("r") and tail[1:].isdigit():
                return [r for r in rows if int(r.get("ordinal", 0)) == int(tail[1:])]
    return []


def _json_object(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("the model returned no JSON object")
    body = json.loads(text[start : end + 1])
    if not isinstance(body, dict):
        raise ValueError("the proposal is not an object")
    return body


def _cited_precedents(
    candidates: list[dict[str, Any]], tools: BoundTools
) -> dict[str, dict[str, Any]]:
    cited = sorted({str(c["precedent_ref"]) for c in candidates if c.get("precedent_ref")})
    if not cited:
        return {}
    rows = tools[PRECEDENT_TOOL](
        engagement_id=tools.engagement_id, scope=tools.scope_path, ids=cited
    ).value["rows"]
    return {str(r["precedent_id"]): r for r in rows}
