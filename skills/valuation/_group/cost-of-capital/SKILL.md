---
name: cost-of-capital
version: 0.1.0
status: superseded
scope: valuation/_group
title: Cost of Capital
tier: mid
description: >-
  Build a discount rate from sourced, dated components with the build-up shown. Use when a
  DCF or capitalised-earnings method is in scope.
inputs:
  - engagement_profile
  - coc_data
outputs:
  - cost_of_capital
tools:
  - index_lookup
data_sensitivity: masked_only
hitl: company_specific_premium_requires_review
output_contract: skills/cost-of-capital@1.0.0
references:
  - buildup-method.md
  - size-premium-sources.md
scripts: []
---

# Cost of Capital

> **Superseded by methodology (P167).** The owner decided on 2026-10-05 that this
> is not a procedure this tool runs: the firm's model computes the WACC; what the analyst supplies is inputs - Kroll for market data, Capital IQ for the comps' unlevered betas and the cost of debt by rating - and the rules for gathering them are `knowledge/methodology/cost-of-capital-inputs.md`, attached to every valuation run from `foundations/valuation/_group/cost-of-capital-inputs.md`. The frontmatter stays so the Skill
> Tree, the Scope Resolver and the output contract stay whole; nothing dispatches
> this and nothing will. Its reference files were empty placeholders.

## When to use

A discount rate is needed and the engagement profile establishes industry and size.

## When not to use

The cost of capital dataset returns not-in-dataset for a required component. Surface it rather than substituting.

## Procedure

Not written, and not to be written. Superseded by methodology - see the note above
for where the knowledge lives and what attaches it to a run.

## Escalate when

A component vintage is older than the freshness threshold; no size premium band matches; the industry classification is contested.
