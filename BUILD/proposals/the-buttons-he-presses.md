# The buttons he presses

*Proposed 2026-09-21, from the fifth interview session. Not yet in `plan.json` - this is
the thing being run by him first.*

Version 1 stops being something that watches and becomes something he drives. **Test the
connection**, **Update** (ShareFile to Box), **Set up model**, and **three appendix
buttons** - C economic conditions, E major market indices, F M&A markets. G, H and I need
no button: they carry forward unchanged in the copy of last year's report.

---

## What is already here, and what is wrong with it

`ports/storage/sharefile.py` and `ports/delivery/box.py` both exist as *contracts* -
registered names whose every method refuses, written so `AA_STORAGE_ADAPTER=sharefile` is
a loud refusal rather than a silent fallback to the local folder. That arrangement was
right and it bought exactly what it was meant to. But three things in it are wrong against
what is now known:

**1. The sides are reversed.** Storage is the read side; delivery is the write side. The
build put ShareFile on the read side and Box on the write side - documents read out of
ShareFile, deliverables written into Box. The real arrangement is the other way: the
client uploads to ShareFile, the files are moved to **Box**, and Box is where the tool
reads. There is no Box adapter on the storage side, so nothing can sweep a Box folder.

**2. The credentials are guessed, and the guess is wrong.** `ports/delivery/box.py` names
`BOX_ENTERPRISE_ID`. `ClbSmt/box.sharefile.automation` proves the working shape is client
credentials **with user impersonation** - `box_subject_type=user`, `box_subject_id`, and
the Box app needs "Generate User Access Tokens" switched on. So the credential is
`BOX_USER_ID`, and an enterprise id alone would authenticate as a service identity that
cannot see his folders.

**3. ShareFile cannot be authenticated from cold.** The same repo: *"ShareFile's password
grant cannot satisfy an MFA challenge, so any account with MFA enabled must authenticate
interactively."* Three env vars are therefore **not** enough. A person logs in once, and
everything after lives on a refresh token that may rotate. This is a design constraint,
not a configuration detail: an expired token is something a person fixes, and a run that
dies on one at 7am must say so in those words.

**4. Delivery is fenced off from the Update button.** Its contract says *"no reading of
client folders"* and *"two inbound edges only - released artifacts, and the run
manifest."* Copying a client's trial balance into Box is neither. Pushing the relay
through the delivery port would quietly widen an invariant that was written on purpose.
The relay gets its own surface instead.

---

## The shape of the relay

The Update button copies from ShareFile to Box **as a backup for Power Automate**, which
is being built to do the same thing automatically. That framing decides most of the
design, because the failure that matters is not a copy that did not happen - he would see
that - but **two copiers fighting**.

- **Copy, never move.** Nothing is deleted from ShareFile. If the relay is wrong, the
  source is still there; if it deleted, it would be racing Power Automate over files
  neither could get back.
- **Idempotent on content hash.** The same bytes already in Box is a skip, reported as a
  skip. Pressing Update twice, or pressing it after Power Automate already ran, converges
  rather than producing a second copy under a mangled name.
- **Different bytes at the same name is not a skip and not an overwrite.** It is the one
  case a person has to see: the client re-sent something. Box's own versioning takes it
  and the relay reports it as a re-send.
- **Not a run.** It writes no run record, releases no deliverable and cannot be reached
  from a graph step. It is an operator action, and the graph's guarantees do not apply to
  it precisely because it is not producing anything anyone will rely on.
- **It says what it did.** A list: copied, skipped, re-sent, failed - each with a name.
  That list is what B-054's request-list tracker reads to learn what arrived.
- **Partial failure is reported, not retried into silence.** Nine of twelve copied is nine
  of twelve, named, not "an error occurred".

## The shape of the appendices

**Three buttons, not six.** G assumptions & limiting conditions, H certification and I
qualifications of Chartwell & Staff *"can stay the same as the prior years. Don't need to
be updated."* Setting up the report already begins by copying last year's, so those three
arrive in the copy and **no code touches them at all**. What is left needing a button is
**C** economic conditions, **E** major market indices and **F** M&A markets.

That collapses the design. There is no longer a carried-forward source kind beside a
per-period one - there is one kind, and it is per-period. And the Appendix H boundary stops
needing a guard: nothing in the system writes to H, because H is whatever last year's
report said. The non-negotiable is satisfied by construction rather than by a check, which
is the stronger of the two.

**The source is a Word document.** He points each button at a file - the industry data
arrives as a .docx and becomes Appendix F, and so on. So an appendix is an **id**, a
**source document he points at**, and an **anchor in the report**. Still data rather than
code, because the real report has not been seen here and the first one will not match a
guess.

**Binding.** The non-negotiable is *bind by named range, never by cell address*. The Word
equivalent is a **bookmark or a heading**, never a paragraph index - a report where somebody
added a sentence must not get Appendix F written into Appendix E. An anchor that cannot be
found is a refusal naming the anchor, never a best guess.

**The hazard is that Word content does not travel as text.** Copying a body of content from
one .docx into another is not a string operation. Paragraphs carry style *names* that must
resolve in the destination, numbered lists carry a numbering definition that lives elsewhere
in the file, and every image or chart is a separate relationship part. Copy the paragraphs
alone and you get a document that opens without complaint and is laid out wrong - which is
the failure mode worth designing against, because it is the one nobody notices until it has
been sent. So the transfer carries styles, numbering and embedded parts with the content,
and **reports what it could not carry** rather than dropping it silently.

Two things are unknown until a real appendix document is in hand, and both are config
rather than a rewrite: whether the source document *is* the appendix in whole or contains
it as a region, and whether these documents carry charts as images or as live chart parts.
The first is handled by letting a source name an anchor of its own, defaulting to the whole
document. The second is a finding if it arrives.

---

## What cannot be proved here

Nothing in this repo can reach a real Box tenant or a real ShareFile account. Tests will
prove the *logic* - idempotency, ordering, refusal, token expiry, anchor binding - against
a fake that replays the HTTP shapes the reference repo records. **That is not evidence the
connection works**, and a phase that closed on it while claiming otherwise would be this
build's signature defect with a network adapter attached.

So: the code phases close here on the fake. One phase at the end is `gate: human` and
closes only on a signoff from the work machine saying the test button really connected.
Until that signoff exists, `serve.py --check` reports these seams as NOT INSTALLED - the
honest word, because what is missing is credentials on a machine, not a join this build
left unmade.

The report template is the same problem, one step worse: it has not been seen at all. P91
and P92 build against a synthetic report carrying the same anchors, and against synthetic
appendix documents carrying the things that break a copy - a numbered list, a table, an
image, a style the destination does not define. The registry being data is what makes the
real report a config change rather than a rewrite. But if the real report turns out not to
have stable bookmarks or headings at all, that is a finding that comes back here rather than
something to work around quietly.

---

## The phases

**P87 - Box, on the side documents are read from**
A real `ports/storage/box.py`: list, read, stat, over client credentials with user
impersonation. Stable order by path, sha256 computed rather than trusted, no cache that
outlives a sweep. Registers `AA_STORAGE_ADAPTER=box`. Corrects `BOX_ENTERPRISE_ID` to
`BOX_USER_ID` in the delivery adapter, which is a finding against the blueprint and gets
recorded as one.

**P88 - A connection test that says which part failed**
Credentials present, then token obtained, then folder listed, then a file's bytes read.
Four results, reported separately, because "connection failed" does not tell him whether
to fix a secret, an app permission or a folder id. The Test button on `/admin`.

**P89 - ShareFile, and the login a person does once**
The authorization-code flow. The refresh token is held through the Secrets Port, never in
`knowledge/` and never committed. Rotation is handled; expiry is reported in the words of
the thing he has to do about it. The ShareFile half of the Test button reports "never
authenticated", "token expired" and "connected" as three different things.

**P90 - The relay, which may be pressed twice**
The Update button, as above: copy not move, idempotent by hash, re-sends surfaced, partial
failure named, a record of what arrived, and no path from a graph step to it. Proven
against the fake, including the case that matters - Power Automate got there first.

**P91 - A report is a document with named places in it**
The appendix registry: id, anchor in the report, source document. Reading a report and
finding its anchors; a missing anchor refuses and names itself. Bookmarks and headings only,
and a test proves a paragraph index cannot be used as an anchor. Plus the part that is
actually hard - moving a body of Word content between documents with its styles, numbering
and embedded parts intact, and naming whatever could not be carried instead of dropping it.

**P92 - A button for each appendix that changes**
Three: C economic conditions, E major market indices, F M&A markets. Each pointed once at
the Word document its data arrives in, then pressed when that data is ready. G, H and I get
no button and no code path - they arrive in the copy of last year's report, which is why
nothing in this system can write the certification. Every update shows what it will change
before it writes, and writes a new copy rather than editing last year's report in place.

**P93 - `gate: human`. It really connected.**
Closed only with a signoff from the work machine: the Test button green against real Box
and real ShareFile, the Update button having really copied a real file once, and one
appendix really updated in a real report. Until then this phase is open and the build says
so.

**C54 - What a button is allowed to claim**
The integration checkpoint: that a green test does not read as a working connection, that
the relay cannot be reached from a run, that delivery's two-edge contract is still two
edges, and that no appendix path can write a conclusion.

---

## What this plan does not include

Items 1-6 from the session's build list - the version-1 spine: a recipe that finishes, the
input-help workbook, structure read from last year's model, deterministic line matching,
the documents pointer, and the subtotals that tie or explain themselves. That is the larger
half and it is what makes a run produce anything. This plan is the surface and the plumbing
around it.

**They are independent.** Nothing in P87-P93 needs the spine, and nothing in the spine
needs the buttons. So the order is a choice about which is wanted first at work, not a
dependency - and it is his.
