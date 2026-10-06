---
name: gpc-scrub
version: 0.1.0
status: superseded
scope: valuation/_group
title: GPC Scrub
tier: high
description: >-
  Screen guideline public companies and scrub the resulting multiples, reporting both the
  accepted and rejected sets. Use for a market approach.
inputs:
  - engagement_profile
  - multiples_data
outputs:
  - comparable_set
  - rejected_set
  - scrubbed_multiples
tools:
  - index_lookup
data_sensitivity: masked_only
hitl: comparable_set_requires_review
output_contract: skills/gpc-scrub@1.0.0
references:
  - comparability-criteria.md
  - multiple-scrubbing.md
scripts: []
---

# GPC Scrub

> **Superseded by methodology (P167).** The owner decided on 2026-10-05 that this
> is not a procedure this tool runs: comps are screened by a person in Capital IQ, by keyword and by industry, and the set is carried from last year for a repeat client; the rules for reading an export and presenting the set are `knowledge/methodology/gpc-screening.md`, attached to every valuation run from `foundations/valuation/_group/gpc-screening.md`. The frontmatter stays so the Skill
> Tree, the Scope Resolver and the output contract stay whole; nothing dispatches
> this and nothing will. Its reference files were empty placeholders.

## When to use

A market approach is in scope and the subject company profile is established.

## When not to use

The multiples dataset returns not-in-dataset. Stop and surface that — never substitute a remembered multiple.

## Procedure

Not written, and not to be written. Superseded by methodology - see the note above
for where the knowledge lives and what attaches it to a run.

## Escalate when

Fewer than the firm minimum of comparables survive; a multiple is stale beyond the freshness threshold; the subject has no clear industry analogue.
