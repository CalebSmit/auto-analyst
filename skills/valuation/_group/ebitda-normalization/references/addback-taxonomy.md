# The add-back taxonomy

Five categories. Every candidate is exactly one of them; the category says why the
line is not part of the earnings a buyer would pay for, and the reviewer reads it
before anything else.

## `owner_related`

Pay and perquisites to the people who own the business, at whatever level they chose
to set them. Officer salaries and bonuses, owner health and life premiums paid by the
company, retirement contributions for owners above the plan's terms for staff. Every
officer-pay item runs through the officer-compensation test (`officer-comp-tests.md`)
against the engagement's benchmark; the benchmark is cited on the item. Owner-related
items recur every year by nature - recurrence is not a mark against them.

Mark officer and owner pay with `officer_compensation: true`. The tagging skill's
`officer_compensation` category is the usual cue; a description naming an owner,
shareholder, member or partner is another.

## `discretionary`

Spending the business did not need to make and a buyer would not: personal vehicles,
travel that is really vacation, club memberships, charitable contributions, family
members on payroll for no work, the owner's personal insurance. Discretionary items
usually recur; what makes them add-backs is that the choice to spend was the owner's.
The line's description and its tag are the evidence; if the description only *might*
mean personal use, say so in the rationale and keep the confidence low.

## `related_party`

Dealings with entities the owners also own, at prices the owners set: rent paid to the
owner's real-estate LLC, management fees to an affiliate, purchases from a sister
company. The add-back is the difference between what was paid and a market price, and
the market price is almost never in the documents. Name the candidate, put the missing
fact in `needs_fact` ("market rent for the facility"), and it is reviewed. Never assume
a market price.

## `non_recurring`

One-time events: a legal settlement, a bad-debt write-off from a single customer's
failure, a special project, a restructuring, storm damage, a one-off consulting
engagement. The shape is a line present in some periods and absent in others, or a
description that names the event. A line present in every period of the table is not
non-recurring however it is described; if you name it anyway, the procedure flags it
`recurs_in_all_periods` and a person decides. Be careful with lines that recur under
different names.

## `accounting_normalization`

Treatments that distort earnings without being discretionary or one-off: a change in
inventory method, revenue recognised on a different basis in one year, an accrual
booked in the wrong period, lease expense under one standard against another. These
are the least common and the most argued; the rationale has to name the treatment.

## What is not an add-back

- Depreciation and amortization, interest, taxes: the D, I, T and A in EBITDA are
  handled by the definition, not by the schedule.
- A line that is merely large. Size is the reviewer's question and the materiality
  threshold answers it; a big ordinary expense is an ordinary expense.
- A negative adjustment you have not been asked for. Under-market owner pay is a real
  normalization, and it is an `owner_related` item like any other - the benchmark test
  states which way it runs.
