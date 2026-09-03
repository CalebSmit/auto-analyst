---
name: gpc-scrub
version: 0.1.0
status: skeleton
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

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. No phase has been scheduled to write the procedure yet.

## When to use

A market approach is in scope and the subject company profile is established.

## When not to use

The multiples dataset returns not-in-dataset. Stop and surface that — never substitute a remembered multiple.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

Fewer than the firm minimum of comparables survive; a multiple is stale beyond the freshness threshold; the subject has no clear industry analogue.
