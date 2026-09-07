# ruff: noqa: E501 - this module is one browser page held in a string. Wrapping the CSS
# and the template literals to a hundred columns would make them harder to read, not
# easier, and the same exception is taken by the ops console for the same reason.
"""The admin dashboard: the page a person who is not a developer actually uses.

Everything here was reachable already, as JSON over HTTP. That is not the same as usable:
labelling a folder with its practice group, clearing methodology, or reading why preflight
will not let an engagement start are all things a managing director has to be able to do
without a terminal, and until there is a page they cannot.

Deliberately one file with no build step and no framework. It is read by whoever maintains
this after the first person, and a page they can read in one sitting is worth more here
than a page that is pleasant to write. Same house style as the ops console.

Every action posts through the same API a script would use, so there is nothing the page
can do that is not also on the record: `who` and `reason` travel with every write, and a
refusal comes back as a diagnostic the page prints rather than swallows.
"""

from __future__ import annotations

__all__ = ["PAGE"]

PAGE = """<!doctype html>
<meta charset="utf-8"><title>Automated Analyst - admin</title>
<style>
body{font:13px/1.45 system-ui,sans-serif;margin:0;background:#0f1216;color:#d7dbe0}
header{padding:12px 18px;border-bottom:1px solid #262b33;display:flex;gap:18px;align-items:baseline}
h1{font-size:15px;margin:0}
main{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:14px}
section{border:1px solid #262b33;border-radius:6px;padding:10px 12px;margin-bottom:14px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#8b93a1;margin:0 0 8px}
.mono{font-family:ui-monospace,monospace;font-size:12px}
.row{display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-bottom:1px solid #1a1f26}
.pass{color:#5fcf8a}.warn{color:#f0b64a}.fail{color:#ff6b6b}.muted{color:#8b93a1}
button{font:12px system-ui;background:#1c222b;color:#d7dbe0;border:1px solid #313944;
 border-radius:4px;padding:3px 9px;cursor:pointer}
button:hover{background:#252d38}
input{font:12px system-ui;background:#0b0e12;color:#d7dbe0;border:1px solid #313944;
 border-radius:4px;padding:3px 6px;width:100%;box-sizing:border-box;margin:2px 0}
#said{padding:6px 18px;border-bottom:1px solid #262b33;min-height:18px}
details summary{cursor:pointer;color:#8b93a1;font-size:12px}
</style>
<header>
 <h1>Admin</h1>
 <span id="where" class="mono muted"></span>
 <span style="margin-left:auto"><a href="/" style="color:#7cb7ff">ops console</a></span>
</header>
<div id="said" class="mono"></div>
<main>
<div>
 <section><h2>This environment</h2><div id="setup"></div></section>
 <section><h2>Preflight</h2><div id="pre"></div>
  <div style="margin-top:8px"><button onclick="refresh()">Re-run</button></div></section>
 <section><h2>Engagements</h2><div id="roster"></div>
  <details style="margin-top:8px"><summary>Add an engagement</summary>
   <input id="e_id" placeholder="engagement id, e.g. HEND-2026-04">
   <input id="e_client" placeholder="client name">
   <input id="e_scope" placeholder="practice group / segment / disposition">
   <input id="e_watch" placeholder="watch id">
   <input id="e_dest" placeholder="destination id">
   <input id="e_folder" placeholder="folder under the watch root">
   <input id="e_pin" placeholder="template pin, e.g. Chartwell_ESOP_Model_v9@9.4 - blank to use the group default">
   <button onclick="addEngagement()">Register (paused)</button>
  </details>
 </section>
</div>
<div>
 <section><h2>Practice groups</h2><div id="scopes"></div></section>
 <section><h2>Workflows</h2><div id="recipes"></div>
  <div class="muted" style="margin-top:6px">A workflow runs on client work only after the
   board approves it. Editing one after approval un-approves it, which is the point.</div></section>
 <section><h2>Methodology</h2><div id="meth"></div>
  <div class="muted" style="margin-top:6px">Clearing records that <b>you</b> read the file.
   It reaches every model call, so it is checked by digest on every run.</div></section>
 <section><h2>What is wired</h2><div id="seams"></div></section>
</div>
</main>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
let WHO=localStorage.getItem('aa_who')||'';
function say(m,cls){$('said').className='mono '+(cls||'');$('said').textContent=m}
function who(){
 if(!WHO){WHO=prompt('Your name - every change here is recorded against it')||'';
  if(WHO)localStorage.setItem('aa_who',WHO)}
 return WHO}
async function j(u){const r=await fetch(u);if(!r.ok)throw await detail(r);return r.json()}
async function detail(r){
 try{const b=await r.json();const d=(b.detail&&b.detail.refused||[])[0];
  return d?(d.code+' - '+d.detail+(d.what_now?'  |  '+d.what_now:'')):JSON.stringify(b.detail);}
 catch(e){return r.status+' '+r.statusText}}
async function post(u,body){
 const r=await fetch(u,{method:'POST',headers:{'content-type':'application/json'},
  body:JSON.stringify(body)});
 if(!r.ok)throw await detail(r);
 return r.json()}
async function act(fn,done){
 try{await fn();say(done,'pass');refresh()}catch(e){say(String(e),'fail')}}

async function refresh(){
 let setup=null;
 try{setup=await j('/api/admin/setup')}catch(e){
  $('setup').innerHTML='<div class="warn">This environment has never been configured.</div>'+
   '<div style="margin-top:8px"><button onclick="initialise()">Initialise it</button></div>';
  $('where').textContent='not configured';
  ['pre','roster','scopes','meth'].forEach(i=>$(i).innerHTML='<i class="muted">after setup</i>');
  return seams()}
 $('where').textContent=setup.environment+' - configuration v'+setup.version;
 $('setup').innerHTML=[
  ['watches',(setup.watches||[]).map(w=>w.id+' &rarr; '+esc(w.root)).join('<br>')],
  ['destinations',(setup.destinations||[]).map(d=>esc(d.id)).join(', ')],
  ['credentials',(setup.credentials||[]).map(c=>esc(c.name)).join(', ')],
 ].map(([k,v])=>`<div class="row"><span>${k}</span><span class="mono">${v||'<i>none</i>'}</span></div>`).join('');
 roster(setup);
 preflight();scopes();methodology();workflows();seams();
}
function roster(setup){
 const rows=setup.roster||[];
 $('roster').innerHTML=rows.map(r=>`<div class="row"><span>${esc(r.engagement_id)}</span>
  <span class="mono muted">${esc(r.scope_path)}</span>
  <span class="mono ${r.recipe?'':'muted'}" title="what order the work happens in"
   >${esc(r.recipe||'(watch default)')}</span>
  <span class="${r.state==='active'?'pass':'muted'}">${esc(r.state)}</span>
  <span><button onclick="setRecipe('${esc(r.engagement_id)}','${esc(r.recipe||'')}')">recipe</button>
   <button onclick="editProfile('${esc(r.engagement_id)}')">profile</button>
   ${r.state==='active'
   ?`<button onclick="move('${esc(r.engagement_id)}','pause')">pause</button>`
   :`<button onclick="move('${esc(r.engagement_id)}','activate')">activate</button>`}</span>
  </div>`).join('')||'<i class="muted">no engagements yet</i>';
}
function setRecipe(id,current){
 const chosen=prompt('Which recipe does '+id+' run?\n\nBlank inherits the watch default.',current);
 if(chosen===null)return;
 act(()=>post(`/api/admin/engagements/${id}/recipe`,
  {who:who(),reason:'recipe chosen from the admin page',recipe:chosen.trim()}),
  chosen.trim()?id+' runs '+chosen.trim()+'.':id+' inherits the watch default.');
}
async function editProfile(id){
 const t=await j(`/api/admin/engagements/${id}/profile/template`);
 const box=document.createElement('div');
 box.innerHTML=`<section><h2>Engagement profile - ${esc(id)}</h2>
  <div class="muted">${t.gaps.length?'Still missing: '+t.gaps.map(esc).join('; ')
   :'Complete. Editing it writes a new version.'}</div>
  <textarea id="p_body" style="width:100%;height:340px;font:12px ui-monospace,monospace;
   background:#0b0e12;color:#d7dbe0;border:1px solid #313944;border-radius:4px;margin-top:6px"
   >${esc(JSON.stringify(t.profile,null,2))}</textarea>
  <div style="margin-top:6px"><button onclick="saveProfile('${esc(id)}')">Save</button>
   <button onclick="this.closest('section').parentNode.remove()">Cancel</button></div>
  </section>`;
 $('roster').parentNode.appendChild(box);
}
function saveProfile(id){
 let body;
 try{body=JSON.parse($('p_body').value)}catch(e){return say('That is not valid JSON: '+e,'fail')}
 act(()=>post(`/api/admin/engagements/${id}/profile`,
  {who:who(),reason:'profile completed from the admin page',profile:body}),
  'Profile saved for '+id+'.');
}
async function preflight(){
 const p=await j('/api/admin/preflight');
 $('pre').innerHTML=`<div class="row"><b class="${p.passed?'pass':'fail'}">
  ${p.passed?'PASS':'FAIL'}</b><span class="mono muted">${esc(p.ran_at)}</span></div>`+
  p.checks.map(c=>`<div class="row"><span class="${c.status}">${esc(c.label)}</span>
   <span class="mono muted">${esc(c.detail)}</span></div>`+
   c.failures.map(f=>`<div class="row mono ${f.severity==='warn'?'warn':'fail'}" style="padding-left:12px">
    <span>${esc(f.code)}</span><span>${esc(f.detail||'')}</span>
    <span class="muted">${esc(f.what_now||'')}</span></div>`
   ).join('')).join('');
}
async function scopes(){
 const s=await j('/api/admin/scopes');
 $('scopes').innerHTML=s.paths.map(p=>`<div class="row"><span class="mono">${esc(p.scope_path)}</span>
  <span class="${p.firm_layer_only?'warn':'pass'}">${p.skills} skill(s)</span>
  <span class="muted">${p.defined?'':'nothing defined yet'}</span></div>`).join('')+
  '<div class="muted" style="margin-top:6px">A folder is labelled by choosing one of these. '+
  'A group with nothing defined gets the firm layer only, and says so.</div>';
}
async function methodology(){
 const m=await j('/api/admin/methodology');
 $('meth').innerHTML=m.files.map(f=>`<div class="row">
  <span class="mono">${esc(f.name)}</span>
  <span class="${f.state==='cleared'?'pass':f.state==='edited'?'fail':'warn'}">${esc(f.state)}</span>
  <span class="muted">${esc(f.cleared_by||'')}</span>
  <span>${f.state==='cleared'?'':`<button onclick="clearFile('${esc(f.name)}')">clear</button>`}</span>
  </div>`).join('')||'<i class="muted">no methodology files</i>';
}
async function workflows(){
 const r=await j('/api/admin/recipes');
 $('recipes').innerHTML=r.recipes.map(x=>`<div class="row">
  <span class="mono">${esc(x.name)}</span>
  <span class="${x.state==='registered'?'pass':x.state==='edited'?'fail':'warn'}">${esc(x.state)}</span>
  <span class="muted">${esc(x.approved_by||'')}</span></div>`).join('')
  ||'<i class="muted">no recipes</i>';
}
async function seams(){
 const r=await j('/api/readiness').catch(()=>null);
 if(!r){$('seams').innerHTML='<i class="muted">unavailable</i>';return}
 $('seams').innerHTML=r.seams.map(s=>`<div class="row">
  <span class="${s.ready?'pass':'fail'}">${esc(s.name)}</span>
  <span class="muted">${esc(s.detail)}</span></div>`).join('');
}
function initialise(){act(()=>post('/api/admin/initialise',
 {who:who(),reason:'first configuration for this environment'}),'Environment initialised.')}
function move(id,what){act(()=>post(`/api/admin/engagements/${id}/${what}`,
 {who:who(),reason:what+'d from the admin page'}),id+' '+what+'d.')}
function clearFile(name){act(()=>post(`/api/admin/methodology/${name}/clear`,{who:who()}),
 'Cleared '+name+'.')}
function addEngagement(){
 const body={who:who(),reason:'registered from the admin page',
  engagement_id:$('e_id').value.trim(),client:$('e_client').value.trim(),
  scope_path:$('e_scope').value.trim(),watch_id:$('e_watch').value.trim(),
  destination_id:$('e_dest').value.trim(),folder:$('e_folder').value.trim(),
  template_pin:$('e_pin').value.trim()};
 act(()=>post('/api/admin/engagements',body),'Registered '+body.engagement_id+', paused.');
}
refresh();
</script>
"""
