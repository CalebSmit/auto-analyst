"""Procedures: the mechanical half of each skill, beside the harness that runs it.

A SKILL.md says what the model does; a procedure says what the code around it does -
what to send, how to read the answer, how to turn it into the output through the tools
the registry allows. The skill tree holds no Python (P10 made that a test), so the
procedures live here, one module per skill, found by the skill's name.
"""

from __future__ import annotations

from harness.dispatch import Procedure
from harness.procedures.ebitda_normalization import EbitdaNormalization, EbitdaVerification
from harness.procedures.line_item_tagging import LineItemTagging
from harness.procedures.model_load import ModelLoad
from harness.procedures.timing_normalization import TimingNormalization

PROCEDURES: dict[str, type[Procedure]] = {
    "timing-normalization": TimingNormalization,
    "line-item-tagging": LineItemTagging,
    "ebitda-normalization": EbitdaNormalization,
    "model-load": ModelLoad,
}

# The self-verification pass, where a skill has one: a separate invocation of the same
# skill that sees the proposal and the evidence and never the first pass's reasoning.
VERIFIERS: dict[str, type[Procedure]] = {
    "ebitda-normalization": EbitdaVerification,
}

__all__ = ["PROCEDURES", "VERIFIERS", "procedure_for", "verifier_for"]


def procedure_for(skill: str) -> Procedure:
    name = skill.split("@", 1)[0]
    if name not in PROCEDURES:
        raise KeyError(f"no procedure for {name!r}; the skill has no mechanical half yet")
    return PROCEDURES[name]()


def verifier_for(skill: str) -> Procedure:
    name = skill.split("@", 1)[0]
    if name not in VERIFIERS:
        raise KeyError(f"no verification pass for {name!r}")
    return VERIFIERS[name]()
