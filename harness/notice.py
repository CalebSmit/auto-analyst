"""The Fixed Notice: when something fails, a fixed message - never an improvised one.

Hard-coded copy for the moments a person is told the system stopped: a blocked release,
an unreachable source, a missing template, a reference-data miss, a quarantined step
with a partial result, a configuration error. No model is anywhere on this path. Nothing
here is generated, so there is nothing to scan.

Two rules the tests hold this module to:

* **Display names only.** A notice names the engagement, the document, the step as a
  person knows it. No node ids, no internal paths, no folder names, no step keys. The
  templates are checked for that, and the values handed in are not interpolated by any
  format engine that could be steered into leaking one.
* **Fixed strings cannot improvise.** The failure this prevents is a calling agent
  narrating around a missing dependency instead of surfacing it. A template with an
  unknown placeholder is refused at import time; a call with a missing value is refused
  at call time. There is no default text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from registries.errors import Diagnostic

__all__ = ["NOTICES", "Notice", "notice", "notice_for"]

_PLACEHOLDER: Final = re.compile(r"\{([a-z_]+)\}")

# Every placeholder any template may use, and what it means. A template naming one
# outside this list is a defect caught at import.
DISPLAY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "engagement",  # the engagement's display name, e.g. "Henderson Manufacturing"
        "document",  # a filename as the client sent it
        "step",  # the step's label, e.g. "EBITDA normalization"
        "deliverable",  # the deliverable's display name, e.g. "FY25 monthly refresh"
        "source",  # a source system's display name, e.g. "ShareFile"
        "dataset",  # a reference dataset's display name
        "term",  # what was looked up and not found
        "owner",  # who the diagnostic says acts next
        "what_now",  # the diagnostic's what_now
        "completed",  # how many steps finished
        "total",  # how many steps the plan had
        "check",  # the QC check that failed, by its display name
        "template",  # the template's display name
    }
)


@dataclass(frozen=True)
class Notice:
    kind: str
    text: str


NOTICES: Final[dict[str, str]] = {
    "blocked_release": (
        "The {deliverable} for {engagement} was not released. The check "
        "'{check}' did not pass, and nothing partial is sent. {owner} has been told what "
        "to do next."
    ),
    "unreachable_source": (
        "{source} could not be reached, so the run for {engagement} stopped before "
        "reading anything. Nothing was processed. It will be tried again when {source} "
        "is back; no action is needed unless this notice repeats."
    ),
    "missing_template": (
        "No template named '{template}' is registered for {engagement}, so the "
        "{deliverable} was not written. Register the template, then re-run."
    ),
    "not_in_dataset": (
        "'{term}' is not in {dataset}. Nothing was estimated in its place. Add the "
        "entry to {dataset} or correct the term, then re-run the step."
    ),
    "quarantined_partial": (
        "The run for {engagement} stopped at '{step}' after trying every way it is "
        "allowed to. {completed} of {total} steps finished and their results are kept; "
        "nothing is released until '{step}' is resolved. A review item is waiting with "
        "the full context."
    ),
    "config_error": (
        "The run for {engagement} could not start. The configuration is wrong and the "
        "run will not guess. {owner} owns the fix: {what_now}"
    ),
    "diagnostic": "{step} did not complete. Owner: {owner}. What to do: {what_now}",
}

# A leaked internal would look like one of these. Kept as data so a new template is
# checked by the same rule as the old ones.
_INTERNAL_LOOKING: Final = (
    re.compile(r"[a-z]+_[a-z]+"),  # node_ids and step_ids
    re.compile(r"[A-Za-z0-9]+/[A-Za-z0-9]+"),  # paths
    re.compile(r"sha256"),  # keys and hashes
    re.compile(r"\.(py|yaml|json)\b"),  # file names
)


def _check_templates() -> None:
    for kind, template in NOTICES.items():
        for name in _PLACEHOLDER.findall(template):
            if name not in DISPLAY_FIELDS:
                raise ValueError(f"notice {kind!r} uses {name!r}, which is not a display field")
        stripped = _PLACEHOLDER.sub("", template)
        for pattern in _INTERNAL_LOOKING:
            if pattern.search(stripped):
                raise ValueError(f"notice {kind!r} contains internal-looking text")


_check_templates()


def notice(kind: str, **display: object) -> Notice:
    """The fixed message for a situation, with display names filled in.

    Substitution is a plain replace of known placeholders, not `str.format`: a value
    containing braces is text, never a directive.
    """
    if kind not in NOTICES:
        raise KeyError(f"no fixed notice for {kind!r}; the set is closed")
    template = NOTICES[kind]
    needed = set(_PLACEHOLDER.findall(template))
    missing = needed - set(display)
    if missing:
        raise ValueError(f"notice {kind!r} needs {sorted(missing)}; there is no default text")
    text = _PLACEHOLDER.sub(lambda m: str(display[m.group(1)]), template)
    return Notice(kind=kind, text=text)


def notice_for(diagnostic: Diagnostic, *, step: str, engagement: str = "") -> Notice:
    """The message a person sees for a diagnostic: the owner and the next action, under
    the step's display name. The code and locator stay in the record, not in the copy."""
    if diagnostic.owner == "config":
        return notice(
            "config_error",
            engagement=engagement or "this engagement",
            owner=_owner_display(diagnostic.owner),
            what_now=diagnostic.what_now,
        )
    return notice(
        "diagnostic",
        step=step,
        owner=_owner_display(diagnostic.owner),
        what_now=diagnostic.what_now,
    )


_OWNER_DISPLAY: Final = {
    "client-data": "The client contact",
    "model": "The skill owner",
    "system": "IT",
    "policy": "The policy owner",
    "config": "The administrator",
    "process": "The engagement owner",
}


def _owner_display(owner: str) -> str:
    return _OWNER_DISPLAY.get(owner, owner)
