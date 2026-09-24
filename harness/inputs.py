"""What each skill step is handed, built from what the steps before it produced.

The executor walks a plan and hands a runner an `Attempt`: a step, and refs to whatever
its declared inputs resolved to. A procedure wants something else - a typed object shaped
for the work it does, built from those upstream outputs plus facts about the engagement.
This is the translation, and it is the piece that was missing between the two.

**One function per skill, in one table.** Not because a table is elegant but because the
alternative is the caller choosing: a runner that took the inputs as an argument would put
"what does the tagging step see" in the hands of whoever wired it up that day, and the
answer would drift between the harness, the evaluator and whatever ran in production.

The constructors themselves already live on the procedures - `TaggingInputs.from_normalized`,
`EbitdaInputs.from_outputs`, `VerificationInputs.from_pass`. This module reads the refs and
calls them; it holds no domain logic of its own, and a change to what a skill needs belongs
in that skill's module rather than here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from harness.procedures.ebitda_normalization import (
    EbitdaInputs,
    VerificationInputs,
)
from harness.procedures.line_item_tagging import TaggingInputs
from harness.procedures.model_load import catalogue_from, inputs_from
from harness.procedures.timing_normalization import FiscalCalendar, SourceFile, TimingInputs
from ops.blobs import ContentRef, ContentStore

__all__ = ["InputsUnavailable", "RunFacts", "build_inputs", "slots_for"]


class InputsUnavailable(Exception):
    """A step asked for something the run does not have.

    Deliberately not a `DiagnosticError`: it means the plan and the run disagree about
    what exists - a step whose producer did not run, a template nobody bound - which is a
    wiring fault rather than a condition an engagement can be in. The executor turns it
    into a quarantine with the step named, which is the honest ending for a step that
    could not be started.
    """


@dataclass(frozen=True)
class RunFacts:
    """What every step of one run shares, and none of it changes mid-run.

    Held as one object rather than eight arguments because these travel together to every
    step, and a signature that takes eight of them is a signature somebody eventually
    passes in the wrong order.
    """

    profile: dict[str, Any]
    """The engagement profile, as written. Three skills read it."""
    policy: Any
    """The engagement's `CheckpointPolicy`: what is auto-accepted, what always goes to a
    person, and the materiality floor."""
    taxonomy_version: str
    sources: tuple[SourceFile, ...]
    """The parsed source documents, as the readers left them."""
    blocks: Any
    """source_id -> locator -> rows. What recompute sums, and what the tie-out gate
    checks a proposal against."""
    template: Any = None
    """The registered template this engagement builds into, or None before one is bound."""
    periods: tuple[str, ...] = ()
    period_slots: Any = None


def _read(blobs: ContentStore, ref: ContentRef) -> dict[str, Any]:
    loaded = json.loads(blobs.get(ref).decode("utf-8"))
    if not isinstance(loaded, dict):
        raise InputsUnavailable(f"{ref.content_hash} is not a step output")
    return loaded


def _upstream(
    step_id: str,
    name: str,
    refs: dict[str, ContentRef],
    blobs: ContentStore,
) -> dict[str, Any]:
    if name not in refs:
        raise InputsUnavailable(
            f"{step_id} needs the output of {name!r}, which this run does not have "
            f"(it has: {', '.join(sorted(refs)) or 'nothing'})"
        )
    return _read(blobs, refs[name])


def _with_periods(sources: tuple[Any, ...]) -> tuple[Any, ...]:
    """Only the sources of a kind that holds figures against periods.

    The registry decides, not this function: `carries_periods` is declared per intake
    document type, so adding a type forces an answer instead of inheriting one.

    Found on the first real client folder. P103 let all twelve bound files into the run,
    and `timing-normalization` was handed board minutes, an org chart and a competitor
    list. It reported each ambiguous - correctly, there are no periods in them - a person
    answered, the step re-ran and reported them again. Thirty passes, thirty review items,
    no progress. A document of a kind that carries no periods is not an ambiguity to
    resolve; it is a question the skill should never have been asked.

    The files are not dropped from the run. They are bound, on the record, and they answer
    request-list items; they are simply not shown to a skill that reads fiscal calendars.
    """
    from registries.contracts import ContractRegistry  # noqa: PLC0415

    dated = {
        t.id for t in ContractRegistry.load().intake_document_types() if t.carries_periods
    }
    return tuple(f for f in sources if f.document_type in dated)


def _calendar_of(profile: Mapping[str, Any] | None) -> FiscalCalendar | None:
    """The engagement's fiscal calendar, if a person recorded one.

    None rather than a December default. The whole reason this reaches the skill is that
    a year end which is assumed is a year end nobody stated, and substituting one here
    would put the system's guess where the guard expects a fact - with the added cruelty
    that it would be right most of the time and silently wrong for exactly the clients
    whose year does not end in December.
    """
    calendar = (profile or {}).get("fiscal_calendar")
    if not isinstance(calendar, Mapping):
        return None
    month, day = calendar.get("year_end_month"), calendar.get("year_end_day")
    if month is None or day is None:
        return None
    return FiscalCalendar(
        basis=str(calendar.get("basis") or "calendar"),
        year_end_month=int(month),
        year_end_day=int(day),
    )


def slots_for(
    timing_output: Mapping[str, Any], slots: Sequence[str]
) -> dict[str, str]:
    """Which of the client's fiscal years fills each of the template's slots.

    **FY1 is the earliest of the slots and the newest year takes the last.** That rule was
    already written down twice - in `evals.metrics.SLOTS`, which maps FY2023 to FY1 and
    FY2025 to FY3, and in the scripted analyst, which sorts the labels and zips them - and
    it was written down nowhere that production could read. `RunFacts.period_slots` was
    declared, read here, and set by nothing, so the catalogue went to the model keyed on
    the client's own labels while the template asked for FY1, and which was which was left
    for the model to infer.

    **More years than slots takes the most recent.** A folder carrying five years against
    three slots is the ordinary case and choosing among them is a judgement (B-073); the
    most recent three is the default an analyst would take, and it is stated in the payload
    so that taking a different three is a correction rather than an archaeology exercise.

    **Fewer years than slots leaves the surplus empty.** Stretching four years over three
    cells, or repeating one, would be inventing a period - and an unfilled input already
    has somewhere to go: it reaches a person and then says `not found` in its own cell.
    """
    table = timing_output.get("normalized_historicals") or {}
    ends: dict[str, str] = {}
    for period in table.get("periods") or ():
        label, end = str(period.get("label") or ""), str(period.get("end") or "")
        if label and end:
            ends.setdefault(label, end)
    ordered = sorted(ends, key=lambda label: (ends[label], label))
    most_recent = ordered[-len(slots) :] if slots else []
    return {label: slot for label, slot in zip(most_recent, slots, strict=False)}


def build_inputs(
    skill: str,
    step_id: str,
    refs: dict[str, ContentRef],
    facts: RunFacts,
    blobs: ContentStore,
    *,
    verifying: bool = False,
) -> Any:
    """The typed inputs for one skill step.

    `skill` is the plan's, not the caller's: the runner takes it from the step it was
    handed, so a step cannot be run as a different skill than the plan compiled.
    """
    name = skill.split("@", 1)[0]

    if name == "timing-normalization":
        if not facts.sources:
            raise InputsUnavailable(f"{step_id} has no parsed source documents to align")
        dated = _with_periods(facts.sources)
        if not dated:
            raise InputsUnavailable(
                f"{step_id} has {len(facts.sources)} source document(s) and none of a kind "
                f"that carries figures over periods "
                f"({', '.join(sorted({f.document_type for f in facts.sources}))}). "
                f"A run of statements is missing, or the folder is all narrative."
            )
        return TimingInputs(files=dated, calendar=_calendar_of(facts.profile))

    if name == "line-item-tagging":
        timing = _upstream(step_id, "timing", refs, blobs)
        return TaggingInputs.from_normalized(
            timing["normalized_historicals"],
            taxonomy_version=facts.taxonomy_version,
            auto_accept_confidence=facts.policy.auto_accept_confidence,
            always_review_categories=facts.policy.always_review_categories,
        )

    if name == "ebitda-normalization":
        timing = _upstream(step_id, "timing", refs, blobs)
        tagging = _upstream(step_id, "tagging", refs, blobs)
        first = EbitdaInputs.from_outputs(
            timing,
            tagging,
            facts.profile,
            facts.blocks,
            materiality_amount=facts.policy.materiality.amount,
            materiality_currency=facts.policy.materiality.currency,
            auto_accept_confidence=facts.policy.auto_accept_confidence,
            always_review_categories=facts.policy.always_review_categories,
        )
        if not verifying:
            return first
        # The verification pass sees the schedule and the evidence, and never the first
        # pass's reasoning. Which half it gets is the procedure's business, not this one's.
        schedule = _upstream(step_id, "schedule", refs, blobs)
        return VerificationInputs.from_pass(schedule, first)

    if name == "model-load":
        if facts.template is None:
            raise InputsUnavailable(
                f"{step_id} has no registered template bound for this engagement"
            )
        timing = _upstream(step_id, "timing", refs, blobs)
        # Derived here rather than carried on the facts: the mapping needs the periods
        # timing settled, and `_facts` is built before any source is read. `facts.period_slots`
        # stays as the override for a caller that has decided differently.
        slots = dict(facts.period_slots or {}) or slots_for(timing, facts.periods)
        catalogue = catalogue_from(timing, facts.profile, period_slots=slots)
        return inputs_from(
            facts.template.key,
            facts.template.template_version,
            [i.as_row() for i in facts.template.inputs.inputs],
            catalogue,
            periods=facts.periods,
            period_slots=tuple(slots.items()),
        )

    raise InputsUnavailable(
        f"{step_id} runs {name!r}, which has no mechanical half yet - a skill whose "
        f"procedure is not built cannot be handed anything"
    )
