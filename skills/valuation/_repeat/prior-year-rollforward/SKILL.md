---
name: prior-year-rollforward
version: 0.1.0
status: skeleton
scope: valuation/_repeat
title: Prior-Year Roll-Forward
tier: mid
description: >-
  Carry forward last year’s approved treatments and surface what changed. Repeat clients
  only.
inputs:
  - normalized_historicals
  - prior_engagement_manifest
outputs:
  - rollforward_report
tools:
  - precedent_lookup
  - recompute
data_sensitivity: masked_only
hitl: changes_from_prior_year_require_review
output_contract: skills/prior-year-rollforward@1.0.0
references:
  - rollforward-conventions.md
scripts: []
---

# Prior-Year Roll-Forward

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. No phase has been scheduled to write the procedure yet.

## When to use

A returning client whose prior engagement manifest is available.

## When not to use

A first engagement, or one where the prior year was not run through this system — there is nothing to roll forward, and pretending otherwise invents continuity.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

The chart of accounts has changed materially · a prior treatment now conflicts with the current taxonomy version.
