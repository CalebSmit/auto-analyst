# Proposal: what the harness research says about this tool

**Status: approved 2026-09-20. Building.**
Raised by Caleb 2026-09-20, who supplied the paper. Written 2026-09-20.

Caleb read *Harness Engineering: Anatomy, Architecture, and Evolution of Coding Agents*
(Barbaste, Darrigol, Vu, Wiltberger; Wavestone AI Lab, July 2026 — arXiv 2609.00006), a
source-code study of eleven production coding harnesses, and asked whether this build is
set up as well as it could be. That paper is about coding agents and this is not one, so
the reading was widened to the literature nearer this problem:

- Anthropic, *Effective context engineering for AI agents*
- Anthropic, *Effective harnesses for long-running agents*
- **LAVA: Logic-Aware Validation and Augmentation for Large-Scale Financial Document
  Auditing** (arXiv 2608.16763) — the closest published system to this one
- *Evaluating Agentic AI in the Wild: Failure Modes, Drift Patterns, and a Production
  Evaluation Framework* (arXiv 2605.01604)
- *A Multistage Extraction Pipeline for Long Scanned Financial Documents* (arXiv
  2604.26462, industrial KYC) and *Multi-Stage Field Extraction of Financial Documents
  with OCR and Compact Vision-Language Models* (arXiv 2510.23066)

## What the research validates, and should not be changed

Stated first because it is the more important result. The paper's two strongest findings
are absences across roughly four million lines of production code, and this repo has both.

| Finding in the corpus | Here |
|---|---|
| 0/11 harnesses use an agentic framework (LangChain, LangGraph, AutoGen…). Rec 15: do not | Uses none |
| 0/11 retrieve with vector embeddings. Rec 16: do not | Precedent and taxonomy lookups are deterministic and scope-keyed |
| Rec 3: start with few tools; defer loading only above ~15 | Four tools |
| Rec 11: safety as data, not imperative code; keep a floor under any bypass | `constraints.yaml`, `scopes.yaml`, guards that fail closed, admins may only tighten |
| Rec 6: auto-discover hierarchical Markdown context files | `foundations/` five-layer scope walk — and **ahead of the corpus**: digest-checked and clearance-gated, which no harness in the study does |
| Rec 12: stay single-agent; multi-agent costs ~15x the tokens | The graph owns every loop, each with an integer maximum |
| Rec 18: do not over-engineer stuck detection | Declared loop bounds are strictly stronger than heuristic detection |

Section 15.5's *scaffold–capability frontier* argues that scaffold complexity past a point
buys operational qualities rather than accuracy. This build spent its complexity on
provenance, guards, audit and refusals - which is what that curve says to spend it on.

## What is deliberately not adopted

- **Compaction.** Seven of eleven harnesses do threshold compaction. Not needed here: a
  skill invocation is one model turn, so there is no conversation to compact. Only the
  *reactive* half - what to do when one assembled context does not fit - applies, and that
  is P83.
- **Multi-agent orchestration, ACP, MCP, skill marketplaces.** These serve developer tools
  with extensible user bases. This has one analyst and a governance chain.
- **The highest-scoring extraction pipelines in the literature.** They route pages to a
  vision-language model. The masking-order invariant forbids it: a VLM reading an unmasked
  client scan puts the client in front of a model before masking can happen. The ceiling
  here is therefore set by *local* OCR, which makes B-042 more consequential than it looks.

## The five findings, each verified against the code

1. **No context-window guard, and the wrong diagnostic when it blows.**
   `harness/context.py` assembles skill body, methodology, precedents, profile and the
   masked payload with no size check. Over the model's input limit the SDK raises
   `BadRequestError`, which `ports/llm/anthropic_messages.py` maps to
   `MODEL_PIN_UNAVAILABLE` - so a 60-page scan reports itself as *the model pin is
   unavailable*. Every input this firm receives is a multi-page scan. → **P83**

2. **Nothing is prompt-cached.** The adapter reads `cache_read_input_tokens` and never
   sets `cache_control`. The context builder already assembles stable-first (skill body,
   references, methodology, then precedents, profile, payload), which is exactly the
   precondition for a cache breakpoint, and methodology reaches every model call.
   Observation 2 of the paper. → **P84**

3. **LAVA has the producer B-040 is missing.** Its arithmetic processor has the model
   generate only a *formula*, executed by a deterministic engine; reported numerical
   infidelity ≈ 0% across three of four rule categories against 0.10–0.25 for baselines.
   That is the analyst's "100% accurate every time", by the mechanism P67 already
   specified. The missing half is the mapping from a passing tie-out to the figures it
   covers, and **what counts as covering is a practice decision, not a build** - held for
   the interview.

4. **No error taxonomy in the evals.** LAVA separates FHR (fabricated evidence), NIR
   (arithmetic error despite faithful extraction) and ECH (edge cases, 10–25% of pairs).
   Those are different repairs: FHR means the locator is wrong, NIR means the cover is.
   `evals/metrics.py` measures per-skill accuracy and separates no kinds, and
   `provenance_of` is unwired (B-041). → **P86**

5. **Layout is discarded before the model sees it.** `ParsedDocument.as_text()` flattens to
   `[page N]` plus plain text. LAVA converts documents to layout-preserving markup because
   financial tables stop meaning anything as flat text; the multistage paper reports 8.8x
   field-level accuracy for staged pipelines over whole-document input. `_tables_from_lines`
   already detects the structure and it is then thrown away. → **P85**

## The order, and why

| Phase | What it does |
|---|---|
| **P83** | A context that says when it will not fit, instead of blaming the model pin |
| **P84** | The stable prefix, cached, with the hit rate reported rather than assumed |
| **P85** | Layout survives into the payload, measured on the SEC filing already in `fixtures/public/` |
| **P86** | Three kinds of wrong: FHR/NIR/ECH in the harness, and `provenance_of` wired |

P83 first because a misleading refusal at four in the afternoon costs the analyst more
than a few points of extraction accuracy, and because it is the failure every scanned
engagement can produce. P86 before any work on B-040's producer, so that whether the
producer helped is a measurement rather than an opinion.
