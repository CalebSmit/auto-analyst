---
name: repurchase-obligation
version: 0.1.0
status: skeleton
scope: valuation/esop/_segment
title: Repurchase Obligation
tier: mid
description: >-
  Model the ESOP repurchase obligation and surface its effect on the indicated range. ESOP
  engagements only.
inputs:
  - normalized_historicals
  - participant_census
outputs:
  - repurchase_schedule
tools:
  - recompute
data_sensitivity: masked_only
hitl: always_surfaces_to_reviewer
output_contract: skills/repurchase-obligation@1.0.0
references:
  - repurchase-methodology.md
scripts:
  - project_repurchase.py
---

# Repurchase Obligation

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. No phase has been scheduled to write the procedure yet.

## When to use

An ESOP engagement with a participant census available.

## When not to use

Without a census — report the gap rather than estimating one.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

Census is missing, stale, or inconsistent with headcount in the financials.
