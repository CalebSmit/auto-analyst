"""Precedent Write-back: approved corrections become examples for next time.

Takes a human decision - by id, never by content - masks what it decided, and admits it
to the Precedent Store. The one path by which the system gets better without anyone
retraining anything, and the reason the store has exactly one writer: an unreviewed
decision must never become tomorrow's example.

What is refused, and why:

* **No decision at that id, a rejection, an escalation, or a decision naming nobody.**
  `PROCESS.PRECEDENT_NO_DECISION`. A rejection records that the proposal was wrong and
  nothing about what is right; there is nothing a future run should copy.
* **A description the masker cannot clear.** `PRIVACY.UNMASKED_PRECEDENT`. The scan runs
  over the masked example exactly as it runs over an outbound payload; a hit means an
  identifier nobody enumerated, and the example stays un-learned until it is corrected
  (blueprint failure mode 2414). Nothing is written.
* **A skill this node has no example shape for.** Tagging is P19's; add-backs are P20's.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from typing import Any

from ops.events import EventBus
from ops.models import DecisionKind
from ops.run_store import DecisionRecord, RunStore
from precedent.store import PrecedentRecord, PrecedentStore
from privacy.mask import Identifier, Masker
from privacy.payload_scan import PayloadScan
from registries.errors import (
    PRECEDENT_NO_DECISION,
    UNMASKED_PRECEDENT,
    DiagnosticError,
    diagnose,
)

__all__ = ["EXAMPLE_SHAPES", "PrecedentWriteback", "WritebackRefused"]

NODE = "precedent_writeback"
TAGGING = "line-item-tagging"


class WritebackRefused(DiagnosticError):
    """Nothing was written, and this is why."""


def _tagging_example(decision: DecisionRecord) -> dict[str, Any]:
    """What a tagging decision teaches: the description, the category, the two flags,
    the reason. On a correction the answer overrides the proposal field by field, so a
    reviewer who changed only the NWC flag leaves the category as proposed."""
    merged = dict(decision.proposal)
    if decision.decision is DecisionKind.CORRECTED:
        merged.update(decision.answer)
    missing = [k for k in ("description", "category") if not str(merged.get(k, "")).strip()]
    if missing:
        raise WritebackRefused(
            diagnose(
                PRECEDENT_NO_DECISION,
                f"{decision.item_id}: the decision carries no {', '.join(missing)}; "
                f"there is no example in it",
                locator=decision.item_id,
            )
        )
    rationale = decision.rationale.strip() or str(merged.get("rationale", "")).strip()
    return {
        "description": str(merged["description"]),
        "category": str(merged["category"]),
        "excluded_from_al": bool(merged.get("excluded_from_al", False)),
        "include_in_nwc": bool(merged.get("include_in_nwc", False)),
        "rationale": rationale,
    }


def _addback_example(decision: DecisionRecord) -> dict[str, Any]:
    """What an add-back decision teaches: the line's description, the add-back
    category a person approved, and the reason. Never the amount - an amount is an
    engagement's, and an example that carried one would be a figure with no source."""
    merged = dict(decision.proposal)
    if decision.decision is DecisionKind.CORRECTED:
        merged.update(decision.answer)
    missing = [k for k in ("description", "category") if not str(merged.get(k, "")).strip()]
    if missing:
        raise WritebackRefused(
            diagnose(
                PRECEDENT_NO_DECISION,
                f"{decision.item_id}: the decision carries no {', '.join(missing)}; "
                f"there is no example in it",
                locator=decision.item_id,
            )
        )
    rationale = decision.rationale.strip() or str(merged.get("rationale", "")).strip()
    return {
        "description": str(merged["description"]),
        "category": str(merged["category"]),
        "rationale": rationale,
    }


EXAMPLE_SHAPES: dict[str, Callable[[DecisionRecord], dict[str, Any]]] = {
    TAGGING: _tagging_example,
    "ebitda-normalization": _addback_example,
}
MASKED_FIELDS = ("description", "rationale")


class PrecedentWriteback:
    def __init__(
        self,
        store: RunStore,
        precedents: PrecedentStore,
        masker: Masker,
        scan: PayloadScan,
        bus: EventBus,
    ) -> None:
        self.store = store
        self.precedents = precedents
        self.masker = masker
        self.scan = scan
        self.bus = bus

    def write(
        self,
        run_id: str,
        item_id: str,
        *,
        client_id: str,
        scope_path: str,
        identifiers: Iterable[Identifier],
    ) -> PrecedentRecord:
        """One decision, by id, into the store. The decision is read from the log; a
        caller cannot hand this an example."""
        run = self.store.run(run_id)
        decision = next((d for d in self.store.decisions(run_id) if d.item_id == item_id), None)
        if decision is None or not decision.writes_precedent or not decision.decided_by.strip():
            found = "no decision" if decision is None else f"{decision.decision}"
            raise WritebackRefused(
                diagnose(
                    PRECEDENT_NO_DECISION,
                    f"{run_id}/{item_id}: {found}",
                    locator=f"{run_id}/{item_id}",
                    expected="an accepted or corrected decision naming a person",
                    found=found,
                )
            )
        skill = decision.skill.split("@", 1)[0]
        shape = EXAMPLE_SHAPES.get(skill)
        if shape is None:
            raise WritebackRefused(
                diagnose(
                    PRECEDENT_NO_DECISION,
                    f"{run_id}/{item_id}: no example shape for {skill or 'an unnamed skill'!r}",
                    locator=f"{run_id}/{item_id}",
                )
            )
        taxonomy_version = str(run.versions.get("taxonomy", "")).strip()
        if not taxonomy_version:
            raise WritebackRefused(
                diagnose(
                    PRECEDENT_NO_DECISION,
                    f"{run_id} pinned no taxonomy; an example with no version is not reusable",
                    locator=run_id,
                )
            )

        example = shape(decision)
        declared = list(identifiers)
        for field in MASKED_FIELDS:
            text = str(example.get(field, ""))
            if not text:
                continue
            masked = self.masker.mask(text, run.engagement_id, declared, run_id=run_id)
            result = self.scan.check(masked.text, masked.identifiers)
            if not result.passed:
                self._emit(
                    run_id,
                    run.engagement_id,
                    "precedent.writeback.refused",
                    f"{item_id}: {field} did not clear the scan; not written",
                    level="warn",
                    diagnostic_code=UNMASKED_PRECEDENT,
                    payload={"item_id": item_id, "field": field, "reasons": list(result.reasons)},
                )
                raise WritebackRefused(
                    diagnose(
                        UNMASKED_PRECEDENT,
                        f"{run_id}/{item_id}: {field} did not clear the outbound scan "
                        f"({'; '.join(result.reasons)}); the example stays un-learned",
                        locator=f"{run_id}/{item_id}",
                    )
                )
            example[field] = masked.text

        practice, segment, disposition = _split_scope(scope_path)
        precedent_id = "prec_" + hashlib.sha256(f"{run_id}/{item_id}".encode()).hexdigest()[:16]
        record = PrecedentRecord(
            precedent_id=precedent_id,
            decision_run_id=run_id,
            decision_item_id=item_id,
            engagement_id=run.engagement_id,
            client_id=client_id,
            practice=practice,
            segment=segment,
            disposition=disposition,
            skill=skill,
            taxonomy_version=taxonomy_version,
            decided_by=decision.decided_by,
            decided_at=decision.decided_at,
            decision=str(decision.decision),
            description=str(example["description"]),
            example={
                "precedent_id": precedent_id,
                **example,
                "taxonomy_version": taxonomy_version,
                "decision": str(decision.decision),
                "skill": skill,
            },
        )
        written = self.precedents.admit(record)
        self._emit(
            run_id,
            run.engagement_id,
            "precedent.written",
            f"{item_id}: {decision.decision} by {decision.decided_by} -> {written.precedent_id}",
            payload={
                "item_id": item_id,
                "precedent_id": written.precedent_id,
                "decision": str(decision.decision),
                "decided_by": decision.decided_by,
                "scope": scope_path,
            },
        )
        return written

    def sweep(
        self,
        run_id: str,
        *,
        client_id: str,
        scope_path: str,
        identifiers: Iterable[Identifier],
    ) -> tuple[PrecedentRecord, ...]:
        """Every precedent candidate on a run - the accepted and corrected decisions - in
        decision order. One that will not clear the scan is skipped with its event; the
        rest are written."""
        declared = list(identifiers)
        written = []
        for decision in self.store.decisions(run_id):
            if not decision.writes_precedent:
                continue
            try:
                written.append(
                    self.write(
                        run_id,
                        decision.item_id,
                        client_id=client_id,
                        scope_path=scope_path,
                        identifiers=declared,
                    )
                )
            except WritebackRefused as refused:
                if refused.diagnostic.code != UNMASKED_PRECEDENT:
                    raise
        return tuple(written)

    def _emit(
        self,
        run_id: str,
        engagement_id: str,
        event_type: str,
        message: str,
        *,
        level: str | None = None,
        diagnostic_code: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type=event_type,
            message=message,
            level=level,
            diagnostic_code=diagnostic_code,
            payload=payload or {},
        )


def _split_scope(scope_path: str) -> tuple[str, str, str]:
    parts = scope_path.split("/")
    if len(parts) != 3 or not all(parts):
        raise ValueError(f"{scope_path!r} is not a practice/segment/disposition path")
    return parts[0], parts[1], parts[2]
