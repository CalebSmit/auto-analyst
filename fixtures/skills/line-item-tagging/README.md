# fixtures/skills/line-item-tagging/

The 400-item fixture the skill is scored against. Synthetic throughout: the descriptions
are the ordinary vocabulary of a small-company chart of accounts, written the several
ways bookkeepers write them, with no client, no account number and no value anywhere.

| file | what it is |
|---|---|
| `items.json` | 400 line items as the procedure sees them: `line_item_ref`, description, source labels, the statement the source sheet suggests, the periods present. No values, because the model gets none. |
| `gold.json` | The analyst gold set: category and both flags per ref. Assigned per account by hand; the edge cases follow `edge-cases.md` and `nwc-inclusion-rules.md`. |
| `proposals.json` | Twenty batches of twenty - what a model is expected to propose, replayed through the fake port. Made by a deliberately plain cue-matcher over the taxonomy, so it disagrees with the gold set exactly where a description is combined, sparse, or means different things in different places. |
| `disagreements.md` | Every row where the proposals and the gold set differ, with why the gold is right. **This is the review list for the P19 sign-off.** |

## How the gold set was built

The blueprint's own plan is that the first gold set is the 200 line items two analysts
agreed on, with the ones they disagreed on as the edge cases. That measurement needs the
firm's analysts and a real chart, and neither exists until the P24 pilot. Until then the
gold set is authored: one category per account, the firm taxonomy's default flags, and
a flag override only where `nwc-inclusion-rules.md` says the treatment departs (accrued
interest, income taxes payable on a pass-through, restricted cash held for operations).

What the sign-off confirms is not that 95% is a good number - it is that the gold set is
right on the rows where the system and the gold set differ. Those rows are in
`disagreements.md`, each with the rule that decides it.

## How the proposals were built

A cue-matcher: the taxonomy's own cue words, matched against the description's words
with a light stem, the statement hint as a tie-breaker, and a small preference for the
more specific category when two match. It is not a model and it is not meant to be
clever; it is meant to be *wrong in the places a model is wrong* - a combined line, a
bare "Misc", a deposit that could be either side of the sheet - so the disagreement
list is a real review list rather than an empty one.

Regenerated deterministically; a rebuild is byte-identical.
