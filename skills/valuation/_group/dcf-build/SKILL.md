---
name: dcf-build
version: 0.1.0
status: skeleton
scope: valuation/_group
title: DCF Build
tier: high
description: >-
  Assemble discounted cash flow inputs — build-up, forecast structure, terminal value — and
  the range they imply. Use when a DCF is in scope.
inputs:
  - normalized_historicals
  - addback_schedule
  - cost_of_capital
outputs:
  - dcf_inputs
  - indicated_range
tools:
  - recompute
data_sensitivity: masked_only
hitl: assumptions_require_review
output_contract: skills/dcf-build@1.0.0
references:
  - wacc-buildup.md
  - terminal-value.md
  - forecast-conventions.md
scripts: []
---

# DCF Build

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. No phase has been scheduled to write the procedure yet.

## When to use

Normalized historicals and a cost of capital build are available and a DCF is in scope.

## When not to use

Historicals are not yet tied out. Never emit a single point value — the output schema requires a two-element range.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

A forecast driver has no historical basis; the implied growth rate falls outside firm bounds; cost of capital components are missing.
