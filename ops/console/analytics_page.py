# ruff: noqa: E501 - this module is one browser page held in a string. Wrapping the CSS
# and the template literals to a hundred columns would make them harder to read, not
# easier, and the same exception is taken by the other two pages for the same reason.
"""The analytics dashboard: is this working, and what should we fix first?

`ops/analytics.py` has computed all of this since P23 and nothing has ever rendered it.
The four questions it answers are the ones that decide whether the project continues, and
they were reachable only as JSON at `/api/analytics` - which means they were reachable by
somebody who already knew to look, which is not the same as being answered.

Deliberately a second page rather than a tab on the live console. They answer different
questions: the console is "what is happening right now", and standing in front of it is how
you watch one run. This is "across every run, is it working" - read weekly, by somebody
deciding whether to keep going, and not while anything is on fire.

No charts. Numbers with their denominators, ranked lists, and the human baseline printed
beside the rate it is meant to be compared against - or `unmeasured`, which is the honest
word until two analysts have measured it on real line items. A sparkline would look more
like a dashboard and say less.
"""

from __future__ import annotations

__all__ = ["PAGE"]

PAGE = """<!doctype html>
<meta charset="utf-8"><title>Automated Analyst - analytics</title>
<style>
body{font:13px/1.45 system-ui,sans-serif;margin:0;background:#0f1216;color:#d7dbe0}
header{padding:12px 18px;border-bottom:1px solid #262b33;display:flex;gap:18px;align-items:baseline}
h1{font-size:15px;margin:0}
main{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:14px}
section{border:1px solid #262b33;border-radius:6px;padding:10px 12px;margin-bottom:14px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#8b93a1;margin:0 0 8px}
.mono{font-family:ui-monospace,monospace;font-size:12px}
.row{display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-bottom:1px solid #1a1f26}
.big{font-size:19px}
.pass{color:#5fcf8a}.warn{color:#f0b64a}.fail{color:#ff6b6b}.muted{color:#8b93a1}
a{color:#7cb7ff}
select{font:12px system-ui;background:#0b0e12;color:#d7dbe0;border:1px solid #313944;border-radius:4px;padding:2px 6px}
.bar{height:6px;background:#1c222b;border-radius:3px;overflow:hidden;flex:1;margin:6px 0 0}
.bar>i{display:block;height:100%;background:#3f6fa8}
</style>
<header>
 <h1>Analytics</h1>
 <span class="mono muted" id="since"></span>
 <span>over
  <select id="days" onchange="refresh()">
   <option value="7">7 days</option><option value="30" selected>30 days</option>
   <option value="90">90 days</option><option value="365">a year</option>
  </select>
 </span>
 <span style="margin-left:auto"><a href="/">live console</a> &middot; <a href="/admin">admin</a></span>
</header>
<main>
<div>
 <section><h2>Is it healthy?</h2><div id="head"></div></section>
 <section><h2>Where runs stop</h2><div id="funnel"></div>
  <div class="muted" style="margin-top:6px">Each stage counts the runs that reached it. The
   drop is where the work actually goes.</div></section>
 <section><h2>Outcomes by week</h2><div id="outcomes" class="mono"></div></section>
</div>
<div>
 <section><h2>What to fix first</h2><div id="failures"></div>
  <div class="muted" style="margin-top:6px">Ranked by how often it happened, with the owner
   the diagnostics registry gives it. The largest class is usually client data, and no
   amount of engineering removes that.</div></section>
 <section><h2>Is it getting better?</h2><div id="trends"></div></section>
 <section><h2>Anything stuck?</h2><div id="stuck"></div></section>
 <section><h2>By skill</h2><div id="skills" class="mono"></div></section>
</div>
</main>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const pct=v=>v===null||v===undefined?'<span class="muted">no data</span>':(v*100).toFixed(1)+'%';
const num=v=>v===null||v===undefined?'<span class="muted">no data</span>':esc(v);

async function refresh(){
 const days=$('days').value;
 const a=await (await fetch('/api/analytics?days='+days)).json();
 $('since').textContent='since '+a.since;

 const h=a.head;
 $('head').innerHTML=[
  ['Runs', h.runs+' <span class="muted">('+h.finished+' finished)</span>'],
  ['First-pass yield', pct(h.first_pass_yield)+' <span class="muted">delivered with no guard failure</span>'],
  ['Time to first reviewable', num(h.time_to_first_reviewable_min)+' <span class="muted">min, median</span>'],
  ['Review items per run', num(h.review_items_per_run)+' <span class="muted">median</span>'],
  ['Model spend per engagement', '$'+num(h.model_spend_per_engagement_usd)+' <span class="muted">median</span>'],
  ['Released then corrected', `<span class="${h.released_then_corrected?'fail':'pass'}">${num(h.released_then_corrected)}</span>`],
 ].map(([k,v])=>`<div class="row"><span>${k}</span><span>${v}</span></div>`).join('');

 const top=Math.max(1,...a.funnel.map(f=>f.reached));
 $('funnel').innerHTML=a.funnel.map(f=>`<div style="padding:4px 0;border-bottom:1px solid #1a1f26">
   <div class="row" style="border:0;padding:0"><span>${esc(f.stage)}</span>
    <span>${f.reached}${f.dropped?` <span class="warn">-${f.dropped}</span>`:''}</span></div>
   <div class="bar"><i style="width:${(f.reached/top*100).toFixed(1)}%"></i></div></div>`).join('')
  ||'<i class="muted">no runs yet</i>';

 $('outcomes').innerHTML=a.outcomes.map(o=>`<div class="row"><span>${esc(o.week)}</span>
   <span class="pass">${o.clean} clean</span><span>${o.released_with_review} reviewed</span>
   <span class="warn">${o.blocked} blocked</span><span class="fail">${o.halted} halted</span>
   </div>`).join('')||'<i class="muted">nothing finished yet</i>';

 $('failures').innerHTML=a.failures.slice(0,12).map(f=>`<div class="row">
   <span class="mono">${esc(f.code)}</span><span>${f.count}</span>
   <span class="muted">${esc(f.owner)}</span></div>`).join('')
  ||'<i class="muted">nothing has failed</i>';

 const t=a.trends;
 const baseline=t.override_rate_human_baseline;
 $('trends').innerHTML=[
  ['Auto-accept rate', pct(t.auto_accept_rate)],
  ['Override rate', pct(t.override_rate)],
  ['Human baseline', baseline==='unmeasured'
    ? '<span class="warn">unmeasured</span> <span class="muted">two analysts, 200 real line items</span>'
    : pct(baseline)],
  ['Tie-out failure rate', pct(t.tieout_failure_rate)],
  ['Cost per engagement', '$'+num(t.cost_per_engagement_usd)],
 ].map(([k,v])=>`<div class="row"><span>${k}</span><span>${v}</span></div>`).join('');

 const s=a.stuck;
 $('stuck').innerHTML=[
  ['Quarantined steps', s.quarantined_steps],
  ['Review items past SLA', s.review_items_past_sla],
  ['Of those, unassigned', s.review_owners_unassigned],
  ['Stalled runs', s.stalled_runs],
 ].map(([k,v])=>`<div class="row"><span>${k}</span><span class="${v?'fail':'pass'}">${v}</span></div>`).join('')
  +(s.skills_flagged_by_drift.length
    ? `<div class="row"><span>Skills flagged by drift</span><span class="fail mono">${s.skills_flagged_by_drift.map(esc).join(', ')}</span></div>`
    : '<div class="row"><span>Skills flagged by drift</span><span class="pass">none</span></div>');

 $('skills').innerHTML=a.skills.map(k=>`<div class="row">
   <span>${esc(k.skill)}</span><span class="muted">${esc(k.scope)}</span>
   <span>${k.runs} runs</span><span>auto ${pct(k.auto_accept_rate)}</span>
   <span>override ${pct(k.override_rate)}</span>
   <span class="${k.drift_flags.length?'fail':''}">${k.drift_flags.map(esc).join(', ')}</span>
   </div>`).join('')||'<i class="muted">no skill has been routed yet</i>';
}
refresh();setInterval(refresh,60000);
</script>
"""
