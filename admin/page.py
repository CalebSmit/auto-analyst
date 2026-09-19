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
.board{{grid-template-columns:minmax(0,1.05fr) minmax(0,1fr) minmax(0,.9fr);
 grid-template-rows:repeat(6,minmax(0,1fr));
 grid-template-areas:"steps pre scopes" "steps pre scopes" "steps pre recipes"
  "eng meth recipes" "eng meth seams" "eng meth seams"}}
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
    <p class="why">Seven steps, in order. Each is checked against the live configuration, so
     this cannot tell you something is done when it is not.</p></header>
   <div class="body"><div id="checklist"><div class="skel"></div><div class="skel"></div></div></div>
  </section>

  <section class="card" style="grid-area:eng">
   <header><h2>Engagements<span class="of" id="n-roster"></span></h2>
    <p class="why">One per piece of client work. The practice group you give it decides
     which skills it gets, which methodology it carries and which model it builds into.</p></header>
   <div class="body"><div id="roster"><div class="skel"></div></div></div>
   <div class="foot">
    <button onclick="showAdd()">Add an engagement</button>
    <span class="note" style="margin:0">It starts paused. Nothing is read until you activate it.</span>
   </div>
  </section>

  <section class="card" style="grid-area:pre">
   <header><h2>Preflight</h2>
    <p class="why">Fourteen checks over the live configuration. A setup mistake found here
     is one that does not stop a run at three in the afternoon.</p></header>
   <div class="body"><div id="pre"><div class="skel"></div></div></div>
   <div class="foot"><button onclick="refresh()">Run again</button></div>
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

  <section class="card" style="grid-area:seams">
   <header><h2>What is wired</h2>
    <p class="why">Derived from the code, not from this sentence.</p></header>
   <div class="body"><div id="seams"><div class="skel"></div></div></div>
  </section>
 </div>
</div>

<div class="modal" id="add-card" style="display:none">
 <section class="card">
  <header><h2>New engagement</h2>
   <p class="why">Start with the client; the id and folder are suggested from it and can be changed.</p></header>
  <div class="body">
   <div class="cols two" style="gap:0 1rem">
    <div>
     <label for="e_client">Client</label>
     <input id="e_client" placeholder="Henderson Manufacturing" oninput="suggest()">
     <label for="e_id">Engagement id</label>
     <input id="e_id" placeholder="HEND-2026-01" oninput="this.dataset.typed=1">
     <label for="e_scope">Practice group</label>
     <select id="e_scope" style="width:100%;margin-bottom:.55rem"></select>
     <label for="e_kind">Is this a repeat client?</label>
     <select id="e_kind" style="width:100%;margin-bottom:.55rem">
      <option value="repeat">Repeat &mdash; we valued them before, and last year&rsquo;s model exists</option>
      <option value="non-repeat">New &mdash; first time we have valued this client</option>
     </select>
     <div class="sub">Three quarters of our work is repeat. It decides what last year&rsquo;s
      workbook is used for, and what the run may look at from previous years.</div>
    </div>
    <div>
     <label for="e_watch">Watched folder</label>
     <select id="e_watch" style="width:100%;margin-bottom:.55rem"></select>
     <label for="e_dest">Deliverables go to</label>
     <select id="e_dest" style="width:100%;margin-bottom:.55rem"></select>
     <label for="e_folder">Their folder, under the watch root</label>
     <input id="e_folder" placeholder="Henderson Manufacturing/2026 Valuation" oninput="this.dataset.typed=1">
    </div>
   </div>
   <label for="e_pin">Excel model template <span style="color:var(--ink-4);text-transform:none;letter-spacing:0">&mdash; optional, not the AI model</span></label>
   <input id="e_pin" placeholder="Leave blank to use the practice group&rsquo;s default">
  </div>
  <div class="foot">
   <button class="primary" onclick="addEngagement()">Register</button>
   <button class="quiet" onclick="hideAdd()">Cancel</button>
  </div>
 </section>
</div>
<div id="toast"></div>
{SHELL}
<script>
let SETUP = null, SCOPES = null, METH = {{files: []}}, ME = null;

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
  const configured = !!SETUP;
  const watches = configured ? (SETUP.watches || []).length : 0;
  const dests = configured ? (SETUP.destinations || []).length : 0;
  const roster = configured ? (SETUP.roster || []) : [];
  const files = METH.files || [];
  const cleared = files.length > 0 && files.every(f => f.state === 'cleared');
  const active = roster.filter(r => r.state === 'active').length;

  const steps = [
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
  const next = steps.findIndex(s => !s.done);
  const done = steps.filter(s => s.done).length;

  $('checklist').innerHTML =
    `<div class="r" style="border:0;padding:0 0 12px">
      <span class="lbl"><b>${{done}} of ${{steps.length}} done</b></span>
      <span class="sub">${{next === -1 ? 'Ready to run' : 'Next: ' + esc(steps[next].t.toLowerCase())}}</span>
     </div>
     <div class="bar ${{next === -1 ? 'good' : ''}}" style="margin-bottom:14px">
      <i style="width:${{(done / steps.length * 100).toFixed(0)}}%"></i></div>
     <div class="steps">` +
    steps.map((s, i) => `<div class="step ${{s.done ? 'done' : ''}} ${{i === next ? 'now' : ''}}">
       <span class="mark">${{s.done ? '&#10003;' : i + 1}}</span>
       <span><span class="t">${{esc(s.t)}}</span><span class="d">${{esc(s.d)}}</span></span>
       ${{s.go && i === next ? `<span class="go"><button class="primary" data-act="${{esc(s.go[1])}}"${{data(s.go[2])}}>${{esc(s.go[0])}}</button></span>` : ''}}
      </div>`).join('') + '</div>';
}}

/* What a button does, by name. The values ride in data attributes: an engagement id, a
   client's folder and a methodology filename are all free text, and none of them is
   allowed to become script. */
ACTIONS.initialise = () => initialise();
ACTIONS.addWatch = () => addWatch();
ACTIONS.addDestination = () => addDestination();
ACTIONS.showAdd = () => showAdd();
ACTIONS.clearFile = d => clearFile(d.name);
ACTIONS.approveRecipe = d => approveRecipe(d.name, d.state);
ACTIONS.move = d => move(d.id, d.to);
ACTIONS.retire = d => retire(d.id);
ACTIONS.showFiles = d => showFiles(d.id);
ACTIONS.settings = d => settings(d.id);
ACTIONS.setRecipe = d => setRecipe(d.id, d.recipe);
ACTIONS.editProfile = d => editProfile(d.id);
ACTIONS.copyText = d => copyText(d.text);
ACTIONS.activateFrom = (d, el) => {{ el.closest('.modal').remove(); move(d.id, 'activate'); }};

/* ---------------------------------------------------------------- panels */
async function refresh() {{
  try {{
    SETUP = await get('/api/admin/setup');
    online();
  }} catch (e) {{
    // A machine nobody has configured yet answers with a refusal, and that is not the same
    // as a server nobody can reach: the first is this page's whole purpose, the second
    // means nothing below can be trusted.
    SETUP = null;
    if (!e || !e.code) offline(e);
  }}

  ME = await get('/api/admin/whoami').catch(() => null);
  $('chrome-right').innerHTML =
    (SETUP ? esc(SETUP.environment) + ' &middot; configuration v' + esc(SETUP.version)
           : '<span class="pill warn"><i class="dot"></i>not set up</span>') +
    (ME ? ' &middot; <span title="Every change is recorded against this name. It is who the '
        + 'system resolved you as, not something typed here.">acting as <b>'
        + esc(ME.name) + '</b></span>' : '');

  METH = await get('/api/admin/methodology').catch(() => ({{files: []}}));
  checklist();
  roster();
  preflight();
  scopes();
  methodology();
  workflows();
  seams();
}}

function roster() {{
  const rows = SETUP ? (SETUP.roster || []) : [];
  const n = $('n-roster');
  if (n) n.textContent = rows.length ? String(rows.length) : '';
  $('roster').innerHTML = rows.length ? rows.map(r => `<div class="r engagement">
     <span class="lbl"><b>${{esc(r.client || r.engagement_id)}}</b><br>
      <span class="sub" style="white-space:normal">${{esc(r.engagement_id)}} &middot; ${{esc(r.scope_path)}} &middot; ${{r.recipe ? esc(r.recipe) : 'default workflow'}}</span>
      ${{(r.profile_gaps || []).length ? `<span class="why-line"><a href="#profile=${{esc(r.engagement_id)}}" data-act="editProfile" data-id="${{esc(r.engagement_id)}}" style="color:var(--warn)" title="${{esc(r.profile_gaps.join('; '))}}">profile: ${{esc(r.profile_gaps.length === 1 ? r.profile_gaps[0] : r.profile_gaps.length + ' things missing')}}</a></span>` : ''}}
      ${{r.is_repeat && !r.prior_model ? `<span class="why-line"><a href="#settings=${{esc(r.engagement_id)}}" data-act="settings" data-id="${{esc(r.engagement_id)}}" style="color:var(--warn)" title="A repeat client's work starts from last year's workbook. Until this is set there is nothing to roll forward from.">last year&rsquo;s model: not set</a></span>` : ''}}</span>
     <span class="pill ${{r.state === 'active' ? 'good' : ''}}"><i class="dot"></i>${{esc(r.state)}}</span>
     <span class="acts">
      <button class="quiet" data-act="showFiles" data-id="${{esc(r.engagement_id)}}" title="Where this engagement's files go, what is there, and adding more">files</button>
      <button class="quiet" data-act="settings" data-id="${{esc(r.engagement_id)}}" title="Budget, review level and how long files are held before a run">settings</button>
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

  $('pre').innerHTML =
    `<div class="r" style="border:0;padding:0 0 10px">
      <span class="lbl"><span class="pill ${{p.passed ? 'good' : 'bad'}}"><i class="dot"></i>${{p.passed ? 'All clear' : plural(blocking.length, 'blocker', 'blockers')}}</span></span>
      <span class="sub">${{p.checks.length}} checks${{warnings.length ? ' &middot; ' + plural(warnings.length, 'warning', 'warnings') : ''}}</span>
     </div>` +
    (shown.length
      ? shown.map(f => `<div class="r">
          <span class="lbl"><b>${{esc(f.detail)}}</b>
           <span class="d">${{esc(f.what_now || '')}}</span></span>
          <span class="pill ${{f.severity === 'fail' ? 'bad' : 'warn'}}">${{f.severity === 'fail' ? 'blocks' : 'warning'}}</span>
         </div>`).join('')
      : '<div class="empty"><b>Nothing is in the way</b>Every check passed against the live configuration.</div>') +
    `<details style="margin-top:10px"><summary>All ${{p.checks.length}} checks</summary>` +
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
  $('scopes').innerHTML =
    '<div class="r head"><span class="lbl">Practice group</span><span class="sub">Skills</span></div>' +
    SCOPES.paths.map(p => `<div class="r"><span class="lbl mono">${{esc(p.scope_path)}}</span>
      <span class="sub">${{p.skills}}</span>
      ${{p.focus ? '<span class="pill good">focus</span>' : ''}}${{p.parked ? '<span class="pill">parked</span>' : ''}}
      ${{p.firm_layer_only ? '<span class="pill warn">firm layer only</span>' : '<span class="pill good">defined</span>'}}
      </div>`).join('') +
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

async function workflows() {{
  const r = await get('/api/admin/recipes').catch(() => ({{recipes: []}}));
  $('recipes').innerHTML = (r.recipes || []).length ? r.recipes.map(x => `<div class="r">
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
      <span class="pill ${{ai.reaches_a_model ? 'good' : ''}}"><i class="dot"></i>${{ai.reaches_a_model ? 'live' : 'no spend'}}</span>
     </div>` : '')
    + r.seams.map(s => `<div class="r">
     <span class="lbl">${{esc(s.name)}}<span class="d">${{esc(s.detail)}}</span></span>
     <span class="pill ${{s.ready ? 'good' : (s.needs_installing ? 'warn' : 'bad')}}"><i class="dot"></i>${{
       s.ready ? 'wired' : (s.needs_installing ? 'not installed' : 'not wired')}}</span>
    </div>`).join('');
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
  $('e_watch').innerHTML = opts(SETUP ? SETUP.watches || [] : [], w => w.id, w => w.id + ' \\u2014 ' + (w.root || '/'));
  $('e_dest').innerHTML = opts(SETUP ? SETUP.destinations || [] : [], d => d.id, d => d.id + ' \\u2014 ' + (d.name || d.path || ''));
  if (!SETUP) {{
    return say('The environment has not been set up yet - do the first step on this page, '
      + 'then add an engagement.', 'bad');
  }}
  $('add-card').style.display = '';
  if ((SETUP.watches || []).length === 1) $('e_watch').value = SETUP.watches[0].id;
  if ((SETUP.destinations || []).length === 1) $('e_dest').value = SETUP.destinations[0].id;
  $('e_client').focus();
}}

/* A client name suggests an engagement id and a folder, until somebody types their own. */
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
    <div class="excerpt" style="display:flex;gap:.6rem;align-items:center;box-shadow:inset 3px 0 0 var(--gold)">
     <span style="flex:1;min-width:0;overflow-wrap:anywhere">${{esc(f.absolute || f.relative)}}</span>
     <button class="small" data-act="copyText" data-text="${{esc(f.absolute || f.relative)}}">Copy path</button></div>
    ${{f.can_add ? `<div id="drop" tabindex="0" style="border:2px dashed var(--line);border-radius:var(--radius);padding:1.1rem;text-align:center;color:var(--ink-3);margin:.2rem 0 .8rem;cursor:pointer">
      <b style="color:var(--navy);font-weight:600">Drop client files here</b>, or click to choose them.<br>
      <span style="font-size:.84rem">Statements, trial balances, forecasts - as the client sent them. Nothing is renamed or opened here; the sweep reads them.</span>
      <input type="file" id="pick" multiple style="display:none"></div>`
      : '<p class="note">Files can be added from this page only when storage is a local folder. Put them in the folder above.</p>'}}
    <div class="section-label">In the folder now (${{f.files.length}})</div>
    <div id="file-list">${{f.files.length ? f.files.map(x => `<div class="r"><span class="lbl">${{esc(x.path)}}</span>
       <span class="sub">${{esc(size(x.bytes))}}</span><span class="sub">${{esc(ago(x.modified))}}</span></div>`).join('')
      : '<div class="empty"><b>Nothing yet</b>The client&rsquo;s files will be listed here once they are in the folder.</div>'}}</div>
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
      {{name: 'budget', label: 'Spend limit per run (USD)', value: row.budget_usd ?? '', hint: 'What one run of this engagement may cost in model calls. Firm ceiling: $' + SETUP.firm_ceiling_usd + '. This is per run, not per month. Blank leaves it as it is.', required: false}},
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
  const recipes = (r.recipes || []).map(x => ({{value: x.name, label: x.name + (x.state === 'registered' ? '' : '  (not approved)')}}));
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
        value: recipes.some(x => x.value === 'mature-company-valuation') ? 'mature-company-valuation' : (recipes[0] || {{}}).value, options: recipes}},
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
  scale_convention: 'Figures are stated in units of', owner_compensation_baseline: 'Owner compensation benchmark',
  materiality_threshold: 'Materiality threshold', checkpoint_policy: 'Review policy',
  auto_accept_confidence: 'Auto-accept at confidence', sla_hours: 'Answer within (hours)',
  always_review_categories: 'Always review these categories', year_end_month: 'Year-end month',
  year_end_day: 'Year-end day',
}};
const labelFor = k => PROFILE_LABEL[k] || k.replace(/_/g, ' ');
const kindOf = v => Array.isArray(v) ? 'list' : typeof v === 'number' ? 'number'
  : typeof v === 'boolean' ? 'boolean' : v === null ? 'text' : typeof v === 'object' ? 'object' : 'text';

function profileField(path, key, value) {{
  const kind = kindOf(value);
  if (key === 'scale_convention') {{
    const choices = [[1, 'units (as stated)'], [1000, 'thousands'], [1000000, 'millions']];
    return `<div class="field"><label>${{esc(labelFor(key))}}</label>
      <select class="pf" data-path="${{esc(path)}}" data-kind="number">${{choices.map(([v, l]) =>
        `<option value="${{v}}"${{Number(value) === v ? ' selected' : ''}}>${{l}}</option>`).join('')}}</select></div>`;
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
  return `<p class="note" style="margin:0 0 .8rem"><span class="mono">${{esc([f.practice, f.segment, f.disposition].filter(Boolean).join('/'))}}</span>
     &middot; ${{esc(f.schema_version || '')}}${{f.recorded_by ? ' &middot; last recorded by ' + esc(f.recorded_by) + (f.recorded_at ? ' on ' + esc(String(f.recorded_at).slice(0, 10)) : '') : ''}}</p>
    ${{loose.map(([k, v]) => profileField(k, k, v)).join('')}}
    ${{groups.map(([k, v]) => `<div class="section-label">${{esc(labelFor(k))}}</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(12rem,1fr));gap:0 .8rem">
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
    <details style="margin-top:.6rem"><summary>Edit as JSON instead</summary>
     <p class="note" style="margin:.2rem 0 .4rem">When this is open, the JSON is what is saved.</p>
     <textarea id="p_body" style="height:min(20rem,40vh);font-family:var(--mono);font-size:.86rem">${{esc(JSON.stringify(t.profile, null, 2))}}</textarea>
    </details>
   </div>
   <div class="foot"><button class="quiet" onclick="this.closest('.modal').remove()">Cancel</button>
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

/* A link to a piece of setup opens it: #profile=ENGAGEMENT for its profile, so the person who
   owns the missing judgements can be sent straight to them. */
refresh().then(() => {{
  const wanted = decodeURIComponent(location.hash.slice(1));
  if (wanted.startsWith('profile=')) editProfile(wanted.slice(8));
  if (wanted.startsWith('files=')) showFiles(wanted.slice(6));
}});
</script>
"""
