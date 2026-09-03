"""Diagnostics, in the shape the blueprint requires of every failure path.

No registry raises a bare exception. Every failure carries a stable code, an owner and
what to do next, because a message nobody can act on is a defect: a tie-out mismatch is
usually the client's trial balance, a schema violation is our skill, a Box timeout is
infrastructure — and "the run failed" tells none of those three people anything.

The full diagnostics registry (the versioned enum of every code, with CI asserting that
each one has a ``what_now``) is a later phase. This module carries only the codes P02
can actually raise, in the right shape, so that later phase is an extension rather than
a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Owner = Literal["client-data", "model", "system", "policy", "config", "process"]


@dataclass(frozen=True)
class Diagnostic:
    """What a failure has to be able to say for itself."""

    code: str
    owner: Owner
    what_now: str
    detail: str = ""
    locator: str = ""

    def __str__(self) -> str:
        parts = [f"{self.code} [{self.owner}]"]
        if self.locator:
            parts.append(f"at {self.locator}")
        if self.detail:
            parts.append(f"- {self.detail}")
        parts.append(f"| what to do: {self.what_now}")
        return " ".join(parts)


class DiagnosticError(Exception):
    """The base for every failure this system raises deliberately.

    The rule is not "registries carry diagnostics", it is "failures do". `except
    DiagnosticError` is the one handler that can always report a code, an owner and a
    next action, which is what makes an operator-facing error surface possible at all.
    """

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(str(diagnostic))
        self.diagnostic = diagnostic


class RegistryError(DiagnosticError):
    """A registry refused something."""


class ContractViolation(RegistryError):
    """An instance did not satisfy the contract it was validated against."""

    def __init__(self, diagnostic: Diagnostic, all_diagnostics: tuple[Diagnostic, ...]) -> None:
        super().__init__(diagnostic)
        self.all = all_diagnostics


# The codes this package raises. Families and owners follow the diagnostics table in
# the blueprint; SCOPE.* is the config-owned family, which is where a registry pin that
# names something nobody registered belongs — it is a setup gap, not a model failure.
UNKNOWN_CONTRACT = "SCOPE.UNKNOWN_CONTRACT"
CONTRACT_INDEX_INVALID = "SCOPE.CONTRACT_INDEX_INVALID"
UNKNOWN_CONSTRAINTS = "SCOPE.UNKNOWN_CONSTRAINTS"
UNKNOWN_ADAPTER = "SCOPE.UNKNOWN_ADAPTER"
MISSING_CREDENTIAL = "SCOPE.MISSING_CREDENTIAL"
MODEL_PIN_UNAVAILABLE = "SCOPE.MODEL_PIN_UNAVAILABLE"
UNREADABLE_FILE = "INTAKE.UNREADABLE_FILE"
WRITE_FAILED = "DELIVER.WRITE_FAILED"
SCHEMA_INVALID = "SKILL.SCHEMA_INVALID"
NO_PROVENANCE = "SKILL.NO_PROVENANCE"
FABRICATED_SOURCE = "SKILL.FABRICATED_SOURCE"
UNKNOWN_RUN = "PROCESS.UNKNOWN_RUN"
ILLEGAL_TRANSITION = "PROCESS.ILLEGAL_TRANSITION"
APPEND_ONLY_VIOLATION = "PROCESS.APPEND_ONLY_VIOLATION"
MANIFEST_INCOMPLETE = "PROCESS.MANIFEST_INCOMPLETE"

WHAT_NOW: dict[str, tuple[Owner, str]] = {
    UNKNOWN_CONTRACT: (
        "config",
        "Pin an id and version that contracts/registry.yaml lists, or register the "
        "contract there. An unpinned or unknown version is never resolved to a guess.",
    ),
    CONTRACT_INDEX_INVALID: (
        "config",
        "contracts/registry.yaml and the files on disk disagree. Reconcile them - the "
        "index is the pin, so an unlisted schema file is not a contract.",
    ),
    UNKNOWN_CONSTRAINTS: (
        "config",
        "constraints.yaml is at a version this run did not pin. Constraints are pinned "
        "per run and recorded in the plan hash; resolve the mismatch deliberately.",
    ),
    UNKNOWN_ADAPTER: (
        "config",
        "No adapter is registered under that name for this port. Check the "
        "AA_*_ADAPTER value against ports.adapters() - an unknown name is never "
        "resolved to a default, because a silent fallback is how a run ends up "
        "reading from somewhere nobody chose.",
    ),
    MISSING_CREDENTIAL: (
        "config",
        "The secrets port has no value under that name. Add it to .env (see "
        ".env.example). The value is never printed, here or anywhere else.",
    ),
    MODEL_PIN_UNAVAILABLE: (
        "config",
        "The pinned model is not available. Choose a new pin deliberately and "
        "re-run: a run that silently substituted a different model would produce "
        "figures nobody could attribute.",
    ),
    UNREADABLE_FILE: (
        "client-data",
        "The file could not be read. A figure that cites nothing is worse than a "
        "figure that never existed, so the run stops rather than proceeding with a "
        "null source id. Ask the client for a readable copy.",
    ),
    WRITE_FAILED: (
        "system",
        "The delivery port could not write. Usually transient. The write is keyed, "
        "so retrying produces no duplicate.",
    ),
    SCHEMA_INVALID: (
        "model",
        "The output does not match the skill's declared schema. Fix the skill, not the "
        "schema - a validator that bends is worse than no validator.",
    ),
    NO_PROVENANCE: (
        "model",
        "A figure is missing source_id, locator or source_version, or they are "
        "malformed. No number without a source: send it back through the skill with "
        "the source excerpt attached.",
    ),
    FABRICATED_SOURCE: (
        "model",
        "A figure cites the system's own reasoning as its source. This is rejected as "
        "hard as a missing source. Requote the underlying document, or report the item "
        "as unavailable.",
    ),
    UNKNOWN_RUN: (
        "process",
        "No run is recorded under that id. The run store is the source of truth for "
        "what happened; an id it does not know was never started, or was started "
        "against a different store.",
    ),
    ILLEGAL_TRANSITION: (
        "process",
        "A run cannot move between those two states. The state machine is small and "
        "closed on purpose - if the move is legitimate, the transition table is what "
        "needs changing, deliberately, not the call site.",
    ),
    APPEND_ONLY_VIOLATION: (
        "system",
        "Something tried to change or remove a recorded event. The event table is "
        "append-only in the API, in the ORM and in the database. Correct the record by "
        "emitting a further event, never by editing one - a trace that can be edited "
        "is not evidence of anything.",
    ),
    MANIFEST_INCOMPLETE: (
        "system",
        "The manifest assembled from the run store does not satisfy "
        "run_manifest@1.0.0. This is a defect in the writer or a gap in what the run "
        "recorded; the run is not closed out until a valid manifest exists, because a "
        "run with no defensible record is worse than a run that visibly failed.",
    ),
}


def diagnose(code: str, detail: str = "", locator: str = "") -> Diagnostic:
    """Build a diagnostic from a registered code. An unregistered code is a bug here."""
    owner, what_now = WHAT_NOW[code]
    return Diagnostic(code=code, owner=owner, what_now=what_now, detail=detail, locator=locator)
