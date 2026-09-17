# The workflow, as currently understood

The non-ESOP engagement from first contact to delivered model, step by step.
Each step: what happens, who does it, what it needs, what it produces, how long it
takes, and the session it came from. Rewrite a step when an answer changes it; the
session logs keep the history.

*First draft from high-level answers. Order within steps 3-6 is not yet confirmed.*

## Engagement types seen so far

| Type | What it is | Notes |
|---|---|---|
| Startup / pre-revenue | Early-stage company, including a technology spun off from an existing company to become its own business | Most common for this analyst so far. No revenue history, so the forecast carries the valuation. (2026-09-16-1) |
| Purchase price allocation (PPA) | Model and valuation done after a business has already been bought or sold | Often. Standard (likely financial reporting) and how the tangible asset model fits: unconfirmed. (2026-09-16-1) |
| Buy-sell agreement | Valuation under a buy-sell agreement | One starting soon; none done yet. (2026-09-16-1) |
| **Mature operating company - the pilot** | The first engagement type the system takes on (chosen 2026-09-16) | Uses the three core methods. Chosen as the easiest. Standard and level of value: usually fair market value, controlling (2026-09-17-2). (2026-09-16-1) |
| Market value, for the owners' information | A normal operating company valued because the owners want to know | A few done. "A little easier." (2026-09-16-1) |

**Volume:** about 10 engagements in the first 3 months: ~25% pre-revenue, ~25% purchase
price allocation, ~25% mature operating company ("a normal valuation, kinda like an ESOP"),
~25% a mix of the others (buy-sell etc.). (2026-09-16-1)

**Core method set:** a DCF, a guideline public company (GPC) analysis and guideline M&A
transactions are run on nearly every engagement, "to get a better idea of what is going
on". One-off or custom analyses are added on top (e.g. the tangible asset model). (2026-09-16-1)

Whether these share one workflow or differ beyond added analyses: unknown.

## The pilot sequence - mature operating company

As stated, in order (2026-09-16-1):

1. **Historicals in** - organize the data from all the different documents received and input it into the model.
2. **Forecast.**
3. **Set up the models** - the DCF and the others.
4. **Find comps and comparable transactions** - guideline public companies and guideline M&A transactions.
5. **WACC data.**
6. **Ranges, not weights** (2026-09-17-1): each method gives an enterprise value range; the final enterprise value is chosen within the ranges, and the MD decides. The system stops at presenting the ranges.
7. Associate review, then the internal value review with the MD (see Steps 7-9).

**Where the hours go** (2026-09-16-1):

1. Data retrieval - getting everything from the documents into the model. The most time.
2. The forecast.
3. Also slow: getting the model's checks to pass (see decisions.md), and entering every long-term debt instrument into the model's debt tab one by one.

**Dependencies (settled 2026-09-17-1):** the DCF structure already exists in the template, so
"set up the models" means filling inputs. GPC, M&A transactions and WACC are independent and
can run side by side. The DCF's terminal value uses the GPC and transaction multiples (medians
and averages of EV/EBITDA and EV/revenue) when the exit multiple method is chosen over Gordon
Growth.

## Steps

1. **Client uploads documents to ShareFile.** Client. Produces: raw documents. (2026-09-16-1)
2. **Analyst downloads everything from ShareFile into the internal Box folder.** Analyst. Manual today. Folder structure and naming: unknown. (2026-09-16-1)
3. **Set up the model.** Analyst. Repeat clients (a large share) start from last year's model: historicals copied over and only the new period entered; forecast by the same methodology with fresh assumptions; new WACC data as of the new valuation date; comps kept unless there is good reason to change; last year's adjustment items with new amounts (2026-09-17-2). Starting point for new clients: unknown. (2026-09-16-1)
4. **Historical financials into the model - first priority.** Analyst. Needs: historical statements (separate PDFs per year, sometimes Excel) and interim financials when given. Client-provided Excel tabs are copied into the firm's model and highlighted yellow as client-sourced. (2026-09-16-1)
5. **Forecast.** Analyst. If the client gives a forecast (usually Excel), it is copied in (yellow) and used **unchanged** as the source of truth; the firm's forecast ties to it wherever possible, except interest expense, which comes from the firm's debt tab (2026-09-17-1). If not, the firm builds one from drivers beneath the income statement - revenue growth % per year, COGS % of revenue, opex % of revenue (sometimes improving gradually) - with modest assumptions, sends it to the client, and the client rarely pushes back; drivers are easy to change (2026-09-17-1). Repeat clients: forecast done "slightly different" from last year based on client input. (2026-09-16-1)
6. **Valuation analyses.** Analyst. WACC data; guideline public company comps and model; M&A transactions and model; tangible asset model when applicable. Dependencies between these: unknown. (2026-09-16-1)
- **Due diligence meeting(s)** - timing relative to the steps above unknown. The MD meets the client; the team takes notes on what the client presents about the last year and what they think about the forecast. The notes rarely change the model; they explain the forecast and unusual costs, for the report (corrected 2026-09-17-1). (2026-09-16-1)
7. **Associate review.** When the analyst says the model is done (and the client has provided everything), the associate (PM) reviews it. Some MDs also review the model directly on complex engagements. (2026-09-16-1)
8. **Internal value review (IVR).** Analyst and/or associate present the model to the MD. She looks first at the M&A transaction multiples, then the comps, then the industry and market context. Afterwards usually little changes - at most the multiples used or a WACC assumption like the company-specific risk premium (2026-09-17-2). (2026-09-16-1)
9. **MD decides whether report writing starts.** If yes, the report is written and sent to the client. Who writes it, and what happens when the MD says no: unknown. The system stops before the report, and never concludes. (2026-09-16-1)
