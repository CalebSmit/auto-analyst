# /improve-agent — the protocol

You are running the `/improve-agent` command. This file is the whole of your instructions
for it, in Cursor and in Claude Code alike. Follow it exactly.

**What this is for.** The system in this repo does the mechanical stages of valuation work
under strong guarantees, but most of what it knows about *how the work is actually done*
is synthetic. The person running this command is a valuation analyst in the division
this build focuses on (`focus:` in `scope/scopes.yaml`, today **valuation / non-ESOP**).
You interview them, one question at a time, until they say stop. Then you turn what you
learned into changes to the system, with their approval, through the build's own rules.
Over many sessions, that is how the system goes from synthetic to theirs.

---

## 1. Before the first question

Run every command in this file inside the project environment:
`python -m uv run python tools/interview.py ...`. A bare `python` may lack the
dependencies, and the gap report then says `could not ...` instead of answering.

1. Read `CLAUDE.md`. Its rules and non-negotiables bind you here too. In particular:
   nothing concludes, signs or certifies; a skill proposes and never acts; guards are not
   configurable; only a human decision writes precedent.
2. Run `python tools/interview.py status`. It creates `knowledge/` on first use and tells
   you: sessions so far, topic coverage, open follow-ups, the backlog, **what the code
   says is missing for the focus division**.
3. Run `python tools/interview.py session` and note the path it prints. That is this
   session's log.
4. Skim `knowledge/profile.md`, `knowledge/workflow.md`, `knowledge/decisions.md` and the
   last session log, so you do not ask something already answered.
5. If the person typed anything after the command (for example "improve agent, focus on
   add-backs" or "let's do the Oakmont project"), that steers the first question.
6. Say, in two or three lines: which session this is, what is covered so far, and what
   you plan to ask about first and why. Then ask the first question.

## 2. Choosing each question

In this order:

0. **The "Next session" queue** at the top of `knowledge/followups.md`, if there is one:
   ask those in their numbered order, one per message, following a thread an answer opens
   before moving to the next number. "Ask me questions" means start here.
1. **An open follow-up** from `knowledge/followups.md`, if one fits the current thread.
2. **The thread you are on.** If the last answer opened something - a reason not given, a
   term you do not understand, a "usually", an exception, a document mentioned but not
   provided - follow it now. Depth on one topic beats breadth.
3. **The next topic** from `status`: open before partial, priority 1 first. Use its
   `angles` as directions, not a script.
4. **A gap the code reported** that no topic yet covers.

Regularly (roughly every third or fourth question once basics are covered) steer toward a
**real project**: ask them to pick one, give it a codename, and walk it - documents in the
order they arrived, decisions made and why, what the reviewer changed. Concrete cases are
the most valuable evidence this interview produces.

## 3. Asking

- **One question per message. Never two.** No "and also". No numbered lists of questions.
  The person wants to answer each one precisely.
- One short line of *why* you are asking is welcome when it helps them answer well.
- Ask in plain text so they can answer at length. Offer choices only when the answer
  genuinely is a closed choice.
- Specific beats general. Not "how do you handle add-backs?" but "On the last engagement
  where you added back owner compensation, how did you set the market rate, and where did
  the number come from?"
- When a document would answer better than words, ask for it: a file path, or ask them to
  put it in `knowledge/projects/<codename>/docs/`. Real client documents are allowed here
  (decided 2026-09-16; see `BUILD/OPEN.md`, Settled). Read what they give you.
- If you do not understand a term, a piece of firm jargon or an abbreviation, ask - that is
  a question, not a failure.
- Ask about **order and contingency**: what came first, what they could start without,
  what they do when something arrives late, revised, contradictory or never.

## 4. After every answer — record before asking again

Context can end at any moment. Nothing learned may live only in the conversation.
Before the next question:

1. **Append to the session log**: the question, the answer as given (verbatim or closely
   paraphrased), any files provided, and where you recorded what.
2. **Update the knowledge files** the answer touches:
   - `profile.md` — who they are, tools, AI models, approvals
   - `workflow.md` — steps, order, inputs and outputs, timings
   - `decisions.md` — `When <situation>, I <do this>, because <reason>.` with codename and session
   - `documents.md` — document types, formats, arrival order, out-of-order handling
   - `projects/<codename>/notes.md` — a project's timeline, documents and decisions
   Cite the session (e.g. `(2026-09-16-1)`) on everything you write.
3. **Mark coverage** when a topic moves:
   `python tools/interview.py mark <topic> partial --note "..." --session 2026-09-16-1`.
   Use `covered` only when the topic's `done_when` is actually met.
4. **Queue follow-ups** in `followups.md` as `- [ ] ...` for anything worth returning to
   that you are not asking next. Tick `- [x]` ones you have asked.
5. **Add identifiers** to `identifiers.txt`: every client name, person's name, entity,
   place, account or product name that could identify a client, the moment it appears.
6. **Contradictions are findings.** If an answer contradicts an earlier answer, the code,
   a skill's reference file or the blueprint, say so plainly and ask which is right. Do
   not silently pick one.
7. **Out-of-bounds wishes are findings too.** If what they describe would need the system
   to conclude a value, sign something, learn from unreviewed output, lower a guard, or
   use Excel automation, say which non-negotiable it meets, record the need in
   `decisions.md`, and suggest the in-bounds shape (usually: the system assembles, a
   person decides).

Keep the recording quiet: do it, then ask the next question. Do not narrate each file you
touched unless something went wrong.

## 5. When they say stop

"Stop", "done", "that's enough", "let's build", or anything plainly meaning it.

1. **Finish recording** the last answer (section 4).
2. **Summarise the session** in a few lines at the end of the session log and to them:
   what was learned, which topics moved, what is still unclear.
3. **Propose a build list** — changes the new knowledge justifies. Write each to
   `knowledge/backlog.md` as `## B-NNN title` with `status: proposed`, what it changes,
   the files, its size, and the answers behind it. Prefer a few well-evidenced changes
   over many speculative ones. Show them the list, numbered, one line each.
4. **Ask one question:** which of these to build now. Mark the rest `proposed` (for later)
   or `declined` as they say.
5. **Build what they approve**, the way the repo requires (section 6), then mark those
   items `built`.
6. **Close out every session, built or not:**
   - `python tools/interview.py scan` must print `clean`. If it finds an identifier in a
     committable file, remove it from that file (codename or generic wording) and rescan.
   - `python tools/verify.py --fast`, and the full `python tools/verify.py` if code changed.
   - `python tools/gate.py render`.
   - Tell them in two lines what changed and what the next session will pick up.
   - Do not commit or push unless they ask.

If they stop without wanting a build, do steps 1, 2 and 6, and leave the proposals in the
backlog.

Before closing, **queue the next session**: write a numbered "Next session" list at the top
of `followups.md` - the questions that would most change the backlog or confirm what was
just built, in asking order, suited to what they will have to hand.

## 6. How knowledge becomes the system

**The boundary.** `knowledge/` is committed to the private repo (decided 2026-09-16) and may
hold anything: real names, documents, figures. **Nothing that identifies a client leaves
it**, because skills, methodology and fixtures reach every prompt for every client. Committed files carry
generalised rules and codenames only. Worked examples in skills are rewritten generically,
or masked. `interview.py scan` enforces this against `identifiers.txt`.

Where an approved change lands, and the path it must take:

| Knowledge | Lands in | Path |
|---|---|---|
| A workflow for an engagement type | `recipes/<name>.yaml` | Write the recipe; it compiles and the plan assertions check it; registration is a person's act at `/admin`. |
| A new skill, or a rewritten skill body | `skills/…` | **Only through the governance chain** (`governance/README.md`) — drop a draft into the intake root and walk the chain. Never write into `skills/` directly. |
| Changes to an inherited skill for the focus division | `skills/valuation/non-esop/_segment/overlays.yaml` | Overlays may only tighten review and sensitivity. |
| How the division does its work | `foundations/valuation/non-esop/*.md` | Write it; a person clears it at `/admin` before any run uses it. Tell them it needs clearing. |
| The mechanical half of a skill | `harness/procedures/<skill>.py` + tests | Normal code change, with tests beside it. |
| The division's Excel model | `templates/bindings.yaml`, `templates/inputs/` | Bind at `valuation/non-esop/_segment`; bind by named range, never by cell address. |
| Chart of accounts conventions | `taxonomy/` | A **new taxonomy version**; never edit a published one in place. |
| Test cases from real projects | `fixtures/` | **Masked or synthetic only.** Never a real document or figure. |
| A decision that is a person's, not the code's | `BUILD/OPEN.md` | Record it; move answered items to Settled with a date. |

**The build's rules apply to every change.** New work is a phase: `python tools/gate.py
extend` with the reason, or `gate amend` on the current interview phase. A moved public
surface is checked with `python tools/surfaces.py --check` and accepted only after the
reason is recorded. Record abandoned approaches with `gate ledger`. Run the rehearsals
(`tools/simulate_firm.py`, and `--scripted`) after changes to intake, the driver, the
guards or the consoles.

**Scale the build to the evidence.** One session's answers rarely justify a new skill. They
often justify a clarified reference file, a recipe step, a follow-up, or a decision
recorded in OPEN.md. The system becomes autonomous by accumulation; do not try to make it
so in one sitting.

## 7. What "done" looks like, eventually

The interview is not the goal. It is finished for a topic when the system can do that
part of the work on a real engagement and the analyst would not redo it. Across sessions,
aim the build toward this, in order:

1. The pilot engagement type has a recipe that runs end to end on the local dashboard
   (`python tools/serve.py`) with a person pressing run and answering the review queue.
2. Every step in it has a real skill and a mechanical half — no step stops for want of one.
3. It loads the division's real Excel template.
4. It has been run on real projects from this interview, with the analyst's decisions as
   the comparison.
5. Only then: fewer clicks. Automatic pickup of a watched folder is already built;
   hosting (Azure) is an adapter for later, not a rewrite.
