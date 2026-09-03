---
name: cost-of-capital
version: 0.1.0
status: skeleton
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

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. No phase has been scheduled to write the procedure yet.

## When to use

A discount rate is needed and the engagement profile establishes industry and size.

## When not to use

The cost of capital dataset returns not-in-dataset for a required component. Surface it rather than substituting.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

A component vintage is older than the freshness threshold; no size premium band matches; the industry classification is contested.
