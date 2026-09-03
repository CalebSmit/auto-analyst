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
UNRESOLVED_SCOPE = "SCOPE.UNRESOLVED"
UNKNOWN_PRACTICE = "SCOPE.UNKNOWN_PRACTICE"
UNKNOWN_SEGMENT = "SCOPE.UNKNOWN_SEGMENT"
UNKNOWN_DISPOSITION = "SCOPE.UNKNOWN_DISPOSITION"
UNKNOWN_REVIEW_LEVEL = "SCOPE.UNKNOWN_REVIEW_LEVEL"
AMBIGUOUS_SKILL = "SCOPE.AMBIGUOUS_SKILL"
SKILL_INVALID = "SCOPE.SKILL_INVALID"
RECIPE_INVALID = "SCOPE.RECIPE_INVALID"
PLAN_REFUSED = "PROCESS.PLAN_REFUSED"
LATE_RESULT = "PROCESS.LATE_RESULT"
PRECEDENT_OUT_OF_SCOPE = "SCOPE.PRECEDENT_OUT_OF_SCOPE"
UNMASKED_PRECEDENT = "PRIVACY.UNMASKED_PRECEDENT"
UNMASKED_IDENTIFIER = "PRIVACY.UNMASKED_IDENTIFIER"
TOKEN_CROSS_ENGAGEMENT = "PRIVACY.TOKEN_CROSS_ENGAGEMENT"
VAULT_UNAVAILABLE = "PRIVACY.VAULT_UNAVAILABLE"
UNMASK_RESIDUAL = "GUARD.UNMASK_RESIDUAL"
TIEOUT_MISMATCH = "GUARD.TIEOUT_MISMATCH"
RECONCILE_CONFLICT = "GUARD.RECONCILE_CONFLICT"
NUMERIC_DRIFT = "GUARD.NUMERIC_DRIFT"
UNKNOWN_SOURCE = "SKILL.UNKNOWN_SOURCE"
UNDECLARED_CYCLE = "LOOP.UNDECLARED_CYCLE"
LOOP_CEILING_EXCEEDED = "LOOP.CEILING_EXCEEDED"
TOOL_NOT_DECLARED = "POLICY.TOOL_NOT_DECLARED"
ARG_OUT_OF_SCOPE = "POLICY.ARG_OUT_OF_SCOPE"
BUDGET_EXCEEDED = "POLICY.BUDGET_EXCEEDED"
CAP_EXCEEDED = "POLICY.CAP_EXCEEDED"
UNKNOWN_TOOL = "SCOPE.UNKNOWN_TOOL"
OVERLAY_LOOSENS = "POLICY.OVERLAY_LOOSENS"
MULTI_TURN_STEP = "POLICY.MULTI_TURN_STEP"
UNKNOWN_RUN = "PROCESS.UNKNOWN_RUN"
ILLEGAL_TRANSITION = "PROCESS.ILLEGAL_TRANSITION"
APPEND_ONLY_VIOLATION = "PROCESS.APPEND_ONLY_VIOLATION"
MANIFEST_INCOMPLETE = "PROCESS.MANIFEST_INCOMPLETE"
DIAGNOSTICS_INVALID = "PROCESS.DIAGNOSTICS_INVALID"

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
    UNRESOLVED_SCOPE: (
        "config",
        "The scope path is malformed, or scopes.yaml itself does not hold together. A "
        "run is never started unscoped: resolution decides which skills the engagement "
        "can even see, so there is no sensible default to fall back to.",
    ),
    UNKNOWN_PRACTICE: (
        "config",
        "No such practice group in scope/scopes.yaml. Adding one is an entry there plus "
        "a folder under skills/ - deliberately a two-line change. Until it is declared, "
        "an engagement scoped to it resolves to nothing, which is why this fails at the "
        "start of the run rather than producing an empty skill set.",
    ),
    UNKNOWN_SEGMENT: (
        "config",
        "That segment is not declared under that practice group in scope/scopes.yaml. "
        "Segments are per practice; a segment of one group is not a segment of another.",
    ),
    UNKNOWN_DISPOSITION: (
        "config",
        "That client disposition is not declared in scope/scopes.yaml. Dispositions cut "
        "across every practice group, so the list is short and shared.",
    ),
    UNKNOWN_REVIEW_LEVEL: (
        "config",
        "The value is not on the ladder in scope/scopes.yaml. Place it deliberately: an "
        "unranked review level cannot be compared, and an overlay that cannot be "
        "compared cannot be refused. Where a new value sits is a decision, not a "
        "spelling.",
    ),
    AMBIGUOUS_SKILL: (
        "config",
        "Two skills of the same name are declared at the same layer, so resolution has "
        "no deepest answer. Rename one, or move it to the layer where it is actually "
        "true - the tree resolves by depth, and a tie has no meaning.",
    ),
    SKILL_INVALID: (
        "config",
        "A SKILL.md is missing frontmatter, or missing a field the tree requires. A "
        "skill that cannot declare its own tools, privacy class and review floor cannot "
        "be dispatched, because there would be nothing for the Policy Gate to enforce.",
    ),
    RECIPE_INVALID: (
        "config",
        "The recipe does not compile: a step naming something that does not exist, an "
        "output schema the contract registry does not pin, or a loop region whose "
        "members do not hang together. Nothing executes that has not been through the "
        "compiler, so this is where a broken plan stops.",
    ),
    UNDECLARED_CYCLE: (
        "config",
        "The plan graph contains a cycle that is not a declared, bounded loop region. "
        "Every loop is declared with an integer ceiling the compiler checks - a cycle "
        "nobody declared has no ceiling, and a loop with no ceiling is how a run spends "
        "a budget on one step. Declare it in the recipe's `loops:` block or remove the "
        "dependency that closes it.",
    ),
    LOOP_CEILING_EXCEEDED: (
        "config",
        "A declared loop asks for more iterations than the constraint registry allows, "
        "or is not an in-run loop at all. Ceilings are raised in constraints.yaml "
        "deliberately, never in the recipe that wants the extra go.",
    ),
    MULTI_TURN_STEP: (
        "policy",
        "A skill invocation is one model turn. If a skill needs a tool result, that is "
        "another step in the plan - compiled, keyed and visible - not a hidden turn "
        "inside one. Multi-turn skills need the Policy Gate bound to the permission "
        "callback, a seventh declared loop, and context_ref redefined as a transcript "
        "hash; all three together, or the guarantees rot silently.",
    ),
    TOOL_NOT_DECLARED: (
        "policy",
        "The skill proposed a tool that is not on its declared allowlist in "
        "constraints.yaml. A skill reaches the tools it declares and no others; if it "
        "genuinely needs this one, the allowlist changes under review, not the call.",
    ),
    ARG_OUT_OF_SCOPE: (
        "policy",
        "An argument failed a constraint predicate: it names another engagement, a path "
        "outside the engagement root, a row limit above the cap, an unpinned version, "
        "or a write on a read-only tool. Reading another engagement's folder returns "
        "perfectly valid data, which is exactly why only a check before execution "
        "catches it.",
    ),
    BUDGET_EXCEEDED: (
        "policy",
        "The estimated cost of this call exceeds what remains of the run's budget. The "
        "ceiling is in constraints.yaml and is raised there, deliberately; a run does "
        "not get to decide it deserves more.",
    ),
    CAP_EXCEEDED: (
        "policy",
        "The runtime's call-time cap was hit - too many calls to one tool in a step, or "
        "a tool returned more rows than its cap allows. Caps are applied by the runtime "
        "from the registry, never trusted from the caller, and a tool that ignores its "
        "cap is broken rather than generous.",
    ),
    UNKNOWN_TOOL: (
        "config",
        "No tool is registered under that name. The namespace is six names, declared in "
        "constraints.yaml; a name outside it is not a tool that has not been written "
        "yet, it is a name nothing will ever answer to.",
    ),
    OVERLAY_LOOSENS: (
        "policy",
        "An overlay tried to lower a review requirement, widen a privacy class or add a "
        "tool. Overlays may only tighten. If the looser setting is genuinely right, it "
        "belongs in the skill at the layer where it is true - changing it from a deeper "
        "layer would mean the shallower promise was never worth anything.",
    ),
    PLAN_REFUSED: (
        "process",
        "A compiled plan violates an invariant and will not execute. The assertions run "
        "before every execution rather than in CI alone, because a plan is built per run "
        "and CI has never seen this one. Fix the recipe or the scope it was compiled "
        "against; there is no flag that skips the check.",
    ),
    PRECEDENT_OUT_OF_SCOPE: (
        "config",
        "A precedent source returned an example from outside the engagement's resolved "
        "scope. The query is built from that scope so a Corporate Finance decision is "
        "never available to an ESOP valuation; a source answering with one is broken, "
        "and the builder refuses the whole batch rather than filtering quietly.",
    ),
    UNMASKED_IDENTIFIER: (
        "system",
        "An identifier from the engagement's vault reached the outbound payload scan "
        "unmasked, or a token the masker was expected to substitute is missing. Nothing "
        "leaves for a model until it is fixed: the masker is the control and the scan is "
        "the proof it worked, and a scan that let this through would be neither.",
    ),
    TOKEN_CROSS_ENGAGEMENT: (
        "system",
        "A mask token in this run's output was not issued under this run's engagement. "
        "Resolving it would hand one client another client's value, which is the "
        "cross-client failure this whole band exists to prevent. The run stops; find "
        "where the token came from before anything else.",
    ),
    VAULT_UNAVAILABLE: (
        "system",
        "The mask vault cannot be opened - the encryption key is missing from the "
        "secrets port, or the store is unreachable. Nothing can be masked or unmasked "
        "without it, and nothing is: a run does not proceed on unmasked payloads "
        "because the vault was down.",
    ),
    TIEOUT_MISMATCH: (
        "client-data",
        "A stated total does not match what the Recompute Engine derived from the cited "
        "source rows, outside the run's tolerance. Both values, the delta and the rows "
        "are in the manifest. Usually the client's own schedule does not foot; sometimes "
        "the skill cited the wrong rows. Either way a person decides which - the run does "
        "not pick the nicer number.",
    ),
    RECONCILE_CONFLICT: (
        "model",
        "Two skills disagree about the same thing - a line item categorised two ways, a "
        "period present in one output and absent from another. Both positions and their "
        "sources are on the record. Conflicts route to review; they are never resolved by "
        "preferring whichever skill wrote last.",
    ),
    NUMERIC_DRIFT: (
        "system",
        "A number or a citation marker changed between the validated figures and what was "
        "written out. Rounding, a swapped scale, a dropped cell: the numeric lock does not "
        "care which. Nothing is released until the two token sets are identical, because "
        "a transform that changes a figure is not a transform.",
    ),
    UNKNOWN_SOURCE: (
        "model",
        "A figure cites a source_id that is not in this run's intake manifest, or a "
        "locator that does not exist in the Source Parse Store. The hash is well-formed "
        "and the document is not here. A figure that cannot be traced to a file the run "
        "actually read is not evidence of anything.",
    ),
    UNMASK_RESIDUAL: (
        "system",
        "A mask token survived into output that was meant to be re-identified, or a "
        "token present in the input never resolved. A released artifact carries zero "
        "mask tokens; this one does not release until the unmasking is complete.",
    ),
    UNMASKED_PRECEDENT: (
        "system",
        "A precedent arrived unmasked. The store holds masked examples only, written "
        "downstream of a human decision. An unmasked one means the write-back or the "
        "store has been bypassed, and nothing from that batch reaches a model.",
    ),
    LATE_RESULT: (
        "process",
        "A result arrived for an attempt something newer has replaced, or for a step "
        "key the ledger already holds. Neither is a defect in the result - it is "
        "simply not the one anything downstream was built on. Nothing is overwritten: "
        "a step key is written once, which is what makes a retry, a resume and a "
        "manual re-run the same operation.",
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
    DIAGNOSTICS_INVALID: (
        "system",
        "The diagnostics registry does not hold together: a code with no what_now, an "
        "owner nobody is, or a family the blueprint does not name. Fix registries/errors.py; "
        "a message nobody can act on is a defect, and this is the check that finds one "
        "before a run does.",
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
