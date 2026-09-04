"""Orchestration: the model proposes a plan, and the plan is still compiled and asserted.

Three blueprint nodes:

* `orchestrator.py` - the Orchestrator Agent. One mid-tier call whose context holds the
  Skill Index and the job manifest, never a SKILL.md body. Returns a plan proposal with
  no numeric field in it anywhere.
* `plan.py` - the Run Plan. A proposal becomes a `Recipe` and goes through the same
  compiler and the same plan assertions as a named one; if it does not survive, the named
  recipe runs and the refusal is on the record. The compiled plan is written down as an
  artifact before execution begins.
* `triage.py` - Triage & Escalation. The high-tier fallback for when nothing fits, whose
  output schema has no shape a number could be recorded in.

This arrives last on purpose. Every phase before it ran on named recipes, so the
verification spine was proven against a fixed plan before anything model-driven produced
one.
"""

from orchestrate.manifest import DocumentSummary, JobManifest, RecipeOption
from orchestrate.orchestrator import (
    ORCHESTRATOR_VERSION,
    PROPOSAL_CONTRACT,
    Orchestrator,
    Proposal,
)
from orchestrate.plan import (
    PLAN_CONTRACT,
    PROPOSED_RECIPE,
    REQUIRED_LOOPS,
    Planned,
    RunPlanner,
    recipe_from_proposal,
    run_plan_document,
)
from orchestrate.triage import TRIAGE_CONTRACT, Assessment, Triage

__all__ = [
    "ORCHESTRATOR_VERSION",
    "PLAN_CONTRACT",
    "PROPOSAL_CONTRACT",
    "PROPOSED_RECIPE",
    "REQUIRED_LOOPS",
    "TRIAGE_CONTRACT",
    "Assessment",
    "DocumentSummary",
    "JobManifest",
    "Orchestrator",
    "Planned",
    "Proposal",
    "RecipeOption",
    "RunPlanner",
    "Triage",
    "recipe_from_proposal",
    "run_plan_document",
]
