# knowledge/model-setup/

The private half of the model-setup skill. The skill itself - the procedure that builds the
firm's model from client documents, and rebuilds it for a repeat client from last year's -
lives at `skills/valuation/_group/model-setup/` and is read by the model on every run, so
nothing in it may name a client. Everything that does name one goes here.

## What goes here

- **Worked examples** - the engagements the procedure was learned on, with the client's
  name, what the documents looked like and what the finished Input tab looked like.
- **Prior models** - or notes on them: which named ranges a repeat client's model carries,
  which ones changed year to year, which ones never do (the valuation date and the latest
  fiscal year end are the two the analyst named on 2026-09-18).
- **Where it went wrong** - the mistakes the procedure exists to prevent, by client.

## What the skill does with it

The skill cites these by shape, never by name: *a manufacturing client with a 52-week
year*, not the client. When an example here is general enough to be a rule, the rule moves
to `knowledge/methodology/` and its `foundations/` twin, where every model call reads it.

## What is still unknown

Everything, until the laptop. The questions the skill's arrival answers:

- Which Input-tab fields the from-scratch path fills, in what order, from which document.
- How the repeat path decides a line item is the same line as last year's.
- Which treatments carry forward unasked and which are re-decided every year.
- What the procedure does when the prior model is a version the current template is not.

Add every client named in anything here to `knowledge/identifiers.txt` the day you type
it; `python -m uv run python tools/interview.py scan` must print `clean`.
