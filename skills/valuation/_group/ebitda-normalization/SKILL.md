---
name: ebitda-normalization
version: 0.1.0
status: draft
scope: valuation/_group
title: EBITDA Normalization
tier: high
description: >-
  Identify and quantify non-recurring, discretionary and owner-related adjustments to
  EBITDA. Use when normalizing historical earnings for a valuation.
inputs:
  - normalized_historicals
  - tagged_line_items
  - engagement_profile
outputs:
  - addback_schedule
tools:
  - recompute
  - chart_of_accounts_lookup
  - precedent_lookup
data_sensitivity: masked_only
hitl: material_addbacks_require_review
output_contract: skills/ebitda-normalization@1.0.0
proposal_contract: skills/ebitda-normalization-proposal@1.0.0
references:
  - addback-taxonomy.md
  - officer-comp-tests.md
  - worked-examples.md
---

# EBITDA Normalization

Finds the adjustments that turn reported earnings into the earnings a buyer would pay
for, and shows where each one came from. **You propose an add-back; you never apply
one, and you never state its amount.** A candidate names a tagged line and the periods
it applies to. The amount is that line's own figure in that period, read from the
normalized historicals and re-derived by the `recompute` tool from the rows behind it
before it reaches the schedule. Every item above the engagement's materiality threshold
goes to a person whatever your confidence says. Add-backs are where a valuation gets
argued; an add-back nobody looked at is a liability, not a time saving.

## When to use

Historical earnings need normalizing for a valuation and the line items have already
been tagged. The engagement profile carries an owner-compensation benchmark.

## When not to use

- The line items are untagged. Tagging is what tells you which lines are owner-related.
- The engagement profile has no owner-compensation baseline. That is checked **before
  you are called** and escalates; if you see a profile with none, stop and say so.
- To decide what the business is worth. A schedule of proposed adjustments with
  evidence is the output; a normalized EBITDA figure is not, and there is no field for
  one.

## What you receive

Inside the data sentinels: the periods of the historical table; one entry per tagged
line with its `line_item_ref`, description, taxonomy category, the two flags, the source
labels it was aligned from, and the periods it has a value in; the benchmark's basis,
source and date (not its amount); and the materiality currency. You do not receive
values. Whether a line is an add-back is decided by what the line *is* and when it
occurs, not by how big it is - size is the reviewer's question, and the procedure
answers it from the figures without you.

## Procedure

1. **Screen against the add-back taxonomy.** Walk the tagged lines with
   `addback-taxonomy.md`: owner and officer pay, discretionary and personal spending run
   through the business, related-party dealings, one-time events, and accounting
   treatments that distort earnings. A line's tagged category is your first cue; its
   description is the second; the periods it appears in is the third.
2. **Name the periods.** A line present in only some periods is the ordinary shape of
   a non-recurring item. A line present in every period is probably not non-recurring:
   you may still name it under another category, and if you name it `non_recurring`
   the procedure flags it as recurring and sends it to a person rather than onto the
   schedule as proposed.
3. **Mark officer and owner pay** with `officer_compensation: true`. The procedure runs
   the officer-compensation test from `officer-comp-tests.md` against the engagement's
   benchmark and cites the benchmark on every such item. You do not run the test.
4. **Say what you would need to know.** An add-back that depends on a fact not in the
   documents - a market rent, the terms of a settlement, whether a family member works
   in the business - carries `needs_fact` with the question. It is reviewed, never
   assumed.
5. **Attach a rationale and a confidence** to each candidate. The rationale names what
   in the description, the tag or the pattern of periods decided it. The confidence is
   about whether it is an add-back at all, not about the amount, which is not yours.
6. **Cite precedents** you were shown with `precedent_ref` where you follow one.
   Departing from one is allowed and is reviewed.

## Output

The proposal contract `skills/ebitda-normalization-proposal@1.0.0`, as JSON and nothing
else: `candidates`, each with `candidate_id`, `line_item_ref`, `category`, `periods`,
`rationale`, `confidence`, and optionally `officer_compensation`, `needs_fact` and
`precedent_ref`. The procedure turns each candidate-period into a schedule item of
`skills/ebitda-normalization@1.0.0` with the figure, the evidence rows, `recomputed`
from the tool, `above_materiality` from the engagement threshold, and `review_required`
from rules you cannot relax.

## Verification pass

Every schedule is checked by a second, separate invocation of this skill. That pass
receives the schedule's items - description, category, period, amount, the cited rows
and the excerpts - and **not** the first pass's rationale or confidence. If the payload
you receive is marked `verification`, you are that pass: for every `candidate_id`, say
whether the cited rows and excerpts support the item as the add-back it claims to be,
and why not when they do not, in `skills/ebitda-normalization-verification-proposal@1.0.0`.
Do not propose new candidates and do not restate amounts. An item you do not support
goes to a person.

## Escalate when

- The engagement profile has no owner-compensation benchmark. Checked before the call.
- An add-back depends on a fact not in the documents: `needs_fact`, and it is reviewed.
- A candidate recurs across all periods and you would still call it non-recurring:
  name it, and the procedure marks it `recurs_in_all_periods` and sends it to a person.
- Two lines look like the same adjustment counted twice (a settlement and the legal
  fees around it, an owner's vehicle and its insurance): name both, say so in each
  rationale, and let the reviewer take one.
