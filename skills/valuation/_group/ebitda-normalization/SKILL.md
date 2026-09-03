---
name: ebitda-normalization
version: 0.1.0
status: skeleton
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
references:
  - addback-taxonomy.md
  - officer-comp-tests.md
  - worked-examples.md
scripts:
  - compute_addbacks.py
---

# EBITDA Normalization

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. The procedure is written in **P20**.

## When to use

Historical earnings need normalizing for a valuation and line items have already been tagged.

## When not to use

Line items are untagged, or the engagement profile has no owner-compensation baseline. Never apply an add-back — propose it with evidence.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

An add-back depends on a fact not in the documents; a candidate recurs across all periods (probably not non-recurring); owner compensation has no benchmark available.
