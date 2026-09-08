"""Engagement Binding: stamps every incoming file with which deal it belongs to.

Resolves an incoming item to exactly one engagement_id before anything reads it. Fails
closed: an unbound file is never processed "to figure out later what it is". The single
cheapest defence against cross-client contamination, and the one that has to happen
first - before extraction, before masking, before any model call.

Two bindings, both by convention and both closed:

* **Engagement**, from the folder the sweep found the file under. The file's path must
  sit under the target's location, and the engagement must be active on the roster at
  the moment of binding - the planner's answer is not trusted twice.
* **Document type**, from the filename against the configuration's convention table.
  A filename matching no declared type is *held*: recorded, reported, never processed,
  and never guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from intake.config import ConfigStore
from intake.roster import ProjectRoster
from intake.sweep import SweepTarget
from ports.storage import FileRef
from registries.errors import NO_ENGAGEMENT, RegistryError, diagnose

__all__ = ["Bound", "EngagementBinder", "bind_document_type"]


@dataclass(frozen=True)
class Bound:
    ref: FileRef
    engagement_id: str
    watch_id: str
    document_type: str | None
    """None means held: no declared type claims this filename."""

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
        return Bound(
            ref=ref,
            engagement_id=entry.engagement_id,
            watch_id=target.watch_id,
            document_type=bind_document_type(filename, self.config.conventions()),
        )


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
