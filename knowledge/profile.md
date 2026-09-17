# Profile

Who the analyst is: role, team, who reviews their work, the tools and
AI models they use today and which are firm-approved. One fact per line, each
ending with the session it came from, e.g. `(2026-09-16-1)`.

## Role

- Title: Analyst, non-ESOP valuation. (2026-09-16-1)
- Tenure in the role: about 3 months as of 2026-09-16; feels they have a good picture of how the whole engagement works. (2026-09-16-1)
- Owns, start to finish: pulling the client's uploads from ShareFile into the internal Box folder, setting up the model, and completing the entire model - forecasts, WACC data, guideline public company comps and model, M&A transactions and model, and (recently) a tangible asset model. (2026-09-16-1)
- Hands off by presenting the model to the MD once they judge it done and the client has provided everything. (2026-09-16-1)

## Team on an engagement

- Analyst (this person): builds the model end to end. (2026-09-16-1)
- Associate, acting as project manager: keeps everything on schedule and reviews the model once the analyst says it is done. (2026-09-16-1)
- Managing Director: the client relationship - talks to the client, answers the big questions, leads the due diligence meetings. Sometimes reviews the model. (2026-09-16-1)

## Review chain

1. Analyst says the model is done. (2026-09-16-1)
2. Associate (PM) reviews it. Usually the only model-level reviewer. (2026-09-16-1)
3. **Internal value review (IVR):** the model is presented to the MD by the analyst, the associate, or both. (2026-09-16-1)
4. The MD decides whether it is ready for the report to be written and sent to the client. (2026-09-16-1)

- Exception: MDs usually do not review the model itself, but this analyst's MD does, because her engagements are often very complex. So a reviewer requirement varies by MD and by complexity, not just by role. (2026-09-16-1)

## Tools and AI models

- The firm has Claude: uses Claude Code on the work computer. (2026-09-16-1)
- Any Cursor model may also be used. (2026-09-16-1)
- Has an Anthropic API key on the firm's account. It belongs in `.env` on the work machine only - never in knowledge/ or any committed file. (2026-09-17-1)
- Data systems: client uploads arrive in ShareFile; internal working files are kept in Box. (2026-09-16-1)
- Capital IQ for guideline public companies and M&A transactions. No API subscription, so pulls are manual exports. (2026-09-17-1)
- Kroll for WACC market data; Capital IQ for the comps' betas and for the cost of debt by credit rating. (2026-09-17-2)
