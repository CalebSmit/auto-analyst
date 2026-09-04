# Officer-compensation tests

Owner pay is the add-back every valuation has and the one every reader questions, so
it is tested the same way every time, against a benchmark the engagement recorded
before the run started, and the benchmark is cited on the item.

## The benchmark

The engagement profile's `owner_compensation_baseline`: an amount, a currency, a basis
(`survey_median`, `survey_75th`, `prior_engagement`, `analyst_estimate`), the source
(the survey and edition, or the prior engagement), and the date it was taken as of.
It is required. A profile without one does not reach this skill - the dispatcher
escalates before any model call - because a profile that omits it silently is exactly
how the test gets skipped.

You receive the basis, the source and the date. You do not receive the amount, and you
do not need it: the test is the procedure's, not yours.

## The test

For every period, the procedure sums the officer-pay lines the proposal marked
`officer_compensation: true` - through the `recompute` tool, so the total is on the
record - and compares the total to the benchmark:

| result | what the schedule says |
|---|---|
| total above the benchmark | the add-back is the line as stated; the excess over the benchmark is the model's to compute at load |
| total at or below the benchmark | the item stays on the schedule with the comparison stated, so the reviewer sees under-market pay rather than nothing |
| benchmark in a different currency | the item is reviewed; nothing is converted here |

Every officer-pay item carries `officer_comp_benchmark` with the basis, source and
date, and is reviewed - `owner_related` is on every engagement's always-review list,
and if it were not, the materiality threshold would catch it.

## What counts as officer pay

Salary, bonus, commissions and guaranteed payments to owners and officers; payroll
taxes on that pay when the chart breaks them out by person; benefits paid for owners
above what staff receive. Not: pay to non-owner managers, however senior, unless the
engagement says the buyer would replace them - that is a `needs_fact`.

## Two owners, one benchmark

The benchmark is per business, not per person, unless the profile says otherwise.
Two owners each drawing a market salary for a full-time role are not an add-back
between them; say so in the rationale and let the reviewer decide with the profile in
front of them.
