---
name: line-item-tagging
version: 0.1.0
status: skeleton
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
references:
  - firm-taxonomy.md
  - nwc-inclusion-rules.md
  - edge-cases.md
scripts: []
---

# Line-Item Tagging

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. The procedure is written in **P19**.

## When to use

A normalized historical table needs every line categorised for downstream analysis.

## When not to use

Line items are still unaligned across periods — run timing normalization first, or the same account gets tagged twice under different names.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

A line item does not map to any taxonomy category; a description is materially ambiguous; a precedent conflicts with the current taxonomy version.
