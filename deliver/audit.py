"""Auditing a workbook this system delivered: the delivery side's one call into the audit.

A thin module with a reason to exist, and the reason is a boundary rather than a
behaviour. `tools/formula_audit.py` is the engine; this is the only place on the delivery
path that reaches it.

**Why not call the engine directly from each caller.** `tests/p10` holds a non-negotiable:
outside `tools/` itself, only `harness/runtime.py` may bind a tool implementation, and
`ops/` is one of the packages that must stay clean. The first version of the console's
audit route imported `tools.formula_audit` and was correctly refused - not on a
technicality. The rule is there because `ops/` is the *record*: a surface that computes
something is a surface that can disagree with what the run recorded, and the trace in this
build is derived from the event stream precisely so that it cannot. `deliver/` may reach
`tools/` - `deliver/qc.py` already does, for the template writer - because the delivery
path is where work is done rather than reported.

**It imports nothing from `ops`.** Bytes in, findings out, no bus and no store. That is
what lets `ops/console/app.py` import it without a cycle: the console reaches the delivery
side for the reading, and the *recording* of a release audit stays in `deliver/release.py`,
where the bus already is.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from tools.formula_audit import Audit, Finding
from tools.formula_audit import audit as audit_formulas

__all__ = [
    "AUDITED_SUFFIXES",
    "FINDINGS_IN_THE_EVENT",
    "Audit",
    "Finding",
    "audit_workbook",
    "is_a_workbook",
    "worth_seeing",
]

# What the formula audit is run over. A workbook; nothing else has formulas in it.
AUDITED_SUFFIXES = (".xlsx", ".xlsm")

# How many findings travel in the release event. The record is a record, not a report: the
# whole audit is re-derivable from the released bytes, and an event carrying four hundred
# findings is an event nothing will render.
FINDINGS_IN_THE_EVENT = 25


def is_a_workbook(name: str) -> bool:
    """Whether an artifact's name says it has formulas in it.

    On the name and not on the bytes, because the delivery path has the name before it has
    anywhere to put the bytes, and a thing delivered as `carried-across.csv` is not a
    workbook whatever it happens to contain.
    """
    return name.lower().endswith(AUDITED_SUFFIXES)


def audit_workbook(data: bytes, *, include_convention: bool = False) -> Audit:
    """The audit of one workbook's formulas. Reads; writes nothing, repairs nothing."""
    return audit_formulas(data, include_convention=include_convention)


def worth_seeing(result: Audit) -> Sequence[Finding]:
    """The findings a person should look at: the file disagreeing with itself, and the
    patterns that break. Not the convention findings, which are correct and, on a workbook
    this build did not write, numerous."""
    return result.of("wrong", "suspect")


def as_event_payload(name: str, result: Audit) -> dict[str, Any]:
    """What the release records about an audit.

    Here rather than in `release.py` so the shape of the payload and the audit it
    describes are decided in one place - the console reads this payload back, and two
    modules agreeing on a dict by having both been written on the same evening is the
    kind of agreement that stops holding.
    """
    seen = worth_seeing(result)
    return {
        "artifact": name,
        "formulas": result.formulas,
        "counts": {
            severity: len(result.of(severity))
            for severity in ("wrong", "suspect", "convention")
        },
        "findings": [f.as_dict() for f in seen[:FINDINGS_IN_THE_EVENT]],
        "truncated": max(0, len(seen) - FINDINGS_IN_THE_EVENT),
        "did_not_run": list(result.skipped),
    }
