---
name: dcf-build
version: 0.1.0
status: superseded
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

> **Superseded by methodology (P167).** The owner decided on 2026-10-05 that this
> is not a procedure this tool runs: the firm's model already does the DCFs - exit multiple or Gordon Growth, CAPM or build-up, relevering beta to a target structure - and takes inputs. What the model needs is in `knowledge/methodology/cost-of-capital-inputs.md` and `knowledge/methodology/gpc-screening.md`, attached to every valuation run from `foundations/valuation/_group/`. The frontmatter stays so the Skill
> Tree, the Scope Resolver and the output contract stay whole; nothing dispatches
> this and nothing will. Its reference files were empty placeholders.

## When to use

Normalized historicals and a cost of capital build are available and a DCF is in scope.

## When not to use

Historicals are not yet tied out. Never emit a single point value — the output schema requires a two-element range.

## Procedure

Not written, and not to be written. Superseded by methodology - see the note above
for where the knowledge lives and what attaches it to a run.

## Escalate when

A forecast driver has no historical basis; the implied growth rate falls outside firm bounds; cost of capital components are missing.
