---
name: dol-adequate-consideration
version: 0.1.0
status: skeleton
scope: valuation/esop/_segment
title: DOL Adequate Consideration
tier: high
description: >-
  Assemble the adequate-consideration record a DOL-standard ESOP valuation requires. Use
  only on ESOP engagements.
inputs:
  - normalized_historicals
  - addback_schedule
  - indicated_range
outputs:
  - adequate_consideration_record
tools:
  - recompute
data_sensitivity: masked_only
hitl: always_surfaces_to_reviewer
output_contract: skills/dol-adequate-consideration@1.0.0
references:
  - dol-guidance.md
  - case-history.md
  - independence-checklist.md
scripts: []
---

# DOL Adequate Consideration

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. No phase has been scheduled to write the procedure yet.

## When to use

An ESOP engagement where a trustee will rely on the valuation, and the file has to evidence the process as well as the number.

## When not to use

Any non-ESOP engagement — it does not resolve into scope there. Never as a substitute for the appraiser’s own judgment on adequacy.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

Any input without a source · any assumption the appraiser has not confirmed · any indication of a related-party term.
