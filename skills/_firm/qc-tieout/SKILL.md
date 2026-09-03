---
name: qc-tieout
version: 0.1.0
status: skeleton
scope: _firm
title: QC / Tie-Out Review
tier: high
description: >-
  Run the pre-handoff checklist: cross-statement tie-outs, movement checks, coverage gaps
  and unresolved items. Cannot approve.
inputs:
  - normalized_historicals
  - tagged_line_items
  - template_mapping
outputs:
  - qc_findings
  - readiness
tools:
  - recompute
data_sensitivity: masked_only
hitl: always_surfaces_to_reviewer
output_contract: skills/qc-tieout@1.0.0
references:
  - qc-checklist.md
  - movement-thresholds.md
scripts: []
---

# QC / Tie-Out Review

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. No phase has been scheduled to write the procedure yet.

## When to use

Work is assembled and about to be handed to an analyst.

## When not to use

As a substitute for review. The readiness field cannot say approved — only items_outstanding or no_automated_issues_found.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

A tie-out fails and the cause is not locatable; a movement exceeds the threshold with no documented explanation.
