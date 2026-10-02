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
    expected: str = ""
    found: str = ""
    delta: str = ""
    step_id: str = ""
    skill: str = ""
    retryable: bool = False
    """Whether a second attempt with the same input could end differently. False for
    every guard and loop code: a retry with unchanged input fails identically, which is
    the fact the Loop Controller is built around."""

    def __str__(self) -> str:
        parts = [f"{self.code} [{self.owner}]"]
        if self.locator:
            parts.append(f"at {self.locator}")
        if self.expected or self.found:
            parts.append(f"expected {self.expected or '?'}, found {self.found or '?'}")
            if self.delta:
                parts.append(f"(delta {self.delta})")
        if self.detail:
            parts.append(f"- {self.detail}")
        parts.append(f"| what to do: {self.what_now}")
        return " ".join(parts)

    def as_dict(self) -> dict[str, object]:
        """The wire shape: what a quarantine record, a review item and a manifest carry."""
        return {
            "code": self.code,
            "owner": self.owner,
            "what_now": self.what_now,
            "detail": self.detail,
            "where": self.locator,
            "expected": self.expected,
            "found": self.found,
            "delta": self.delta,
            "step_id": self.step_id,
            "skill": self.skill,
            "retryable": self.retryable,
        }


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
PROVIDER_REFUSED_A_FIELD = "SCOPE.PROVIDER_REFUSED_A_FIELD"
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
CITED_VALUE_ABSENT = "SKILL.CITED_VALUE_ABSENT"
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
LOOP_EXHAUSTED = "LOOP.EXHAUSTED"
INPUT_UNCHANGED = "LOOP.INPUT_UNCHANGED"
REVIEW_SLA_BREACH = "PROCESS.REVIEW_SLA_BREACH"
RUN_STALLED = "PROCESS.RUN_STALLED"
QC_FAILED = "DELIVER.QC_FAILED"
TEMPLATE_MISSING = "DELIVER.TEMPLATE_MISSING"
UNKNOWN_TYPE = "INTAKE.UNKNOWN_TYPE"
NO_ENGAGEMENT = "INTAKE.NO_ENGAGEMENT"
STALE_DECISION = "PROCESS.STALE_DECISION"
RATIONALE_REQUIRED = "PROCESS.RATIONALE_REQUIRED"
WATCH_OVERLAP = "INTAKE.WATCH_OVERLAP"
ENGAGEMENT_LOCKED = "PROCESS.ENGAGEMENT_LOCKED"
INJECTION_DETECTED = "INTAKE.INJECTION_DETECTED"
UNKNOWN_TAXONOMY = "SCOPE.UNKNOWN_TAXONOMY"
UNKNOWN_LINE_ITEM = "SKILL.UNKNOWN_LINE_ITEM"
UNKNOWN_PRECEDENT = "SKILL.UNKNOWN_PRECEDENT"
PRECEDENT_NO_DECISION = "PROCESS.PRECEDENT_NO_DECISION"
VERIFICATION_PASS = "LOOP.VERIFICATION_PASS"
TEMPLATE_INPUTS_MISSING = "CONFIG.TEMPLATE_INPUTS_MISSING"
CELL_ADDRESS_BINDING = "CONFIG.CELL_ADDRESS_BINDING"
BELOW_GATE = "SKILL.BELOW_GATE"
ADAPTER_NOT_WIRED = "SCOPE.ADAPTER_NOT_WIRED"
GROUP_UNDEFINED = "SCOPE.GROUP_UNDEFINED"
GATE_SKIPPED = "SKILL.GATE_SKIPPED"
CLIENT_DATA_IN_DRAFT = "SKILL.CLIENT_DATA_IN_DRAFT"
SHADOW_INSUFFICIENT = "SKILL.SHADOW_INSUFFICIENT"
METHODOLOGY_UNCLEARED = "CONFIG.METHODOLOGY_UNCLEARED"
METHODOLOGY_UNSAFE = "CONFIG.METHODOLOGY_UNSAFE"
METHODOLOGY_TOO_LARGE = "CONFIG.METHODOLOGY_TOO_LARGE"
CONTEXT_TOO_LARGE = "INTAKE.CONTEXT_TOO_LARGE"
RECIPE_UNREGISTERED = "SCOPE.RECIPE_UNREGISTERED"
UNKNOWN_CRITERIA = "SCOPE.UNKNOWN_CRITERIA"
NO_REQUEST_LIST = "SCOPE.NO_REQUEST_LIST"
UNKNOWN_APPENDIX = "SCOPE.UNKNOWN_APPENDIX"
APPENDIX_REGISTRY_INVALID = "SCOPE.APPENDIX_REGISTRY_INVALID"
APPENDIX_CARRIES_FORWARD = "SCOPE.APPENDIX_CARRIES_FORWARD"
OUTCOME_CONTRADICTED = "PROCESS.OUTCOME_CONTRADICTED"
WORKER_LOST = "PROCESS.WORKER_LOST"
TRANSPORT_EXHAUSTED = "PROCESS.TRANSPORT_EXHAUSTED"
PATH_UNREADABLE = "CONFIG.PATH_UNREADABLE"
CREDENTIAL_EXPIRED = "CONFIG.CREDENTIAL_EXPIRED"
PROFILE_INCOMPLETE = "CONFIG.PROFILE_INCOMPLETE"
TEMPLATE_UNREGISTERED = "CONFIG.TEMPLATE_UNREGISTERED"
TEMPLATE_HASH_MISMATCH = "CONFIG.TEMPLATE_HASH_MISMATCH"
DESTINATION_UNWRITABLE = "CONFIG.DESTINATION_UNWRITABLE"
BUDGET_ABOVE_CEILING = "CONFIG.BUDGET_ABOVE_CEILING"
BINDING_MISSING = "CONFIG.BINDING_MISSING"
ADMIN_FORBIDDEN = "CONFIG.ADMIN_FORBIDDEN"
CREDENTIAL_REFUSED = "CONFIG.CREDENTIAL_REFUSED"

WHAT_NOW: dict[str, tuple[Owner, str]] = {
    PATH_UNREADABLE: (
        "config",
        "A watch root cannot be listed through the Storage Port. Fix the path or the "
        "mount, or remove the watch. Nothing is swept from a place that cannot be read, "
        "and a run does not start to find that out.",
    ),
    CREDENTIAL_REFUSED: (
        "config",
        "A credential is set and the service rejected it. That is a different repair "
        "from a missing one: the secret is wrong, revoked, or the app lacks the "
        "permission this call needs - for Box, 'Generate User Access Tokens' has to be "
        "enabled before a user can be impersonated. The value is never printed.",
    ),
    CREDENTIAL_EXPIRED: (
        "config",
        "A credential the environment expects is past the expiry recorded for it, or "
        "expires within thirty days. Rotate it through the Secrets Port and record the "
        "new expiry. Preflight sees presence and dates, never a value.",
    ),
    PROFILE_INCOMPLETE: (
        "config",
        "The engagement profile is missing, invalid, or lacks a checkpoint policy with an "
        "owner and an SLA. Three skills read it as a required input, so the engagement "
        "cannot be activated until it is complete (finding F1).",
    ),
    TEMPLATE_UNREGISTERED: (
        "config",
        "The template the engagement's scope binds to is not in the Template Registry at "
        "that version. Register it, or bind the scope to one that is. A run does not "
        "write into a workbook nobody validated.",
    ),
    TEMPLATE_HASH_MISMATCH: (
        "config",
        "The template on disk is not the bytes the registry pinned. Somebody edited the "
        "master in place. Restore it, or register the edited file as a new version.",
    ),
    DESTINATION_UNWRITABLE: (
        "config",
        "The delivery destination could not be written through the Delivery Port. Fix "
        "the path, the mount or the credential. A run does not build a deliverable it "
        "cannot deliver.",
    ),
    BUDGET_ABOVE_CEILING: (
        "config",
        "A per-run budget sits above the firm ceiling in constraints.yaml. Lower the "
        "budget; raising the ceiling is a governance change, not an admin one.",
    ),
    BINDING_MISSING: (
        "config",
        "The engagement resolves to no delivery destination, no template, or more than "
        "one of either. Bind exactly one in the configuration. Every active engagement "
        "resolves to exactly one destination and one template pin.",
    ),
    ADMIN_FORBIDDEN: (
        "config",
        "The change is outside what an admin may do: lowering a review requirement, "
        "raising a budget above the firm ceiling, or touching something that fails "
        "closed. Those enter through the governance chain, not the Admin tab.",
    ),
    UNKNOWN_CRITERIA: (
        "config",
        "The run criteria version named is not a file under ops/criteria/, or names a "
        "criterion the scorecard cannot measure. Pin a version that exists; a run scored "
        "against 'whatever is newest' cannot say what bar it was judged by.",
    ),
    # Two that were raised as UNKNOWN_CRITERIA until 2026-10-02, so a missing request
    # list and an unknown appendix were both answered with advice about pinning a
    # criteria version. `what to do` is the half a person acts on, and borrowing a code
    # borrows its advice for a problem it was not written about.
    NO_REQUEST_LIST: (
        "config",
        "Write a starting list for the division under intake/request_lists/, named for "
        "the scope path with slashes as hyphens - valuation-non-esop.yaml serves "
        "valuation/non-esop and every segment under it, because the lookup walks up "
        "and stops at the practice. Or pass a list on the command for this one "
        "engagement. The refusal itself says why another division's is not lent.",
    ),
    UNKNOWN_APPENDIX: (
        "config",
        "No appendix in this report carries that id. The refusal lists the ones an "
        "update can be applied to; everything else in the registry carries forward "
        "from last year's document and nothing writes it. Name one of the listed ids.",
    ),
    APPENDIX_CARRIES_FORWARD: (
        "config",
        "The appendix named is real and nothing updates it: it arrives already written "
        "in the copy of last year's report and this tool has no content to put anywhere. "
        "That is the line it is holding, not a failure. The refusal lists the appendices "
        "an update does apply to; name one of those.",
    ),
    APPENDIX_REGISTRY_INVALID: (
        "config",
        "The appendix registry itself is wrong rather than the id asked for: an entry "
        "without the fields an appendix needs, or two entries sharing an id. The id is "
        "what a button names, so a duplicate makes one unreachable and the other "
        "ambiguous. Fix APPENDICES in report/appendices.py, or the rows passed to "
        "registry_from.",
    ),
    OUTCOME_CONTRADICTED: (
        "system",
        "Close-out claimed an outcome the record does not support: the scorecard "
        "computed a different verdict from the events, the review items and the guard "
        "results. Close the run out with the outcome the verdict supports, or fix what "
        "the record shows. Nothing is written until the claim and the computation agree.",
    ),
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
    PROVIDER_REFUSED_A_FIELD: (
        "system",
        "The provider rejected a field in the request rather than the model or its "
        "length. That is this build's mistake, not a configuration one: the adapter "
        "sent something the API does not accept. The model pin is fine - do not change "
        "it. The refusal names the field.",
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
    GROUP_UNDEFINED: (
        "config",
        "The engagement's practice group or segment is declared in the scope registry but "
        "nothing is defined behind it, so the run resolves to the firm layer only. That "
        "is correct and it is not useful: the engagement gets the firm's skills and none "
        "of its group's. Not a failure and not a blocker - the practice leads name the "
        "segments, and until they do this is the honest state rather than a short list "
        "that looks like a considered answer.",
    ),
    ADAPTER_NOT_WIRED: (
        "config",
        "An adapter was selected whose implementation is not in this repo: it is a port "
        "contract waiting for one of the firm's existing connectors. It refuses rather "
        "than returning something, because a run reading from - or writing to - "
        "somewhere nobody chose is the failure the ports exist to prevent. Either wire "
        "the connector in behind the contract, or select an adapter that is built. "
        "HANDOFF.md says which are which.",
    ),
    GATE_SKIPPED: (
        "process",
        "A candidate skill reached a stage of the governance chain with no record that "
        "an earlier one happened. The chain is linear so that removing any one gate "
        "breaks the path rather than routing around it. Run the missing stage and let it "
        "record its own evidence; there is no method that marks a stage done.",
    ),
    CLIENT_DATA_IN_DRAFT: (
        "client-data",
        "A dropped draft carries something shaped like real client data - an account "
        "number, an identifier, a pasted statement. The draft is held in triage and "
        "goes no further. Take the real data out of the example and drop it again; a "
        "skill is a procedure, and its examples are synthetic.",
    ),
    SHADOW_INSUFFICIENT: (
        "process",
        "The candidate has not held its agreement threshold over the stated number of "
        "real runs, so it cannot be promoted. Either it disagrees with the registered "
        "version too often, or it has not yet run beside it enough times. Neither is "
        "fixed by approving it again: let it keep shadowing.",
    ),
    METHODOLOGY_UNCLEARED: (
        "config",
        "A methodology file in foundations/ is not cleared, or is not the version that "
        "was cleared. It is not attached and the run stops rather than proceeding "
        "without the firm's reference material, because a run that quietly drops half "
        "its methodology answers a different question from the one that was asked. "
        "Methodology reaches every model call, so it is read by a person once and "
        "recorded by digest; editing a file after it was cleared is what this catches, "
        "and it catches it by the hash changing rather than by anybody remembering. "
        "Clear it from the admin surface, or restore the version that was cleared.",
    ),
    RECIPE_UNREGISTERED: (
        "config",
        "The recipe is not approved for client work, or is not the version that was "
        "approved. A recipe is the order the work happens in - which skills run, against "
        "which inputs, with which guards between them - so an unapproved one is a "
        "sequence nobody reviewed running on a client engagement. A recipe edited after "
        "the board saw it is the same problem wearing the name of something that was "
        "approved, which is why the check is on the file and not on the name. Take it "
        "through the board; approval is a decision and registration is a deployment.",
    ),
    METHODOLOGY_TOO_LARGE: (
        "config",
        "One layer of foundations/ is past the size ceiling in constraints.yaml. That is "
        "content on every model call of every run that resolves through the layer - the "
        "firm layer being all of them - so it is a standing cost per run rather than a "
        "one-off. Reported at setup because the alternative is finding it in a bill and "
        "not knowing which document caused it. Either take something out of the layer, "
        "or raise the ceiling deliberately, which is a decision about what a run costs "
        "and belongs in constraints.yaml rather than in whatever wanted the room.",
    ),
    CONTEXT_TOO_LARGE: (
        "client-data",
        "One step's assembled context is past the ceiling in constraints.yaml, and the "
        "section that pushed it over is named above. Almost always that is one client "
        "document: a scan of a whole year's statements goes to the model as text, and a "
        "long enough one does not fit in a single turn however good the model is. Split "
        "the document, or send the statements the step actually needs - a balance sheet "
        "step does not need the notes. Raising the ceiling is the other answer and it is "
        "a decision about what a run costs, so it lives in constraints.yaml rather than "
        "in whatever wanted the room. Refused here rather than at the provider, because "
        "a refusal from there says only that the request was too long and not which "
        "document made it so.",
    ),
    METHODOLOGY_UNSAFE: (
        "config",
        "A methodology file cannot be cleared because it carries something shaped like a "
        "real engagement's data, or something shaped like an instruction to the model "
        "reading it. Both matter more here than in a skill draft: this content goes into "
        "every prompt of every run, for every client, and the outbound scan only knows "
        "the current engagement's identifiers - so a worked example quoting a real deal "
        "would travel everywhere and trip nothing. Take the example out, or mask it the "
        "way a precedent is masked.",
    ),
    BELOW_GATE: (
        "model",
        "A skill version scored below one of its acceptance gates, or the version is "
        "already registered. It cannot be registered and does not ship. Fix the skill "
        "against its fixtures and re-run the evaluation; do not lower the gate - the "
        "thresholds are the practice's, set against a real fixture set, not the "
        "skill's to negotiate.",
    ),
    TEMPLATE_INPUTS_MISSING: (
        "config",
        "The bound workbook does not declare every named range the mapping requires. "
        "Either add the named ranges to the template, or map them to existing ranges in "
        "the binding. Registration refuses the template until it does, so the gap is "
        "found at binding rather than delivered as empty cells. Blocks activation of "
        "any engagement bound to this template, not a run.",
    ),
    CELL_ADDRESS_BINDING: (
        "config",
        "A template binding or a mapping destination is a cell address rather than a "
        "named range. B44 is not a contract: one inserted row would shift every "
        "mapping below it and produce a plausibly wrong deliverable. Define a named "
        "range in the workbook for the input and bind to that name.",
    ),
    VERIFICATION_PASS: (
        "process",
        "Not a failure. The self-verification pass was admitted as an iteration of its "
        "declared region: a separate invocation that sees the schedule, the cited rows "
        "and the excerpts, never the first pass's rationale. It is on the loop ledger so "
        "the iteration counts against the run's ceiling like any other and so a plan "
        "that skipped it would be visible as a missing iteration.",
    ),
    LOOP_EXHAUSTED: (
        "model",
        "A declared loop reached its ceiling without its exit condition being met. The "
        "step is quarantined with every attempt on record and a review item carries both "
        "positions - decide the item, or fix the cause and re-run the step by key. Do not "
        "raise the ceiling in the recipe; ceilings live in constraints.yaml.",
    ),
    INPUT_UNCHANGED: (
        "model",
        "The next iteration would carry byte-identical input to a previous one, so it "
        "would be the same call at the same price with the same answer. The loop stopped "
        "early rather than spending the remaining iterations. The skill returned the same "
        "output to the same feedback; look at the skill or the feedback, not the loop.",
    ),
    REVIEW_SLA_BREACH: (
        "process",
        "A review item has been open longer than the review SLA allows. The run is still "
        "waiting and burning no budget; the item needs a decision from the named reviewer "
        "or an escalation to the engagement owner. Nothing here is a system fault.",
    ),
    TRANSPORT_EXHAUSTED: (
        "system",
        "Every retry this step was allowed failed to reach what it was calling. Retries "
        "cover transport only - a timeout, a refused connection, a provider that did not "
        "answer - so the step's own logic has not run and nothing it would have produced "
        "is lost. Check whatever it was reaching for, then resume the run; resume is "
        "replay, so only this step is re-attempted and nothing before it is paid for twice.",
    ),
    WORKER_LOST: (
        "system",
        "The worker executing this run died mid-step: its job ended without a result and "
        "a step started and never ended. Nothing completed is lost - the ledger holds "
        "every finished step. Check the worker, then resume the run; resume is replay, "
        "so only the lost step is re-attempted and nothing before it is paid for twice.",
    ),
    RUN_STALLED: (
        "system",
        "A running run has recorded no event for longer than the stall threshold. The "
        "worker may have died holding the lock. Check the worker, then resume the run - "
        "resume is replay, so nothing completed is re-executed.",
    ),
    QC_FAILED: (
        "system",
        "The deliverable failed its QC checks and was not released. The Fixed Notice "
        "names the check; fix the template or the bindings and re-run the delivery step "
        "by key. A deliverable never ships partially valid.",
    ),
    TEMPLATE_MISSING: (
        "system",
        "The template registry has no template bound for this scope at the pinned "
        "version. Register one under the scope path, or bind a fallthrough at a higher "
        "layer. The run stops here rather than writing into a guessed workbook.",
    ),
    UNKNOWN_TYPE: (
        "client-data",
        "The intake classifier could not say what kind of document this is, so no skill "
        "can claim it. Tell the classifier what it is by filename convention or engagement "
        "profile, or exclude the file. Nothing is processed under a guessed type.",
    ),
    NO_ENGAGEMENT: (
        "client-data",
        "A file arrived that no engagement claims - no matching folder, header or "
        "profile. Assign it to an engagement explicitly, or leave it unprocessed. A file "
        "with no engagement has no scope, and a run with no scope has no skills.",
    ),
    STALE_DECISION: (
        "process",
        "Another reviewer decided this item after you opened it, or it was already "
        "decided. Nothing you entered was written. Read their decision - it is in the "
        "refusal - and if you disagree, escalate on the item rather than deciding over "
        "them. Two reviewers never silently overwrite each other.",
    ),
    RATIONALE_REQUIRED: (
        "process",
        "An edit, a rejection or an escalation needs a reason, and a correction needs the "
        "corrected value. The reason is what the decision log is for: six months later "
        "it is the only record of why a line was treated that way. Add it and decide "
        "again; nothing was written.",
    ),
    WATCH_OVERLAP: (
        "config",
        "Two watches claim the same path, or two roster entries claim the same folder "
        "under one watch. Nothing was swept: an overlap would start two runs on one file. "
        "Fix the watch roots or the roster folders so every path has exactly one claimant, "
        "then sweep again.",
    ),
    ENGAGEMENT_LOCKED: (
        "process",
        "Another run holds this engagement's lock, so this run is queued behind it rather "
        "than started alongside it - two runs on one engagement would write the same mask "
        "vault and the same output folder. Nothing to do unless the holder is past its "
        "timeout, which is raised as an incident and never cleared automatically.",
    ),
    INJECTION_DETECTED: (
        "client-data",
        "A document carries text that reads as instructions to a model - hidden or not - "
        "and the Untrusted Content Boundary stopped the run before any model saw it. The "
        "pattern and where it sat are on the record; the document is quarantined. Ask the "
        "sender for a clean copy, or have a person confirm the text is benign and re-run.",
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
    CITED_VALUE_ABSENT: (
        "model",
        "A figure read off the page cites a real location, and the number is not there. The "
        "source row says something else - a different amount, the opposite sign, or no "
        "amount at all. A citation that points at the right place with the wrong number is "
        "worse than none, because it looks checked. Both values are in the detail: requote "
        "the row, or report the item as unavailable.",
    ),
    UNKNOWN_SOURCE: (
        "model",
        "A figure cites a source_id that is not in this run's intake manifest, or a "
        "locator that does not exist in the Source Parse Store. The hash is well-formed "
        "and the document is not here. A figure that cannot be traced to a file the run "
        "actually read is not evidence of anything.",
    ),
    UNKNOWN_TAXONOMY: (
        "config",
        "The run pinned a chart-of-accounts taxonomy version that is not on disk, or the "
        "file at that version is malformed. Nothing tags against a taxonomy it cannot "
        "read. Add the version under taxonomy/ or pin one that exists; never edit a "
        "listed version in place, because recorded runs cite it.",
    ),
    UNKNOWN_LINE_ITEM: (
        "model",
        "A tagging proposal names a line_item_ref that is not in the normalized table "
        "the step was given, or names one twice. The model was shown every ref; a tag "
        "on a line that does not exist is not a tag. The step is refused; on a repair "
        "pass the proposal has to account for exactly the refs it was given.",
    ),
    UNKNOWN_PRECEDENT: (
        "model",
        "A tagging proposal cited a precedent id the store does not hold within this "
        "engagement's scope. A model cannot invent a precedent, and one from outside "
        "the scope was never shown to it. The citation is dropped and the item goes to "
        "a person; the tag itself may still be right.",
    ),
    PRECEDENT_NO_DECISION: (
        "system",
        "Something asked the Precedent Store to record an example with no human "
        "decision behind it: no decision at that id, a rejection or an escalation, or a "
        "decision naming nobody. The store has exactly one writer and it is downstream "
        "of a person. Nothing was written; find the caller, because this is a bypass "
        "attempt rather than a data problem.",
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
        "run_manifest@1.1.0. This is a defect in the writer or a gap in what the run "
        "recorded; the run is not closed out until a valid manifest exists, because a "
        "run with no defensible record is worse than a run that visibly failed.",
    ),
}


def diagnose(
    code: str,
    detail: str = "",
    locator: str = "",
    *,
    expected: object = "",
    found: object = "",
    delta: object = "",
    step_id: str = "",
    skill: str = "",
    retryable: bool = False,
) -> Diagnostic:
    """Build a diagnostic from a registered code. An unregistered code is a bug here."""
    owner, what_now = WHAT_NOW[code]
    return Diagnostic(
        code=code,
        owner=owner,
        what_now=what_now,
        detail=detail,
        locator=locator,
        expected="" if expected == "" else str(expected),
        found="" if found == "" else str(found),
        delta="" if delta == "" else str(delta),
        step_id=step_id,
        skill=skill,
        retryable=retryable,
    )
