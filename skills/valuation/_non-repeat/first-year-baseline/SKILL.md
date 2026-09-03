---
name: first-year-baseline
version: 0.1.0
status: skeleton
scope: valuation/_non-repeat
title: First-Year Baseline
tier: mid
description: >-
  Establish the conventions a new client’s file will be built on, and record them for next
  year. New clients only.
inputs:
  - normalized_historicals
  - tagged_line_items
outputs:
  - baseline_record
tools:
  - chart_of_accounts_lookup
data_sensitivity: masked_only
hitl: baseline_requires_review
output_contract: skills/first-year-baseline@1.0.0
references:
  - baseline-conventions.md
scripts: []
---

# First-Year Baseline

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. No phase has been scheduled to write the procedure yet.

## When to use

A first engagement for a client, where no prior treatments exist.

## When not to use

A returning client — roll forward instead of re-deciding, or the file will contradict last year.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

Two defensible conventions exist and the choice materially changes the outcome.
