# knowledge/methodology/

The firm's valuation knowledge, as far as the interviews have recorded it, one file per
question the model has to handle in the model: how EBITDA is adjusted, which balance sheet
lines are not working capital, what a normal level of working capital is, how guideline
companies are screened, which cost-of-capital inputs the model takes, and how the firm's
reports are written. Written 2026-10-05 from the five `/improve-agent` sessions and the
owner's decision that `dcf-build`, `gpc-scrub` and `cost-of-capital` are knowledge the model
consults rather than procedures the tool runs - the firm's own model does those.

**Each file has three parts.** *What we know*: every relevant thing the analyst said, each
cited to the session and question it came from. *What the model should do with it*: rules, in
the imperative, only where the interviews support them. *What is still unknown*: the precise
questions to answer on the work laptop, where the real documents and the firm's model are.
A short honest file beats a long plausible one; the open questions are the point.

**Where the model reads them.** It does not read these files. The rules section of each one
is copied verbatim into `foundations/valuation/_group/<same name>.md`, which the Context
Builder attaches to every valuation run once a person has cleared it at `/admin`
(`foundations/README.md` says how, and why clearance is a person's act). `tests/p167` holds
each rule file to its knowledge file, so the two cannot drift: change the rules here, and
the test says the foundations copy is stale.

**How to fill one in on the work laptop.** Answer a question under *What is still unknown*
by moving it into *What we know* with its source - the model file, a report, a conversation
with a reviewer, dated - and, where it changes what the model should do, into the rules. Then
copy the rules section into the foundations file and clear it again (an edit loses its
clearance, by design). Never put a client's name, a person's name or a real engagement's
figures in here: these files feed every prompt for every client, and
`python -m uv run python tools/interview.py scan` must print `clean` before a session ends.

**What they replace.** The skills `dcf-build`, `gpc-scrub` and `cost-of-capital` under
`skills/valuation/_group/` are superseded by these files and say so in their own SKILL.md.
Their reference files were empty placeholders; nothing in here came from them.
