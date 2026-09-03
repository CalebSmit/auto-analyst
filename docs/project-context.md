# Project Context: AI DDR & Model Loader

*Working document — first draft, to be refined as architecture develops.*

## 1. Vision

Build an AI-powered analyst pipeline that automates the early, mechanical stages of deal work (DDR data extraction/tagging, financial statement normalization, and model building), freeing analysts to focus on judgment calls. The system should behave like a junior analyst with a toolbox: an **orchestrator agent** reads incoming client data and decides which specialized **skill** to invoke (DCF build, GPC scrub, EBITDA normalization, etc.), modeled conceptually on how Claude routes to skill files.

## 2. High-Level Workflow

```
ShareFile (client uploads)
        ↓
Orchestrator Agent  →  reads incoming files, classifies content, decides next action
        ↓
Skill Library  →  DCF builder, GPC scrub, EBITDA normalization, other modular "skills"
        ↓
DDR Processor  →  unstructured client docs → LLM → structured/tagged response → verification + analysis
        ↓
Model Builder  →  normalizes historicals, masks/unmasks sensitive account data, tags line items, loads into model template
        ↓
Client Model (deliverable)
```

### DDR Processor (detail, from current deck)
- Input: unstructured response data (raw figures/line items pulled from client docs)
- LLM structures the response into tagged fields (e.g., A.1, A.2, A.3)
- A second LLM pass performs **response verification** and **analysis** on the structured output

### Model Builder (detail, from current deck)
1. **Normalize timing** — convert single-date files (monthly or annual) into one historical table with matching line items
2. **Mask sensitive account names** — real account names (e.g., "Bob's LLC Checking") replaced with generic labels (e.g., "Masked_Company_1 Checking") before sending to LLM, to avoid exposing sensitive/identifying data
3. **Tag line items** — LLM categorizes each line item (Category, Excluded from A/L?, Include in NWC?, etc.)
4. **Unmask sensitive account names** — a deterministic Python script (not the LLM) maps masked labels back to real account names/numbers
5. **Load model** — combine historical financials (IS, IS.m, BS, BS.m), an AI-ready model template, cost of capital data, and multiples data via a Python script to produce the final **client model**

**Key design pattern worth preserving:** LLM only ever touches masked/anonymized data for classification and reasoning tasks; a deterministic script handles re-identification and final numeric assembly. This keeps sensitive client data out of LLM context where possible and keeps the numeric assembly step auditable/deterministic.

## 3. Orchestrator Agent Concept

- Sits between file ingestion (ShareFile) and the skill library
- Reads incoming file(s), determines document type/intent, and routes to the correct skill or sequence of skills
- Skills are modular, independently maintained files/functions — analogous to how Claude Skills work (a `SKILL.md`-style definition per capability)
- Initial candidate skills to define:
  - DCF build
  - GPC (guideline public company) scrub
  - EBITDA normalization
  - DDR tagging/categorization (as shown above)
  - Model loading/assembly

## 4. Tech Stack (current thinking)

| Layer | Choice | Notes |
|---|---|---|
| IDE / dev environment | Cursor | Primary build tool |
| Version control | GitHub | Standard repo workflow |
| Cloud hosting | Microsoft Azure (tentative) | Using a free student trial for now — **no cloud access at work yet**, so architecture should not be hard-locked to Azure |
| LLM orchestration | TBD | Likely an agent framework with tool/skill routing |
| File ingestion | ShareFile | Where clients upload source documents |

**Design constraint:** Because there's no work-sanctioned cloud yet and Azure is just a personal stopgap, the architecture should be built for **portability** — avoid deep vendor lock-in where reasonably possible (e.g., abstract storage, compute, and secrets handling behind interfaces so a future switch to AWS/GCP/on-prem work infra doesn't require a rewrite).

## 5. Immediate Next Step

Build an **architecture blueprint** as a single HTML file:
- Visual diagram with connectors showing the full workflow start to end
- ShareFile → Orchestrator → Skill Library → DDR Processor → Model Builder → Client Model
- Purpose: something concrete to work toward/present at work, not yet a functional build

## 6. Open Questions / To Define Later

- Exact skill file format/spec (structure, inputs/outputs, how orchestrator selects among them)
- Where masking/unmasking logic lives (part of orchestrator, or its own service)
- Auth/security model for ShareFile ingestion
- Which pieces need to be Azure-specific vs. cloud-agnostic
- Model template versioning (AI-ready model template mentioned in Model Builder step)
- Cost of capital / multiples data sourcing (internal DB? external API?)

## 7. Source Material

Current thinking is based on an internal deck: **"AI DDR & Model Loader"** (Chartwell), covering:
- DDR Processor (pp. 3)
- Model Builder (pp. 5–9): timing normalization, masking, tagging, unmasking, model loading

---
*Last updated: 2026-08-31. Update this file as the architecture blueprint and skill definitions take shape.*
