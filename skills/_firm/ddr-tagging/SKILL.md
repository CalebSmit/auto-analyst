---
name: ddr-tagging
version: 0.1.0
status: skeleton
scope: _firm
title: DDR Tagging & Structuring
tier: mid
description: >-
  Convert unstructured client DDR responses into tagged, schema-valid fields against the
  request schedule. Use when a DDR response document has been received.
inputs:
  - ddr_response_document
  - request_schedule
outputs:
  - tagged_fields
  - outstanding_items
tools:
  - chart_of_accounts_lookup
data_sensitivity: masked_only
hitl: low_confidence_fields_require_review
output_contract: skills/ddr-tagging@1.0.0
references:
  - tagging-taxonomy.md
  - worked-examples.md
scripts: []
---

# DDR Tagging & Structuring

> **Skeleton.** This file exists so the Skill Tree and the Skill Index are real, and so
> the Scope Resolver resolves against something rather than against a fixture. The
> frontmatter above is complete and is what the index reads. Everything below is a
> placeholder. No phase has been scheduled to write the procedure yet.

## When to use

A DDR response — narrative, spreadsheet or scanned form — has arrived and needs to be structured against the request schedule.

## When not to use

The document is financial statements rather than a DDR response. Route to classification first. Never use this to answer a DDR item the client did not answer.

## Procedure

Not written. A skeleton is not a skill: nothing dispatches this until it has a
procedure, fixtures and a review, and the Skill Registry is what makes it live.

## Escalate when

A response appears to answer an item not on the schedule; a single element answers several items ambiguously; the document is illegible.
