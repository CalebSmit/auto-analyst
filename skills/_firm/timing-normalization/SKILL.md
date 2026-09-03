---
name: timing-normalization
version: 0.1.0
status: skeleton
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
references:
  - period-conventions.md
  - line-item-matching.md
scripts:
  - align_periods.py
---

# Timing Normalization

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. The procedure is written in **P18**.

## When to use

Two or more statement files covering different periods need to become one historical table.

## When not to use

A single period from a single file. Do not use to fill a missing period — a gap is reported, never interpolated.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

Period type or units are ambiguous; a line item exists in some periods and not others with no obvious predecessor; two files claim the same period with different figures.
