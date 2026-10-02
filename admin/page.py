# ruff: noqa: E501 - this module is one browser page held in a string. Wrapping the
# template literals to a hundred columns would make them harder to read, not easier.
"""The setup surface: the page a person who is not a developer actually uses.

Everything here was reachable as JSON long before it was reachable at all. That is not the
same as usable: labelling a folder with its practice group, clearing methodology, or
reading why preflight will not let an engagement start are all things a managing director
has to be able to do without a terminal.

**The setup path is the page.** A first-time reader does not want six panels, they want to
know what to do next - so the first thing they see is the six steps, which are done, and
one button on the one that is not. The panels are underneath, for somebody who knows what
they are looking for. The checklist is derived from the live configuration on every load
rather than remembered, so it cannot claim a step is finished when the thing it describes
was undone somewhere else.

**Nothing here can do what the API cannot.** Every action posts through the same endpoints
a script would use, so there is nothing the page can do that is not also on the record:
the identity travels with every write, and a refusal comes back as a diagnostic the page
prints - the *what to do now*, not the status code.

Deliberately one file with no build step and no framework. It is read by whoever maintains
this after the first person, and a page they can read in one sitting is worth more here
than one that was pleasant to write.
"""

from __future__ import annotations

from ui import CSS, SHELL
from ui.theme import shell

__all__ = ["PAGE"]

PAGE = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Setup - Automated Analyst</title>
<style>{CSS}
/* Six panels and a checklist. The checklist holds three rows of the left column because
   while there is work in it, it is the screen. */
.board{{grid-template-columns:minmax(0,1.05fr) minmax(0,1fr) minmax(0,.9fr);
 grid-template-rows:repeat(6,min-content);
 grid-template-areas:"steps pre scopes" "steps pre scopes" "steps pre recipes"
  "steps meth recipes" "eng meth seams" "eng meth seams" "report report report"}}

/* And gives them back when it is finished. A checklist with every box ticked is the least
   useful thing on a screen and it was holding the best position on it permanently: on a
   machine that has been set up, the engagements are what somebody came to look at. The
   steps stay one keystroke away rather than being removed, because "how did this get set
   up" is a real question and the answer should not require reading the code. */
body.all-done .board{{grid-template-areas:"steps pre scopes" "eng pre scopes" "eng pre recipes"
  "eng meth recipes" "eng meth seams" "eng meth seams" "report report report"}}
body.all-done #checklist .bar{{display:none}}
#checklist .bar{{margin-bottom:var(--s4)}}
#checklist details{{margin-top:var(--s2)}}
</style>
{shell("Setup", "/admin")}
<div class="wrap">
 <div id="offline"></div>
 <div class="page-head">
  <h1>Setup</h1>
  <p>Everything the system needs before it can look at a client&rsquo;s files. Every change
   here is recorded against it &mdash; against whoever the system resolved you as, with the
   reason given.</p>
 </div>

 <div class="board">
  <section class="card" style="grid-area:steps">
   <header><h2>Getting set up</h2>
    <p class="why">Eleven steps, in order. Each is checked against the live system &mdash; the
     first two against this machine and the rest against the configuration &mdash; so this
     cannot tell you something is done when it is not.</p></header>
   <div class="body"><div id="checklist"><div class="skel"></div><div class="skel"></div></div></div>
  </section>

  <section class="card" style="grid-area:eng">
   <header><h2>Engagements<span class="of" id="n-roster"></span></h2>
    <p class="why">One per piece of client work. The practice group you give it decides
     which skills it gets, which methodology it carries and which model it builds into.</p></header>
   <div class="body"><div id="roster"><div class="skel"></div></div></div>
   <div class="foot">
    <button data-act="showAdd">Add an engagement</button>
    <span class="note" style="margin:0">It starts paused. Nothing is read until you activate it.</span>
   </div>
  </section>

  <section class="card" style="grid-area:pre">
   <header><h2>Preflight</h2>
    <p class="why">Fourteen checks over the live configuration. A setup mistake found here
     is one that does not stop a run at three in the afternoon.</p></header>
   <div class="body"><div id="pre"><div class="skel"></div></div></div>
   <div class="foot"><button data-act="refresh">Run again</button></div>
  </section>

  <section class="card" style="grid-area:meth">
   <header><h2>Methodology</h2>
    <p class="why">How the firm does the work. It reaches <b>every</b> model call, so
     somebody has to read each file and clear it. Editing a cleared file un-clears it.</p></header>
   <div class="body"><div id="meth"><div class="skel"></div></div></div>
  </section>

  <section class="card" style="grid-area:scopes">
   <header><h2>Practice groups</h2>
    <p class="why">What an engagement can be labelled with, and what each label gets you
     today.</p></header>
   <div class="body"><div id="scopes"><div class="skel"></div></div></div>
  </section>

  <section class="card" style="grid-area:recipes">
   <header><h2>Workflows</h2>
    <p class="why">The order the work happens in. One runs on client work only after the
     board approves it; editing it afterwards un-approves it.</p></header>
   <div class="body"><div id="recipes"><div class="skel"></div></div></div>
  </section>

  <section class="card" style="grid-area:report">
   <header><h2>Setting up the report</h2>
    <p class="why">Start from last year's, then press an appendix when its data is
     ready. G, H and I carry forward in the copy &mdash; nothing here writes them.</p></header>
   <div class="body"><div id="report"><div class="skel"></div></div></div>
  </section>

  <!-- A stream: every seam the code has, plus the connections a person tests. -->
  <section class="card stream" style="grid-area:seams">
   <header><h2>What is wired</h2>
    <p class="why">Derived from the code, not from this sentence.</p></header>
   <div class="body"><div id="seams"><div class="skel"></div></div>
    <div class="r lede" style="margin-top:var(--s4)">
     <span class="lbl">Box connection<span class="d">Four questions, asked in order:
      the credentials, the token, the folder, a file. Nothing here has ever reached a
      real Box - this is the first thing that would.</span></span>
     <button data-act="testBox">Test it</button>
    </div>
    <div class="r lede">
     <span class="lbl">ShareFile connection<span class="d">A ShareFile account with MFA
      cannot be signed in by a program, so this part is a person with a browser, once.
      After that it runs on a token that gets renewed.</span></span>
     <span><button data-act="signInShareFile">Sign in</button>
      <button data-act="testShareFile">Test it</button></span>
    </div>
    <div class="r lede">
     <span class="lbl">Update from ShareFile<span class="d">Copies what is in ShareFile
      into Box. Power Automate does this on its own; this is for when it has not. Nothing
      is deleted, and anything already there is left alone.</span></span>
     <button data-act="updateFromShareFile">Update</button>
    </div>
    <div id="connection"></div>
   </div>
  </section>
 </div>
</div>

<div class="modal" id="add-card" style="display:none">
 <section class="card">
  <header><h2>New engagement</h2>
   <p class="why">Start with the client; the id and folder are suggested from it and can be changed.</p></header>
  <div class="body">
   <!-- Three questions, asked in the order somebody answers them: who it is, where their
        files are, how it runs. Eight controls in one stack is a form; the same eight under
        three rules is a thing with a shape, and the shape is what tells you how much is
        left before you start. -->
   <p class="section-label">Who it is</p>
   <div class="cols two ask">
    <div class="field">
     <label for="e_client">Client</label>
     <input id="e_client" placeholder="Henderson Manufacturing">
    </div>
    <div class="field">
     <label for="e_id">Engagement id</label>
     <input id="e_id" placeholder="HEND-2026-01">
     <p class="hint">Suggested from the client name. Change it if the firm numbers these differently.</p>
    </div>
    <div class="field">
     <label for="e_scope">Practice group</label>
     <select id="e_scope"></select>
    </div>
    <div class="field">
     <label for="e_kind">Is this a repeat client?</label>
     <select id="e_kind">
      <option value="repeat">Repeat &mdash; we valued them before, and last year&rsquo;s model exists</option>
      <option value="non-repeat">New &mdash; first time we have valued this client</option>
     </select>
     <p class="hint">Three quarters of our work is repeat. It decides what last year&rsquo;s
      workbook is used for, and what a run may look at from previous years.</p>
    </div>
   </div>

   <p class="section-label">Where its files are</p>
   <div class="cols two ask">
    <div class="field">
     <label for="e_watch">Watched folder</label>
     <select id="e_watch"></select>
    </div>
    <div class="field">
     <label for="e_dest">Deliverables go to</label>
     <select id="e_dest"></select>
    </div>
    <div class="field wide">
     <label for="e_folder">Their folder, under the watch root</label>
     <input id="e_folder" placeholder="Henderson Manufacturing/2026 Valuation">
     <p class="hint" id="e_folder_hint"></p>
    </div>
   </div>

   <p class="section-label">How it runs</p>
   <div class="field">
    <label for="e_pin">Excel model template <span class="aside">&mdash; optional, and not the AI model</span></label>
    <input id="e_pin" placeholder="Leave blank to use the practice group&rsquo;s default">
    <p class="hint">The workbook a finished run writes into. Which AI model answers a skill is
     set for the whole machine, not per engagement, and the panel behind this says which one it is.</p>
   </div>
  </div>
  <div class="foot">
   <span class="spacer">It starts paused. Nothing is read until you activate it.</span>
   <button class="quiet" data-act="hideAdd">Cancel</button>
   <button class="primary" data-act="addEngagement">Register</button>
  </div>
 </section>
</div>
<div id="toast"></div>
{SHELL}
<script>
/* SETUP is always an object, never null.

   A fresh machine has no configuration document and `/api/admin/setup` refuses - which is
   this page's whole purpose, because the button that writes the first one is step three of
   the checklist below. SETUP was set to null for that case and most of the page guarded
   for it; `checklist()` read `SETUP.recipes` without the guard, threw, and took every
   panel after it down with it. So on the one machine that needs this page, the page was
   twelve grey rectangles under a banner blaming the network.

   Null was the wrong shape for "nothing is set up". An empty object is the true one: every
   `(SETUP.x || [])` on this page then reads empty rather than throwing. Whether a
   configuration exists is a separate fact, because it is a separate question. */
let SETUP = {{}}, CONFIGURED = false, SCOPES = null, METH = {{files: []}}, ME = null;

/* The approved workflows, fetched once and read by two things.

   Step seven of the checklist read `SETUP.recipes`, and `/api/admin/setup` has never
   returned a `recipes` key - the recipes live behind `/api/admin/recipes`, which is what
   the Workflows panel has always used. So on every machine, configured or not, the step
   saw an empty list: it could not be ticked, its Approve button could not appear, and the
   checklist could not reach "Ready to run" however much was set up. The panel beside it
   said four approved at the same time, which is how it stayed invisible - the right answer
   was on the screen, two inches away, under a different name.

   Built and wired to nothing, in the one list a person follows on their first day. */
let RECIPES = [];

/* The registry names a disposition "Repeat client"; this is what it means to somebody
   setting one up. Keyed by the registry's id so the two cannot drift apart silently. */
const KIND_SAYS = {{
  'repeat': 'Repeat — we valued them before, and last year’s model exists',
  'non-repeat': 'New — first time we have valued this client',
}};

/* The name on a change is the system's, not one anybody types here. The page reads it so
   it can show you whose name is going on what you are about to do; it sends nothing, and
   the server fills it in. Asking would invite somebody to disagree with it by accident,
   and the disagreement is refused - which reads like a broken button. */
function who() {{ return ''; }}

/* ---------------------------------------------------------------- the steps */
function checklist() {{
  const configured = CONFIGURED;
  const watches = (SETUP.watches || []).length;
  const dests = (SETUP.destinations || []).length;
  const roster = SETUP.roster || [];
  const files = METH.files || [];
  const cleared = files.length > 0 && files.every(f => f.state === 'cleared');
  const active = roster.filter(r => r.state === 'active').length;
  /* The two that live in .env rather than in the configuration document. Without them the
     seven steps below can all be done and a run still cannot mask anything or ask anything,
     which is the state this screen used to call "Ready to run". */
  const env = SETUP.environment_ready || {{}};
  const approved = RECIPES.filter(x => x.state === 'registered');
  const runnable = approved.filter(x => x.can_finish !== false);
  const vault = env.vault || {{ready: false, detail: 'unknown', name: 'AA_VAULT_KEY'}};
  const model = env.model || {{ready: false, adapter: '?', detail: 'unknown'}};

  const steps = [
    /* Before the configuration, because neither can be fixed from this page: both are
       lines in a file on this machine, and a person who reaches step seven without them
       has done six steps that cannot be used yet. */
    {{done: vault.ready, t: 'Set the masking key',
      d: vault.ready
        ? vault.detail
        : vault.detail || (vault.name + ' is not set. Nothing can be masked without it, and '
            + 'the worker pool will not start.'),
      go: vault.ready ? null : ['How to set it', 'explainVault']}},
    {{done: model.ready, t: 'Connect the AI model',
      d: model.ready
        ? ('Answered by ' + model.adapter)
        : ('Skills are answered by ' + model.adapter + ' \u2014 ' + model.detail
           + '. Setup will finish and no work will be done.'),
      go: ['Test the connection', 'testModel']}},
    {{done: configured, t: 'Set this environment up',
      d: 'Writes the first configuration. Nothing else can be saved until it exists.',
      go: configured ? null : ['Set it up', 'initialise']}},
    {{done: watches > 0, t: 'Say which folder to watch',
      d: watches ? (SETUP.watches || []).map(w => w.name + ' (' + (w.root || 'the whole inbox') + ')').join('; ')
                 : 'The folder client files arrive in' + (SETUP && SETUP.inbox_root ? ', under ' + SETUP.inbox_root : '') + '.',
      go: configured && !watches ? ['Choose a folder', 'addWatch'] : null}},
    {{done: dests > 0, t: 'Say where deliverables go',
      d: dests ? (SETUP.destinations || []).map(d => d.name + ' (' + (d.path || 'the outbox') + ')').join('; ')
               : 'The folder a finished workbook is written to' + (SETUP && SETUP.outbox_root ? ', under ' + SETUP.outbox_root : '') + '.',
      go: configured && watches && !dests ? ['Choose a folder', 'addDestination'] : null}},
    {{done: cleared, t: 'Clear the methodology',
      d: cleared ? 'All ' + files.length + ' files read and cleared'
                 : 'Somebody reads each file once. Runs are blocked until they have.',
      go: configured && !cleared && files.some(f => f.state !== 'cleared')
        ? ['Read the next one', 'clearFile',
           {{name: (files.find(f => f.state !== 'cleared') || {{}}).name || ''}}] : null}},
    /* Approval is a board decision and the register is not committed, so a clone has
       nothing approved and Activate refuses at the last step for the want of a step that
       was never on the list. It sits before registering because that is where the watch
       form asks which workflow to run. */
    {{done: approved.length > 0, t: 'Approve a workflow',
      d: approved.length
        ? approved.length + ' approved' + (runnable.length ? '; ' + runnable[0].name + ' is the one a run finishes' : '')
        : 'Nothing runs a workflow nobody approved. ' + (RECIPES.length
            ? RECIPES.length + ' are on disk, waiting.' : ''),
      go: (() => {{
        const waiting = RECIPES.filter(x => x.state !== 'registered')
          .sort((a, b) => (a.can_finish === false) - (b.can_finish === false))[0];
        return approved.length || !waiting ? null
          : ['Approve ' + waiting.name, 'approveRecipe', {{name: waiting.name, state: waiting.state}}];
      }})()}},
    {{done: roster.length > 0 && roster.every(r => Number(r.budget_usd) > 0), t: 'Set a spend limit',
      d: (() => {{
        /* The ceiling comes from the configuration document, so an unconfigured machine
           does not have it - and the sentence rendered "the firm ceiling of $undefined".
           A number nobody has is left out of the sentence rather than printed as a word. */
        const ceiling = SETUP.firm_ceiling_usd;
        if (!roster.length) return 'What each engagement may cost in model calls, in total. Without one the only cap is '
          + (ceiling === undefined ? 'the firm ceiling' : 'the firm ceiling of $' + ceiling)
          + ' a run, with no limit on the number of runs.';
        const open = roster.filter(r => !(Number(r.budget_usd) > 0));
        if (!open.length) return 'Set on ' + plural(roster.length, 'engagement', 'engagements');
        return open[0].client + ' has none, so its runs are capped only by '
          + (ceiling === undefined ? 'the firm ceiling' : 'the firm ceiling of $' + ceiling)
          + ' each, with no limit on the total'
          + (open.length > 1 ? '; ' + (open.length - 1) + ' more like it' : '');
      }})(),
      go: (() => {{
        const open = roster.find(r => !(Number(r.budget_usd) > 0));
        return open ? ['Set one', 'settings', {{id: open.engagement_id}}] : null;
      }})()}},
    {{done: roster.length > 0, t: 'Register an engagement',
      d: roster.length ? plural(roster.length, 'engagement', 'engagements') + ' on the roster'
                       : 'The client work itself, and the practice group it belongs to.',
      go: (configured && watches && dests && !roster.length) ? ['Add one', 'showAdd'] : null}},
    {{done: roster.length > 0 && roster.every(r => !(r.profile_gaps || []).length), t: 'Fill in the engagement profile',
      d: (() => {{
        const missing = roster.filter(r => (r.profile_gaps || []).length);
        if (!roster.length) return 'Twelve things about the client the skills read - the industry, the size, the year end, what owner pay should be. It takes about ten minutes and nothing runs without it.';
        if (!missing.length) return 'Complete for ' + plural(roster.length, 'engagement', 'engagements');
        return missing[0].client + ' still needs ' + plural(missing[0].profile_gaps.length, 'answer', 'answers')
          + (missing.length > 1 ? ', and ' + (missing.length - 1) + ' more like it' : '');
      }})(),
      go: (() => {{
        const first = roster.find(r => (r.profile_gaps || []).length);
        return first ? ['Fill it in', 'editProfile', {{id: first.engagement_id}}] : null;
      }})()}},
    {{done: active > 0, t: 'Activate it',
      d: active ? plural(active, 'engagement active', 'engagements active')
                : 'Preflight has to pass for it first. Until then nothing is read.',
      go: roster.length && !active
        ? ['Activate ' + roster[0].engagement_id, 'move',
           {{id: roster[0].engagement_id, to: 'activate'}}] : null}},
  ];
  /* Every step that has something to press shows it, and only the next one shows it
     loudly. The button used to render on `next` alone, which turned "in order" into a
     requirement: a fresh clone runs on the fake adapter, so step two - connect the AI
     model - can never be marked done, so it was permanently `next`, so step three's
     **Set it up** button never appeared. A machine nobody had configured could not be
     configured from the page whose whole purpose is configuring it.

     Order is still the advice. It is not a lock, because the steps are not actually
     dependent in that way: a person can write the first configuration before they have an
     API key, and the checklist should not be the thing stopping them. */
  const next = steps.findIndex(s => !s.done);
  const done = steps.filter(s => s.done).length;

  const left = steps.length - done;
  const drawn = '<div class="steps">' + steps.map((s, i) =>
    `<div class="step ${{s.done ? 'done' : ''}} ${{i === next ? 'now' : ''}}">
       <span class="mark">${{s.done ? '&#10003;' : i + 1}}</span>
       <span><span class="t">${{esc(s.t)}}</span><span class="d">${{esc(s.d)}}</span></span>
       ${{s.go ? `<span class="go"><button class="${{i === next ? 'primary' : 'quiet'}}" data-act="${{esc(s.go[1])}}"${{data(s.go[2])}}>${{esc(s.go[0])}}</button></span>` : ''}}
      </div>`).join('') + '</div>';

  /* The figure is what is left, not what is finished. "5 of 7 done" is a score; "2 steps
     left" is the thing somebody is actually holding in their head, and it counts down to a
     word rather than to a number. */
  $('checklist').innerHTML =
    `<div class="progress">
      <span class="n">${{left || '&#10003;'}}</span>
      <span class="of">${{left
        /* The step's own title, not a lowercased copy of it. `toLowerCase()` was there to
           make it read as a continuation of "Next:", and it turned "Connect the AI model"
           into "connect the ai model" - the one title with an acronym in it. */
        ? `<b>${{left === 1 ? 'step left' : 'steps left'}}</b>Next: ${{esc(steps[next].t)}}`
        : '<b>Ready to run</b>A run would mask, ask a model and write a workbook.'}}</span>
      <span class="of done">${{done}} of ${{steps.length}}<br>done</span>
     </div>
     <div class="bar ${{next === -1 ? 'good' : ''}}">
      <i style="width:${{(done / steps.length * 100).toFixed(0)}}%"></i></div>` +
    (next === -1
      ? `<details><summary>What was done, in order</summary>${{drawn}}</details>`
      : drawn);

  /* And it stops holding the best position on the screen once it has nothing to say. The
     checklist is the reason a first-time reader is here and dead weight to everybody else,
     so when every step is done the board gives its rows to the panels and the steps go
     behind a summary line. Written on the wrapper rather than by rebuilding the grid, so
     there is one place the layout is decided. */
  document.body.classList.toggle('all-done', next === -1);
}}

/* What a button does, by name. The values ride in data attributes: an engagement id, a
   client's folder and a methodology filename are all free text, and none of them is
   allowed to become script. */
ACTIONS.refresh = () => refresh();
ACTIONS.hideAdd = () => hideAdd();
ACTIONS.addEngagement = () => addEngagement();
/* A dialog this page builds itself rather than through `ask()`, so its cancel needs a name
   like everything else. `el` is the button; the modal is whatever contains it. */
ACTIONS.closeModal = (d, el) => el.closest('.modal').remove();
ACTIONS.initialise = () => initialise();
ACTIONS.testBox = () => testConnection('box');
ACTIONS.testShareFile = () => testConnection('sharefile');
/* How deep the folder has to be, taken from the watch that is selected. A pattern watch
   at depth 2 sweeps <root>/<a>/<b>, and a folder one level shallower matches nothing that
   will ever be listed - which registering now refuses, and which used to be a green setup
   page over a folder nobody was looking at. Saying it here means nobody has to be refused. */
function folderHint() {{
  const slot = $('e_folder_hint');
  if (!slot) return;
  const watch = (SETUP && SETUP.watches || []).find(w => w.id === $('e_watch').value);
  if (!watch || watch.kind === 'bound') {{ slot.textContent = ''; return; }}
  const depth = Number(watch.depth || 2);
  const shape = Array.from({{length: depth}}, (_, i) => '<' + 'abcdefg'[i] + '>').join('/');
  slot.textContent = 'Exactly ' + depth + ' level' + (depth === 1 ? '' : 's')
    + ' below ' + (watch.root || 'the root') + ', because this watch sweeps '
    + (watch.root || '') + '/' + shape + '. The client’s files go inside it.';
}}

ACTIONS.testModel = () => testConnection('model');

/* The one step on this page a button cannot do. The key never leaves the machine and is
   never typed into a browser, so what a person needs here is the command and the file -
   and a line saying what losing it costs, because that is not recoverable. */
ACTIONS.explainVault = () => ask({{
  title: 'Set the masking key',
  why: 'It is generated on this machine and lives in .env, which is never committed. '
     + 'Nothing is masked without it and the worker pool will not start. If that file is '
     + 'replaced, every token the vault already holds becomes unreadable.',
  /* The command goes in `body`, which is monospace and keeps its line breaks. The
     newlines are written doubled because this file is a format template: a single
     escape is a real newline by the time the browser sees it, which is an
     unterminated string. `node --check` in tests/p42 caught exactly that, twice. */
  body: 'Run this in the project folder:\\n\\n'
      + 'python -c "from cryptography.fernet import Fernet; '
      + 'print(Fernet.generate_key().decode())"\\n\\n'
      + 'Put the line it prints into .env as:\\n\\n'
      + 'AA_VAULT_KEY=the-line-it-printed\\n\\n'
      + 'Then restart the server.',
  fields: [],
  ok: 'Close',
  note: '.env is never committed, so the key stays on this machine.'
}});
ACTIONS.signInShareFile = () => signInShareFile();
ACTIONS.updateFromShareFile = () => updateFromShareFile();
ACTIONS.pickReport = () => pickReport();
ACTIONS.updateAppendix = d => updateAppendix(d.appendix, false);
ACTIONS.previewAppendix = d => updateAppendix(d.appendix, true);
ACTIONS.addWatch = () => addWatch();
ACTIONS.addDestination = () => addDestination();
ACTIONS.showAdd = () => showAdd();
ACTIONS.clearFile = d => clearFile(d.name);
ACTIONS.approveRecipe = d => approveRecipe(d.name, d.state);
ACTIONS.move = d => move(d.id, d.to);
ACTIONS.retire = d => retire(d.id);
ACTIONS.showFiles = d => showFiles(d.id);
ACTIONS.updateTracker = d => runTracker(d.id, false);
ACTIONS.previewTracker = d => runTracker(d.id, true);
ACTIONS.settings = d => settings(d.id);
ACTIONS.setRecipe = d => setRecipe(d.id, d.recipe);
ACTIONS.editProfile = d => editProfile(d.id);
ACTIONS.copyText = d => copyText(d.text);
ACTIONS.activateFrom = (d, el) => {{ el.closest('.modal').remove(); move(d.id, 'activate'); }};

/* ---------------------------------------------------------------- panels */
async function refresh() {{
  try {{
    SETUP = await get('/api/admin/setup');
    CONFIGURED = true;
    online();
  }} catch (e) {{
    // A machine nobody has configured yet answers with a refusal, and that is not the same
    // as a server nobody can reach: the first is this page's whole purpose, the second
    // means nothing below can be trusted.
    //
    // The test used to be `e.code`, which is only set when the server refused with a
    // structured diagnostic. The refusal this page exists to handle - no configuration
    // document yet - is a plain sentence with no code, so it took the other branch and a
    // fresh machine was told its own server was unreachable. `refused` is set by every
    // answer that came back from the server, which is the thing actually being asked.
    SETUP = {{}};
    CONFIGURED = false;
    if (!e || !e.refused) offline(e);
  }}

  /* The two facts that are about this machine rather than about its configuration, asked
     separately so a machine with no configuration still gets them. Merged in rather than
     replacing, because a configured machine already has them in `setup` and the two
     cannot disagree - they are the same two methods behind both routes. */
  if (!CONFIGURED) {{
    const env = await get('/api/admin/environment').catch(() => null);
    if (env) Object.assign(SETUP, env);
  }}

  ME = await get('/api/admin/whoami').catch(() => null);
  $('chrome-right').innerHTML =
    (CONFIGURED ? esc(SETUP.environment) + ' &middot; configuration v' + esc(SETUP.version)
           : '<span class="pill warn"><i class="dot"></i>not set up</span>') +
    (ME ? ' &middot; <span title="Every change is recorded against this name. It is who the '
        + 'system resolved you as, not something typed here.">acting as <b>'
        + esc(ME.name) + '</b></span>' : '');

  METH = await get('/api/admin/methodology').catch(() => ({{files: []}}));
  /* Before `checklist()`, because step seven is about these. One fetch, two readers. */
  RECIPES = (await get('/api/admin/recipes').catch(() => null) || {{}}).recipes || [];
  checklist();
  roster();
  preflight();
  scopes();
  methodology();
  workflows();
  seams();
  reportPanel();
}}

function roster() {{
  const rows = SETUP.roster || [];
  const n = $('n-roster');
  if (n) n.textContent = rows.length ? String(rows.length) : '';
  $('roster').innerHTML = rows.length ? rows.map(r => `<div class="r engagement">
     <span class="lbl"><b>${{esc(r.client || r.engagement_id)}}</b><br>
      <span class="sub" style="white-space:normal">${{esc(r.engagement_id)}} &middot; ${{esc(r.scope_path)}} &middot; ${{r.recipe ? esc(r.recipe) : 'default workflow'}}</span>
      ${{(r.profile_gaps || []).length ? `<span class="why-line"><a href="#profile=${{esc(r.engagement_id)}}" data-act="editProfile" data-id="${{esc(r.engagement_id)}}" style="color:var(--warn)" title="${{esc(r.profile_gaps.join('; '))}}">profile: ${{esc(r.profile_gaps.length === 1 ? r.profile_gaps[0] : r.profile_gaps.length + ' things missing')}}</a></span>` : ''}}
      ${{r.is_repeat && !r.prior_model ? `<span class="why-line"><a href="#settings=${{esc(r.engagement_id)}}" data-act="settings" data-id="${{esc(r.engagement_id)}}" style="color:var(--warn)" title="A repeat client's work starts from last year's workbook. Until this is set there is nothing to roll forward from.">last year&rsquo;s model: not set</a></span>` : ''}}</span>
     <span class="pill ${{r.state === 'active' ? 'good' : ''}}"><i class="dot"></i>${{esc(r.state)}}</span>
     <span class="acts">
      <a class="btn quiet" href="#files=${{esc(r.engagement_id)}}" data-act="showFiles" data-id="${{esc(r.engagement_id)}}" title="Where this engagement's files go, what is there, and adding more">files</a>
      <a class="btn quiet" href="#settings=${{esc(r.engagement_id)}}" data-act="settings" data-id="${{esc(r.engagement_id)}}" title="Budget, review level and how long files are held before a run">settings</a>
      <button class="quiet" data-act="setRecipe" data-id="${{esc(r.engagement_id)}}" data-recipe="${{esc(r.recipe || '')}}">workflow</button>
      <button class="quiet" data-act="editProfile" data-id="${{esc(r.engagement_id)}}">profile</button>
      ${{r.state === 'active'
        ? `<button data-act="move" data-id="${{esc(r.engagement_id)}}" data-to="pause">Pause</button>`
        : `<button class="primary" data-act="move" data-id="${{esc(r.engagement_id)}}" data-to="activate">Activate</button>`}}
      ${{r.state === 'archived' ? '' : `<button class="quiet" data-act="retire" data-id="${{esc(r.engagement_id)}}" title="Retire this engagement. It stops being swept and stays on the record.">retire</button>`}}
     </span></div>`).join('')
   : '<div class="empty"><b>No engagements yet</b>An engagement is one piece of client work.</div>';
}}

async function preflight() {{
  let p;
  try {{ p = await get('/api/admin/preflight'); }}
  catch (e) {{
    $('pre').innerHTML = '<div class="empty"><b>Not available yet</b>Set the environment up first.</div>';
    return;
  }}
  const blocking = p.checks.flatMap(c => c.failures.filter(f => f.severity === 'fail'));
  const warnings = p.checks.flatMap(c => c.failures.filter(f => f.severity !== 'fail'));
  const shown = blocking.concat(warnings);

  /* "All clear" is only all clear when there is nothing under it. On a real setup this
     badge read **All clear** with "15 checks, 3 warnings" beside it and two warning cards
     below it - a green label on a panel that is telling you about three things. What
     `passed` means is that nothing *blocks* a run, which is the fact worth being green
     about, so when there is something to say the badge says that instead and the warnings
     underneath are left to speak for themselves.

     This comment is here rather than inside the template literal below, which is where it
     was written first. An HTML comment is a comment to a browser parsing HTML; inside a
     template literal it is text - so the two backticks in it ended the literal and took
     the whole script with it. Every panel on the page rendered as a grey bar, the suite
     stayed green, and it was found by looking at the screen. Nothing here parsed this
     JavaScript until tests/p140. */
  $('pre').innerHTML =
    `<div class="r lede">
      <span class="lbl"><span class="pill ${{p.passed ? 'good' : 'bad'}}"><i class="dot"></i>${{
        p.passed
          ? (warnings.length ? 'Nothing blocks a run' : 'All clear')
          : plural(blocking.length, 'blocker', 'blockers')}}</span></span>
      <span class="sub">${{p.checks.length}} checks${{warnings.length ? ' &middot; ' + plural(warnings.length, 'warning', 'warnings') : ''}}</span>
     </div>` +
    (shown.length
      ? shown.map(f => `<div class="r">
          <span class="lbl"><b>${{esc(f.detail)}}</b>
           <span class="d">${{esc(f.what_now || '')}}</span></span>
          <span class="pill ${{f.severity === 'fail' ? 'bad' : 'warn'}}">${{f.severity === 'fail' ? 'blocks' : 'warning'}}</span>
         </div>`).join('')
      : '<div class="empty"><b>Nothing is in the way</b>Every check passed against the live configuration.</div>') +
    `<details><summary>All ${{p.checks.length}} checks</summary>` +
    p.checks.map(c => `<div class="r"><span class="lbl">${{esc(c.label)}}</span>
       <span class="sub">${{esc(c.detail)}}</span>
       <span class="pill ${{c.status === 'pass' ? 'good' : c.status === 'warn' ? 'warn' : 'bad'}}">${{esc(c.status)}}</span></div>`).join('') +
    '</details>';
}}

async function scopes() {{
  try {{ SCOPES = await get('/api/admin/scopes'); }}
  catch (e) {{
    $('scopes').innerHTML = '<div class="empty"><b>Not read</b>' + esc((e && e.text) || 'the practice groups could not be read') + '</div>';
    return;
  }}
  /* One pill per row. Three of them - focus, parked, firm layer only, defined - put a row
     of badges beside every line, which is the thing the stylesheet's own note says makes a
     tool look like a toy. Only one of the four is ever the reason somebody is reading the
     row, so that one is the pill and the rest are words. */
  const standing = p => p.parked ? ['parked', '']
    : p.firm_layer_only ? ['firm layer only', 'warn']
    : p.focus ? ['focus', 'good'] : ['defined', 'good'];

  $('scopes').innerHTML =
    '<div class="r head"><span class="lbl">Practice group</span><span class="num">Skills</span><span class="sub">Standing</span></div>' +
    SCOPES.paths.map(p => {{
      const [word, tone] = standing(p);
      return `<div class="r"><span class="lbl mono">${{esc(p.scope_path)}}${{
        p.focus && p.parked ? '<span class="d">the focus division</span>' : ''}}</span>
      <span class="num">${{p.skills}}</span>
      <span class="pill ${{tone}}">${{word}}</span>
      </div>`;
    }}).join('') +
    '<p class="note">A group with nothing defined behind it gets the firm&rsquo;s skills and none of its own &mdash; the honest state until its leads name their segments, not an error.</p>';
}}

function methodology() {{
  const files = METH.files || [];
  $('meth').innerHTML = files.length ? files.map(f => `<div class="r">
     <span class="lbl mono">${{esc(f.name)}}</span>
     <span class="sub">${{esc(f.cleared_by || '')}}</span>
     <span class="pill ${{f.state === 'cleared' ? 'good' : f.state === 'edited' ? 'bad' : 'warn'}}">${{f.state === 'edited' ? 'edited since' : esc(f.state)}}</span>
     ${{f.state === 'cleared' ? '' : `<button data-act="clearFile" data-name="${{esc(f.name)}}">Clear</button>`}}
     </div>`).join('')
   : '<div class="empty"><b>No methodology files</b>They live in <span class="mono">foundations/</span>.</div>';
}}

function workflows() {{
  $('recipes').innerHTML = RECIPES.length ? RECIPES.map(x => `<div class="r">
     <span class="lbl mono">${{esc(x.name)}}</span>
     <span class="sub">${{esc(x.approved_by || '')}}</span>
     <span class="pill ${{x.state === 'registered' ? 'good' : x.state === 'edited' ? 'bad' : 'warn'}}">${{x.state === 'registered' ? 'approved' : x.state === 'edited' ? 'edited since' : 'not approved'}}</span>
     ${{x.state === 'registered' ? '' : `<button class="btn" data-act="approveRecipe" data-name="${{esc(x.name)}}" data-state="${{esc(x.state)}}">Approve</button>`}}
     </div>`).join('')
   : '<div class="empty"><b>No workflows</b></div>';
}}

async function seams() {{
  const r = await get('/api/readiness').catch(() => null);
  if (!r) {{ $('seams').innerHTML = '<div class="empty">Unavailable</div>'; return; }}
  /* `needs_installing` is software somebody adds, not a join this build left unmade, and
     saying "not wired" about it would send a person looking in the wrong place. */
  const ai = SETUP && SETUP.ai_model;
  $('seams').innerHTML =
    (ai ? `<div class="r">
      <span class="lbl">AI model<span class="d">${{esc(ai.adapter)}} &mdash; ${{esc(ai.means)}}${{
        ai.reaches_a_model ? '. Skills ask for low, mid or high: ' + esc(Object.values(ai.tiers).join(', ')) : ''}}</span></span>
      <button class="ghost" data-act="testModel">Test</button>
      <span class="pill ${{ai.reaches_a_model ? 'good' : ''}}"><i class="dot"></i>${{ai.reaches_a_model ? 'live' : 'no spend'}}</span>
     </div>` : '')
    + r.seams.map(s => `<div class="r">
     <span class="lbl">${{esc(s.name)}}<span class="d">${{esc(s.detail)}}</span></span>
     <span class="pill ${{s.ready ? 'good' : (s.needs_installing ? 'warn' : 'bad')}}"><i class="dot"></i>${{
       s.ready ? 'wired' : (s.needs_installing ? 'not installed' : 'not wired')}}</span>
    </div>`).join('');
}}

/* The connection test. Four steps, each shown on its own, because "it failed" does not
   say whether to open .env, the Box developer console, or the folder's URL. A step after
   a failure reads "not reached" rather than red: the one thing this button is for is
   pointing at the right screen, and colouring a step nobody asked about would undo it. */
async function testConnection(service) {{
  const box = $('connection');
  const asking = {{box: 'Box', sharefile: 'ShareFile', model: 'the model'}}[service] || service;
  box.innerHTML = `<div class="note tight">Asking ${{esc(asking)}}&hellip;</div>`;
  let r;
  try {{
    r = await post('/api/admin/connection/' + service, {{}});
  }} catch (e) {{
    box.innerHTML = `<div class="note tight bad">${{esc((e && e.detail) || 'The test could not be run.')}}</div>`;
    return;
  }}
  const pill = s => s === 'pass' ? 'good' : (s === 'fail' ? 'bad' : '');
  box.innerHTML =
    `<div class="r lede"><span class="lbl">${{r.connected ? 'Connected' : 'Not connected'}}
      <span class="d">${{esc(r.proves)}}</span></span>
     <span class="pill ${{r.connected ? 'good' : 'bad'}}"><i class="dot"></i>${{
       r.connected ? 'reached ' + esc(r.service) : 'did not'}}</span></div>`
    + r.steps.map(s => `<div class="r">
       <span class="lbl">${{esc(s.label)}}<span class="d">${{esc(s.detail)}}</span></span>
       <span class="pill ${{pill(s.status)}}"><i class="dot"></i>${{esc(s.status)}}</span>
      </div>`).join('')
    + (r.connected && !r.in_use
        ? `<div class="note tight">${{service === 'model'
            ? 'The door opens, and runs are still answering from a stand-in. Set ' +
              '<code>AA_LLM_ADAPTER=anthropic_messages</code> in .env to make this the ' +
              'adapter a run uses.'
            : 'The plumbing works, and runs are still reading somewhere else. Set ' +
              '<code>AA_STORAGE_ADAPTER=box</code> to make this the adapter a sweep uses.'
          }}</div>`
        : '');
}}

/* The sign-in is a person and a browser, and it has to be: an MFA challenge cannot be
   answered by a program. The window is opened from the click rather than after the fetch
   returns, because a popup opened later is a popup the browser blocks - and a blocked
   popup here looks like a broken button. */
async function signInShareFile() {{
  const tab = window.open('', '_blank');
  let r;
  try {{
    r = await post('/api/admin/sharefile/sign-in', {{}});
  }} catch (e) {{
    if (tab) tab.close();
    $('connection').innerHTML =
      `<div class="note tight bad">${{esc((e && e.detail) || 'Sign-in could not be started.')}}</div>`;
    return;
  }}
  if (tab) tab.location = r.url; else window.location = r.url;
  $('connection').innerHTML =
    `<div class="note tight">Finish signing in on the ShareFile tab, then press
     <b>Test it</b>. Nothing is stored here until that sign-in comes back.</div>`;
}}

/* Update. Safe to press twice, and the report says so rather than leaving somebody to
   infer it from a screen full of "skipped". */
async function updateFromShareFile() {{
  const box = $('connection');
  box.innerHTML = '<div class="note tight">Copying from ShareFile&hellip;</div>';
  let r;
  try {{
    r = await post('/api/admin/sharefile/update', {{}});
  }} catch (e) {{
    box.innerHTML = `<div class="note tight bad">${{esc((e && e.detail) || 'The copy could not be run.')}}</div>`;
    return;
  }}
  const c = r.counts;
  const pill = o => o === 'failed' ? 'bad' : (o === 'skipped' ? '' : 'good');
  box.innerHTML =
    `<div class="r lede"><span class="lbl">${{c.copied}} copied, ${{c.skipped}} already there,
      ${{c.resent}} re-sent${{c.failed ? ', ' + c.failed + ' failed' : ''}}
      <span class="d">${{esc(r.means)}}</span></span>
     <span class="pill ${{r.complete ? 'good' : 'bad'}}"><i class="dot"></i>${{
       r.complete ? 'all of it' : 'partly'}}</span></div>`
    + r.moves.filter(m => m.outcome !== 'skipped').map(m => `<div class="r">
       <span class="lbl">${{esc(m.path)}}${{m.detail ? '<span class="d">' + esc(m.detail) + '</span>' : ''}}</span>
       <span class="pill ${{pill(m.outcome)}}"><i class="dot"></i>${{esc(m.outcome)}}</span>
      </div>`).join('')
    + (c.skipped && !c.copied && !c.resent && !c.failed
        ? `<div class="note tight">Everything was already in Box. Nothing needed doing,
           which is what it looks like when Power Automate has already run.</div>`
        : '');
}}

/* The report. Three buttons, not six: G, H and I stay the same as prior years and arrive
   in the copy of last year's file, so there is nothing here that could write the
   certification. Each button is pointed at the Word document its data arrived in. */
let REPORT = '';
let SOURCES = {{}};

async function pickReport() {{
  /* In the page, not a browser pop-up: a pop-up cannot explain itself and blocks
     everything behind it, and this is the one question on the panel that needs a
     sentence of context. */
  const said = await ask({{
    title: 'Which report is being set up',
    why: "This period's report - the copy of last year's. It is read and never written "
       + 'to; each appendix update leaves a new file beside it.',
    fields: [{{
      name: 'path', label: 'Path to the .docx', required: true, value: REPORT || '',
      placeholder: 'C:\\... or a path on this machine',
      hint: 'Press Set up from last year first if this period does not have one yet.',
    }}],
    ok: 'Use this report',
  }});
  if (!said) return;
  REPORT = said.path.trim();
  reportPanel();
}}

async function reportPanel() {{
  const box = $('report');
  if (!REPORT) {{
    box.innerHTML = `<div class="r lede"><span class="lbl">No report chosen
      <span class="d">Point at this period's report &mdash; the copy of last year's that
      is being set up. Nothing is written to it; each update writes a new file.</span></span>
      <button data-act="pickReport">Choose</button></div>`;
    return;
  }}
  let r;
  try {{
    r = await get('/api/admin/report/appendices?report=' + encodeURIComponent(REPORT));
  }} catch (e) {{
    box.innerHTML = `<div class="note tight bad">${{esc((e && e.detail) || 'That report could not be read.')}}</div>`
      + `<div class="r"><span class="lbl">${{esc(REPORT)}}</span><button data-act="pickReport">Choose another</button></div>`;
    return;
  }}
  box.innerHTML =
    `<div class="r lede"><span class="lbl">${{esc(r.report)}}
      <span class="d">Each update writes a new file beside this one. This one is never
      edited &mdash; it is usually the only copy of last year's work.</span></span>
     <button data-act="pickReport">Change</button></div>`
    + r.appendices.map(a => `<div class="r">
       <span class="lbl">Appendix ${{esc(a.letter)}} &mdash; ${{esc(a.title)}}
        <span class="d">${{a.found
          ? 'bound to a ' + esc(a.kind) + ', ' + a.owns + ' block(s)'
          : esc(a.detail)}}</span></span>
       <span>${{a.found ? `<input class="path" id="src-${{esc(a.appendix)}}"
           placeholder="the .docx its data arrived in"
           value="${{esc(SOURCES[a.appendix] || '')}}">
         <button data-act="previewAppendix" data-appendix="${{esc(a.appendix)}}">Preview</button>
         <button data-act="updateAppendix" data-appendix="${{esc(a.appendix)}}">Update</button>`
        : '<span class="pill bad"><i class="dot"></i>no anchor</span>'}}</span>
      </div>`).join('')
    + `<div class="note tight">Appendices G, H and I are not listed because nothing
       updates them. They carry forward in the copy of last year's report, which is why
       no part of this system writes the certification.</div>`
    + '<div id="appendix-result"></div>';
}}

async function updateAppendix(id, dry) {{
  const field = $('src-' + id);
  const source = field ? field.value.trim() : '';
  const out = $('appendix-result');
  if (!source) {{
    out.innerHTML = '<div class="note tight bad">Point it at the Word document first.</div>';
    return;
  }}
  SOURCES[id] = source;
  out.innerHTML = '<div class="note tight">Reading both documents&hellip;</div>';
  let r;
  try {{
    r = await post('/api/admin/report/appendix/' + encodeURIComponent(id),
                   {{report: REPORT, source: source, dry_run: !!dry}});
  }} catch (e) {{
    out.innerHTML = `<div class="note tight bad">${{esc((e && e.detail) || 'That did not work.')}}</div>`;
    return;
  }}
  out.innerHTML =
    `<div class="r lede"><span class="lbl">Appendix ${{esc(r.letter)}}:
      ${{r.replaced_blocks}} block(s) out, ${{r.arriving_blocks}} in
      <span class="d">${{r.dry_run ? 'Nothing was written.' : 'Written to ' + esc(r.written_to)}}</span></span>
     <span class="pill ${{r.complete ? 'good' : 'bad'}}"><i class="dot"></i>${{
       r.complete ? (r.dry_run ? 'would work' : 'done') : 'something was left behind'}}</span></div>`
    + (r.left_behind.length
        ? r.left_behind.map(w => `<div class="r"><span class="lbl">Not carried
            <span class="d">${{esc(w)}}</span></span>
            <span class="pill bad"><i class="dot"></i>by hand</span></div>`).join('')
        : '')
    + ((r.styles.length || r.numbering.length || r.images.length)
        ? `<div class="note tight">Brought across with the text:
           ${{r.styles.length}} style(s), ${{r.numbering.length}} list(s), ${{r.images.length}} image(s).
           Without those it would open cleanly and be laid out wrong.</div>`
        : '');
}}

/* The DD tracker. His words: "it just reads what we asked for and what we received, and
   updates it whenever we get info from the client." The preview exists because the first
   thing anybody wants to know about a tool that writes into their workbook is what it is
   about to do to it. */
async function runTracker(id, dry) {{
  const box = $('tracker-result');
  if (!box) return;
  box.innerHTML = '<div class="note tight">Reading the folder&hellip;</div>';
  let r;
  try {{
    r = await post(`/api/admin/engagements/${{id}}/dd-tracker`, {{dry_run: !!dry}});
  }} catch (e) {{
    box.innerHTML = `<div class="note tight bad">${{esc((e && e.detail) || 'That did not work.')}}</div>`;
    return;
  }}
  const c = r.counts;
  box.innerHTML =
    `<div class="r lede"><span class="lbl">${{c.provided}} of ${{r.items.length}} provided,
      ${{c.outstanding}} still outstanding${{c.not_applicable ? ', ' + c.not_applicable + ' not applicable' : ''}}
      <span class="d">${{r.files_seen}} file(s) read. ${{r.inferred}} matched by reading the
       document rather than by its number &mdash; worth a glance.${{
        r.dry_run ? ' Nothing was written.' : ' Written to ' + esc(r.tracker) + '.'}}</span></span>
     <span class="pill ${{r.essential_outstanding.length ? 'warn' : 'good'}}"><i class="dot"></i>${{
       r.essential_outstanding.length ? r.essential_outstanding.length + ' essential owed' : 'nothing essential owed'}}</span></div>`
    + (r.is_a_starting_point
        ? `<div class="note tight">This list is a starting point, not the firm's own.
           Replace it with the real request list when there is one, and these numbers
           become something to act on rather than something to check.</div>`
        : '')
    + (r.essential_outstanding.length
        ? `<div class="r"><span class="lbl">Still needed before the model can start
            <span class="d">${{r.essential_outstanding.map(esc).join(', ')}}</span></span></div>`
        : '')
    + (r.unmatched_files.length
        ? `<div class="r"><span class="lbl">${{r.unmatched_files.length}} file(s) answered nothing
            <span class="d">${{r.unmatched_files.map(esc).join('<br>')}}</span></span>
           <span class="pill warn"><i class="dot"></i>look at these</span></div>`
        : '');
}}

/* ---------------------------------------------------------------- actions */
function initialise() {{
  act(() => post('/api/admin/initialise',
    {{who: who(), reason: 'first configuration for this environment'}}),
    'Environment set up.');
}}
/* Retiring is the only thing on this page that ends something, so it asks first. The
   route has existed since P24 and no button ever called it, which meant an engagement
   could be made and paused and never put away - and a roster nobody can tidy is one
   people stop reading. */
async function retire(id) {{
  const answer = await ask({{
    title: 'Retire ' + id,
    why: 'It stops being swept and no new run starts. Nothing already recorded is removed - '
      + 'the runs, decisions and manifests stay exactly as they are.',
    fields: [{{name: 'reason', label: 'Why', kind: 'textarea', required: true}}],
    ok: 'Retire it', danger: true,
  }});
  if (!answer) return;
  act(() => post(`/api/admin/engagements/${{id}}/archive`, {{who: who(), reason: answer.reason}}),
    id + ' retired.');
}}

function move(id, what) {{
  act(() => post(`/api/admin/engagements/${{id}}/${{what}}`,
    {{who: who(), reason: what + 'd from the setup page'}}),
    id + ' ' + what + 'd.');
}}
function showAdd() {{
  const opts = (list, value, label) => list.map(x => `<option value="${{esc(value(x))}}">${{esc(label(x))}}</option>`).join('');
  /* The practice group and "is this a repeat client" are one string in the scope path -
     valuation/non-esop/repeat - and two questions in somebody's head. Asked separately and
     joined on submit: the group comes from the registry without its disposition, and
     `addEngagement` puts the disposition back. Three quarters of the work turns on that
     last segment, and it was the last word of a control called Practice group, written as
     "non-repeat".

     Both lists are handed over by the console. The page never takes a scope path apart:
     which segment means which question is the registry's business, and a page that sliced
     the string would be a second place to be wrong about it. */
  const groups = SCOPES ? SCOPES.groups || [] : [];
  const kinds = SCOPES ? SCOPES.dispositions || [] : [];
  $('e_scope').innerHTML = opts(groups, p => p.group,
    p => (p.name || p.group) + (p.focus ? '  (focus)' : '') + (p.parked ? '  (parked)' : ''));
  /* The markup carries the two dispositions that exist, so the control is right before
     anything loads. The registry is still asked, so a third disposition added to
     scopes.yaml appears here instead of being silently unofferable - in the registry's
     own words if nobody has written a plainer one. */
  if (kinds.length) $('e_kind').innerHTML = opts(kinds, d => d.id, d => KIND_SAYS[d.id] || d.name);
  $('e_watch').innerHTML = opts(SETUP.watches || [], w => w.id, w => w.id + ' \\u2014 ' + (w.root || '/'));
  $('e_dest').innerHTML = opts(SETUP.destinations || [], d => d.id, d => d.id + ' \\u2014 ' + (d.name || d.path || ''));
  /* `CONFIGURED`, not `!SETUP`. Making SETUP an empty object rather than null fixed the
     page that threw on a fresh machine and silently killed this refusal in the same move,
     because an empty object is truthy - so the form would have opened on a machine with no
     configuration to save into. Any test for "has it been set up" is the flag, everywhere. */
  if (!CONFIGURED) {{
    return say('The environment has not been set up yet - do the first step on this page, '
      + 'then add an engagement.', 'bad');
  }}
  $('add-card').style.display = '';
  if ((SETUP.watches || []).length === 1) $('e_watch').value = SETUP.watches[0].id;
  folderHint();
  $('e_watch').addEventListener('change', folderHint);
  if ((SETUP.destinations || []).length === 1) $('e_dest').value = SETUP.destinations[0].id;
  /* Bound here rather than written on the elements: this page dispatches every control
     through ACTIONS, and a form that wired four of its own was two mechanisms for one job.
     Bound once - showAdd can be called again and addEventListener is idempotent for an
     identical listener only if the function is identical, so these are named. */
  $('e_client').addEventListener('input', suggest);
  $('e_id').addEventListener('input', wasTyped);
  $('e_folder').addEventListener('input', wasTyped);
  $('e_client').focus();
}}

/* A client name suggests an engagement id and a folder, until somebody types their own. */
function wasTyped(e) {{ e.currentTarget.dataset.typed = 1; }}
function suggest() {{
  const client = $('e_client').value.trim();
  const year = new Date().getFullYear();
  const letters = client.replace(/[^A-Za-z ]/g, '').split(/\\s+/).filter(Boolean)
    .filter(w => !/^(llc|inc|co|corp|company|the|group|ltd)$/i.test(w));
  const code = (letters.length > 1 ? letters.slice(0, 4).map(w => w[0]).join('') : (letters[0] || '').slice(0, 4))
    .toUpperCase().padEnd(4, 'X');
  if (!$('e_id').dataset.typed) $('e_id').value = client ? code + '-' + year + '-01' : '';
  if (!$('e_folder').dataset.typed) $('e_folder').value = client ? client.replace(/[\\\\/:*?"<>|]/g, '') + '/' + year + ' Valuation' : '';
}}
function hideAdd() {{ $('add-card').style.display = 'none'; }}

function addEngagement() {{
  const body = {{
    who: who(), reason: 'registered from the setup page',
    engagement_id: $('e_id').value.trim(), client: $('e_client').value.trim(),
    scope_path: $('e_scope').value + '/' + $('e_kind').value, watch_id: $('e_watch').value,
    destination_id: $('e_dest').value, folder: $('e_folder').value.trim(),
    template_pin: $('e_pin').value.trim(),
  }};
  if (!body.engagement_id || !body.client) return say('An engagement needs an id and a client.', 'bad');
  act(() => post('/api/admin/engagements', body).then(() => {{
      hideAdd();
      setTimeout(() => showFiles(body.engagement_id), 400);
    }}),
    'Registered ' + body.engagement_id + '. Add its files next; it stays paused until you activate it.');
}}


/* ---------------------------------------------------------------- files */
const size = n => n === null || n === undefined ? '' : n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(0) + ' KB' : (n / 1048576).toFixed(1) + ' MB';

async function showFiles(id) {{
  let f;
  try {{ f = await get(`/api/admin/engagements/${{id}}/files`); }}
  catch (e) {{ return say(e.text || String(e), 'bad', e.code); }}
  document.querySelectorAll('.modal.files').forEach(m => m.remove());
  const box = document.createElement('div');
  box.className = 'modal files';
  box.innerHTML = `<section class="card" role="dialog" aria-modal="true">
   <header><h2>Files &mdash; ${{esc(f.client || id)}}</h2>
    <p class="why">${{esc(id)}} &middot; ${{esc(f.state)}}. A run starts once files stop changing for ${{esc(f.quiet_period_minutes)}} minutes${{f.state === 'active' ? '' : ' - and only after the engagement is activated'}}.</p></header>
   <div class="body">
    <div class="section-label">Where they go</div>
    <div class="excerpt path">
     <span>${{esc(f.absolute || f.relative)}}</span>
     <button class="small" data-act="copyText" data-text="${{esc(f.absolute || f.relative)}}">Copy path</button></div>
    ${{f.can_add ? `<div id="drop" class="drop" tabindex="0">
      <b>Drop client files here</b>, or click to choose them.<br>
      <span class="sm">Statements, trial balances, forecasts - as the client sent them. Nothing is renamed or opened here; the sweep reads them.</span>
      <input type="file" id="pick" multiple style="display:none"></div>`
      : '<p class="note">Files can be added from this page only when storage is a local folder. Put them in the folder above.</p>'}}
    <div class="section-label">In the folder now (${{f.files.length}})</div>
    <div id="file-list">${{f.files.length ? f.files.map(x => `<div class="r"><span class="lbl">${{esc(x.path)}}</span>
       <span class="sub">${{esc(size(x.bytes))}}</span><span class="sub">${{esc(ago(x.modified))}}</span></div>`).join('')
      : '<div class="empty"><b>Nothing yet</b>The client&rsquo;s files will be listed here once they are in the folder.</div>'}}</div>
   </div>
    <div class="section-label">Due diligence request list</div>
    <div class="r lede">
     <span class="lbl">What was asked for, and what has come back
      <span class="d">Reads the folder above and refreshes the tracker beside it. Anything
       you have typed in it &mdash; notes, In Model?, Not Applicable &mdash; is left exactly
       where you put it.</span></span>
     <span><button class="small" data-act="previewTracker" data-id="${{esc(id)}}">What would change</button>
      <button data-act="updateTracker" data-id="${{esc(id)}}">Update</button></span>
    </div>
    <div id="tracker-result"></div>
   </div>
   <div class="foot"><span class="spacer">Every file added here is recorded against your name.</span>
    ${{f.state === 'paused' ? `<button data-act="activateFrom" data-id="${{esc(id)}}">Activate ${{esc(id)}}</button>` : ''}}
    <button class="primary" data-close>Done</button></div>
  </section>`;
  document.body.appendChild(box);
  const close = () => {{ box.remove(); document.removeEventListener('keydown', onKey); }};
  const onKey = e => {{ if (e.key === 'Escape') close(); }};
  document.addEventListener('keydown', onKey);
  box.addEventListener('click', e => {{ if (e.target === box || e.target.dataset.close !== undefined) close(); }});
  const drop = box.querySelector('#drop');
  if (drop) {{
    const pick = box.querySelector('#pick');
    drop.addEventListener('click', () => pick.click());
    drop.addEventListener('keydown', e => {{ if (e.key === 'Enter' || e.key === ' ') pick.click(); }});
    drop.addEventListener('dragover', e => {{ e.preventDefault(); drop.style.borderColor = 'var(--accent)'; drop.style.background = 'var(--accent-soft)'; }});
    drop.addEventListener('dragleave', () => {{ drop.style.borderColor = ''; drop.style.background = ''; }});
    drop.addEventListener('drop', e => {{ e.preventDefault(); drop.style.borderColor = ''; drop.style.background = ''; upload(id, e.dataTransfer.files); }});
    pick.addEventListener('change', () => upload(id, pick.files));
  }}
}}

async function upload(id, list) {{
  const files = Array.from(list || []);
  if (!files.length) return;
  let added = 0;
  for (const file of files) {{
    say('Adding ' + file.name + ' (' + size(file.size) + ')...');
    try {{
      const content = await new Promise((resolve, reject) => {{
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '');
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      }});
      const r = await post(`/api/admin/engagements/${{id}}/files`,
        {{name: file.name, content_base64: content, reason: 'client file added from the setup page'}});
      added += 1;
      if (r.replaced) say(file.name + ' replaced the file of the same name - the sweep will treat it as a new version.');
    }} catch (e) {{ say(file.name + ': ' + (e.text || String(e)), 'bad', e.code); }}
  }}
  if (added) say(plural(added, 'file', 'files') + ' added to ' + id + '.', 'good');
  showFiles(id);
}}

async function copyText(text) {{
  try {{ await navigator.clipboard.writeText(text); say('Copied.', 'good'); }}
  catch (e) {{ say('Copy it from the box: ' + text); }}
}}

/* ---------------------------------------------------------------- settings */
async function settings(id) {{
  const row = (SETUP.roster || []).find(r => r.engagement_id === id) || {{}};
  const quiet = (SETUP.intake || {{}}).quiet_period_minutes;
  const answer = await ask({{
    title: 'Settings for ' + (row.client || id),
    why: 'Each change is recorded with its reason. A budget cannot go above the firm ceiling, a review level can be raised but not lowered, and files can be held for less time than the environment allows, never more.',
    fields: [
      /* Says what it caps. It read "Spend limit per run" with the hint "This is per run,
         not per month", and harness/budget.py checks it against the engagement's spend
         across every run it has ever had - so fifty dollars set as a generous per-run
         allowance halts the third run at a ceiling nobody meant to set. */
      {{name: 'budget', label: 'Spend limit for this engagement (USD, all runs)', value: row.budget_usd ?? '',
        hint: 'What this engagement may cost in model calls in total, across every run it has - not per run. '
            + 'Without one, each run may cost up to the firm ceiling of $' + SETUP.firm_ceiling_usd
            + ' and nothing caps the total. Blank leaves it as it is.', required: false}},
      {{name: 'level', label: 'Review level', kind: 'select', value: row.review_level || 'standard',
        options: (SETUP.review_levels || ['standard', 'elevated']).map(v => ({{value: v, label: v}}))}},
      {{name: 'quiet', label: 'Quiet period - minutes files must stop changing before a run', value: '', placeholder: quiet ? 'environment default: ' + quiet : '', required: false}},
      ...(row.is_repeat ? [{{name: 'prior', label: 'Last year’s model', value: row.prior_model || '',
        hint: 'The workbook this year is rolled forward from. A file on this machine - a synced Box or OneDrive path, not a web link. Blank leaves it as it is.',
        required: false}}] : []),
      {{name: 'reason', label: 'Why', kind: 'textarea', required: true}},
    ],
    ok: 'Save settings',
  }});
  if (!answer) return;
  const jobs = [];
  if (String(answer.budget).trim() !== '' && Number(answer.budget) !== row.budget_usd)
    jobs.push(() => post(`/api/admin/engagements/${{id}}/budget`, {{who: who(), reason: answer.reason, usd: Number(answer.budget)}}));
  if (answer.prior !== undefined && String(answer.prior).trim() !== (row.prior_model || ''))
    jobs.push(() => post(`/api/admin/engagements/${{id}}/prior-model`, {{who: who(), reason: answer.reason, prior_model: String(answer.prior).trim()}}));
  if (answer.level && answer.level !== row.review_level)
    jobs.push(() => post(`/api/admin/engagements/${{id}}/review-level`, {{who: who(), reason: answer.reason, level: answer.level}}));
  if (String(answer.quiet).trim() !== '')
    jobs.push(() => post(`/api/admin/engagements/${{id}}/intake`, {{who: who(), reason: answer.reason, quiet_period_minutes: Number(answer.quiet)}}));
  if (!jobs.length) return say('Nothing changed.');
  act(async () => {{ for (const job of jobs) await job(); }}, 'Settings saved for ' + id + '.');
}}

/* ---------------------------------------------------------------- folders */
const slug = s => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 30);

async function addWatch() {{
  const r = await get('/api/admin/recipes').catch(() => ({{recipes: []}}));
  /* Two things can be wrong with a workflow and the label used to say only one. Not
     approved is a decision nobody has taken; not built is a skill nobody has written, and
     a run that picks one pays for every step before the gap and then stops. */
  const says = x => x.name
    + (x.state === 'registered' ? '' : '  (not approved)')
    + (x.can_finish === false ? '  — will stop at ' + (x.unbuilt || []).join(', ') : '');
  const recipes = (r.recipes || []).map(x => ({{value: x.name, label: says(x)}}));
  /* Default to one that can actually finish, rather than to a name written down here.
     The form used to prefer 'mature-company-valuation' by name - a recipe whose own test
     asserts it cannot finish - so the default path spent money and delivered nothing. */
  const finishable = (r.recipes || []).filter(x => x.can_finish !== false && x.state === 'registered');
  const preferred = (finishable[0] || (r.recipes || [])[0] || {{}}).name;
  const answer = await ask({{
    title: 'Which folder to watch',
    why: 'Where client files arrive. Most set-ups need one: a folder of client folders, one per engagement.'
      + (SETUP.inbox_root ? ' It is a folder under ' + SETUP.inbox_root + '.' : ''),
    fields: [
      {{name: 'name', label: 'Name', value: 'Clients', required: true}},
      {{name: 'root', label: 'Folder, under the inbox', value: 'Clients', hint: 'Leave blank to watch the inbox itself.', required: false}},
      {{name: 'kind', label: 'What is in it', kind: 'select', value: 'pattern', options: [
        {{value: 'pattern', label: 'A folder of client folders - one per engagement'}},
        {{value: 'bound', label: 'One engagement\u2019s files'}}]}},
      {{name: 'recipe', label: 'Workflow its engagements run unless they say otherwise', kind: 'select',
        value: preferred, options: recipes}},
      {{name: 'reason', label: 'Why', kind: 'textarea', required: true, value: 'where client files arrive'}},
    ],
    ok: 'Watch this folder',
  }});
  if (!answer) return;
  act(() => post('/api/admin/watches', {{who: who(), reason: answer.reason, id: 'w-' + (slug(answer.name) || 'clients'),
    kind: answer.kind, name: answer.name, root: answer.root.trim().replace(/^[\\\\/]+|[\\\\/]+$/g, ''), recipe: answer.recipe, depth: 2}}),
    'Watching ' + (answer.root || 'the inbox') + '.');
}}

async function addDestination() {{
  const answer = await ask({{
    title: 'Where deliverables go',
    why: 'The folder a finished workbook is written to, once, when a run is released.'
      + (SETUP.outbox_root ? ' It is a folder under ' + SETUP.outbox_root + '.' : ''),
    fields: [
      {{name: 'name', label: 'Name', value: 'Deliverables', required: true}},
      {{name: 'path', label: 'Folder, under the outbox', value: 'Deliverables', required: false}},
      {{name: 'reason', label: 'Why', kind: 'textarea', required: true, value: 'where finished models are written'}},
    ],
    ok: 'Use this folder',
  }});
  if (!answer) return;
  act(() => post('/api/admin/destinations', {{who: who(), reason: answer.reason, id: 'd-' + (slug(answer.name) || 'out'),
    name: answer.name, path: answer.path.trim().replace(/^[\\\\/]+|[\\\\/]+$/g, ''), adapter: 'local_folder'}}),
    'Deliverables go to ' + (answer.path || 'the outbox') + '.');
}}

async function clearFile(name) {{
  let text = '';
  try {{ text = (await get(`/api/admin/methodology/${{name}}/text`)).text; }}
  catch (e) {{ return say(e.text || String(e), 'bad', e.code); }}
  const answer = await ask({{
    title: 'Clear ' + name,
    body: text,
    why: 'Clearing records, under your name, that you read this file and it is fit to reach every model call for every client in its practice group.',
    note: 'The file is scanned for client names and for anything that reads like an instruction to a model before it is cleared. Editing it afterwards un-clears it.',
    ok: 'I have read it - clear it',
  }});
  if (!answer) return;
  act(() => post(`/api/admin/methodology/${{name}}/clear`, {{who: who()}}), 'Cleared ' + name + '.');
}}

async function approveRecipe(name, state) {{
  const edited = state === 'edited';
  const answer = await ask({{
    title: (edited ? 'Re-approve ' : 'Approve ') + name,
    why: edited
      ? 'This workflow was approved and the file has been edited since, so it stopped being approved on its own. Approving records that you read what it says now.'
      : 'Approving records, under your name, that these steps in this order are what the practice does. Until one is approved no engagement can run it.',
    note: 'The approval is of this exact file. Editing it afterwards un-approves it, the same way editing a cleared methodology file un-clears it.',
    fields: [{{name: 'reason', label: 'Why this workflow is right', required: true}}],
    ok: edited ? 'I have read it - re-approve it' : 'I have read it - approve it',
  }});
  if (!answer) return;
  act(() => post(`/api/admin/recipes/${{encodeURIComponent(name)}}/approve`,
      {{who: who(), reason: answer.reason}}),
    'Approved ' + name + '.');
}}

async function setRecipe(id, current) {{
  const r = await get('/api/admin/recipes').catch(() => ({{recipes: []}}));
  const options = [{{value: '', label: 'The watched folder\u2019s default'}}].concat(
    (r.recipes || []).map(x => ({{
      value: x.name,
      label: x.name + (x.state === 'registered' ? '' : x.state === 'edited' ? '  (edited since approval - will not run)' : '  (not approved - will not run)'),
    }})));
  const answer = await ask({{
    title: 'Workflow for ' + id,
    why: 'The order the work happens in. Only a workflow the board approved runs on client work; choosing one that is not approved is allowed, and preflight will say so.',
    fields: [
      {{name: 'recipe', label: 'Workflow', kind: 'select', options, value: current || '', required: false}},
      {{name: 'reason', label: 'Why', kind: 'textarea', required: true, placeholder: 'e.g. mature operating company - the pilot workflow'}},
    ],
    ok: 'Set workflow',
  }});
  if (!answer) return;
  const chosen = answer.recipe.trim();
  act(() => post(`/api/admin/engagements/${{id}}/recipe`,
    {{who: who(), reason: answer.reason, recipe: chosen}}),
    chosen ? id + ' runs ' + chosen + '.' : id + ' uses the default workflow.');
}}

/* The engagement profile, as a form. What the system fills in itself - the schema, the
   engagement and its scope, who recorded it and when - is shown and not editable; the rest
   are fields, grouped as the profile groups them. The JSON stays one click away for
   anything the form does not cover. */
const PROFILE_FIXED = new Set(['schema_version', 'engagement_id', 'practice', 'segment',
  'disposition', 'recorded_by', 'recorded_at']);
const PROFILE_LABEL = {{
  industry_classification: 'Industry', size_band: 'Size band', fiscal_calendar: 'Fiscal calendar',
  scale_convention: 'Our working papers are kept in',
  statements_arrive_in: "The client's statements arrive in",
  owner_compensation_baseline: 'Owner compensation benchmark',
  materiality_threshold: 'Materiality threshold', checkpoint_policy: 'Review policy',
  auto_accept_confidence: 'Auto-accept at confidence', sla_hours: 'Answer within (hours)',
  always_review_categories: 'Always review these categories', year_end_month: 'Year-end month',
  year_end_day: 'Year-end day',
}};
const labelFor = k => PROFILE_LABEL[k] || k.replace(/_/g, ' ');
const kindOf = v => Array.isArray(v) ? 'list' : typeof v === 'number' ? 'number'
  : typeof v === 'boolean' ? 'boolean' : v === null ? 'text' : typeof v === 'object' ? 'object' : 'text';

/* Two scale questions sit next to each other and they are not the same question, so
   both are pick-lists rather than number boxes and both say which one they are. The
   arrival scale has a blank option and the working-paper convention does not: the firm
   always has a convention, and what the client sent is a fact that may not be known yet.
   Blank is sent as null and the store drops it, so "not stated" survives a save. */
/* A line under the two groups whose numbers mean the opposite of what a number usually
   means here: both of them get stricter as they get smaller, and one of them has a
   perfectly ordinary-looking `0` in it on a complete profile.

   Seen on a real engagement: **Materiality threshold · Amount · 0**, with no help text on
   the group and "Complete" at the top of the form. Nothing tells a reader that 0 is the
   strictest setting rather than an unfilled box, and the cost of guessing wrong is either
   a reviewer asked about everything or a reviewer asked about nothing.

   Said in the direction a person decides in - what happens if I raise it - rather than as
   a definition of the field. */
const GROUP_NOTE = {{
  materiality_threshold:
    'Anything above this goes to a person whatever its confidence. <b>0 means nothing is '
    + 'immaterial</b> - every item is shown. Raising it shows fewer, and the firm floor in '
    + 'the Constraint Registry is as high as it may go.',
  checkpoint_policy:
    'This can only ask for <b>more</b> review than the skills do, never less: a floor below '
    + 'what a skill declares is refused, and a policy that sets no auto-accept '
    + 'auto-accepts nothing.',
}};

const SCALES = [[1, 'units (as stated)'], [1000, 'thousands'], [1000000, 'millions']];
const SCALE_FIELDS = {{
  scale_convention: {{blank: null, note: 'How this firm presents its own work.'}},
  statements_arrive_in: {{blank: 'not stated — read it off the page',
    note: 'What the client sent. Leave it blank unless you know; a cue on the page always wins.'}},
}};

function profileField(path, key, value) {{
  const kind = kindOf(value);
  const scale = SCALE_FIELDS[key];
  if (scale) {{
    const options = (scale.blank ? [['', scale.blank]] : []).concat(SCALES);
    return `<div class="field"><label>${{esc(labelFor(key))}}</label>
      <select class="pf" data-path="${{esc(path)}}" data-kind="number">${{options.map(([v, l]) =>
        `<option value="${{v}}"${{String(value == null ? '' : value) === String(v) ? ' selected' : ''}}>${{esc(l)}}</option>`).join('')}}</select>
      <p class="hint">${{esc(scale.note)}}</p></div>`;
  }}
  const shown = kind === 'list' ? value.join(', ') : value === null || value === undefined ? '' : value;
  return `<div class="field"><label>${{esc(labelFor(key))}}</label>
    <input class="pf" data-path="${{esc(path)}}" data-kind="${{kind}}" value="${{esc(shown)}}"
     ${{kind === 'number' ? 'inputmode="decimal"' : ''}} ${{kind === 'list' ? 'placeholder="comma separated"' : ''}}></div>`;
}}

function profileForm(profile) {{
  const fixed = Object.entries(profile).filter(([k]) => PROFILE_FIXED.has(k));
  const loose = Object.entries(profile).filter(([k, v]) => !PROFILE_FIXED.has(k) && kindOf(v) !== 'object');
  const groups = Object.entries(profile).filter(([k, v]) => !PROFILE_FIXED.has(k) && kindOf(v) === 'object');
  const f = Object.fromEntries(fixed);
  return `<p class="note" style="margin:0 0 var(--s3)"><span class="mono">${{esc([f.practice, f.segment, f.disposition].filter(Boolean).join('/'))}}</span>
     &middot; ${{esc(f.schema_version || '')}}${{f.recorded_by ? ' &middot; last recorded by ' + esc(f.recorded_by) + (f.recorded_at ? ' on ' + esc(String(f.recorded_at).slice(0, 10)) : '') : ''}}</p>
    ${{loose.map(([k, v]) => profileField(k, k, v)).join('')}}
    ${{groups.map(([k, v]) => `<div class="section-label">${{esc(labelFor(k))}}</div>
      ${{GROUP_NOTE[k] ? `<p class="section-note">${{GROUP_NOTE[k]}}</p>` : ''}}
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(12rem,1fr));gap:0 var(--s4)">
       ${{Object.entries(v).map(([ck, cv]) => kindOf(cv) === 'object'
          ? `<div class="field"><label>${{esc(labelFor(ck))}}</label><textarea class="pf" data-path="${{esc(k + '.' + ck)}}" data-kind="json" rows="2">${{esc(JSON.stringify(cv))}}</textarea></div>`
          : profileField(k + '.' + ck, ck, cv)).join('')}}
      </div>`).join('')}}`;
}}

function readProfileForm(base) {{
  const out = JSON.parse(JSON.stringify(base));
  for (const input of document.querySelectorAll('.pf')) {{
    const parts = input.dataset.path.split('.');
    let at = out;
    for (const part of parts.slice(0, -1)) at = at[part];
    const raw = input.value.trim(), last = parts[parts.length - 1];
    const kind = input.dataset.kind;
    if (kind === 'number') {{
      if (raw === '') at[last] = null;
      else if (isNaN(Number(raw))) throw new Error(labelFor(last) + ' should be a number');
      else at[last] = Number(raw);
    }} else if (kind === 'list') {{
      at[last] = raw ? raw.split(',').map(x => x.trim()).filter(Boolean) : [];
    }} else if (kind === 'boolean') {{
      at[last] = raw === 'true';
    }} else if (kind === 'json') {{
      at[last] = JSON.parse(raw || 'null');
    }} else {{
      at[last] = raw === '' && at[last] === null ? null : raw;
    }}
  }}
  return out;
}}

async function editProfile(id) {{
  let t;
  try {{ t = await get(`/api/admin/engagements/${{id}}/profile/template`); }}
  catch (e) {{ return say(e.text || String(e), 'bad', e.code); }}
  const box = document.createElement('div');
  box.className = 'modal';
  box.innerHTML = `<section class="card"><header><h2>Engagement profile &mdash; ${{esc(id)}}</h2>
    <p class="why">${{t.gaps.length
      ? '<b style="color:var(--bad)">Still missing:</b> ' + t.gaps.map(esc).join('; ')
      : 'Complete. Saving writes a new version; the old one stays on the record.'}}</p></header>
   <div class="body">
    <p class="note" style="margin-top:0">Everything the system already knows is filled in.
     The blanks are judgements: the industry code, the size band, the owner-compensation
     benchmark, and who reviews this engagement and how quickly.</p>
    <div id="p_form">${{profileForm(t.profile)}}</div>
    <details style="margin-top:var(--s3)"><summary>Edit as JSON instead</summary>
     <p class="note" style="margin:var(--s1) 0">When this is open, the JSON is what is saved.</p>
     <textarea id="p_body" class="code-area">${{esc(JSON.stringify(t.profile, null, 2))}}</textarea>
    </details>
   </div>
   <div class="foot"><button class="quiet" data-act="closeModal">Cancel</button>
    <button class="primary" id="p_save">Save profile</button></div></section>`;
  document.body.appendChild(box);
  const onKey = e => {{ if (e.key === 'Escape' && document.body.contains(box) && !document.querySelector('.modal .narrow')) {{ box.remove(); document.removeEventListener('keydown', onKey); }} }};
  document.addEventListener('keydown', onKey);
  $('p_save').addEventListener('click', () => saveProfile(id, t.profile, box));
  const first = box.querySelector('.pf');
  if (first) first.focus();
}}
async function saveProfile(id, base, box) {{
  let body;
  try {{
    body = box.querySelector('details').open ? JSON.parse($('p_body').value) : readProfileForm(base);
  }} catch (e) {{ return say('Not saved: ' + (e.message || e), 'bad'); }}
  const answer = await ask({{
    title: 'Save the profile for ' + id,
    fields: [{{name: 'reason', label: 'Why', kind: 'textarea', required: true,
      value: 'profile completed from the setup page'}}],
    ok: 'Save',
  }});
  if (!answer) return;
  act(() => post(`/api/admin/engagements/${{id}}/profile`,
    {{who: who(), reason: answer.reason, profile: body}}).then(() => box.remove()),
    'Profile saved for ' + id + '.');
}}

/* A link to a piece of setup opens it, so the person who owns a missing judgement can be
   sent straight to it rather than told where to look.

   One table, because the two halves had drifted: the page handed out `#settings=` and the
   router did not know it, so that link worked when clicked - it carries `data-act` as well -
   and did nothing when pasted or reloaded, which is the only reason a link has a URL. And
   the router knew `#files=` while nothing linked to it. A test now asserts the two sides are
   the same set, in both directions. */
const DEEP_LINKS = {{
  'profile=': editProfile,
  'settings=': settings,
  'files=': showFiles,
}};
refresh().then(() => {{
  const wanted = decodeURIComponent(location.hash.slice(1));
  for (const [prefix, open] of Object.entries(DEEP_LINKS)) {{
    if (wanted.startsWith(prefix)) return open(wanted.slice(prefix.length));
  }}
}});
</script>
"""
