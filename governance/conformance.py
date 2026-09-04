"""The Conformance Check: two scans and a diff, then a gap report.

A rough draft is a document from outside the system and gets the same treatment as a
client document: assume nothing, scan first.

**Scan one, injection.** The same `UntrustedBoundary` a client PDF meets. A strong hit
holds the draft in triage and it goes no further.

**Scan two, client data.** Pattern-based, because governance has no engagement
credentials and no vault - the isolation is that the connection does not exist, not that
a permission denies it. So the patterns live here rather than being imported from
`privacy/`, which would give this module a reason to reach the masking layer. It errs
toward flagging and a person clears it: somebody drafting a skill will paste a real trial
balance in as an example sooner or later, and that must not quietly become a file in the
repo.

**The diff.** The draft against the Skill Contract: frontmatter that is missing, tools
that are not in the constraint registry, an output contract that is not pinned, a scope
layer that does not exist, no escalation rules, no fixtures. The gap report is what makes
adaptation tractable - it turns "make this fit" into a checklist instead of a judgment
about where to begin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from governance.candidate import Stage
from governance.record import GovernanceRecord
from guards.untrusted import UntrustedBoundary
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.errors import CLIENT_DATA_IN_DRAFT, DiagnosticError, diagnose
from registries.scopes import ScopeRegistry
from registries.skills import REQUIRED_FRONTMATTER

__all__ = ["ConformanceCheck", "DraftHeld", "Gap", "GapReport"]

NODE = "skill_conformance"

# What real client data looks like from outside a vault. Deliberately broad: this errs
# toward flagging, and a person clears it. A synthetic example that trips one of these
# should be rewritten rather than exempted - an example that looks like a client file is
# one somebody will later mistake for one.
CLIENT_DATA_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("ein", re.compile(r"\b\d{2}-\d{7}\b")),
    ("account number", re.compile(r"\b\d{4,5}[-.]\d{2,4}(?:[-.]\d{2,4})?\b")),
    ("money over a thousand", re.compile(r"[$€£]\s?\d{1,3}(?:,\d{3})+(?:\.\d{2})?\b")),
    ("engagement id", re.compile(r"\b[A-Z]{4}-20\d{2}-\d{2}\b")),
    ("email address", re.compile(r"\b[\w.+-]+@(?!example[.]|chartwell[.]invalid)[\w-]+[.]\w{2,}")),
)

# The half of the Skill Contract that is a shape, not a value. `registries.skills`
# already names what a SKILL.md must declare; this adds what each declaration has to
# resolve against.
SENSITIVITY = ("masked_only", "masked_with_context", "unmasked")
HITL_REQUIRED = ("hitl",)


@dataclass(frozen=True)
class Gap:
    """One thing the draft has to gain before it is a skill."""

    field: str
    why: str
    fixable_by_bench: bool = True
    """False for anything only a person can supply. Fixtures are the whole point of the
    distinction: they are evidence, and evidence cannot be authored by the thing it
    vouches for."""

    def line(self) -> str:
        return f"{'[bench]' if self.fixable_by_bench else '[person]'} {self.field}: {self.why}"


@dataclass(frozen=True)
class GapReport:
    candidate_id: str
    gaps: tuple[Gap, ...] = ()
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    injection_findings: tuple[str, ...] = ()
    client_data_findings: tuple[str, ...] = ()

    @property
    def conforms(self) -> bool:
        return not self.gaps

    @property
    def for_the_bench(self) -> tuple[Gap, ...]:
        return tuple(g for g in self.gaps if g.fixable_by_bench)

    @property
    def for_a_person(self) -> tuple[Gap, ...]:
        return tuple(g for g in self.gaps if not g.fixable_by_bench)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "conforms": self.conforms,
            "gaps": [{"field": g.field, "why": g.why, "bench": g.fixable_by_bench} for g in
                     self.gaps],
            "injection_findings": list(self.injection_findings),
            "client_data_findings": list(self.client_data_findings),
        }

    def report(self) -> str:
        if self.conforms:
            return f"{self.candidate_id}: conforms to the skill contract"
        return "\n".join([f"{self.candidate_id}: {len(self.gaps)} gap(s)"] +
                         [f"  {g.line()}" for g in self.gaps])


class DraftHeld(DiagnosticError):
    """A scan hit. The draft stays in triage and reaches nothing."""


class ConformanceCheck:
    def __init__(
        self,
        record: GovernanceRecord,
        contracts: ContractRegistry | None = None,
        constraints: ConstraintRegistry | None = None,
        scopes: ScopeRegistry | None = None,
    ) -> None:
        self.record = record
        self.contracts = contracts or ContractRegistry.load()
        self.constraints = constraints or ConstraintRegistry.load()
        self.scopes = scopes or ScopeRegistry.load()
        self.boundary = UntrustedBoundary()
        self._layers: frozenset[str] | None = None

    def scan(self, candidate_id: str, text: str, checked_by: str = NODE) -> GapReport:
        """Both scans and the diff. Raises on a hit; returns the gap report otherwise."""
        injection = self.boundary.check(text, source_id=candidate_id, label="skill_draft")
        client_data = find_client_data(text)
        if not injection.passed or client_data:
            self._hold(candidate_id, injection.reasons, client_data, checked_by)

        frontmatter, body = split_frontmatter(text)
        report = GapReport(
            candidate_id=candidate_id,
            gaps=self._diff(frontmatter, body),
            frontmatter=frontmatter,
            body=body,
            injection_findings=tuple(injection.reasons),
            client_data_findings=tuple(f"{kind}: {found}" for kind, found in client_data),
        )
        self.record.append(
            candidate_id,
            Stage.SCANNED,
            actor=checked_by,
            ref=f"gaps:{len(report.gaps)}",
            detail={"node": NODE, "gap_report": report.as_dict()},
        )
        return report

    # -- the two scans

    def _hold(
        self,
        candidate_id: str,
        injection: tuple[str, ...],
        client_data: list[tuple[str, str]],
        checked_by: str,
    ) -> None:
        found = [f"{kind}: {text}" for kind, text in client_data]
        d = diagnose(
            CLIENT_DATA_IN_DRAFT if client_data else "INTAKE.INJECTION_DETECTED",
            (
                f"the draft carries {len(client_data)} thing(s) that look like client data "
                f"({', '.join(kind for kind, _ in client_data)})"
                if client_data
                else f"the draft carries an instruction aimed at a model: {'; '.join(injection)}"
            ),
            locator=candidate_id,
        )
        self.record.append(
            candidate_id,
            "held",
            actor=checked_by,
            ref=d.code,
            detail={
                "node": NODE,
                "injection": list(injection),
                "client_data": found,
                "what_now": d.what_now,
            },
        )
        raise DraftHeld(d)

    # -- the diff against the skill contract

    def _diff(self, frontmatter: dict[str, Any], body: str) -> tuple[Gap, ...]:
        gaps: list[Gap] = []
        for key in REQUIRED_FRONTMATTER:
            if not frontmatter.get(key):
                gaps.append(Gap(key, "the skill contract requires it and the draft has none"))

        tools = frontmatter.get("tools") or []
        for tool in tools if isinstance(tools, list) else [tools]:
            if str(tool) not in self.constraints.tools:
                gaps.append(
                    Gap(
                        "tools",
                        f"{tool!r} is not in the constraint registry's namespace "
                        f"({', '.join(sorted(self.constraints.tools))})",
                    )
                )

        contract = frontmatter.get("output_contract")
        if contract and str(contract) not in self.contracts.ids():
            gaps.append(
                Gap(
                    "output_contract",
                    f"{contract!r} is not pinned in the contract registry; an unpinned "
                    f"version is never resolved to a guess",
                )
            )

        layer = frontmatter.get("scope")
        if layer and not self._layer_exists(str(layer)):
            gaps.append(Gap("scope", f"{layer!r} is not a layer the scope registry declares"))

        sensitivity = frontmatter.get("data_sensitivity")
        if sensitivity and str(sensitivity) not in SENSITIVITY:
            gaps.append(
                Gap("data_sensitivity", f"{sensitivity!r} is not one of {', '.join(SENSITIVITY)}")
            )

        if "when not to use" not in body.lower():
            gaps.append(
                Gap(
                    "when not to use",
                    "the contract asks every skill to say where it does not apply; a skill "
                    "that never declines is one that fires where it should not",
                )
            )
        if not frontmatter.get("escalate") and "escalat" not in body.lower():
            gaps.append(Gap("escalation rules", "nothing says when this hands to a person"))
        if not frontmatter.get("fixtures"):
            gaps.append(
                Gap(
                    "fixtures",
                    "no fixture set is named. The bench cannot supply these: they are "
                    "evidence the skill works, and evidence does not come from the thing "
                    "being tested",
                    fixable_by_bench=False,
                )
            )
        return tuple(gaps)

    def _layer_exists(self, layer: str) -> bool:
        return layer in self.valid_layers()

    def valid_layers(self) -> frozenset[str]:
        """Every layer any declared scope path resolves through. A new skill may target a
        layer no skill occupies yet - that is the ordinary case for the first skill in a
        practice group - so this asks the scope registry rather than the tree."""
        if self._layers is None:
            found: set[str] = set()
            for scope in self.scopes.combinations():
                found.update(self.scopes.layers_for(scope))
            self._layers = frozenset(found)
        return self._layers


def find_client_data(text: str) -> list[tuple[str, str]]:
    """Everything in the draft that looks like it came from a real engagement."""
    found: list[tuple[str, str]] = []
    for kind, pattern in CLIENT_DATA_PATTERNS:
        for match in pattern.finditer(text):
            found.append((kind, match.group(0)))
    return found


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """YAML frontmatter and the body. A draft with neither is not an error here - it is
    the ordinary case, and every missing field becomes a gap."""
    if not text.lstrip().startswith("---"):
        return {}, text
    parts = text.lstrip().split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        loaded = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}, parts[2]
    return (loaded if isinstance(loaded, dict) else {}), parts[2]


def read_draft(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")
