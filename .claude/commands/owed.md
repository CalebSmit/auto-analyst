---
description: What the client still owes on an engagement, read off the folder - and the chase note, if I ask for one
argument-hint: "<engagement id> [--write to refresh the tracker]"
---

## 1. Ask

```
python -m uv run python tools/aa.py owed <engagement>
```

That reads the engagement's folder against its request list and **writes nothing**. Use it
first, always. `--write` refreshes the tracker workbook beside the folder, and only when I
say so: it is a write into a file I keep notes in. Anything I wrote in it is read back and
kept, but I would still rather be asked.

If the engagement is not on the roster, say so and stop. If its division has no request
list, the tool refuses rather than handing over another division's - that refusal is
correct, and the answer is that somebody writes the list for that division, not that you
find one that is close.

## 2. Tell me, in this order

1. **Still owed and essential.** The items the work actually waits on. These are the ones
   worth an email.
2. **Still owed.** The rest.
3. **Answered nothing on the list.** A document in the folder that matched no item. Say
   which, and say which of the two it probably is: something nobody asked for that may
   answer an item not on the list, or something the matching failed on. Both want a look
   and they have different answers.
4. **Matched by inference.** Items matched by something other than their name. Those are
   the ones to check first, because a wrong match reads as an item satisfied.

Do not read me the whole list. If nothing is outstanding, that is one line.

## 3. If I ask for a chase note

Draft it from the **essential outstanding** items and nothing else, in my voice: short,
no preamble, each item named the way the request list names it so the client can match it
to what they were sent. Then run it past the prose checks before you show it to me:

```
python -m uv run python tools/prose_checks.py <draft.md>
```

An em dash in an email to a client is the tell, same as in a report.

**Do not send anything.** Give me the draft. Who it goes to and when is the engagement
owner's call, and on most of these the associate chases rather than me.

## 4. What not to do

- Do not `--write` unless I asked.
- Do not guess that an item is satisfied because a file looks related. The tool's
  inference is already recorded as inference; adding yours on top of it loses the
  distinction.
- Do not decide an item is *not applicable*. That is a judgement about the engagement and
  it belongs in the tracker, written by a person.

$ARGUMENTS
