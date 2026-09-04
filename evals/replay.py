"""The Replay Harness: re-runs past engagements against a candidate and diffs the result.

Falls out of the rest of the design: the dispatcher records what each step was given
(`inputs:<step>`), what the model answered (`proposal:<step>`) and what the step emitted
(`output:<step>`) as content-addressed blobs, and the `skill.completed` event names all
three. Replaying a step is restoring its recorded inputs and running a candidate over
them. The harness reads those blobs and the run store - never the vault and never a
released artifact - so it stays inside the sandbox isolation: the skill only ever saw
masked data, and the candidate sees exactly what the original saw.

The answer is a diff, not a pass/fail: every path that changed between what was
delivered and what the candidate produced, and - where a person later corrected an item
on that run - whether the candidate agrees with the correction. A diff of zero on fifty
runs is a very different kind of confidence from a green fixture suite.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from harness.procedures.ebitda_normalization import (
    Benchmark,
    EbitdaInputs,
    Line,
    VerificationInputs,
)
from harness.procedures.line_item_tagging import LineItem, TaggingInputs
from harness.procedures.model_load import FigureRef, ModelLoadInputs, TemplateInput
from harness.procedures.timing_normalization import SourceFile, TimingInputs
from ops.blobs import ContentRef, ContentStore
from ops.models import DecisionKind
from ops.run_store import RunStore
from review.log import DecisionLog

__all__ = [
    "Change",
    "CorrectionCheck",
    "Replay",
    "ReplayHarness",
    "StepRecord",
    "json_diff",
    "restore",
]

ID_KEYS = ("line_item_ref", "candidate_id", "named_range", "canonical_label", "figure_ref")


@dataclass(frozen=True)
class Change:
    path: str
    before: Any
    after: Any

    def line(self) -> str:
        return f"{self.path}: {self.before!r} -> {self.after!r}"


@dataclass(frozen=True)
class CorrectionCheck:
    """A human correction on the original run, and whether the candidate agrees."""

    item_id: str
    decided_by: str
    answer: dict[str, Any]
    candidate: dict[str, Any] | None
    agrees: bool


@dataclass(frozen=True)
class StepRecord:
    run_id: str
    step_id: str
    skill: str
    inputs_ref: str
    proposal_ref: str
    output_ref: str


@dataclass(frozen=True)
class Replay:
    record: StepRecord
    candidate_skill: str
    delivered: dict[str, Any]
    candidate: dict[str, Any]
    changes: tuple[Change, ...]
    corrections: tuple[CorrectionCheck, ...]

    @property
    def unchanged(self) -> bool:
        return not self.changes

    def report(self) -> str:
        head = (
            f"replay {self.record.run_id}/{self.record.step_id}: {self.record.skill} -> "
            f"{self.candidate_skill}: {len(self.changes)} change(s)"
        )
        lines = [head, *(f"  {c.line()}" for c in self.changes[:50])]
        if len(self.changes) > 50:
            lines.append(f"  ... {len(self.changes) - 50} more")
        for c in self.corrections:
            lines.append(
                f"  correction on {c.item_id} by {c.decided_by}: "
                f"{'candidate agrees' if c.agrees else 'candidate disagrees'}"
            )
        return "\n".join(lines)


class ReplayHarness:
    def __init__(self, store: RunStore, blobs: ContentStore) -> None:
        self.store = store
        self.blobs = blobs

    # -- what was recorded

    def records(self, run_id: str) -> tuple[StepRecord, ...]:
        found = []
        for event in self.store.events(run_id):
            if event.type != "skill.completed":
                continue
            p = event.payload
            if not all(k in p for k in ("inputs_ref", "proposal_ref", "output_ref")):
                continue
            found.append(
                StepRecord(
                    run_id=run_id,
                    step_id=str(event.step_id),
                    skill=str(p.get("skill", "")),
                    inputs_ref=str(p["inputs_ref"]),
                    proposal_ref=str(p["proposal_ref"]),
                    output_ref=str(p["output_ref"]),
                )
            )
        return tuple(found)

    def record_for(self, run_id: str, step_id: str, skill: str | None = None) -> StepRecord:
        matches = [
            r
            for r in self.records(run_id)
            if r.step_id == step_id and (skill is None or r.skill.split("@")[0] == skill)
        ]
        if not matches:
            raise KeyError(f"{run_id}/{step_id}: no recorded skill step to replay")
        return matches[-1]  # the pass that was delivered: the last one on the record

    def inputs_of(self, record: StepRecord) -> Any:
        return restore(record.skill, self._json(record.inputs_ref))

    def delivered(self, record: StepRecord) -> dict[str, Any]:
        body: dict[str, Any] = self._json(record.output_ref)
        return body

    def _json(self, content_hash: str) -> Any:
        return json.loads(self.blobs.get(_ref(content_hash)).decode("utf-8"))

    # -- the replay

    def replay(
        self,
        run_id: str,
        step_id: str,
        candidate: Callable[[Any], Mapping[str, Any]],
        *,
        candidate_skill: str,
        skill: str | None = None,
    ) -> Replay:
        """Restore the step's recorded inputs, run the candidate over them, diff."""
        record = self.record_for(run_id, step_id, skill)
        inputs = self.inputs_of(record)
        before = self.delivered(record)
        after = dict(candidate(inputs))
        changes = json_diff(before, after)
        corrections = tuple(self._corrections(run_id, after))
        return Replay(
            record=record,
            candidate_skill=candidate_skill,
            delivered=before,
            candidate=after,
            changes=changes,
            corrections=corrections,
        )

    def _corrections(self, run_id: str, candidate: dict[str, Any]) -> list[CorrectionCheck]:
        checks = []
        for decision in DecisionLog(self.store).entries(run_id):
            if decision.decision is not DecisionKind.CORRECTED or not decision.answer:
                continue
            item = _find_item(candidate, decision.item_id)
            agrees = item is not None and all(
                item.get(k) == v for k, v in decision.answer.items() if k in item
            )
            checks.append(
                CorrectionCheck(
                    item_id=decision.item_id,
                    decided_by=decision.decided_by,
                    answer=dict(decision.answer),
                    candidate=item,
                    agrees=agrees,
                )
            )
        return checks


# ------------------------------------------------------------------ the diff


def json_diff(before: Any, after: Any, path: str = "$") -> tuple[Change, ...]:
    """Every path that differs. Lists of keyed objects align by their id, so a moved
    item is not reported as every field of two items changing."""
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[Change] = []
        for key in sorted(set(before) | set(after)):
            if key not in before:
                changes.append(Change(f"{path}.{key}", None, after[key]))
            elif key not in after:
                changes.append(Change(f"{path}.{key}", before[key], None))
            else:
                changes.extend(json_diff(before[key], after[key], f"{path}.{key}"))
        return tuple(changes)
    if isinstance(before, list) and isinstance(after, list):
        key = _id_key(before) or _id_key(after)
        if key:
            b = {str(x[key]): x for x in before if isinstance(x, dict) and key in x}
            a = {str(x[key]): x for x in after if isinstance(x, dict) and key in x}
            changes = []
            for k in sorted(set(b) | set(a)):
                where = f"{path}[{key}={k}]"
                if k not in b:
                    changes.append(Change(where, None, a[k]))
                elif k not in a:
                    changes.append(Change(where, b[k], None))
                else:
                    changes.extend(json_diff(b[k], a[k], where))
            return tuple(changes)
        changes = []
        for n in range(max(len(before), len(after))):
            if n >= len(before):
                changes.append(Change(f"{path}[{n}]", None, after[n]))
            elif n >= len(after):
                changes.append(Change(f"{path}[{n}]", before[n], None))
            else:
                changes.extend(json_diff(before[n], after[n], f"{path}[{n}]"))
        return tuple(changes)
    if before != after:
        return (Change(path, before, after),)
    return ()


def _id_key(items: list[Any]) -> str | None:
    if not items or not all(isinstance(x, dict) for x in items):
        return None
    for key in ID_KEYS:
        if all(key in x for x in items):
            return key
    return None


def _find_item(body: Any, item_id: str) -> dict[str, Any] | None:
    if isinstance(body, dict):
        if any(body.get(k) == item_id for k in ID_KEYS):
            return body
        for value in body.values():
            found = _find_item(value, item_id)
            if found is not None:
                return found
    elif isinstance(body, list):
        for value in body:
            found = _find_item(value, item_id)
            if found is not None:
                return found
    return None


def _ref(content_hash: str) -> ContentRef:
    return ContentRef(content_hash=content_hash, size_bytes=0, media_type="application/json")


# ------------------------------------------------------------------ restoring inputs


def restore(skill: str, data: Mapping[str, Any]) -> Any:
    """A procedure's inputs object, from what the dispatcher recorded of it."""
    name = skill.split("@", 1)[0]
    if name == "timing-normalization":
        return TimingInputs(
            files=tuple(
                SourceFile(
                    source_id=f["source_id"],
                    filename=f["filename"],
                    document_type=f["document_type"],
                    blocks=f["blocks"],
                    scale=f["scale"],
                    currency=f["currency"],
                    period_type=f["period_type"],
                    period_ends=tuple(f["period_ends"]),
                    ambiguous=tuple(f.get("ambiguous", ())),
                    source_version=int(f.get("source_version", 1)),
                    block_periods=dict(f.get("block_periods", {})),
                )
                for f in data["files"]
            )
        )
    if name == "line-item-tagging":
        return TaggingInputs(
            items=tuple(
                LineItem(
                    line_item_ref=i["line_item_ref"],
                    description=i["description"],
                    source_labels=tuple(i.get("source_labels", ())),
                    statement_hint=i.get("statement_hint"),
                    periods=tuple(i.get("periods", ())),
                )
                for i in data["items"]
            ),
            taxonomy_version=data["taxonomy_version"],
            auto_accept_confidence=data.get("auto_accept_confidence"),
            always_review_categories=frozenset(data.get("always_review_categories", ())),
        )
    if name == "ebitda-normalization":
        if "schedule" in data:
            return VerificationInputs(
                schedule=dict(data["schedule"]),
                descriptions=dict(data["descriptions"]),
                blocks=dict(data["blocks"]),
            )
        b = data.get("benchmark")
        return EbitdaInputs(
            periods=tuple(data["periods"]),
            lines=tuple(
                Line(
                    line_item_ref=ln["line_item_ref"],
                    description=ln["description"],
                    category=ln["category"],
                    excluded_from_al=bool(ln["excluded_from_al"]),
                    include_in_nwc=bool(ln["include_in_nwc"]),
                    source_labels=tuple(ln.get("source_labels", ())),
                    figures=dict(ln["figures"]),
                )
                for ln in data["lines"]
            ),
            blocks=dict(data["blocks"]),
            benchmark=Benchmark(**b) if isinstance(b, dict) else None,
            materiality_amount=float(data["materiality_amount"]),
            materiality_currency=str(data["materiality_currency"]),
            auto_accept_confidence=data.get("auto_accept_confidence"),
            always_review_categories=frozenset(data.get("always_review_categories", ())),
        )
    if name == "model-load":
        return ModelLoadInputs(
            template_key=data["template_key"],
            template_version=data["template_version"],
            inputs=tuple(TemplateInput(**i) for i in data["inputs"]),
            catalogue=tuple(
                FigureRef(
                    figure_ref=c["figure_ref"],
                    source_output=c["source_output"],
                    description=c["description"],
                    period=c["period"],
                    figure=c["figure"],
                )
                for c in data["catalogue"]
            ),
            periods=tuple(data.get("periods", ())),
        )
    raise KeyError(f"no restorer for {name!r}")
