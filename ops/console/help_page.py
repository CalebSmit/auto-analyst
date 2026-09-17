# ruff: noqa: E501 - this module is one browser page held in a string.
"""Help: how to use the tool, in the words of the person using it.

The other pages each explain their own panels. What none of them does is say, start to
finish, what a person does to put a client's files through this and get a model out - or
what the words on those pages mean. This page does both, so the answer to "what do I do
now" is one click from anywhere rather than in a document somebody has to know exists.

Static on purpose. It describes the tool rather than reporting on it, so it cannot go stale
the way a count would; where it names a button or a panel, that name is the one on screen.
"""

from __future__ import annotations

from ui import CSS, SHELL
from ui.theme import shell

__all__ = ["PAGE"]

GLOSSARY: tuple[tuple[str, str], ...] = (
    ("Engagement", "One piece of client work - a client, the year, and the kind of valuation. It has a folder its files go in, a profile, and a workflow."),
    ("Practice group", "Which part of the firm the engagement belongs to, such as valuation / non-ESOP / repeat client. It decides which skills, methodology and Excel model the run uses."),
    ("Profile", "The judgements about an engagement the system cannot work out: industry, size band, owner-compensation benchmark, materiality, and who reviews and how fast."),
    ("Workflow", "The order the work happens in - historicals, tagging, EBITDA, comps, cost of capital, DCF, model load, model checks. Only a workflow the board approved runs on client work."),
    ("Methodology", "How the firm does the work, written down. It reaches every model call, so a person reads each file and clears it once; editing it un-clears it."),
    ("Run", "One pass of the workflow over an engagement's files. It starts on its own once files stop changing for the quiet period."),
    ("Quiet period", "How long the system waits after the last file arrives before starting a run, so a half-uploaded folder does not start a half-run."),
    ("Preflight", "Checks over the setup before anything runs. A setup mistake found here does not stop a run in the middle of the afternoon."),
    ("Review item", "Something the system was not sure enough about to decide alone - an add-back, a tag, a period that does not line up. The run waits for your answer."),
    ("Precedent", "An answer you gave, kept (masked) and shown on later engagements in the same practice group as an example of how the firm decides. Only a person's decision becomes precedent. It teaches later runs; it does not change the run you answered on."),
    ("Decided on this run", "The questions already answered on a run: what was proposed, what was decided, by whom, why, and whether the proposal was revealed before the decision."),
    ("Waiting", "A run stopped on a person: it resumes on its own once its review items are answered."),
    ("Quarantined", "A run stopped on itself: a step failed in a way retrying will not fix. Fix the cause, then Resume - or Halt it."),
    ("Halted", "A run that ended without delivering. Nothing partial leaves the system; the reason is on the run."),
    ("Provenance", "Every number says which file, sheet and cell it came from - and the check confirms the number is actually there."),
    ("Tie-out", "Every total is added up again from the rows it cites. A total that does not re-add is stopped, with both numbers."),
    ("Masking", "Client names and identifiers are replaced before anything reaches a model, and put back afterwards by code, never by the model."),
    ("Forecast (document)", "A client's projection. It is kept out of the historical table, whatever its sheets are called."),
)

PAGE = (
    f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Help - Automated Analyst</title>
<style>{CSS}
.board{{grid-template-columns:minmax(0,1.1fr) minmax(0,1fr) minmax(0,1fr);
 grid-template-rows:minmax(0,1fr) minmax(0,1fr);
 grid-template-areas:"how words words" "how colours stops"}}
.gl{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.1rem 1.4rem}}
.gl .r{{display:block}}
</style>
{shell("Help", "/help")}
<div class="wrap">
 <div class="page-head">
  <h1>Help</h1>
  <p>What you do, in order, and what the words on the other pages mean. The system does the
   mechanical work; every judgement stays yours, and nothing here concludes a value.</p>
 </div>
 <div class="board">
  <section class="card" style="grid-area:how">
   <header><h2>Putting an engagement through</h2>
    <p class="why">Five steps. The first two are once per engagement.</p></header>
   <div class="body"><div class="steps">
    <div class="step"><span class="mark">1</span><span><span class="t">Set up the engagement</span>
     <span class="d">On <a href="/admin">Setup</a>, <b>Add an engagement</b>: start with the client - the id and folder are suggested - and pick the practice group. Then open its <b>profile</b> and fill in the judgements the list says are missing.</span></span></div>
    <div class="step"><span class="mark">2</span><span><span class="t">Add the client&rsquo;s files</span>
     <span class="d">The engagement&rsquo;s <b>files</b> button: drag the statements, trial balances and forecast in as the client sent them. Or put them in the folder it shows - it is the same folder.</span></span></div>
    <div class="step"><span class="mark">3</span><span><span class="t">Activate it</span>
     <span class="d">Once preflight passes. When the files stop changing for the quiet period, a run starts on its own and appears on <a href="/">Activity</a>.</span></span></div>
    <div class="step"><span class="mark">4</span><span><span class="t">Answer what it asks</span>
     <span class="d">The Activity tab shows a count when something waits on you. <b>Review</b> shows the question and the source first; <b>Show the proposal</b> when you are ready to judge it. Accept, correct, reject or escalate - anything but accept needs a reason. The run carries on by itself.</span></span></div>
    <div class="step"><span class="mark">5</span><span><span class="t">Take the model</span>
     <span class="d">A released run lists what it delivered in its detail on Activity, with a download; the run manifest is beside it under <b>Record</b>. Every figure traces to a source file, sheet and cell, and <b>Decided on this run</b> is the list of what a person answered - which is what an associate reviewing it will ask for.</span></span></div>
   </div>
   <p class="note">Starting the tool on a machine: double-click <span class="mono">start.cmd</span> in the project folder. It sets up what is missing, checks everything, and opens this dashboard.</p>
   </div>
  </section>

  <section class="card" style="grid-area:words">
   <header><h2>Words you will see</h2>
    <p class="why">In the order you meet them.</p></header>
   <div class="body"><div class="gl">"""
    + "".join(
        f'<div class="r"><span class="lbl"><b>{term}</b><span class="d">{means}</span></span></div>'
        for term, means in GLOSSARY
    )
    + """</div></div>
  </section>

  <section class="card" style="grid-area:colours">
   <header><h2>What the colours mean</h2>
    <p class="why">Three colours carry meaning everywhere; everything else is neutral.</p></header>
   <div class="body">
    <div class="r"><span class="pill good"><i class="dot"></i>fine</span><span class="lbl">Passed, cleared, delivered - nothing for you to do.</span></div>
    <div class="r"><span class="pill warn"><i class="dot"></i>attention</span><span class="lbl">Waiting on a person, or worth a look: a warning, a stopped run, a count of items for you.</span></div>
    <div class="r"><span class="pill bad"><i class="dot"></i>problem</span><span class="lbl">Failed or refused, always with the reason and what to do about it.</span></div>
    <div class="r"><span class="pill accent"><i class="dot"></i>running</span><span class="lbl">Working right now.</span></div>
   </div>
  </section>

  <section class="card" style="grid-area:stops">
   <header><h2>When something stops</h2>
    <p class="why">It stops rather than guesses, and says why.</p></header>
   <div class="body">
    <p style="margin-top:0">Every refusal carries a code, like <span class="mono">CONFIG.METHODOLOGY_UNCLEARED</span>, and a line on what to do now. Read that line first; if the answer is not obvious, the code is the thing to quote.</p>
    <div class="r"><span class="lbl"><b>A run stopped at the model</b><span class="d">No API key in <span class="mono">.env</span>, or the model adapter is still the replay one. <span class="mono">start.cmd</span> asks for the key.</span></span></div>
    <div class="r"><span class="lbl"><b>Preflight says the methodology is not cleared</b><span class="d">On Setup, read each file and clear it. Runs are blocked until then.</span></span></div>
    <div class="r"><span class="lbl"><b>A file started nothing</b><span class="d">Its name matched no document type, or two. Preflight on Setup names it and what to do.</span></span></div>
    <div class="r"><span class="lbl"><b>A run is quarantined</b><span class="d">Its detail on Activity says why. Fix that, then <b>Resume</b> - which asks what changed, because restarting a run a guard refused is a judgement - or <b>Halt</b> it with a reason.</span></span></div>
    <div class="r"><span class="lbl"><b>A banner says the page cannot reach the server</b><span class="d">Nothing below it has changed since the time it names. The runs carry on without the page; it only reads.</span></span></div>
   </div>
  </section>
 </div>
</div>
<div id="toast"></div>
"""
    + SHELL
)
