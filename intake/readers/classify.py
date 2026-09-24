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
    # Added at P96 from the first real client folder this build was shown. Every one of
    # these arrived in it, and every one answers a numbered item on the request list that
    # nothing could previously satisfy. They are not guesses about what a client might
    # send; they are what one did.
    "board_minutes",
    "org_chart",
    "employee_roster",
    "customer_detail",
    "competitor_list",
    "capex_schedule",
    "nonrecurring_items",
    "stockholder_list",
    "business_overview",
    "other",
)

# Word patterns that identify a class, and their weight. Two strong cues make a confident
# answer; one makes a tentative one; a tie is "other" rather than a coin toss.
_CUES: dict[str, tuple[tuple[str, float], ...]] = {
    "trial_balance": (
        (r"\btrial balances?\b", 1.0),
        (r"\bTB(?:[_\s-]|\b)", 0.6),
        (r"\bdebit\b.*\bcredit\b", 1.0),
        (r"\baccount (?:no|number|#)\b", 0.4),
    ),
    "financial_statements": (
        (
            r"\bincome statements?\b|\bstatements? of (?:income|operations)\b|\bprofit and loss\b|\bP&L\b",
            1.0,
        ),
        (r"\bbalance sheets?\b|\bstatements? of financial position\b", 1.0),
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
        (r"\brequest (?:list|schedule)s?\b|\binformation requests?\b", 1.0),
        (r"\bitem\s*#?\b.*\bstatus\b", 0.4),
    ),
    "participant_census": (
        (r"\bcensus\b", 1.0),
        (r"\bparticipant\b", 0.6),
        (r"\bdate of (?:birth|hire)\b|\bDOB\b", 0.6),
    ),
    "tax_return": (
        (r"\bform 1120\b|\bform 1065\b|\bform 1040\b", 1.2),
        (r"\btax returns?\b", 1.0),
        (r"\btaxable income\b", 0.5),
    ),
    "plan_document": (
        (r"\bplan documents?\b", 1.0),
        (r"\bESOP\b.*\bplan\b", 0.5),
        (r"\bvesting\b|\bforfeiture\b", 0.4),
    ),
    "gl_detail": (
        (r"\bgeneral ledgers?\b|\bGL details?\b", 1.0),
        (r"\bjournal\b", 0.5),
        (r"\bposting date\b|\bdocument (?:no|number)\b", 0.5),
    ),
    "cap_table": (
        (r"\bcap(?:italization)? tables?\b", 1.0),
        (r"\bshares? (?:outstanding|held)\b", 0.6),
        (r"\bshareholder\b|\bstockholder\b", 0.5),
    ),
    # ------------------------------------------------------------------- added at P96
    # Every class below arrived in the first real client folder this build was shown, and
    # every one answers a numbered request-list item that nothing could previously satisfy.
    # They are not guesses about what a client might send; they are what one did.
    "board_minutes": (
        (r"\b(?:board|shareholder|stockholder|director)s?['’]? (?:meeting )?minutes\b", 1.0),
        (r"\bminutes of (?:the |a )?(?:annual |special |regular )?(?:board|meeting)\b", 1.0),
        (r"\bboard of directors\b", 0.6),
        (r"\bresolved,? that\b|\bcalled to order\b|\bmotion (?:was )?(?:duly )?(?:made|carried)\b", 0.6),
    ),
    "org_chart": (
        (r"\borg(?:ani[sz]ation(?:al)?)? charts?\b", 1.2),
        (r"\breporting structure\b|\borgani[sz]ation(?:al)? structure\b", 0.6),
    ),
    # Distinct from `participant_census`, which is a plan filing's census and carries dates
    # of birth and hours. This is the headcount a valuation asks for: who works here, doing
    # what. One class for both would let a plan filing satisfy an operational request.
    "employee_roster": (
        (r"\bemployee (?:count|list|roster|classification|headcount)s?\b", 1.0),
        (r"\bheadcount\b|\bstaffing (?:level|summary)\b", 0.8),
        (r"\bfull[- ]time\b.*\bpart[- ]time\b|\bFTEs?\b", 0.5),
        (r"\bnumber of employees\b", 0.6),
    ),
    "customer_detail": (
        (r"\btop \d+ customers\b|\bcustomer concentration\b", 1.2),
        (r"\brevenue by customer\b|\bsales by customer\b", 1.0),
        (r"\b(?:major|largest|key|principal) customers\b", 0.8),
        (r"\bcustomer (?:list|name)s?\b", 0.5),
    ),
    "competitor_list": (
        (r"\b(?:list of |principal |key |major )?competitors?\b", 1.0),
        (r"\bcompetitive (?:landscape|position)\b", 0.8),
        (r"\bcompeting (?:companies|firms)\b", 0.6),
    ),
    "capex_schedule": (
        (r"\bcapital expenditures?\b|\bcap ?ex\b", 1.0),
        (r"\bfixed asset (?:register|schedule|addition)s?\b", 0.8),
        (r"\bdepreciation schedule\b", 0.6),
        (r"\badditions\b.*\bdisposals\b", 0.5),
    ),
    "nonrecurring_items": (
        (r"\bnon-?recurring\b|\bnon-?operating\b", 1.0),
        (r"\bone-?time (?:income|expenses?|charges?|items?)\b", 0.8),
        (r"\b(?:normali[sz]ing|normali[sz]ation) adjustments?\b", 0.8),
        (r"\badd-?backs?\b", 0.6),
    ),
    # Kept apart from `cap_table`: a stockholder list names holders and their shares, while a
    # cap table also carries options, warrants and every other right. Reading one as the
    # other would mark the fully-diluted request satisfied by a document that does not
    # answer it. Both satisfy B.3; only one answers all of it, and keeping that distinction
    # is the reader's job rather than the analyst's.
    "stockholder_list": (
        (r"\blist of (?:stock|share)holders\b|\b(?:stock|share)holder (?:list|register|schedule)s?\b", 1.2),
        (r"\bholders? of record\b", 0.8),
        (r"\bshares? held\b.*\bpercent\b|\bownership percentage\b", 0.5),
    ),
    # The narrative rather than the numbers: what the business does, who it sells to, how it
    # competes, what management said. It repeats the words a forecast and a statement also
    # use - it quotes both - so its cues are the section headings a write-up has and a data
    # file does not.
    "business_overview": (
        (r"\bsources of information\b", 1.0),
        (r"\b(?:company|business) (?:overview|description|profile)\b|\bdescription of the business\b", 1.0),
        (r"\bcompetitive position\b|\bproducts and services\b|\bcustomers and suppliers\b", 0.8),
        (r"\b(?:recent developments|outlook)\b", 0.5),
        (r"\bmanagement (?:indicated|represented|noted|stated)\b", 0.8),
        (r"\bnotes? from (?:client |management )?meetings?\b", 0.8),
    ),
}
_COMPILED = {
    cls: tuple((re.compile(p, re.IGNORECASE | re.DOTALL), w) for p, w in cues)
    for cls, cues in _CUES.items()
}
CONFIDENT = 1.2
TENTATIVE = 0.8


NAMED = 3
"""A cue in the file's own name. The most specific thing anybody said about it."""
INSIDE = 2
"""A cue in the sheet names, headers or first rows - what the document says of itself."""
FILED = 1
"""A cue in a folder along the path. True of every file in that folder, so it is the
weakest of the three and the only one that can be wrong about a particular file."""

FOLDER_WEIGHT = 0.85
"""What a folder cue is worth against the same cue in a filename.

Below 1.0 and above `TENTATIVE`, and both bounds are load-bearing.

Below 1.0, because a folder says something true of everything in it and the folder that
forced this is real: `Historical and Forecasted Financial Statements/` holds balance sheets,
income statements *and* projections. At full weight the word "Forecasted" would make every
file in it a forecast - the exact error P38 exists to prevent, projected years entering the
historical table.

Above the tentative bar, because `Board Minutes/2023.pdf` is a scan with a name that says
nothing, and the client still told us what it is by putting it there. A folder that could
never on its own reach a verdict would be evidence the code collects and then ignores."""


def _spaced(name: str) -> str:
    """An underscore in a path is a space.

    Found on the first real client folder, where every file was named `<thing>_Redacted.pdf`
    and almost nothing classified. A cue ends in `\\b`, an underscore is a word character,
    and so `minutes\\b` does not match `Minutes_Redacted` - there is no boundary between `s`
    and `_`. Silently, and for every cue in the table at once.

    The fix belongs here rather than in the patterns. Widening each `\\b` to
    `(?:\\b|_)` would be forty edits, would have to be remembered by everyone who adds a
    forty-first, and would still miss the `Org_Chart` spelling where the underscore is
    inside the phrase rather than after it. A name is a phrase somebody wrote with the
    separators their filesystem allowed; reading it as words costs one substitution.
    """
    return name.replace("_", " ")


@dataclass(frozen=True)
class Evidence:
    filename: str
    headers: list[str] = field(default_factory=list)
    first_rows: list[str] = field(default_factory=list)
    sheet_names: list[str] = field(default_factory=list)
    folders: list[str] = field(default_factory=list)
    """The folders the file sits in, outermost first, excluding the watched root.

    Added at P96. A client who files a document under `Board Minutes` has told us what it
    is, in the plainest way available, and until P96 the tool discarded that before looking
    at anything. `folders` is last in the field order because the tests that build an
    Evidence positionally predate it."""

    def text(self) -> str:
        return "\n".join(
            [self.filename, *self.sheet_names, *self.headers, *self.first_rows, *self.folders]
        )

    def zones(self) -> tuple[tuple[str, str, float, int], ...]:
        """Each place a cue could be found, with what it is worth and how specific it is."""
        return (
            ("its name", _spaced(self.filename), 1.0, NAMED),
            (
                "what is in it",
                "\n".join([*(_spaced(n) for n in self.sheet_names), *self.headers, *self.first_rows]),
                1.0,
                INSIDE,
            ),
            (
                "the folder it is filed in",
                "\n".join(_spaced(f) for f in self.folders),
                FOLDER_WEIGHT,
                FILED,
            ),
        )


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
    scores: dict[str, float] = {}
    reasons: dict[str, list[str]] = {}
    found_at: dict[str, int] = {}
    for where, text, multiplier, specificity in evidence.zones():
        if not text:
            continue
        for cls, cues in _COMPILED.items():
            for pattern, weight in cues:
                match = pattern.search(text)
                if not match:
                    continue
                scored = weight * multiplier
                scores[cls] = scores.get(cls, 0.0) + scored
                found_at[cls] = max(found_at.get(cls, 0), specificity)
                reasons.setdefault(cls, []).append(
                    f"{match.group(0)!r} in {where} (+{scored:g})"
                )
    if not scores:
        return Classification("other", 0.0, ("no recognisable cue in the headers or first rows",))
    if "forecast" in scores and "financial_statements" in scores:
        # A forecast is shaped like the statements it projects, so it scores on every
        # statement cue. Read as historicals, projected years would enter the historical
        # table and could satisfy a recipe waiting for the real ones. The safe error is the
        # other way round: a historical file with a budget column waits for a person.
        #
        # Unless the only forward-looking cue is the folder. `Historical and Forecasted
        # Financial Statements/Consolidated Balance Sheets.xlsx` is a balance sheet filed
        # beside a forecast, and promoting it here would have been P38's own bug arriving
        # by a new road.
        if found_at["forecast"] >= found_at["financial_statements"]:
            statements = scores.pop("financial_statements")
            reasons["forecast"].append(
                f"forward-looking cue outranks the statement cues ({statements:g} for "
                "financial_statements)"
            )
            scores["forecast"] = max(scores["forecast"], statements)
        else:
            demoted = scores.pop("forecast")
            reasons["financial_statements"].append(
                f"the only forward-looking cue is the folder it is filed in ({demoted:g}), "
                "and the file itself says statement"
            )
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, score = ranked[0]
    # A close second makes the answer "other" rather than a coin toss - but only a second
    # that was found somewhere as specific as the winner.
    #
    # Found by C57. `Board Minutes/Trial Balance 2023.xlsx` scores trial_balance 1.0 from
    # the filename and board_minutes 0.85 from the folder, a margin of 0.15, and went to
    # "other". Before P96 that file was a trial balance in any folder, so reading folders
    # had *created* the ambiguity it then refused to resolve - a plain regression, and the
    # sort that looks like caution. A folder is true of every file in it and cannot make a
    # particular file's own name doubtful. Two cues of equal specificity still can.
    contenders = [
        (cls, value) for cls, value in ranked[1:] if found_at[cls] >= found_at[best]
    ]
    runner_up = contenders[0][1] if contenders else 0.0
    if score < TENTATIVE or (runner_up and score - runner_up < 0.3):
        why = f"strongest cue is {best} at {score:g}, " + (
            f"but {contenders[0][0]} scores {runner_up:g}"
            if runner_up
            else "below the tentative bar"
        )
        return Classification("other", min(score / CONFIDENT, 0.79), (why, *reasons[best]), scores)
    confidence = min(1.0, score / CONFIDENT)
    return Classification(best, round(confidence, 2), tuple(reasons[best]), scores)
