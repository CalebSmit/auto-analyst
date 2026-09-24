"""Engagement Binding: stamps every incoming file with which deal it belongs to.

Resolves an incoming item to exactly one engagement_id before anything reads it. Fails
closed: an unbound file is never processed "to figure out later what it is". The single
cheapest defence against cross-client contamination, and the one that has to happen
first - before extraction, before masking, before any model call.

Two bindings, both by convention and both closed:

* **Engagement**, from the folder the sweep found the file under. The file's path must
  sit under the target's location, and the engagement must be active on the roster at
  the moment of binding - the planner's answer is not trusted twice.
* **Document type**, from the filename against the configuration's convention table -
  and, when no token claims it, from the Document Classifier reading the name and the
  folder it sits in. A file neither claims is *held*: recorded, reported, never processed.

**"Never guessed" used to mean "conventions or nothing", and P103 narrowed it.** The rule
was right and the reading of it was too strict: ten of the first real client folder's
thirteen files were held, and nothing was wrong with any of them - the convention table
carries three types and a valuation receives a dozen. Holding a board minute because
nobody had written the token `minutes` into a config file is not caution, it is a list
somebody has to work through by hand every Monday.

What replaces it is narrower than "guess":

* a **convention always wins**. The firm declaring a token is a decision; a classification
  is evidence. Evidence does not overrule a decision.
* an inference must be **confident** - the classifier's own bar, the same one that decides
  whether a read goes to a person - and must name a type the **Contract Registry declares**.
  `gl_detail` and `cap_table` are classes the classifier can produce and the registry does
  not declare, and neither may bind.
* the binding **says which** did it, so an inferred type is visible as one everywhere it
  travels rather than looking like something the firm declared.
* everything else is still **held**. Emptying the held list was never the goal; a file
  nothing recognises is a question for a person, and that is a real answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from intake.config import ConfigStore
from intake.roster import ProjectRoster
from intake.sweep import SweepTarget
from ports.storage import FileRef
from registries.errors import NO_ENGAGEMENT, RegistryError, diagnose

__all__ = ["Bound", "EngagementBinder", "bind_document_type", "document_type_for"]


@dataclass(frozen=True)
class Bound:
    ref: FileRef
    engagement_id: str
    watch_id: str
    document_type: str | None
    """None means held: neither a convention nor a confident classification claims it."""

    bound_by: str = ""
    """`convention`, `classification`, or empty when held.

    On the binding rather than derivable from it, because "the firm declared this token"
    and "a classifier was confident" are different kinds of fact about the same field, and
    a person reading the intake record should not have to re-run the classifier to tell
    which they are looking at."""

    @property
    def filename(self) -> str:
        return self.ref.path.rsplit("/", 1)[-1]


class EngagementBinder:
    def __init__(self, roster: ProjectRoster, config: ConfigStore) -> None:
        self.roster = roster
        self.config = config

    def bind(self, ref: FileRef, target: SweepTarget) -> Bound:
        inside = ref.path.startswith(f"{target.location}/") if target.location else True
        if not inside:
            raise RegistryError(
                diagnose(
                    NO_ENGAGEMENT,
                    f"{ref.path} is not under {target.location}, the folder bound to "
                    f"{target.engagement_id}; nothing claims it",
                    locator=ref.path,
                )
            )
        entry = self.roster.get(target.engagement_id)
        if entry is None or not entry.is_active:
            state = "not on the roster" if entry is None else str(entry.state)
            raise RegistryError(
                diagnose(
                    NO_ENGAGEMENT,
                    f"{ref.path} maps to {target.engagement_id}, which is {state}; an "
                    f"inactive engagement has no path into the pipeline",
                    locator=ref.path,
                )
            )
        filename = ref.path.rsplit("/", 1)[-1]
        found, how = document_type_for(
            filename, self.config.conventions(), folders=_folders_under(ref.path, target)
        )
        return Bound(
            ref=ref,
            engagement_id=entry.engagement_id,
            watch_id=target.watch_id,
            document_type=found,
            bound_by=how,
        )


CONVENTION = "convention"
CLASSIFICATION = "classification"


def _folders_under(path: str, target: SweepTarget) -> tuple[str, ...]:
    """The folders between the engagement's own folder and the file.

    The engagement's location is stripped first: every file under it shares those
    segments, so they say nothing about any one document - and one of them is the client's
    name, which has no business reaching a classifier's cue table.
    """
    inside = path[len(target.location) + 1 :] if target.location else path
    return tuple(part for part in inside.split("/")[:-1] if part)


def _declared_types() -> frozenset[str]:
    """The intake document types the Contract Registry declares.

    Asked of the registry rather than of `CLASSES`, because the classifier can produce
    types the registry does not declare - `gl_detail` and `cap_table` at the time of
    writing - and a binding is a claim about a document's *type*, which is the registry's
    vocabulary and not the classifier's.
    """
    from registries.contracts import ContractRegistry  # noqa: PLC0415

    return frozenset(t.id for t in ContractRegistry.load().intake_document_types())


def document_type_for(
    filename: str,
    conventions: dict[str, tuple[str, ...]],
    *,
    folders: tuple[str, ...] = (),
) -> tuple[str | None, str]:
    """The document type, and which of the two ways found it.

    Conventions first and always. A classification is only asked for when no token claims
    the name, and only accepted when the classifier would not have sent the read to a
    person anyway - `review_required` is the same bar, so a binding is never more confident
    than the read that follows it.
    """
    declared = bind_document_type(filename, conventions)
    if declared is not None:
        return declared, CONVENTION

    from intake.readers.classify import Evidence, classify  # noqa: PLC0415

    found = classify(Evidence(filename=filename, folders=list(folders)))
    if found.review_required or found.document_type not in _declared_types():
        return None, ""
    return found.document_type, CLASSIFICATION


def bind_document_type(filename: str, conventions: dict[str, tuple[str, ...]]) -> str | None:
    """The declared type whose tokens the filename carries, or None. Exactly one type
    may match; two matching types is an ambiguity, and an ambiguity is not a binding."""
    name = filename.lower()
    matched = sorted(
        doc_type
        for doc_type, tokens in conventions.items()
        if any(_token_in(t.lower(), name) for t in tokens)
    )
    return matched[0] if len(matched) == 1 else None


def _token_in(token: str, name: str) -> bool:
    """A short token - `tb`, `is`, `bs`, `fs` - matches only as a whole word, so `is` does
    not claim `analysis.xlsx` and `bs` does not claim `subs.xlsx`. Anything longer is what
    people actually write out, and matches anywhere in the name as it always has."""
    if len(token) <= 3 and token.isalnum():
        return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", name) is not None
    return token in name
