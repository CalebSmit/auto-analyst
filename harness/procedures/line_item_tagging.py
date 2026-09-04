"""The mechanical half of line-item-tagging.

What the model sees is the pinned taxonomy and the line items' descriptions - never a
value. What comes back is one tag per item. What this module does with it is every check
a proposal has to survive before it is output:

* every `line_item_ref` is one the step was given, once (`SKILL.UNKNOWN_LINE_ITEM`
  otherwise); a ref the proposal forgot is tagged `unmapped` and reviewed;
* every category is in the pinned taxonomy, read through `chart_of_accounts_lookup` so
  the gate checks the version; one that is not becomes `unmapped` and is reviewed;
* every cited precedent is one the store holds in this engagement's scope, read through
  `precedent_lookup`; one that is not is dropped and the item is reviewed;
* `review_required` is set here, from rules a model cannot relax: below the engagement's
  bar, a category the policy always reviews, a departure from the taxonomy's default
  flags, a departure from a cited precedent, a precedent from another taxonomy version,
  or `uncategorisable`.

No arithmetic anywhere - there is nothing to compute. The confidence is the model's own
and is passed through for the Confidence Router to read.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from harness.runtime import BoundTools
from registries.errors import UNKNOWN_LINE_ITEM, DiagnosticError, diagnose
from registries.taxonomy import UNMAPPED, load_taxonomy

__all__ = [
    "CONTRACT",
    "LineItem",
    "LineItemTagging",
    "PROPOSAL_CONTRACT",
    "PRODUCED_BY",
    "ProposalRefused",
    "TaggingInputs",
    "line_item_ref",
    "statement_hint",
]

CONTRACT = "skills/line-item-tagging@1.0.0"
PROPOSAL_CONTRACT = "skills/line-item-tagging-proposal@1.0.0"
PRODUCED_BY = "line-item-tagging@0.1.0"
COA_TOOL = "chart_of_accounts_lookup"
PRECEDENT_TOOL = "precedent_lookup"

BS_SHEET_CUES = ("bs", "balance", "bal sheet", "sofp")
IS_SHEET_CUES = ("is", "p&l", "pl", "income", "profit", "operations", "ops")


class ProposalRefused(DiagnosticError):
    """The proposal does not account for the items it was given."""


def line_item_ref(canonical_label: str) -> str:
    """A stable reference: content-derived, so the same line gets the same ref on every
    run and a reviewer's decision can be matched back to it."""
    digest = hashlib.sha256(canonical_label.strip().lower().encode("utf-8")).hexdigest()
    return f"li_{digest[:10]}"


def statement_hint(locators: Iterable[str]) -> str | None:
    """IS, BS or None, from the sheet names the line's figures cite. A trial balance
    carries both statements and says nothing."""
    sheets = set()
    for loc in locators:
        if "!" in loc:
            sheets.add(loc.split("!", 1)[0].strip("'").lower())
    hints = set()
    for sheet in sheets:
        words = sheet.replace("_", " ").replace("-", " ").split()
        if any(w in BS_SHEET_CUES for w in words) or "balance" in sheet:
            hints.add("BS")
        elif any(w in IS_SHEET_CUES for w in words) or "income" in sheet:
            hints.add("IS")
    return next(iter(hints)) if len(hints) == 1 else None


@dataclass(frozen=True)
class LineItem:
    """One row of the normalized table, as the model is allowed to see it."""

    line_item_ref: str
    description: str
    source_labels: tuple[str, ...] = ()
    statement_hint: str | None = None
    periods: tuple[str, ...] = ()


@dataclass(frozen=True)
class TaggingInputs:
    items: tuple[LineItem, ...]
    taxonomy_version: str
    auto_accept_confidence: float | None = None
    """The engagement's bar, from its checkpoint policy. None means nothing is
    auto-accepted: every item goes to a person."""
    always_review_categories: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_normalized(
        cls,
        normalized_historicals: dict[str, Any],
        *,
        taxonomy_version: str,
        auto_accept_confidence: float | None = None,
        always_review_categories: Iterable[str] = (),
    ) -> TaggingInputs:
        """From timing-normalization's output. Labels, locators' sheet names and period
        labels come through; values do not."""
        periods = {
            p.get("end"): p.get("label", "") for p in normalized_historicals.get("periods", [])
        }
        items = []
        for entry in normalized_historicals.get("line_items", []):
            label = str(entry["canonical_label"])
            figures = entry.get("values", [])
            items.append(
                LineItem(
                    line_item_ref=line_item_ref(label),
                    description=label,
                    source_labels=tuple(str(s) for s in entry.get("source_labels", [])),
                    statement_hint=statement_hint(str(f.get("locator", "")) for f in figures),
                    periods=tuple(
                        periods.get(f.get("period", {}).get("end"), "")
                        for f in figures
                        if isinstance(f.get("period"), dict)
                    ),
                )
            )
        return cls(
            items=tuple(items),
            taxonomy_version=taxonomy_version,
            auto_accept_confidence=auto_accept_confidence,
            always_review_categories=frozenset(always_review_categories),
        )


class LineItemTagging:
    name = "line-item-tagging"
    proposal_contract = PROPOSAL_CONTRACT

    def escalate(self, inputs: TaggingInputs) -> str | None:
        """Nothing stops this skill before the model: its escalations are per item and
        arrive as review items. An empty table is not a judgment call, it is a caller
        error, and a taxonomy that will not load is a config error - both raise."""
        if not inputs.items:
            raise ValueError("line-item-tagging was given no line items")
        load_taxonomy(inputs.taxonomy_version)
        return None

    def terms(self, inputs: TaggingInputs) -> tuple[str, ...]:
        return tuple(i.description for i in inputs.items)

    def payload(self, inputs: TaggingInputs) -> str:
        """The taxonomy at the pinned version and the items. Descriptions, labels,
        statement hints and periods; no values, because the model has no use for them."""
        taxonomy = load_taxonomy(inputs.taxonomy_version)
        body = {
            "taxonomy": {
                "version": taxonomy.version,
                "rules": dict(taxonomy.rules),
                "categories": taxonomy.rows(),
            },
            "items": [
                {
                    "line_item_ref": i.line_item_ref,
                    "description": i.description,
                    "source_labels": list(i.source_labels),
                    "statement_hint": i.statement_hint,
                    "periods": list(i.periods),
                }
                for i in inputs.items
            ],
        }
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
        self, proposal: dict[str, Any], tools: BoundTools, inputs: TaggingInputs, pin: str
    ) -> dict[str, Any]:
        # The taxonomy, through the gate: the version is the run's pin or the call is
        # refused, which is how "tagged against coa-taxonomy@1.0.0" becomes true.
        coa = tools[COA_TOOL](
            engagement_id=tools.engagement_id, version=inputs.taxonomy_version
        ).value
        categories = {row["id"]: row for row in coa["rows"]}

        given = {i.line_item_ref: i for i in inputs.items}
        seen: set[str] = set()
        for item in proposal["items"]:
            ref = str(item["line_item_ref"])
            if ref not in given or ref in seen:
                why = "twice" if ref in seen else "not in the input"
                raise ProposalRefused(
                    diagnose(
                        UNKNOWN_LINE_ITEM,
                        f"the proposal names {ref} {why}; the step was given {len(given)} refs",
                        locator=ref,
                        skill=PRODUCED_BY,
                    )
                )
            seen.add(ref)

        # Cited precedents, verified against the store within this run's scope. One
        # gated read for the batch; an id that does not come back was never in scope.
        cited = sorted(
            {str(i["precedent_ref"]) for i in proposal["items"] if i.get("precedent_ref")}
        )
        known: dict[str, dict[str, Any]] = {}
        if cited:
            rows = tools[PRECEDENT_TOOL](
                engagement_id=tools.engagement_id, scope=tools.scope_path, ids=cited
            ).value["rows"]
            known = {str(r["precedent_id"]): r for r in rows}

        tagged = []
        for item in proposal["items"]:
            tagged.append(
                self._settle(item, given[str(item["line_item_ref"])], categories, known, inputs)
            )
        for ref, line in given.items():
            if ref not in seen:
                tagged.append(_unmapped(line, inputs, "not in the proposal"))
        tagged.sort(key=lambda t: list(given).index(t["line_item_ref"]))
        return {
            "schema_version": CONTRACT,
            "produced_by": PRODUCED_BY,
            "tagged_line_items": tagged,
        }

    def _settle(
        self,
        item: dict[str, Any],
        line: LineItem,
        categories: dict[str, dict[str, Any]],
        known: dict[str, dict[str, Any]],
        inputs: TaggingInputs,
    ) -> dict[str, Any]:
        notes: list[str] = []
        review = False
        category = str(item["category"])
        uncategorisable = bool(item.get("uncategorisable", False))
        excluded = bool(item["excluded_from_al"])
        nwc = bool(item["include_in_nwc"])
        confidence = float(item["confidence"])

        if category not in categories:
            notes.append(f"proposed category {category!r} is not in {inputs.taxonomy_version}")
            category, uncategorisable = UNMAPPED, True
        if uncategorisable and category != UNMAPPED:
            notes.append(f"uncategorisable pairs with {UNMAPPED!r} only; {category!r} set aside")
            category = UNMAPPED
        if category == UNMAPPED:
            uncategorisable = True
        spec = categories[category]
        if category == UNMAPPED:
            excluded, nwc = False, False
            review = True
        elif (excluded, nwc) != (bool(spec["excluded_from_al"]), bool(spec["include_in_nwc"])):
            notes.append("departs from the taxonomy's default flags")
            review = True

        precedent_ref = item.get("precedent_ref") or None
        if precedent_ref is not None:
            precedent = known.get(str(precedent_ref))
            if precedent is None:
                notes.append(f"cited precedent {precedent_ref} is not in this scope; dropped")
                precedent_ref, review = None, True
            else:
                if precedent.get("taxonomy_version") != inputs.taxonomy_version and (
                    precedent.get("category") not in categories
                ):
                    notes.append(
                        f"precedent {precedent_ref} was decided under "
                        f"{precedent.get('taxonomy_version')}; its category is not in "
                        f"{inputs.taxonomy_version}"
                    )
                    review = True
                if (
                    precedent.get("category") != category
                    or bool(precedent.get("excluded_from_al")) != excluded
                    or bool(precedent.get("include_in_nwc")) != nwc
                ):
                    notes.append(f"departs from precedent {precedent_ref}")
                    review = True

        bar = inputs.auto_accept_confidence
        if bar is None or confidence < bar:
            review = True
        if category in inputs.always_review_categories:
            review = True

        rationale = str(item["rationale"]).strip()
        if notes:
            rationale = "; ".join(notes) + " - " + rationale
        return {
            "line_item_ref": line.line_item_ref,
            "description": line.description,
            "category": category,
            "excluded_from_al": excluded,
            "include_in_nwc": nwc,
            "confidence": confidence,
            "rationale": rationale[:400],
            "precedent_ref": precedent_ref,
            "taxonomy_version": inputs.taxonomy_version,
            "review_required": review,
            "uncategorisable": uncategorisable,
        }


def _unmapped(line: LineItem, inputs: TaggingInputs, reason: str) -> dict[str, Any]:
    return {
        "line_item_ref": line.line_item_ref,
        "description": line.description,
        "category": UNMAPPED,
        "excluded_from_al": False,
        "include_in_nwc": False,
        "confidence": 0.0,
        "rationale": reason,
        "precedent_ref": None,
        "taxonomy_version": inputs.taxonomy_version,
        "review_required": True,
        "uncategorisable": True,
    }
