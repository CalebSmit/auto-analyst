---
name: model-load
version: 0.1.0
status: draft
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
proposal_contract: skills/model-load-proposal@1.0.0
references:
  - template-input-map.md
---

# Model Load & Assembly

Routes validated figures to the template's named inputs. **You emit a mapping; you never
write a cell and you never state a value.** The Model Builder resolves every figure you
name and the Template Writer performs every write, by named range and never by cell
address - `B44` is not a contract. The interesting part, which line goes where, is
yours; the risky part, writing numbers into cells, is code.

## When to use

All upstream outputs have cleared their guards and a client model is the deliverable.

## When not to use

- Any input is still awaiting review. A figure a person has not settled does not go
  into a model.
- To fill a gap. A required template input with no source is listed as unmapped and the
  build stops for a person; it is never estimated, defaulted or carried forward.

## What you receive

Inside the data sentinels: the pinned template's declared inputs - each with its name,
the line it expects, the period it expects, and whether it is required - and the
catalogue of figures available to route: each with a `figure_ref`, the skill that
produced it, the line's description and the period. You receive names, lines and
periods. You do not receive values; routing is decided by what a figure *is*, not by
how big it is.

## Procedure

1. **Read the template's inputs** for the pinned version, using `template-input-map.md`
   for how the template names lines and periods (`FY1` is the earliest period on the
   table, `FY3` the latest).
2. **Bind every required input** to exactly one figure whose line and period match.
   Where the template's line combines several of the table's lines (officer
   compensation is salary and bonus together; other operating expense is what the
   taxonomy calls other), say so in `why` and bind the figure that carries the
   combined line, or list the input as unmapped if no figure does. Never bind two
   figures to one input.
3. **List every required input you could not bind** in `unmapped_template_inputs`
   with the reason. The build stops on any required input left unmapped; that is the
   point, not a failure of yours.
4. **List every figure you did not route** in `unrouted_upstream_figures` with the
   reason. A figure with no destination is information for the reviewer, not waste.
5. **Bind optional inputs** where a figure exists for them and leave the rest; an
   optional input needs no entry in either list.

## Output

The proposal contract `skills/model-load-proposal@1.0.0`, as JSON and nothing else:
`bindings`, `unmapped_template_inputs`, `unrouted_upstream_figures`. The procedure
checks every destination against the template's declared inputs through the gated
`template_schema_lookup`, every `figure_ref` against the catalogue, and that no input
is bound twice, then emits `skills/model-load@1.0.0` with every required input either
bound or listed.

## Escalate when

- A required template input has no available source: list it as unmapped; the build
  stops and a person supplies or waives it.
- An upstream figure has no destination: list it as unrouted, with the reason.
- The template version has changed mid-engagement: the pinned version is the one you
  were given; if the inputs you see do not match it, stop and say so.
