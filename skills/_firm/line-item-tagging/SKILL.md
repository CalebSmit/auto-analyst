---
name: line-item-tagging
version: 0.1.0
status: draft
scope: _firm
title: Line-Item Tagging
tier: mid
description: >-
  Categorise each line item and set its A/L and NWC inclusion flags against the firm
  taxonomy. Use after historicals are normalized.
inputs:
  - normalized_historicals
outputs:
  - tagged_line_items
tools:
  - chart_of_accounts_lookup
  - precedent_lookup
data_sensitivity: masked_only
hitl: confidence_below_threshold_requires_review
output_contract: skills/line-item-tagging@1.0.0
proposal_contract: skills/line-item-tagging-proposal@1.0.0
references:
  - firm-taxonomy.md
  - nwc-inclusion-rules.md
  - edge-cases.md
---

# Line-Item Tagging

Gives every line of a normalized historical table a home in the firm taxonomy: a
category, whether it is excluded from the operating A/L base, and whether it counts
toward net working capital. You propose; you do not decide. **A tag below the
engagement's confidence bar goes to a person, and every departure from the taxonomy's
default flags goes to a person regardless of confidence.** Approved tags come back to
you on the next engagement as precedents, which is how an analyst's corrections
compound instead of being made again on every job.

## When to use

A normalized historical table needs every line categorised for downstream analysis -
EBITDA normalization reads the categories, model load reads the flags.

## When not to use

- Line items are still unaligned across periods. Run timing normalization first, or the
  same account gets tagged twice under different names.
- To decide whether an amount is material, reasonable or an add-back. You never see an
  amount, and a category is not a judgment about size.

## What you receive

Inside the data sentinels: the pinned taxonomy in full - every category with its id,
statement, section, default flags and cues - and one entry per line item: a
`line_item_ref`, the canonical description, the source labels it was aligned from, which
statement the source sheet suggests, and the periods it appears in. You receive
descriptions and structure. You do not receive values, because a category is decided by
what a line *is*, and guessing from the amount is the one mistake this skill exists to
avoid. Above the payload you may see precedents: prior decisions an analyst approved on
this or another engagement, each with its id, masked description, category, flags and
rationale.

## Procedure

1. **Read the precedents first.** Where a description matches a precedent's, follow it
   and cite its id in `precedent_ref`. A precedent is an approved decision; departing
   from one is allowed but is reviewed, so say why in the rationale.
2. **Assign the category** from the pinned list, by id, exactly as written. Use
   `firm-taxonomy.md` for how the sections divide and where the usual ambiguities land.
   Prefer the specific category over the general one when the description supports it;
   prefer the general one over a guess when it does not.
3. **Set the two flags.** Start from the category's defaults. Depart only when the
   description says the line is something other than what its category usually is -
   `nwc-inclusion-rules.md` has the cases. An income statement line carries both flags
   false, always.
4. **Attach a confidence and a one-line rationale** to every item. The rationale names
   what in the description decided it. The confidence is your uncertainty about the
   category and both flags together; a confident category with an uncertain flag is
   not a confident tag.
5. **Flag what you cannot place.** A description too sparse to categorise gets
   `category: unmapped` and `uncategorisable: true`. That is a complete answer and a
   person finishes it. Do not pick "other" to avoid it, and do not reason from the
   source labels' position in the sheet.
6. **Account for every ref.** Every `line_item_ref` you were given appears exactly once.
   The procedure checks; a ref you forgot is tagged `unmapped` and reviewed with the
   reason "not in the proposal", which is a worse answer than yours would have been.

## Output

The proposal contract `skills/line-item-tagging-proposal@1.0.0`, as JSON and nothing
else: `items`, each with `line_item_ref`, `category`, `excluded_from_al`,
`include_in_nwc`, `confidence`, `rationale`, and optionally `precedent_ref` and
`uncategorisable`. The procedure checks every ref against the input, every category
against the pinned taxonomy, and every cited precedent against the store within this
engagement's scope, then emits `skills/line-item-tagging@1.0.0` with `review_required`
set by the rules above and by the engagement's bar.

## Escalate when

- A line item does not map to any taxonomy category: `unmapped`, `uncategorisable`,
  and it reaches a person. Never a near-miss category.
- A description is materially ambiguous - it could sit in two sections with different
  flag treatment (a "deposit" that may be prepaid or a customer's; a "loan" that may be
  to or from an owner). Choose the reading the source labels support, say the other in
  the rationale, and keep the confidence low so it is reviewed.
- A precedent conflicts with the current taxonomy version - its category no longer
  exists, or the rules moved. Do not follow it; tag from the taxonomy and cite the
  precedent anyway, so the conflict is visible to the reviewer.
