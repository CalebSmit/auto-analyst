# Report writing

> **Draft knowledge file.** Mined from five recorded interview sessions (2026-09-16 to
> 2026-09-21), one later remark recorded in the backlog (2026-10-02), the open-items register
> and the owner's brief for these files. The interviews reached the report only at its edges:
> who gates it, what the due diligence meeting contributes, how the appendices are set up, and
> the existence of a restricted-use report and a restricted-use deck. **House style, sections,
> voice and the body of the report were never described.** Everything on those is a question.

This file is what the model consults when it is setting up, updating or checking one of the
firm's valuation reports or the deck that goes with it: what the report types are as far as
known, which parts carry forward from last year and which change each period, what the
appendices are and how each is sourced, what the system may never write, and what a draft
should be checked for. It exists because the owner asked for "one that is really good at
writing different reports we use" (owner's brief, 2026-10-05). It is honest about how little of
that is known yet.

## What we know

1. **The report is written only after the MD says so.** The sequence is analyst builds the
   model, associate reviews it, internal value review with the MD, "then the MD decides if it
   looks good to start writing the report on it to send to the client." Who writes it was not
   said. (2026-09-16-1, Q3)

2. **There are restricted-use reports and restricted-use decks.** "At work I'm building a bunch
   of things within Claude Code like workflows to help me write restricted use reports through
   a Word document and also restricted use PowerPoints... it has a lot of context of how to do
   all these things on my work computer." Those workflows have not been seen by this build.
   (2026-10-02, recorded in knowledge/backlog.md B-091)

3. **Setting up a report means copying last year's and getting the appendix information in.**
   "Mainly means copying and pasting the report from last year, then only setting it up.
   Meaning getting the right appendix information in." (2026-09-21-1, updates section)

4. **The named appendices, in the analyst's order:** C economic conditions ("info to pull into
   the report template"); E summary of major market indices; F summary of M&A markets; G
   assumptions and limiting conditions; H certification; I qualifications of the firm and its
   staff. Appendices A, B and D exist by implication and were not named. (2026-09-21-1)

5. **Two kinds of appendix.** C, E and F are market data that changes every period. G, H and I
   "can stay the same as the prior years. Don't need to be updated" - they arrive in the copy
   of last year's report and nothing touches them. (2026-09-21-1)

6. **Each changing appendix is updated on its own, when its data is ready.** "When the
   industry data is ready, I will press the industry update button... and like when the
   economic appendix is done and ready, I will click that button and it will update." The
   analyst points each appendix at where its source lives. (2026-09-21-1)

7. **The appendix source arrives as a Word document.** So an update is a Word-to-Word content
   move, carrying styles, numbering and embedded images or charts, into a named place in the
   report - a bookmark or heading, never a paragraph position. (2026-09-21-1)

8. **The due diligence meeting is the report's qualitative source.** The meeting "is more to
   explain the forecast. And gives color into why they think the forecast will do what they are
   saying. So it's good for writing the report to explain the forecast or to explain why for
   example they had a lot of costs the current year." (2026-09-17-1, Q7)

9. **The MD's own questions at review are the report's likely emphases:** the transaction
   multiples, the comps, and "what is going on in this industry and market that the subject
   company is involved in". Industry and market context is research with sources, and nothing
   in the build gathers it. (2026-09-17-2, Q11)

10. **The value conclusion is the MD's.** Each method gives a range; "we look at those ranges
    and choose a final enterprise value for the company within the range somewhere. But that is
    ultimately up to the managing director." The report states a conclusion that this system
    never produces. (2026-09-17-1, Q10)

11. **Standard and level of value, for the pilot type:** usually fair market value, on a
    controlling basis. (2026-09-17-2, Q13)

12. **Client-sourced material is marked yellow in the model.** The same convention marks a cell
    a person types into. Whether anything equivalent exists in the report was not asked.
    (2026-09-16-1, Q1; 2026-09-18-1, Q3)

13. **House style is unknown, and the build's current prose checks are inferences.** The
    dash the firm uses, how amounts are written, how the valuation date is referred to, which
    terms are capitalised because they are defined - all open, recorded as owed in
    BUILD/OPEN.md, with a test asserting the topic is still open. (BUILD/OPEN.md;
    interview/topics.yaml `report-and-deck`)

14. **The deck has no path in the build at all**, and the right way to bind into it (named
    placeholder or named shape) is not knowable without the firm's template. (backlog B-094)

15. **Nothing concludes, signs or certifies.** The certification (Appendix H) is carried
    forward from last year's report by the copy and never written by code; the appraiser signs
    outside the system. (2026-09-21-1; CLAUDE.md non-negotiables)

## What the model should do with it

- Start a report by copying last year's report for the client, when there is one. For a new
  client, there is no instruction yet - ask.
- Leave Appendices G, H and I exactly as the copy brought them. Never write into H.
- For C, E and F, update only when asked for that appendix, from the Word document the person
  pointed at, into the place in the report that carries that appendix's name. Refuse, naming
  the anchor, when the place cannot be found. Preview before writing; write a new file rather
  than editing the one read.
- Carry styles, numbering and embedded parts with the content, and say what could not be
  carried rather than dropping it silently.
- When drafting or checking any narrative, draw the explanation of the forecast and of an
  unusual year from the due diligence meeting notes, and cite them; do not invent a reason the
  notes do not give.
- Never write a concluded value, a range the MD has not chosen, a signature, or a certification
  statement. Leave every such place for a person.
- Report the prose checks (tells, slips, two spellings of one thing) beside a draft, and never
  block on them, because the house style is not yet the firm's - it is inferred.
- Do not build toward the deck until the template's binding mechanism is known.

## What is still unknown

1. What a restricted-use report is at this firm, how it differs from the full report, and
   which sections it keeps. Whether there are other report types (full narrative, calculation
   report, letter).
2. The sections of each report type, in order, and which change every year versus which are
   boilerplate.
3. Appendices A, B and D: what they are. And whether "industry" is one of the named appendices
   (C, E or F) or a separate one - the analyst named an "industry update button" and an
   "economic appendix" as if they were different.
4. Where each appendix's source Word document comes from (who writes it, which subscription or
   research source feeds it), and whether a source document is the appendix whole or contains
   it as a region.
5. The real report's heading or bookmark names for each appendix; the six anchors in the build
   are guesses.
6. Who writes the report body - analyst, associate, MD - and what "writing" consists of beyond
   setup: which paragraphs are rewritten each year on a repeat client.
7. House style, as rules: the dash; how amounts, percentages and dates are written; how the
   valuation date is referred to; the defined terms and their capitalisation; the firm's
   register.
8. The voice and tense of the narrative, and a report comment the analyst has had about wording
   rather than numbers.
9. What goes in the report from the model - which exhibits, which tables, which figures - and
   whether they are pasted, linked or retyped.
10. The restricted-use deck: what is on each slide, which slides change every year, where the
    figures come from, and whether the template binds by placeholder name or shape name.
11. What the work-machine Claude Code workflows for reports and decks already know, whether any
    of it carries a client's name, and whether it can be copied here, called from here, or must
    stay where it is. (The `work-machine-context` topic; never interviewed.)
12. What happens when the MD says the model is not ready at the internal value review, and
    whether a report is ever written without one.
13. Whether the engagement letter, standard of value and level of value are stated in a fixed
    form of words the report reuses.
