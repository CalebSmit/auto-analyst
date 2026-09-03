---
name: timing-normalization
version: 0.1.0
status: draft
scope: _firm
title: Timing Normalization
tier: mid
description: >-
  Align monthly and annual single-date files onto one historical table with matching line
  items. Use when historical financials arrive across multiple periods or files.
inputs:
  - classified_statements
  - period_metadata
outputs:
  - normalized_historicals
  - alignment_report
tools:
  - timing_normalizer
data_sensitivity: masked_only
hitl: ambiguous_periods_require_review
output_contract: skills/timing-normalization@1.0.0
proposal_contract: skills/timing-normalization-proposal@1.0.0
references:
  - period-conventions.md
  - line-item-matching.md
---

# Timing Normalization

Turns a pile of single-date files into one historical table. You propose the alignment;
the `timing_normalizer` tool performs every arithmetic operation. **Your answer is a
mapping and never a number.** The proposal contract has no numeric field, and a proposal
carrying one is refused before any tool runs.

## When to use

Two or more statement files, or one file with several period columns, need to become one
historical table: the same line items down the side, the periods across the top, every
cell traceable to the row it was read from.

## When not to use

- A single period from a single file. There is nothing to align.
- To fill a missing period. A gap is reported, never interpolated - not from the
  neighbouring months, not from a run-rate, not from last year.
- To restate units. The scale each file was read at travels with every figure; the
  model template restates, this skill does not.

## What you receive

Inside the data sentinels, one entry per file: its `source_id`, filename, document type,
the period each block covers, the scale and currency the Period Detector read, and every
row as `locator: label`. You receive labels and locators. You do not receive values, and
you do not need them: matching "Repairs & Maint." to "Repairs and Maintenance" is
judgment, and summing twelve months is not.

## Procedure

1. **Read the periods first.** Each block is one period. Name it by the conventions in
   `period-conventions.md` (`FY2025`, `M2025-04`, `Q3 2025`), with its type and end
   date, and the block it came from. Two blocks claiming the same period from different
   files are both listed; the tool will compare them and report a conflict if they
   disagree. Do not pick one.
2. **Match line items across periods.** For every row in every block, either place it
   under a canonical label with the rows it aligns to in the other periods, or list it
   as unmatched with the reason. Use `line-item-matching.md`: an exact match, a rename,
   a split (one earlier line becomes several later ones) or a merge (several earlier
   lines become one). Name the kind.
3. **Never invent a predecessor.** A line that exists in some periods and not others,
   with no obvious counterpart, is unmatched in the periods it is absent from. It still
   appears in the table for the periods it has, and the report says where it does not.
4. **Account for every row.** Every locator you were given appears exactly once: under a
   canonical label or in `unmatched`. The tool checks; a row you forgot is reported as
   unmatched with the reason "not in the proposal", which is a worse answer than yours
   would have been.
5. **Say nothing numeric.** No values, no totals, no confidence scores. The tool reads
   the rows, does the arithmetic, and records a derivation for every figure so the
   tie-out guard can re-derive it.

## Output

The proposal contract `skills/timing-normalization-proposal@1.0.0`, as JSON and nothing
else: `periods`, `line_items` (each with `canonical_label`, `kind` and `sources`), and
`unmatched`. The tool turns it into `skills/timing-normalization@1.0.0`: the historical
table, with one figure per period per line item, and the alignment report.

## Escalate when

- The Period Detector flagged a file `ambiguous` on scale or period type. This is
  checked **before you are called**; if you see it anyway, stop and say so.
- A line item exists in some periods and not others with no obvious predecessor, and it
  is material to the table. List it as unmatched; the report reaches a person.
- Two files claim the same period. List both blocks as that period; the tool reports the
  conflict with both figures, and a person decides.
- The chart of accounts changed so much between periods that fewer than most rows can be
  matched with confidence. Say so in `notes`; do not force matches to lift the rate.
