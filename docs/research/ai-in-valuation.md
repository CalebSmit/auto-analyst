# AI in valuation practice: what the research changed here

*Written 2026-09-16, from a field guide Caleb compiled on AI tools, open-source projects and
vendor deployments in valuation and advisory work. The guide's sources were not
re-verified for this note; vendor figures in it are the vendors' own claims.*

This is the record of how that research was read against this build: what it confirms, what
it added, what waits, and what was declined and why. A future session that finds a new tool
or paper should extend this file rather than start another.

---

## The one-line reading

**The research describes the architecture this repo already has.** Its headline pattern -
*extract with provenance, then compute deterministically, and keep a credentialed person on
every judgment* - is the blueprint's. What the research adds is not a new design; it is
evidence about **where extraction breaks** (add-backs, adjustments, footnotes), a set of
**benchmarks** for deciding when to trust it, and a handful of **specific checks and
patterns** worth building.

## What it confirms (already built)

| The research says | Where it already lives |
|---|---|
| Extract once, attach a page-level citation to every number, never re-read the raw PDF at question time | The Source Parse Store (`ops/source_parse.py`), keyed `(run_id, source_id, locator)` and written once; the figure envelope (`contracts/figure.schema.json`) carries `source_id` and `locator` on every value; `guards/provenance.py` refuses a figure whose source is not in the intake manifest |
| Let code do the math, not the model | `tools/recompute.py` is "the only arithmetic a skill can cause"; `guards/tieout.py` re-derives every derived figure |
| Specialist, single-deliverable agents beat one generalist | One skill, one turn, one output contract (`max_turns == 1`); recipes compose them |
| "A harness, not a model" | The orchestrator, graph compiler and guarded runtime are the product; the model is behind a port (`ports/llm`) with a pinned version |
| The AI drafts, a credentialed person signs | No schema has a field a concluded value could go in; `qc-tieout`'s readiness enum cannot say approved; only a human decision writes precedent |
| Build evals, read logs, design gates | `evals/gates.yaml` per skill, replay harness, shadow runs, the 11-stage governance chain |
| Keep generated code out of regulated work, audit everything | Skills contain no code and cannot import tools; the event log is append-only; the vault is the only re-identifier |
| Plain SKILL.md is the lowest lock-in format | It is the format here, parsed by the repo rather than by an SDK |
| Extraction degrades exactly where valuation lives | Add-backs above materiality go to review (`material_addbacks_require_review`), officer compensation is always reviewed, and EBITDA outputs get a self-verification pass that never sees the first pass's reasoning |

## What it added (built 2026-09-16, phase P38)

1. **The model checks, as deterministic code** - `tools/statement_checks.py`. The analyst
   named three checks (net income ties to the client's, the balance sheet balances, cash
   flow ending cash equals balance sheet cash) and named getting them to pass as slow. The
   research's QoE tools (askOdin's "deterministic compiler", Finsider's automated scan) add
   the discipline: **a failure is preserved with both numbers and the difference, never
   smoothed**, and an absence of evidence is never a pass. Every total goes through
   `recompute`. Output fits the `qc-tieout` contract, so the qc-tieout procedure (backlog
   B-004) wires it in rather than rewriting it. Includes period-over-period movement flags
   (Numeric's flux analysis) with no default threshold, because materiality is the
   practice's decision.
2. **A forecast is not history** - `intake/readers/classify.py` and a `forecast` document
   type. Reading the research's provenance-first rule against the pilot found a real defect:
   a client forecast workbook scored on every financial-statement cue and was bound as
   `financial_statements` with full confidence and no review. The pilot recipe waits for
   historicals and nothing else, so a forecast arriving first could have released a run on
   projected years. It is closed at all three places a file is judged: **by name** (the
   first setup declares forecast filename conventions, so "Income Statement Forecast.xlsx"
   matches two types and is held for a person), **by contents** (forward-looking cues take
   precedence over statement cues in the classifier), and **at the table** (the
   timing-normalization procedure holds forecasts out of the historical table in code, and
   escalates a run that has only forecasts). The safe error - a historical file with a
   budget column waits for a person - replaces the unsafe one.
3. **Benchmarks for trusting extraction**, proposed rather than decided - `BUILD/OPEN.md`
   section 5.
4. **Interview topics** the research showed were missing - `interview/topics.yaml`: an
   extraction baseline (the ground truth the benchmark needs), data sources and tools, and
   quality-of-earnings angles on normalization.

## What waits (backlog, with the research idea behind each)

| Idea | Source in the research | Why it waits | Backlog |
|---|---|---|---|
| **"What materials am I missing"** - a per-engagement coverage report against the recipe's expected documents, drafted as a follow-up request to the client | F2's missing-file detection; Hebbia's documents-by-questions matrix | Needs more document types (fixed asset schedule, debt schedule) in the closed vocabulary and an `expected_types` field on recipes; the forecast type was the urgent one | B-009 |
| **An add-back register that grades support** - each adjustment tagged defensible or scrutinize, with the evidence behind it | `vortex-tuck-in-analyst`; askOdin | A contract version for `ebitda-normalization` and a skill change through the governance chain; and the analyst has not yet described their add-backs (next session, question 1) | B-010 |
| **Extraction accuracy measured on real documents** - line items and locators against analyst-keyed ground truth | Stage 1 benchmark (95% / 90%) | Needs one real engagement the analyst keyed by hand, kept as a masked gold case | B-011 |
| **Proof of cash** - revenue reconciled to bank deposits | Finsider, askOdin | No bank statement document type or reader; whether the practice does it at all is unasked | B-012 |
| **Qualitative ratings feeding DCF assumptions**, each with a rating, a confidence and cited evidence | `financial-analyst-skills` (moat to terminal growth) | Assumptions are judgment and `assumptions_require_review`; the mapping from rating to number would be firm methodology, and nobody at the firm has stated one | not yet proposed |

## What was declined, and why

| Idea | Why not here |
|---|---|
| Vector database / embeddings for retrieval | The research's own best example skipped it. Retrieval here is by locator and by scope, which is auditable; similarity search is not. |
| Routing each task to a different frontier model | A model pin names one model and is folded into every plan hash. Two engines behind one step is two runs that share a hash and can disagree - the failure the pin exists to prevent. |
| Agents that write and execute code in a sandbox | A skill proposes and never acts; every tool is named, capped and authorised by the Policy Gate. Generated code is an unbounded tool. |
| Multi-turn agent loops (Chain-of-Thought agent chains, coordinator sub-agents deciding when to retry) | `max_turns == 1` and the graph owns every loop, with an integer ceiling the compiler checks. |
| Local open-weight models (Ollama, Groq-hosted Llama) | The firm's approved route is Claude (decided 2026-09-05); the LLM port keeps it swappable if that changes. |
| Writing into Excel through the application | No Excel automation, COM or VBA; openpyxl into a copy of a pinned template, bound by named range. |
| EDGAR libraries for public filings | Useful later for the guideline public company set, not for the client's own financials. Revisit with the GPC skill. |
| Drafting report narrative | The blueprint stops before the report, and the MD decides at the internal value review whether one is written. Descriptive flux tables are in scope (built); narrative is a scope decision for a person - held in `BUILD/OPEN.md`. |
| The 60% earnings-prediction result | A directional academic finding about public-company statements, not a valuation method. It supports "model for reading, code for numbers", which is already the rule. |

## Build or buy

The research's verdict - build the ingestion and the firm's methodology, consider buying a
valuation engine (Valutico) or a QoE specialist (Finsider, askOdin) - is a firm decision
with procurement and risk review attached. It is held in `BUILD/OPEN.md` rather than decided
by the code. Nothing built here forecloses buying a slice: every external capability would
arrive as an adapter behind an existing port.

---

## Follow-up: the LlamaIndex due-diligence agent, read in full (2026-09-17)

*"How to Build a Financial Due Diligence Agent with LiteParse", Logan Markewich, LlamaIndex
blog. A demo, by its author's own description, not a production system.*

The post is the concrete version of the field guide's headline pattern: parse each PDF once
into text with page coordinates, keep a flat store with no vector database, give the model
three tools (list, search, get page), make it wrap every number it uses in a citation naming
file and page, and **verify each citation by finding the cited text on the cited page** -
through a ladder of forgiving matches (exact, whitespace-flexible, currency symbols stripped,
alphanumeric only, longest token). A citation that cannot be found is shown with an
"unverified" badge rather than hidden.

### What it confirmed

| The post | Here |
|---|---|
| Parse once, keep text with its position | The Source Parse Store: every row keyed by `(run_id, source_id, locator)`, written once |
| No vector database; the working set is small | Retrieval is by locator and scope; precedent lookup is scoped and ranked, never similarity over client files |
| The model must cite file and page for every number | The figure envelope requires `source_id`, `locator` and `source_version`, and the schema refuses fabricated ids |
| Show an unverified citation instead of hiding it | A failed guard is recorded with both values, repaired once through the declared loop, then quarantined into a review item a person reads |

### What it changed (built 2026-09-17, phase P39)

1. **A citation is verified by finding the number, not just the place.** Read against the
   post, the Provenance Check had half of the discipline: it required the cited location to
   exist, and never looked at what was there. A figure read off the page (no derivation)
   could cite a real row and carry a different amount, and nothing re-derives a figure with
   nothing to re-derive. The guard now resolves the rows at the locator and requires the
   figure's value on one of them - by the parsed value, or by the printed text read as a
   statement prints it (currency stripped, parentheses and trailing minus as negative). It
   deliberately stops short of the post's loosest rungs: never the absolute value (an
   expense cited as a gain is the error itself, though the opposite sign is named), and
   never a suffix like `52.00B` (scale is the envelope's to state). New code:
   `SKILL.CITED_VALUE_ABSENT`, with an eleventh adversarial fixture - a transposed amount.
2. **The finding underneath: two blueprint step guards were never called on a live run.**
   Tracing where the Provenance Check runs, to change it, showed the dispatcher ran only the
   schema check. Provenance and Tie-Out were built, tested and used by the eval harness, and
   no live run called them. The blueprint marks both as step guards that exist now; the code
   disagreed. Resolved by wiring both into the dispatcher at the composition root - tie-out at
   the run's recorded tolerance, zero when none is recorded, because a looser one is a
   materiality decision nobody has made. The scripted rehearsal confirms both pass on real
   timing and EBITDA outputs, and now reports any fail-closed step guard that no run emitted.

### What waits

| Idea | Why it waits | Backlog |
|---|---|---|
| **Showing the source on the page** - the reviewer sees the cited number highlighted where it sits | Needs positions per text item (pypdf's text visitor, already used for the hidden-text scan, gives them) and a page renderer, which is a new dependency with a licence to check. A text excerpt with the value marked needs neither | B-013 |
| **A search tool over the engagement's documents** (keyword and regex, filtered by file) | Skills here are one turn with their inputs assembled for them; a searching agent is a different shape. Useful for a person on the review page first | B-014 |

### What it declined

| The post | Why not here |
|---|---|
| An agent loop of up to 30 tool calls | One skill, one turn; the graph owns every loop |
| LiteParse itself | A Node library; this build is Python, and pypdf already gives text runs with positions |
| HTML filings converted to PDF through a headless browser | No client file arrives as HTML; EDGAR waits for the GPC skill |
| Streaming the answer to a chat UI | The output is a structured, guarded artifact, not a chat reply |
