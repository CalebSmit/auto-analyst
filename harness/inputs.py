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
from dataclasses import dataclass
from typing import Any

from harness.procedures.ebitda_normalization import (
    EbitdaInputs,
    VerificationInputs,
)
from harness.procedures.line_item_tagging import TaggingInputs
from harness.procedures.model_load import catalogue_from, inputs_from
from harness.procedures.timing_normalization import SourceFile, TimingInputs
from ops.blobs import ContentRef, ContentStore

__all__ = ["InputsUnavailable", "RunFacts", "build_inputs"]


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
        return TimingInputs(files=facts.sources)

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
        catalogue = catalogue_from(timing, facts.profile, period_slots=facts.period_slots)
        return inputs_from(
            facts.template.key,
            facts.template.template_version,
            [i.as_row() for i in facts.template.inputs.inputs],
            catalogue,
            periods=facts.periods,
        )

    raise InputsUnavailable(
        f"{step_id} runs {name!r}, which has no mechanical half yet - a skill whose "
        f"procedure is not built cannot be handed anything"
    )
