"""The job manifest: what the orchestrator is shown, and the boundary of what it may see.

Three things, per the blueprint: the masked document summary, the classification, and
the engagement profile. Plus the menu of named recipes, because the first question is
"is this the routine shape of a job", and a model that cannot see the recipes can only
answer it by composing one from scratch.

What is deliberately not here:

* **No figures.** A document summary is filenames, declared types and period labels. Not
  a trial balance, not a total, not a single value - the orchestrator is routing, and a
  router that can see the numbers is a router that can be wrong about them.
* **No skill bodies.** The skill footprint in this context is the Skill Index: name and
  one-line description, Tier 1, assembled by the resolved scope. The bodies stay on disk
  until a skill is actually dispatched.
* **No unmasked identifiers.** The manifest is rendered to text, masked, and put through
  the untrusted boundary like any other document-derived content, because most of what
  is in it came from a client file.

`content_hash` is over the rendered text, so "same inputs, same plan" is a claim about
something with an identity rather than about a dataclass somebody might extend.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = ["DocumentSummary", "JobManifest", "RecipeOption"]


@dataclass(frozen=True)
class DocumentSummary:
    """One arrived document, as the orchestrator is allowed to see it."""

    filename: str
    document_type: str
    """The classification, or `unknown` when binding declined to guess."""
    periods: tuple[str, ...] = ()
    """Period labels the reader found. Labels, never their contents."""
    note: str = ""

    def line(self) -> str:
        parts = [f"{self.filename} [{self.document_type}]"]
        if self.periods:
            parts.append(f"periods: {', '.join(self.periods)}")
        if self.note:
            parts.append(self.note)
        return " - ".join(parts)


@dataclass(frozen=True)
class RecipeOption:
    """A named recipe, as a line on a menu."""

    name: str
    title: str
    description: str
    required_types: tuple[str, ...] = ()

    def line(self) -> str:
        required = f" (needs: {', '.join(self.required_types)})" if self.required_types else ""
        return f"{self.name}: {self.description}{required}"


@dataclass(frozen=True)
class JobManifest:
    """Everything the orchestrator reads about this job."""

    engagement_id: str
    scope_path: str
    documents: tuple[DocumentSummary, ...]
    profile: Mapping[str, Any] = field(default_factory=dict)
    """The engagement profile, as configuration recorded it. Labels and conventions -
    industry, fiscal year end, review level - never a figure."""
    recipes: tuple[RecipeOption, ...] = ()
    fallback_recipe: str = ""
    """The named recipe this engagement runs when the proposal is not used. There is
    always one: a run that cannot fall back is a run that depends on a model answering
    well, which is the dependency this whole phase exists to avoid."""
    run_inputs: tuple[str, ...] = ()
    """What arrives from outside the plan and may be named in a step's run_inputs."""
    coverage_gaps: tuple[str, ...] = ()
    """Required document types that never arrived. The Intake Window recorded them; the
    orchestrator sees them because a plan for an incomplete set is a different plan."""
    note: str = ""

    def as_prompt(self) -> str:
        """The manifest as text. This exact string is what gets masked and wrapped."""
        lines = [
            "# Job manifest",
            f"engagement: {self.engagement_id}",
            f"scope: {self.scope_path}",
            "",
            "## Documents that arrived",
            *(f"- {d.line()}" for d in self.documents),
        ]
        if self.coverage_gaps:
            lines += [
                "",
                "## Declared document types that never arrived",
                *(f"- {gap}" for gap in self.coverage_gaps),
            ]
        if self.profile:
            lines += ["", "## Engagement profile", *_profile_lines(self.profile)]
        if self.recipes:
            lines += [
                "",
                "## Named recipes available",
                *(f"- {r.line()}" for r in self.recipes),
            ]
        if self.run_inputs:
            lines += ["", f"## Run inputs available: {', '.join(self.run_inputs)}"]
        if self.note:
            lines += ["", self.note]
        return "\n".join(lines)

    def content_hash(self) -> str:
        return "sha256:" + hashlib.sha256(self.as_prompt().encode("utf-8")).hexdigest()


def _profile_lines(profile: Mapping[str, Any]) -> list[str]:
    """The profile flattened to `key: value` lines, in key order, one level deep.

    Sorted rather than as-written so the same profile renders identically whatever built
    the mapping - the reproducibility claim is over this text.
    """
    lines: list[str] = []
    for key in sorted(profile):
        value = profile[key]
        if isinstance(value, Mapping):
            inner = ", ".join(f"{k}={value[k]}" for k in sorted(value))
            lines.append(f"- {key}: {inner}")
        elif isinstance(value, Sequence) and not isinstance(value, str):
            lines.append(f"- {key}: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"- {key}: {value}")
    return lines
