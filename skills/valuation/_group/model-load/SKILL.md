---
name: model-load
version: 0.1.0
status: skeleton
scope: valuation/_group
title: Model Load & Assembly
tier: mid
description: >-
  Map normalized historicals, cost of capital and multiples onto the firm model template's
  expected inputs. Use as the final assembly step.
inputs:
  - normalized_historicals
  - tagged_line_items
  - cost_of_capital
  - scrubbed_multiples
outputs:
  - template_mapping
tools:
  - template_schema_lookup
data_sensitivity: masked_only
hitl: unmapped_inputs_require_review
output_contract: skills/model-load@1.0.0
references:
  - template-input-map.md
scripts:
  - build_mapping.py
---

# Model Load & Assembly

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. The procedure is written in **P21**.

## When to use

All upstream outputs have cleared their guards and a client model is the deliverable.

## When not to use

Any input is still awaiting review. Never write cells directly — emit a mapping the Template Writer executes.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

A required template input has no available source; an upstream figure has no destination; the template version has changed mid-engagement.
