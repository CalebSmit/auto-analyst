# ruff: noqa: E501 - the patterns read better on one line each
"""The Document Classifier: works out what each file actually is.

A closed set - the Contract Registry's intake document types plus general-ledger detail
and a cap table - and "other", which is a valid, common answer that routes to a person.
Having "other" be a first-class outcome rather than a forced choice is what stops the
system confidently mis-filing an unusual document and building on it for the rest of
the run.

Deterministic first: headers and the first rows carry the words a person would use to
recognise the document, and a closed vocabulary of them classifies most files without a
model. The blueprint's small model call is for the residue and lands with the dispatcher
that can make it; the shape here is what it would fill in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["CLASSES", "Classification", "Evidence", "audited_evidence", "classify"]

# What only an audit leaves on a set of financial statements: the auditor's report, or its
# opinion paragraph. A compilation or review report is not an audit and does not match.
_AUDITED = re.compile(
    r"independent auditor['’]?s['’]? report"
    r"|report of independent (?:certified public accountants|registered public accounting firm)"
    r"|in our opinion,? the (?:accompanying )?(?:consolidated )?financial statements present fairly",
    re.IGNORECASE,
)

CLASSES = (
    "trial_balance",
    "financial_statements",
    "forecast",
    "ddr_response",
    "request_schedule",
    "participant_census",
    "tax_return",
    "plan_document",
    "gl_detail",
    "cap_table",
    "other",
)

# Word patterns that identify a class, and their weight. Two strong cues make a confident
# answer; one makes a tentative one; a tie is "other" rather than a coin toss.
_CUES: dict[str, tuple[tuple[str, float], ...]] = {
    "trial_balance": (
        (r"\btrial balance\b", 1.0),
        (r"\bTB(?:[_\s-]|\b)", 0.6),
        (r"\bdebit\b.*\bcredit\b", 1.0),
        (r"\baccount (?:no|number|#)\b", 0.4),
    ),
    "financial_statements": (
        (
            r"\bincome statement\b|\bstatement of (?:income|operations)\b|\bprofit and loss\b|\bP&L\b",
            1.0,
        ),
        (r"\bbalance sheet\b|\bstatement of financial position\b", 1.0),
        (r"\bcash flows?\b", 0.6),
        (r"\btotal assets\b|\btotal liabilities\b", 0.6),
        (r"\bnet income\b|\bgross (?:profit|margin)\b|\bEBITDA\b", 0.5),
    ),
    # Forward-looking cues. Weighted like any other, then given precedence over the statement
    # cues above in `classify`, because a forecast carries every one of those.
    "forecast": (
        (r"\bforecast(?:s|ed)?\b|\bprojections?\b|\bprojected\b|\bpro ?forma\b", 1.0),
        (r"\bbudget(?:s|ed)?\b", 0.8),
        # "2026E" - estimate. Not P or F: "2025 P&L" is a historical statement.
        (r"\b(?:FY)?(?:19|20)\d{2}E\b", 0.6),
    ),
    "ddr_response": ((r"\bdue diligence\b", 0.8), (r"\bDDR\b", 0.8), (r"\bresponse\b", 0.3)),
    "request_schedule": (
        (r"\brequest (?:list|schedule)\b|\binformation request\b", 1.0),
        (r"\bitem\s*#?\b.*\bstatus\b", 0.4),
    ),
    "participant_census": (
        (r"\bcensus\b", 1.0),
        (r"\bparticipant\b", 0.6),
        (r"\bdate of (?:birth|hire)\b|\bDOB\b", 0.6),
    ),
    "tax_return": (
        (r"\bform 1120\b|\bform 1065\b|\bform 1040\b", 1.2),
        (r"\btax return\b", 1.0),
        (r"\btaxable income\b", 0.5),
    ),
    "plan_document": (
        (r"\bplan document\b", 1.0),
        (r"\bESOP\b.*\bplan\b", 0.5),
        (r"\bvesting\b|\bforfeiture\b", 0.4),
    ),
    "gl_detail": (
        (r"\bgeneral ledger\b|\bGL detail\b", 1.0),
        (r"\bjournal\b", 0.5),
        (r"\bposting date\b|\bdocument (?:no|number)\b", 0.5),
    ),
    "cap_table": (
        (r"\bcap(?:italization)? table\b", 1.0),
        (r"\bshares? (?:outstanding|held)\b", 0.6),
        (r"\bshareholder\b|\bstockholder\b", 0.5),
    ),
}
_COMPILED = {
    cls: tuple((re.compile(p, re.IGNORECASE | re.DOTALL), w) for p, w in cues)
    for cls, cues in _CUES.items()
}
CONFIDENT = 1.2
TENTATIVE = 0.8


@dataclass(frozen=True)
class Evidence:
    filename: str
    headers: list[str] = field(default_factory=list)
    first_rows: list[str] = field(default_factory=list)
    sheet_names: list[str] = field(default_factory=list)

    def text(self) -> str:
        return "\n".join([self.filename, *self.sheet_names, *self.headers, *self.first_rows])


@dataclass(frozen=True)
class Classification:
    document_type: str
    confidence: float
    reasons: tuple[str, ...] = ()
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def review_required(self) -> bool:
        return self.document_type == "other" or self.confidence < 0.8


def audited_evidence(text: str) -> str | None:
    """The phrase showing a document carries an audit opinion, or None. Returned rather than
    a bare flag so the record says why a source was treated as audited."""
    found = _AUDITED.search(text or "")
    return found.group(0) if found else None


def classify(evidence: Evidence) -> Classification:
    text = evidence.text()
    scores: dict[str, float] = {}
    reasons: dict[str, list[str]] = {}
    for cls, cues in _COMPILED.items():
        for pattern, weight in cues:
            match = pattern.search(text)
            if match:
                scores[cls] = scores.get(cls, 0.0) + weight
                reasons.setdefault(cls, []).append(f"{match.group(0)!r} (+{weight:g})")
    if not scores:
        return Classification("other", 0.0, ("no recognisable cue in the headers or first rows",))
    if "forecast" in scores and "financial_statements" in scores:
        # A forecast is shaped like the statements it projects, so it scores on every
        # statement cue. Read as historicals, projected years would enter the historical
        # table and could satisfy a recipe waiting for the real ones. The safe error is the
        # other way round: a historical file with a budget column waits for a person.
        statements = scores.pop("financial_statements")
        reasons["forecast"].append(
            f"forward-looking cue outranks the statement cues ({statements:g} for "
            "financial_statements)"
        )
        scores["forecast"] = max(scores["forecast"], statements)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    if score < TENTATIVE or (runner_up and score - runner_up < 0.3):
        why = f"strongest cue is {best} at {score:g}, " + (
            f"but {ranked[1][0]} scores {runner_up:g}" if runner_up else "below the tentative bar"
        )
        return Classification("other", min(score / CONFIDENT, 0.79), (why, *reasons[best]), scores)
    confidence = min(1.0, score / CONFIDENT)
    return Classification(best, round(confidence, 2), tuple(reasons[best]), scores)
