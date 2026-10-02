"""The questions a managing director asks on first looking at the numbers.

The third of the three reads the analyst asked for: *"from a managing director standpoint,
does the valuation actually make sense"*. It is a different kind of check from the other
two and the difference is the whole design.

`formula_audit.py` says a file disagrees with itself. `prose_checks.py` says a reader will
notice something. Both are statements about an artifact, provable from the artifact.
Nothing here is. **Every finding in this module is a question for a person**, because the
answer depends on the business: a gross margin that moves eight points is a problem in one
industry and a Tuesday in another, and this code has no way to know which. So the evidence
reads as a question, the module concludes nothing, and the thresholds have no defaults -
materiality belongs to the practice (BUILD/OPEN.md section 2), and a default would be this
build quietly setting one.

**What it is not.** Not the valuation. Multiples, discount rates and the conclusion of
value are outside version 1's path and outside anything that could be checked this way -
"nothing concludes, signs or certifies" is the invariant, and a tool that said a valuation
was reasonable would be the clearest possible breach of it. What this reads is the
*historicals*: the table the analyst gathers, before any of that.

**What it does not duplicate.** A single line moving a lot between periods is
`statement_checks.movements`, and it is not re-checked here. The charter of this module is
the thing no single-line check can see:

* **a line that implies another**, and the other is not there. Depreciation with no fixed
  assets. Interest expense with no debt - which is the first question an MD asks and the
  one that feeds the debt tab. Tax expense in a year with a loss before tax. Amortisation
  with no intangibles. A lease liability with no right-of-use asset.
* **a ratio over time**. Gross margin, operating margin, days receivable, days inventory,
  days payable, the current ratio. Each computed from the tagged table and reported when
  it moves more than the caller said to tolerate.
* **the shape of the history**. A year missing from the middle of the range, and fewer
  years than the engagement asked for.

It shares `Line` and the finding shape with `statement_checks.py` deliberately, so the
two compose into one `qc_findings` list rather than into two answers somebody has to
reconcile. Arithmetic goes through `tools.recompute` for the same reason: there is no
second adder in this build. Which lines are operating expenses, current assets or current
claims is asked of the pinned taxonomy rather than listed here, so a new chart of accounts
does not leave a ratio quietly computed over the wrong set.

    python -m uv run python tools/reasonableness.py <table.json> --move points=5 --move days=10
    python -m uv run python tools/reasonableness.py <table.json> --move x=0.5 --years 5

The file is the normalized table as `{"lines": [{"category", "amounts", "locator",
"label"}], "stated": {...}}` - what `timing-normalization` and `line-item-tagging` produce
between them, and what `tools/normalize.py` writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # this is run as a script, from wherever somebody is standing
    sys.path.insert(0, str(ROOT))

from tools._environment import needs  # noqa: E402

# What this tool cannot run without. Called here, before the first project import, because
# that import is where a bare `python tools/reasonableness.py` fails - and what it fails with is a
# traceback about somebody else's library rather than the line to type. P58 was written
# about that failure for `serve.py`; six more tools had it, and this is one of them.
needs("yaml", script="tools/reasonableness.py")

from registries.taxonomy import Taxonomy, load_taxonomy  # noqa: E402
from tools.recompute import recompute  # noqa: E402
from tools.statement_checks import Line, _finding, _money  # noqa: E402

__all__ = [
    "IMPLICATIONS",
    "Implication",
    "Ratio",
    "implications",
    "lines_from",
    "ratios",
    "ratios_for",
    "report",
    "run_questions",
    "shape_of_the_history",
    "tax_in_a_loss_year",
]

# Days in a year, for the working-capital ratios. 365 and not 360: the analyst's own
# spreadsheets use 365, and a ratio computed one way here and another way there is two
# numbers for one thing, which is the failure this module's shared `Line` exists to avoid.
DAYS = 365

# How far below a tolerance a move may land and still count as reaching it.
#
# Not a second tolerance - it is 1e-9 against numbers in the tens - but without it a
# tolerance is a coin toss at its own boundary. A margin of exactly 60.0 and one of
# exactly 55.0 are 4.999999999999993 apart in binary, so "a move of five points or more"
# with a tolerance of five reported nothing, which is the least defensible possible
# behaviour for a threshold somebody chose on purpose.
AT_THE_BOUNDARY = 1e-9


def _reaches(move: float, tolerance: float) -> bool:
    return abs(move) + AT_THE_BOUNDARY >= tolerance


class Implication:
    """A line whose presence implies another line, and the question when it is missing.

    `present` and `expected` are category sets rather than single categories because the
    thing implied is usually a group: interest expense implies *some* form of borrowing,
    and which form is the client's business.
    """

    def __init__(
        self,
        name: str,
        present: Iterable[str],
        expected: Iterable[str],
        asks: str,
        *,
        both_ways: bool = False,
    ) -> None:
        self.name = name
        self.present = frozenset(present)
        self.expected = frozenset(expected)
        self.asks = asks
        self.both_ways = both_ways
        """Whether the absence of `present` beside the presence of `expected` is also a
        question. Debt with no interest expense and interest expense with no debt are both
        worth asking about; tax expense without a loss is not a question at all."""


DEBT = ("line_of_credit", "current_debt", "long_term_debt", "lease_liability")

# Every line-implies-a-line question, as data. A table rather than code so the set can be
# read, argued with and added to by somebody who knows the work better than the person who
# wrote the module - which, for a question about what an MD asks, is the point.
IMPLICATIONS: tuple[Implication, ...] = (
    Implication(
        "depreciation and fixed assets",
        present=("depreciation",),
        expected=("ppe", "accumulated_depreciation"),
        asks=(
            "there is depreciation expense and no fixed assets on the balance sheet. "
            "Either the asset schedule has not arrived, or the expense belongs to "
            "something held off balance sheet - which is an add-back question"
        ),
        both_ways=True,
    ),
    Implication(
        "amortisation and intangibles",
        present=("amortization",),
        expected=("intangibles",),
        asks=(
            "there is amortisation expense and no intangible assets. Usually a prior "
            "acquisition whose balance has been written off, which is worth knowing "
            "about before the forecast"
        ),
    ),
    Implication(
        "interest expense and debt",
        present=("interest_expense",),
        expected=DEBT,
        asks=(
            "there is interest expense and no debt on the balance sheet. The long-term "
            "debt note is the document that answers this, and it is also what the "
            "forecast's interest expense is built from"
        ),
        both_ways=True,
    ),
    Implication(
        "a lease liability and a right-of-use asset",
        present=("lease_liability",),
        expected=("right_of_use_asset",),
        asks=(
            "there is a lease liability and no right-of-use asset. One side of the lease "
            "standard has been recorded and the other has not"
        ),
        both_ways=True,
    ),
    Implication(
        "inventory and cost of sales",
        present=("inventory",),
        expected=("cost_of_sales",),
        asks=(
            "there is inventory on the balance sheet and no cost of sales. A business "
            "holding stock and reporting no cost of what it sold is a presentation "
            "question before it is anything else"
        ),
    ),
    Implication(
        "related-party rent",
        present=("rent", "related_party_payable"),
        expected=(),
        asks=(
            "there is rent expense and a related-party balance. If the premises are "
            "owned by the owner, the market-rent question belongs on the add-back "
            "schedule and needs a fact from outside the statements"
        ),
    ),
)


class Ratio:
    """A ratio over the tagged table, and what it is called when it moves."""

    def __init__(
        self,
        name: str,
        numerator: Iterable[str],
        denominator: Iterable[str],
        *,
        scale: float = 1.0,
        as_days: bool = False,
        unit: str = "points",
        possible: tuple[float | None, float | None] = (None, None),
    ) -> None:
        self.name = name
        self.numerator = tuple(numerator)
        self.denominator = tuple(denominator)
        self.scale = scale
        self.as_days = as_days
        self.unit = unit
        self.possible = possible
        """The range this ratio's arithmetic can produce, or (None, None) for no bound.

        Not a plausibility band and not a tolerance - those are the practice's decision and
        there are no defaults for them anywhere in this module. This is narrower and harder:
        a value outside it cannot be produced by the formula from a table of the shape the
        formula is defined on, so it is a statement about the table rather than about the
        business, and the question the other findings ask of it is not answerable.

        A gross margin above 100 points would need costs that add to revenue. Days
        receivable below zero would need a negative receivable over positive revenue. The
        current ratio below zero would need one side of it negative. Each has one ordinary
        cause: a table carrying signed amounts where these are defined on magnitudes.
        """


def _in_section(taxonomy: Taxonomy, *sections: str) -> tuple[str, ...]:
    """Every category the taxonomy puts in one of these sections.

    Asked of the taxonomy rather than listed here. Which lines are operating expenses and
    which are current is the taxonomy's answer, it is versioned, and a hand-written copy
    is a copy that goes quietly out of date - which is how the operating margin would one
    day be computed over fifteen of the seventeen operating expense lines and look
    entirely plausible while doing it.
    """
    wanted = set(sections)
    return tuple(
        sorted(c.id for c in taxonomy.categories.values() if c.section in wanted)
    )


def ratios_for(taxonomy: Taxonomy) -> tuple[Ratio, ...]:
    """The ratios, built against a taxonomy version.

    A function rather than a constant because three of the six are sums over a *section* -
    every operating expense, every current asset, every current claim - and a section's
    membership belongs to the taxonomy the run pinned.

    `lease_liability` is deliberately in neither side of the current ratio: the taxonomy
    puts it in `liabilities` rather than in a current or non-current section, because the
    split between the two is not on the face of the statements. Putting the whole of it in
    either side would make the ratio wrong in a way nobody could see.
    """
    operating = _in_section(taxonomy, "operating_expenses")
    return (
        # Only the bound the arithmetic gives. A margin has no floor - a business can lose
        # more than it earns, and a reviewer wants to be asked about that rather than told
        # it is impossible - so the lower bound is left open on both margins.
        Ratio(
            "gross margin",
            ("revenue", "-cost_of_sales"),
            ("revenue",),
            scale=100.0,
            possible=(None, 100.0),
        ),
        Ratio(
            "operating margin",
            ("revenue", "-cost_of_sales", *(f"-{c}" for c in operating)),
            ("revenue",),
            scale=100.0,
            possible=(None, 100.0),
        ),
        Ratio(
            "the current ratio",
            _in_section(taxonomy, "current_assets"),
            _in_section(taxonomy, "current_liabilities"),
            unit="x",
            possible=(0.0, None),
        ),
        Ratio(
            "days receivable",
            ("accounts_receivable",),
            ("revenue",),
            as_days=True,
            unit="days",
            possible=(0.0, None),
        ),
        Ratio(
            "days inventory",
            ("inventory",),
            ("cost_of_sales",),
            as_days=True,
            unit="days",
            possible=(0.0, None),
        ),
        Ratio(
            "days payable",
            ("accounts_payable",),
            ("cost_of_sales",),
            as_days=True,
            unit="days",
            possible=(0.0, None),
        ),
    )


# --------------------------------------------------------------------------- helpers


def _amounts(lines: Sequence[Line], categories: Iterable[str], period: str) -> list[float]:
    wanted = set(categories)
    return [
        line.amounts[period]
        for line in lines
        if line.category in wanted and period in line.amounts
    ]


def _total(lines: Sequence[Line], terms: Sequence[str], period: str) -> float | None:
    """A signed sum over categories, where a term prefixed `-` subtracts.

    Through `recompute` rather than `sum`, because every total in this build is taken by
    one adder. `None` when no term contributed anything in the period: a ratio over
    nothing is not zero, it is unanswerable.
    """
    plus: list[float] = []
    minus: list[float] = []
    for term in terms:
        found = _amounts(lines, [term.lstrip("-")], period)
        (minus if term.startswith("-") else plus).extend(found)
    if not plus and not minus:
        return None
    return recompute("difference", [plus, minus], 0.0, tolerance=0.0).recomputed


def _has(lines: Sequence[Line], categories: Iterable[str], period: str) -> bool:
    """Whether any of these categories carries a non-zero amount in the period.

    Zero is treated as absence on purpose: a balance sheet that lists `Long-term debt`
    with nothing against it is telling us there is no debt, and a check that read the
    label rather than the amount would stay silent on exactly the engagement that needed
    the question asked.
    """
    return any(amount != 0 for amount in _amounts(lines, categories, period))


def _periods(lines: Iterable[Line]) -> list[str]:
    return sorted({period for line in lines for period in line.amounts})


# ---------------------------------------------------------------------- the questions


def implications(lines: Sequence[Line]) -> list[dict[str, Any]]:
    """Every line that implies another, asked once per question.

    **Once, naming the periods.** The first version asked per period, and a three-year
    table with depreciation and no fixed assets produced three identical findings - a
    reviewer reads one question and answers it for the history, and three copies of it
    make an eighteen-line report out of six questions. The period still matters and is
    still named, because a client who borrowed in the second year has interest expense in
    two periods and debt in one, and which periods is the useful half of the finding.
    """
    findings: list[dict[str, Any]] = []
    periods = _periods(lines)
    if not periods:
        return [
            _finding(
                "the questions a reviewer asks",
                "could_not_evaluate",
                "the table carries no amounts in any period, so nothing can be asked of it",
            )
        ]

    for rule in IMPLICATIONS:
        gaps: list[str] = []
        reversed_gaps: list[str] = []
        for period in periods:
            if not rule.expected:
                # A question about a pair being present together, not about one missing.
                if all(_has(lines, [one], period) for one in rule.present):
                    gaps.append(period)
                continue
            here = _has(lines, rule.present, period)
            there = _has(lines, rule.expected, period)
            if here and not there:
                gaps.append(period)
            elif rule.both_ways and there and not here:
                reversed_gaps.append(period)

        if gaps:
            findings.append(
                _finding(
                    f"{rule.name} ({_in_words(gaps, periods)})",
                    "fail",
                    f"{_lead(gaps, periods)}{rule.asks}.",
                    locator=_where(lines, rule.present, gaps[0]),
                )
            )
        if reversed_gaps:
            findings.append(
                _finding(
                    f"{rule.name}, the other way round ({_in_words(reversed_gaps, periods)})",
                    "fail",
                    f"{_lead(reversed_gaps, periods)}the opposite of the usual gap: "
                    f"{', '.join(sorted(rule.expected))} is on the table and "
                    f"{', '.join(sorted(rule.present))} is not. Worth the same question "
                    f"from the other side.",
                    locator=_where(lines, rule.expected, reversed_gaps[0]),
                )
            )
        if not gaps and not reversed_gaps:
            findings.append(
                _finding(
                    rule.name,
                    "not_applicable" if not _touched(lines, rule) else "pass",
                    (
                        f"nothing on the table is {' or '.join(sorted(rule.present))}, so "
                        f"the question does not arise"
                    )
                    if not _touched(lines, rule)
                    # "related-party rent appear together" - the rule's name is a
                    # thing, so the sentence is about the pair rather than about it.
                    else f"in every period, {rule.name} is accounted for on both sides",
                )
            )
    return findings


def _in_words(some: Sequence[str], all_of_them: Sequence[str]) -> str:
    """How to name the periods a question applies to, for the check's own title."""
    if len(some) == len(all_of_them):
        return "every period"
    if len(some) == 1:
        return some[0]
    return f"{len(some)} of {len(all_of_them)} periods"


def _and_list(names: Sequence[str]) -> str:
    """`a is`, `a and b are`, `a, b and c are`.

    Carries the verb, because that is the half that keeps getting it wrong: this module has
    already said "related-party rent appear together" and "Cost of sales, Rent is negative
    here", both of which are a list being joined by code that did not know how many things
    were in it.
    """
    if not names:
        return ""
    if len(names) == 1:
        return f"{names[0]} is"
    return f"{', '.join(names[:-1])} and {names[-1]} are"


def _lead(some: Sequence[str], all_of_them: Sequence[str]) -> str:
    """The opening of the evidence sentence, naming the periods exactly.

    Separate from `_in_words` on purpose: the title wants to be short and the evidence
    wants to be exact, and a reviewer answering the question needs the actual years.
    """
    if len(some) == len(all_of_them):
        return "In every period on the table, "
    if len(some) == 1:
        return f"In {some[0]}, "
    return f"In {', '.join(some)}, "


def _touched(lines: Sequence[Line], rule: Implication) -> bool:
    categories = {line.category for line in lines}
    return bool(categories & (rule.present | rule.expected))


def _where(lines: Sequence[Line], categories: Iterable[str], period: str) -> str | None:
    wanted = set(categories)
    for line in lines:
        if line.category in wanted and period in line.amounts and line.amounts[period] != 0:
            return line.locator
    return None


def tax_in_a_loss_year(lines: Sequence[Line], taxonomy: Taxonomy) -> list[dict[str, Any]]:
    """Income tax expense in a year the business lost money before tax.

    An ordinary thing with several ordinary explanations - a state minimum, a prior-year
    true-up, a deferred movement, an S corporation paying tax on something else - and
    every one of them is a fact from outside the statements. So it is asked, and the
    answer goes on the record rather than into a guess about the effective rate.
    """
    findings: list[dict[str, Any]] = []
    operating = _in_section(taxonomy, "operating_expenses")
    before_tax = (
        "revenue",
        "contra_revenue",
        "-cost_of_sales",
        *(f"-{c}" for c in operating),
        "-interest_expense",
        "interest_income",
        "gain_loss_on_disposal",
        "other_income_expense",
    )
    periods = _periods(lines)
    losses: list[tuple[str, float, float]] = []
    unknown: list[str] = []
    for period in periods:
        tax = _total(lines, ("income_tax",), period)
        if tax is None or tax <= 0:
            continue
        pre_tax = _total(lines, before_tax, period)
        if pre_tax is None:
            unknown.append(period)
        elif pre_tax < 0:
            losses.append((period, pre_tax, tax))

    if losses:
        findings.append(
            _finding(
                f"tax in a loss year ({_in_words([p for p, _, _ in losses], periods)})",
                "fail",
                "; ".join(
                    f"{p} shows {_money(before)} before tax and {_money(tax)} of tax"
                    for p, before, tax in losses
                )
                + ". A minimum, a true-up, a deferred movement and an S corporation are "
                "all ordinary answers, and each is a fact from outside the statements.",
                locator=_where(lines, ("income_tax",), losses[0][0]),
            )
        )
    if unknown:
        findings.append(
            _finding(
                f"tax in a loss year ({_in_words(unknown, periods)})",
                "could_not_evaluate",
                f"there is tax expense in {', '.join(unknown)} and not enough of the "
                f"income statement is tagged to work out whether the year was a loss",
            )
        )
    if not losses and not unknown:
        findings.append(
            _finding(
                "tax in a loss year",
                "not_applicable"
                if not any(line.category == "income_tax" for line in lines)
                else "pass",
                "no tax expense is tagged on this table, so the question does not arise"
                if not any(line.category == "income_tax" for line in lines)
                else "no period carries tax expense against a loss before tax",
            )
        )
    return findings


def ratios(
    lines: Sequence[Line], move: Mapping[str, float], taxonomy: Taxonomy
) -> list[dict[str, Any]]:
    """Each ratio over the periods, and every move at or above the tolerance for its unit.

    **`move` is keyed by unit, not one number.** A margin is in points and runs 0 to 100;
    days receivable is in days and runs 20 to 120; the current ratio is in turns and runs
    about 0.5 to 5. One tolerance across all three is a tolerance that is right for one of
    them: `--movement 5` asked a sensible question of the margins, a slightly loose one of
    the days, and no question at all of a current ratio that cannot move five turns.

    A unit with no tolerance given is `could_not_evaluate`, naming the unit. There is no
    default for any of them, because what counts as a move is the practice's decision -
    the same rule `statement_checks.movements` keeps and for the same reason.

    Two comparisons per ratio, and the second is the one an MD actually makes: each step
    between consecutive periods, **and first period to last**. A margin that gives up two
    and a half points a year for three years never trips a step tolerance and has moved
    seven and a half points, which is the whole story of the business.
    """
    for unit, tolerance in move.items():
        if tolerance <= 0:
            raise ValueError(
                f"the tolerance for {unit!r} is {tolerance}; a movement is a positive "
                f"number in the ratio's own unit. There is no default and no zero: a "
                f"tolerance of zero reports every ratio in every period."
            )
    findings: list[dict[str, Any]] = []
    periods = _periods(lines)

    for ratio in ratios_for(taxonomy):
        series: dict[str, float] = {}
        unavailable: list[str] = []
        for period in periods:
            top = _total(lines, ratio.numerator, period)
            bottom = _total(lines, ratio.denominator, period)
            if top is None or bottom is None or bottom == 0:
                unavailable.append(period)
                continue
            value = top / bottom
            series[period] = value * DAYS if ratio.as_days else value * ratio.scale

        if len(series) < 2:
            findings.append(
                _finding(
                    ratio.name,
                    "could_not_evaluate",
                    (
                        f"needs two periods to move between and has {len(series)}"
                        + (f"; no figure for {', '.join(unavailable)}" if unavailable else "")
                    ),
                )
            )
            continue

        allowed: float | None = move.get(ratio.unit)
        ordered = sorted(series)
        reading = ", ".join(f"{p}: {series[p]:,.1f}" for p in ordered)

        # Before anything is asked about how it moved. A reviewer looking at a gross margin
        # of 173 points does not ask what changed in the business; they say the numbers are
        # the wrong way round. Reported once, for the ratio, and the movement questions are
        # not asked at all - every one of them would be a difference between two impossible
        # figures, stated with a confidence this module has not earned.
        low, high = ratio.possible
        impossible = [
            (period, value)
            for period, value in ((p, series[p]) for p in ordered)
            if (low is not None and value < low) or (high is not None and value > high)
        ]
        if impossible:
            bound = (
                f"below {low:,.1f}"
                if low is not None and impossible[0][1] < low
                else f"above {high:,.1f}"
            )
            # The lines that are actually negative, named, rather than a guess at the cause.
            # Naming them is the difference between "something is probably signed" and a
            # row somebody can go and look at. The categories, not every period of them:
            # one signed line is signed in every year, and three periods of the same row is
            # the same fact printed three times.
            involved = {t.lstrip("-") for t in (*ratio.numerator, *ratio.denominator)}
            when = {period for period, _ in impossible}
            signed = sorted(
                {
                    line.label or line.category
                    for line in lines
                    if line.category in involved
                    and any(
                        line.amounts.get(period, 0.0) < 0 for period in when & set(line.amounts)
                    )
                }
            )
            findings.append(
                _finding(
                    ratio.name,
                    "fail",
                    # Short, because one signed table trips four of the six ratios and a
                    # reader meets this sentence four times in a row. Everything that is
                    # the same every time is said in as few words as it can be; what
                    # differs - the figures, the bound, the rows - is what is left.
                    (
                        f"{', '.join(f'{p}: {v:,.1f}' for p, v in impossible)} {ratio.unit}, "
                        f"{bound} - which this ratio's arithmetic cannot produce. It is "
                        f"defined on magnitudes"
                        + (f", and {_and_list(signed)} negative here" if signed else "")
                        + ". No movement is asked about."
                    ),
                )
            )
            continue
        if allowed is None:
            findings.append(
                _finding(
                    ratio.name,
                    "could_not_evaluate",
                    f"{reading} {ratio.unit} - and nobody has said how far this may move. "
                    f"It is measured in {ratio.unit}; give a tolerance in {ratio.unit} and "
                    f"the question can be asked.",
                )
            )
            continue

        moved = False
        for before, after in zip(ordered, ordered[1:], strict=False):
            delta = series[after] - series[before]
            if not _reaches(delta, allowed):
                continue
            moved = True
            findings.append(
                _finding(
                    f"{ratio.name} {before} to {after}",
                    "fail",
                    (
                        f"{series[before]:,.1f} to {series[after]:,.1f} {ratio.unit}, "
                        f"a move of {delta:+,.1f} against a tolerance of "
                        f"{allowed:,.1f}. What changed in the business - and is it in "
                        f"the forecast?"
                    ),
                    threshold=allowed,
                )
            )

        first, last = ordered[0], ordered[-1]
        across = series[last] - series[first]
        if len(ordered) > 2 and _reaches(across, allowed):
            moved = True
            findings.append(
                _finding(
                    f"{ratio.name} across the whole history",
                    "fail",
                    (
                        f"{series[first]:,.1f} in {first} to {series[last]:,.1f} in "
                        f"{last}, a move of {across:+,.1f} {ratio.unit} over "
                        f"{len(ordered)} periods. A trend rather than an event, and the "
                        f"question is whether the forecast continues it or reverses it."
                    ),
                    threshold=allowed,
                )
            )

        if not moved:
            findings.append(
                _finding(
                    ratio.name,
                    "pass",
                    f"{reading} {ratio.unit}; no move of {allowed:,.1f} or more, "
                    f"between periods or across the history",
                    threshold=allowed,
                )
            )
        if unavailable:
            findings.append(
                _finding(
                    f"{ratio.name}, where it could not be computed",
                    "could_not_evaluate",
                    f"no figure for {', '.join(unavailable)}, so those periods are not in "
                    f"the comparison above",
                )
            )
    return findings


def shape_of_the_history(
    lines: Sequence[Line], *, years: int | None = None
) -> list[dict[str, Any]]:
    """Whether the history is the shape the work needs.

    Two questions. A year missing from the middle of the range, which is a gap somebody
    has to either fill or explain. And fewer years than the engagement asked for, when
    the engagement has said how many - it has no default either, because three years and
    five years are both ordinary and which one applies is the engagement's.
    """
    findings: list[dict[str, Any]] = []
    periods = _periods(lines)
    if not periods:
        return [
            _finding("the shape of the history", "could_not_evaluate", "no periods on the table")
        ]

    fiscal = sorted({int(match) for p in periods if (match := p[:4]).isdigit()})
    if len(fiscal) >= 2:
        missing = [y for y in range(fiscal[0], fiscal[-1] + 1) if y not in fiscal]
        findings.append(
            _finding(
                "a year missing from the middle of the range",
                "fail" if missing else "pass",
                (
                    f"the range runs {fiscal[0]} to {fiscal[-1]} and has no "
                    f"{', '.join(str(y) for y in missing)}. A gap in the middle is "
                    f"either a year nobody sent or a year that does not exist, and the "
                    f"two have different answers"
                )
                if missing
                else f"{fiscal[0]} to {fiscal[-1]}, with no year missing",
            )
        )
    else:
        findings.append(
            _finding(
                "a year missing from the middle of the range",
                "could_not_evaluate",
                f"needs two fiscal years to have a middle; the periods are "
                f"{', '.join(periods)}",
            )
        )

    if years is None:
        findings.append(
            _finding(
                "enough years of history",
                "could_not_evaluate",
                "nobody has said how many years this engagement needs, so this cannot be "
                "asked. Three and five are both ordinary; the engagement decides",
            )
        )
    else:
        findings.append(
            _finding(
                "enough years of history",
                "pass" if len(periods) >= years else "fail",
                f"{len(periods)} period(s) on the table against the {years} this "
                f"engagement asked for: {', '.join(periods)}",
                threshold=float(years),
            )
        )
    return findings


def run_questions(
    lines: Sequence[Line],
    taxonomy: Taxonomy,
    *,
    move: Mapping[str, float] | None = None,
    years: int | None = None,
) -> list[dict[str, Any]]:
    """All of them.

    Every tolerance is the caller's. A ratio whose unit has no tolerance is reported as
    not asked rather than left out, so the report says which questions were not put -
    which is the difference between a short report and a quiet one.
    """
    findings = list(implications(lines))
    findings.extend(tax_in_a_loss_year(lines, taxonomy))
    findings.extend(ratios(lines, move or {}, taxonomy))
    findings.extend(shape_of_the_history(lines, years=years))
    return findings


# ------------------------------------------------------------------------------- CLI


def lines_from(payload: Mapping[str, Any]) -> list[Line]:
    """The normalized table, as `Line`s. A row this cannot read raises rather than being
    dropped: a question not asked because a row was silently skipped is the worst
    outcome this module has."""
    rows = payload.get("lines")
    if not isinstance(rows, list):
        raise ValueError("the table needs a 'lines' array - see this module's docstring")
    out: list[Line] = []
    for i, row in enumerate(rows):
        try:
            amounts = {str(k): float(v) for k, v in dict(row["amounts"]).items()}
            out.append(
                Line(
                    category=str(row["category"]),
                    amounts=amounts,
                    locator=str(row.get("locator", "")),
                    label=str(row.get("label", "")),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            # The shape, not the exception. `amounts` as a list rather than a mapping is
            # the ordinary mistake somebody writing one of these by hand makes, and
            # "cannot convert dictionary update sequence element #0 to a sequence" sends
            # them to read the traceback instead of the line they typed.
            raise ValueError(
                f"lines[{i}] is not a line ({exc}). A line is "
                '{"category": "cost_of_sales", "amounts": {"FY2024": 7900}, '
                '"label": "Cost of sales", "locator": "IS!6"} - `amounts` keyed by period, '
                "and the figures are magnitudes rather than signed."
            ) from exc
    return out


def _tolerances(given: Sequence[str]) -> dict[str, float]:
    """`--move points=5` into `{"points": 5.0}`, refusing anything it cannot read.

    A misspelled unit is refused rather than ignored: `--move pts=5` silently doing
    nothing would read as a document with no margin questions in it, which is the one
    outcome worse than being told the flag is wrong.
    """
    units = {ratio.unit for ratio in ratios_for(load_taxonomy("coa-taxonomy@1.0.0"))}
    out: dict[str, float] = {}
    for item in given:
        unit, _, value = item.partition("=")
        if not value:
            raise ValueError(f"--move takes UNIT=N, not {item!r}")
        if unit not in units:
            raise ValueError(
                f"{unit!r} is not a unit any ratio is measured in. The units are: "
                f"{', '.join(sorted(units))}"
            )
        try:
            out[unit] = float(value)
        except ValueError as exc:
            raise ValueError(f"--move {item!r}: {value!r} is not a number") from exc
    return out


def report(findings: Sequence[Mapping[str, Any]], *, as_json: bool) -> str:
    if as_json:
        return json.dumps({"qc_findings": list(findings)}, indent=2, default=str)
    asked = [f for f in findings if f["result"] == "fail"]
    quiet = [f for f in findings if f["result"] == "pass"]
    unknown = [f for f in findings if f["result"] == "could_not_evaluate"]
    moot = [f for f in findings if f["result"] == "not_applicable"]

    lines = [f"  {len(findings)} question(s) asked of the table"]
    if asked:
        lines.append(f"\n  Worth asking  ({len(asked)})")
        for f in asked:
            lines.append(f"    {f['check']}")
            lines.append(f"        {f['evidence']}")
            if f.get("locator"):
                lines.append(f"        at {f['locator']}")
    if quiet:
        lines.append(f"\n  Nothing to ask  ({len(quiet)})")
        for f in quiet:
            lines.append(f"    {f['check']}: {f['evidence']}")
    if unknown:
        lines.append(f"\n  Could not be asked  ({len(unknown)})")
        for f in unknown:
            lines.append(f"    {f['check']}: {f['evidence']}")
    if moot:
        lines.append(f"\n  Does not arise  ({len(moot)})")
        for f in moot:
            lines.append(f"    {f['check']}: {f['evidence']}")
    lines.append(
        "\n  Every line above is a question, not a verdict. Nothing here concludes "
        "anything about the valuation, and nothing can."
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reasonableness.py",
        description="The questions a reviewer asks on first looking at the numbers.",
    )
    parser.add_argument("table", type=Path, help="the normalized table, as JSON")
    parser.add_argument(
        "--move",
        action="append",
        metavar="UNIT=N",
        help="how far a ratio may move before it is asked about, in its own unit: "
        "`--move points=5 --move days=10 --move x=0.5`. Repeatable, no defaults, and a "
        "unit with no tolerance is reported as a question nobody asked. One number for "
        "all three would be right for one of them: a margin runs 0-100 points, days "
        "receivable runs 20-120 days, and the current ratio cannot move five turns.",
    )
    parser.add_argument(
        "--years",
        type=int,
        help="how many years of history this engagement asked for. No default.",
    )
    parser.add_argument(
        "--taxonomy",
        default="coa-taxonomy@1.0.0",
        help="the chart-of-accounts version the table was tagged against. Three of the "
        "ratios are sums over a section, and a section's membership is the taxonomy's.",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if not args.table.is_file():
        print(f"  no such table: {args.table}", file=sys.stderr)
        return 2
    try:
        move = _tolerances(args.move or [])
    except ValueError as exc:
        print(f"  {exc}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(args.table.read_text(encoding="utf-8"))
        lines = lines_from(payload)
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"  {args.table} could not be read as a normalized table: {exc}", file=sys.stderr)
        return 2
    try:
        taxonomy = load_taxonomy(args.taxonomy)
    except Exception as exc:  # noqa: BLE001 - an unregistered taxonomy pin says so
        print(f"  {args.taxonomy} is not a taxonomy this build has: {exc}", file=sys.stderr)
        return 2

    findings = run_questions(lines, taxonomy, move=move, years=args.years)
    print(report(findings, as_json=args.as_json))
    return 1 if any(f["result"] == "fail" for f in findings) else 0


if __name__ == "__main__":  # pragma: no cover - the CLI's own line
    raise SystemExit(main())
