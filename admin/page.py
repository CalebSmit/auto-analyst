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
<style>{CSS}</style>
{shell("Setup", "/admin")}
<div class="wrap">
 <div class="page-head">
  <h1>Setup</h1>
  <p>Everything the system needs before it can look at a client&rsquo;s files. Every change
   here is recorded against it &mdash; against whoever the system resolved you as, with the
   reason given.</p>
 </div>

 <div class="cols side">
  <div>
   <section class="card">
    <header><h2>Getting set up</h2>
     <p class="why">Six steps, in order. Each is checked against the live configuration, so
      this cannot tell you something is done when it is not.</p></header>
    <div class="body"><div id="checklist"><div class="skel"></div><div class="skel"></div></div></div>
   </section>

   <section class="card">
    <header><h2>Engagements</h2>
     <p class="why">One per piece of client work. The practice group you give it decides
      which skills it gets, which methodology it carries and which model it builds into.</p></header>
    <div class="body"><div id="roster"><div class="skel"></div></div></div>
    <div class="foot">
     <button onclick="showAdd()">Add an engagement</button>
     <span class="note" style="margin:0">It starts paused. Nothing is read until you activate it.</span>
    </div>
   </section>

   <section class="card" id="add-card" style="display:none">
    <header><h2>New engagement</h2>
     <p class="why">The seven things the system cannot work out for itself.</p></header>
    <div class="body">
     <div class="cols two" style="gap:0 16px">
      <div>
       <label for="e_id">Engagement id</label>
       <input id="e_id" placeholder="HEND-2026-04">
       <label for="e_client">Client</label>
       <input id="e_client" placeholder="Henderson Manufacturing">
       <label for="e_scope">Practice group</label>
       <select id="e_scope" style="width:100%;margin-bottom:8px"></select>
      </div>
      <div>
       <label for="e_watch">Watched folder</label>
       <select id="e_watch" style="width:100%;margin-bottom:8px"></select>
       <label for="e_dest">Deliverables go to</label>
       <select id="e_dest" style="width:100%;margin-bottom:8px"></select>
       <label for="e_folder">Their folder, under the watch root</label>
       <input id="e_folder" placeholder="Henderson Manufacturing/2026 ESOP">
      </div>
     </div>
     <label for="e_pin">Model template <span style="color:var(--ink-4)">&mdash; optional</span></label>
     <input id="e_pin" placeholder="Leave blank to use the practice group&rsquo;s default">
    </div>
    <div class="foot">
     <button class="primary" onclick="addEngagement()">Register</button>
     <button class="quiet" onclick="hideAdd()">Cancel</button>
    </div>
   </section>
  </div>

  <div>
   <section class="card">
    <header><h2>Preflight</h2>
     <p class="why">Thirteen checks over the live configuration. A setup mistake found here
      is one that does not stop a run at three in the afternoon.</p></header>
    <div class="body"><div id="pre"><div class="skel"></div></div></div>
    <div class="foot"><button onclick="refresh()">Run again</button></div>
   </section>

   <section class="card">
    <header><h2>Methodology</h2>
     <p class="why">How the firm does the work. It reaches <b>every</b> model call, so
      somebody has to read each file and clear it. Editing a cleared file un-clears it.</p></header>
    <div class="body"><div id="meth"><div class="skel"></div></div></div>
   </section>

   <section class="card">
    <header><h2>Practice groups</h2>
     <p class="why">What an engagement can be labelled with, and what each label gets you
      today.</p></header>
    <div class="body"><div id="scopes"><div class="skel"></div></div></div>
   </section>

   <section class="card">
    <header><h2>Workflows</h2>
     <p class="why">The order the work happens in. One runs on client work only after the
      board approves it; editing it afterwards un-approves it.</p></header>
    <div class="body"><div id="recipes"><div class="skel"></div></div></div>
   </section>

   <section class="card">
    <header><h2>What is wired</h2>
     <p class="why">Derived from the code, not from this sentence.</p></header>
    <div class="body"><div id="seams"><div class="skel"></div></div></div>
   </section>
  </div>
 </div>
</div>
<div id="toast"></div>
{SHELL}
<script>
let SETUP = null, SCOPES = null, METH = {{files: []}}, ME = null;

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
      go: configured ? null : ['Set it up', 'initialise()']}},
    {{done: watches > 0, t: 'Say which folder to watch',
      d: watches ? plural(watches, 'folder watched', 'folders watched') : 'The tree client files arrive in.'}},
    {{done: dests > 0, t: 'Say where deliverables go',
      d: dests ? plural(dests, 'destination', 'destinations') : 'The folder a finished workbook is written to.'}},
    {{done: cleared, t: 'Clear the methodology',
      d: cleared ? 'All ' + files.length + ' files read and cleared'
                 : 'Somebody reads each file once. Runs are blocked until they have.'}},
    {{done: roster.length > 0, t: 'Register an engagement',
      d: roster.length ? plural(roster.length, 'engagement', 'engagements') + ' on the roster'
                       : 'The client work itself, and the practice group it belongs to.',
      go: (configured && watches && dests && !roster.length) ? ['Add one', 'showAdd()'] : null}},
    {{done: active > 0, t: 'Activate it',
      d: active ? plural(active, 'engagement active', 'engagements active')
                : 'Preflight has to pass for it first. Until then nothing is read.'}},
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
       ${{s.go && i === next ? `<span class="go"><button class="primary" onclick="${{s.go[1]}}">${{esc(s.go[0])}}</button></span>` : ''}}
      </div>`).join('') + '</div>';
}}

/* ---------------------------------------------------------------- panels */
async function refresh() {{
  try {{ SETUP = await get('/api/admin/setup'); }}
  catch (e) {{ SETUP = null; }}

  ME = await get('/api/admin/whoami').catch(() => null);
  $('chrome-right').innerHTML =
    (SETUP ? esc(SETUP.environment) + ' &middot; configuration v' + esc(SETUP.version)
           : '<span class="pill warn"><i class="dot"></i>not set up</span>') +
    (ME ? ' &middot; <span title="Every change is recorded against this name. It is who the '
        + 'system resolved you as, not something typed here.">acting as <b style="color:var(--ink-2)">'
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
  $('roster').innerHTML = rows.length ? rows.map(r => `<div class="r">
     <span class="lbl"><b>${{esc(r.engagement_id)}}</b><br>
      <span class="sub">${{esc(r.client || '')}} &middot; ${{esc(r.scope_path)}}</span></span>
     <span class="sub">${{r.recipe ? esc(r.recipe) : 'default workflow'}}</span>
     <span class="pill ${{r.state === 'active' ? 'good' : ''}}"><i class="dot"></i>${{esc(r.state)}}</span>
     <span>
      <button class="quiet" onclick="setRecipe('${{esc(r.engagement_id)}}','${{esc(r.recipe || '')}}')">workflow</button>
      <button class="quiet" onclick="editProfile('${{esc(r.engagement_id)}}')">profile</button>
      ${{r.state === 'active'
        ? `<button onclick="move('${{esc(r.engagement_id)}}','pause')">Pause</button>`
        : `<button class="primary" onclick="move('${{esc(r.engagement_id)}}','activate')">Activate</button>`}}
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
           <span class="d" style="display:block;color:var(--ink-3);font-size:12.5px;margin-top:3px">${{esc(f.what_now || '')}}</span></span>
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
  SCOPES = await get('/api/admin/scopes');
  $('scopes').innerHTML =
    '<div class="r head"><span class="lbl">Practice group</span><span class="sub">Skills</span></div>' +
    SCOPES.paths.map(p => `<div class="r"><span class="lbl mono">${{esc(p.scope_path)}}</span>
      <span class="sub">${{p.skills}}</span>
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
     ${{f.state === 'cleared' ? '' : `<button onclick="clearFile('${{esc(f.name)}}')">Clear</button>`}}
     </div>`).join('')
   : '<div class="empty"><b>No methodology files</b>They live in <span class="mono">foundations/</span>.</div>';
}}

async function workflows() {{
  const r = await get('/api/admin/recipes').catch(() => ({{recipes: []}}));
  $('recipes').innerHTML = (r.recipes || []).length ? r.recipes.map(x => `<div class="r">
     <span class="lbl mono">${{esc(x.name)}}</span>
     <span class="sub">${{esc(x.approved_by || '')}}</span>
     <span class="pill ${{x.state === 'registered' ? 'good' : x.state === 'edited' ? 'bad' : 'warn'}}">${{x.state === 'registered' ? 'approved' : x.state === 'edited' ? 'edited since' : 'not approved'}}</span>
     </div>`).join('')
   : '<div class="empty"><b>No workflows</b></div>';
}}

async function seams() {{
  const r = await get('/api/readiness').catch(() => null);
  if (!r) {{ $('seams').innerHTML = '<div class="empty">Unavailable</div>'; return; }}
  $('seams').innerHTML = r.seams.map(s => `<div class="r">
     <span class="lbl">${{esc(s.name)}}<span class="d" style="display:block;color:var(--ink-3);font-size:12.5px;margin-top:2px">${{esc(s.detail)}}</span></span>
     <span class="pill ${{s.ready ? 'good' : 'bad'}}"><i class="dot"></i>${{s.ready ? 'wired' : 'not wired'}}</span>
    </div>`).join('');
}}

/* ---------------------------------------------------------------- actions */
function initialise() {{
  act(() => post('/api/admin/initialise',
    {{who: who(), reason: 'first configuration for this environment'}}),
    'Environment set up.');
}}
function move(id, what) {{
  act(() => post(`/api/admin/engagements/${{id}}/${{what}}`,
    {{who: who(), reason: what + 'd from the setup page'}}),
    id + ' ' + what + 'd.');
}}
function clearFile(name) {{
  if (!confirm('Clearing records that you read ' + name + ' and it is fit to reach every model call.\\n\\nProceed?')) return;
  act(() => post(`/api/admin/methodology/${{name}}/clear`, {{who: who()}}), 'Cleared ' + name + '.');
}}
function setRecipe(id, current) {{
  const chosen = prompt('Which workflow does ' + id + ' run?\\n\\nLeave blank to use the watched folder default.', current);
  if (chosen === null) return;
  act(() => post(`/api/admin/engagements/${{id}}/recipe`,
    {{who: who(), reason: 'workflow chosen from the setup page', recipe: chosen.trim()}}),
    chosen.trim() ? id + ' runs ' + chosen.trim() + '.' : id + ' uses the default workflow.');
}}

function showAdd() {{
  const opts = (list, value, label) => list.map(x => `<option value="${{esc(value(x))}}">${{esc(label(x))}}</option>`).join('');
  $('e_scope').innerHTML = opts(SCOPES ? SCOPES.paths : [], p => p.scope_path,
    p => p.scope_path + (p.firm_layer_only ? '  (nothing defined yet)' : ''));
  $('e_watch').innerHTML = opts(SETUP ? SETUP.watches || [] : [], w => w.id, w => w.id + ' \\u2014 ' + (w.root || '/'));
  $('e_dest').innerHTML = opts(SETUP ? SETUP.destinations || [] : [], d => d.id, d => d.id + ' \\u2014 ' + (d.name || d.path || ''));
  $('add-card').style.display = '';
  $('add-card').scrollIntoView({{behavior: 'smooth', block: 'center'}});
  $('e_id').focus();
}}
function hideAdd() {{ $('add-card').style.display = 'none'; }}

function addEngagement() {{
  const body = {{
    who: who(), reason: 'registered from the setup page',
    engagement_id: $('e_id').value.trim(), client: $('e_client').value.trim(),
    scope_path: $('e_scope').value, watch_id: $('e_watch').value,
    destination_id: $('e_dest').value, folder: $('e_folder').value.trim(),
    template_pin: $('e_pin').value.trim(),
  }};
  if (!body.engagement_id || !body.client) return say('An engagement needs an id and a client.', 'bad');
  act(() => post('/api/admin/engagements', body).then(hideAdd),
    'Registered ' + body.engagement_id + '. It is paused until you activate it.');
}}

async function editProfile(id) {{
  let t;
  try {{ t = await get(`/api/admin/engagements/${{id}}/profile/template`); }}
  catch (e) {{ return say(e.text || String(e), 'bad', e.code); }}
  const box = document.createElement('section');
  box.className = 'card';
  box.innerHTML = `<header><h2>Engagement profile &mdash; ${{esc(id)}}</h2>
    <p class="why">${{t.gaps.length
      ? 'Still missing: ' + t.gaps.map(esc).join('; ')
      : 'Complete. Saving writes a new version; the old one stays on the record.'}}</p></header>
   <div class="body">
    <p class="note" style="margin-top:0">Everything the system already knows is filled in.
     The blanks are judgements: the industry code, the size band, the owner-compensation
     benchmark, and who reviews this engagement and how quickly.</p>
    <textarea id="p_body" style="height:340px;font-family:var(--mono);font-size:12.5px">${{esc(JSON.stringify(t.profile, null, 2))}}</textarea>
   </div>
   <div class="foot"><button class="primary" onclick="saveProfile('${{esc(id)}}')">Save profile</button>
    <button class="quiet" onclick="this.closest('section').remove()">Cancel</button></div>`;
  $('roster').closest('section').after(box);
  box.scrollIntoView({{behavior: 'smooth', block: 'center'}});
}}
function saveProfile(id) {{
  let body;
  try {{ body = JSON.parse($('p_body').value); }}
  catch (e) {{ return say('That is not valid JSON: ' + e, 'bad'); }}
  act(() => post(`/api/admin/engagements/${{id}}/profile`,
    {{who: who(), reason: 'profile completed from the setup page', profile: body}}),
    'Profile saved for ' + id + '.');
}}

refresh();
</script>
"""
