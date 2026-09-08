# ruff: noqa: E501 - this module is one browser page held in a string. Wrapping the
# template literals to a hundred columns would make them harder to read, not easier.
"""The analytics dashboard: is this working, and what should we fix first?

`ops/analytics.py` has computed all of this since P23 and nothing rendered it. The four
questions it answers are the ones that decide whether the project continues, and they were
reachable only as JSON - which means reachable by somebody who already knew to look, which
is not the same as answered.

**A second page rather than a tab on the live console.** They answer different questions.
The console is *what is happening right now*, read standing up while a run goes. This is
*across every run, is it working*, read sitting down, weekly, by somebody deciding whether
to keep going. Putting them together would make one of them the thing you scroll past.

**Four questions, in four cards, in the order somebody asks them.** Is it healthy. Where do
runs stop. What should we fix. Is it getting better. Anything stuck. Each card says in one
line what it is for, because a table of figures that only makes sense to whoever built it
is not a dashboard.

**No charts.** Numbers with their denominators, ranked lists, and the human baseline
printed beside the rate it is meant to be compared against - or `unmeasured`, which is the
honest word until two analysts have measured it on real line items. A sparkline would look
more like a dashboard and say less.
"""

from __future__ import annotations

from ui import CSS, SHELL
from ui.theme import shell

__all__ = ["PAGE"]

PAGE = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analytics - Automated Analyst</title>
<style>{CSS}</style>
{shell("Analytics", "/analytics")}
<div class="wrap">
 <div class="page-head" style="display:flex;align-items:flex-end;gap:20px;flex-wrap:wrap">
  <div style="flex:1;min-width:280px">
   <h1>Analytics</h1>
   <p>Across every run rather than any one of them: whether this is working, and what to
    fix first. Read it weekly, not while something is on fire.</p>
  </div>
  <div style="display:flex;align-items:center;gap:9px;padding-bottom:4px">
   <label for="days" style="margin:0">Period</label>
   <select id="days" onchange="refresh()">
    <option value="7">Last 7 days</option>
    <option value="30" selected>Last 30 days</option>
    <option value="90">Last 90 days</option>
    <option value="365">Last year</option>
   </select>
  </div>
 </div>

 <div class="metrics" id="head" style="margin-bottom:16px">
  <div class="metric"><span class="k">Loading</span><span class="v">&mdash;</span></div>
 </div>

 <div class="cols side">
  <div>
   <section class="card">
    <header><h2>Where runs stop</h2>
     <p class="why">Every run passes through these in order. The drop at each stage is
      where the work actually goes &mdash; and where a person is being asked for something.</p></header>
    <div class="body"><div id="funnel"><div class="skel"></div><div class="skel"></div></div></div>
   </section>

   <section class="card">
    <header><h2>What to fix first</h2>
     <p class="why">Ranked by how often it happened, each with the owner the diagnostics
      registry gives it. The largest class is usually client data, and no amount of
      engineering removes that &mdash; which is worth knowing before anybody plans a sprint.</p></header>
    <div class="body"><div id="failures"><div class="skel"></div></div></div>
   </section>

   <section class="card">
    <header><h2>Outcomes by week</h2>
     <p class="why">The mix, not the total. A rising share of clean runs is the thing to
      watch; a rising share of halted ones is the thing to act on.</p></header>
    <div class="body"><div id="outcomes"><div class="skel"></div></div></div>
   </section>
  </div>

  <div>
   <section class="card">
    <header><h2>Anything stuck?</h2>
     <p class="why">Work that has stopped and is waiting on somebody.</p></header>
    <div class="body"><div id="stuck"><div class="skel"></div></div></div>
   </section>

   <section class="card">
    <header><h2>Is it getting better?</h2>
     <p class="why">Auto-accept and override rates over the period, beside the human
      baseline they have to be judged against.</p></header>
    <div class="body"><div id="trends"><div class="skel"></div></div></div>
   </section>

   <section class="card">
    <header><h2>By skill</h2>
     <p class="why">Which skills are carrying the work, how much of it goes to a person,
      and whether any has drifted from what it was approved at.</p></header>
    <div class="body"><div id="skills"><div class="skel"></div></div></div>
   </section>
  </div>
 </div>
</div>
<div id="toast"></div>
{SHELL}
<script>
const money = v => (v === null || v === undefined) ? '&mdash;' : '$' + Number(v).toFixed(2);

function metric(k, v, caption, tone) {{
  return `<div class="metric ${{tone || ''}}"><span class="k">${{k}}</span>
    <span class="v">${{v}}</span><span class="c">${{caption}}</span></div>`;
}}

async function refresh() {{
  let a;
  try {{ a = await get('/api/analytics?days=' + $('days').value); }}
  catch (e) {{ return say(e.text || String(e), 'bad', e.code); }}

  $('chrome-right').innerHTML = 'since ' + esc(a.since);
  head(a.head);
  funnel(a.funnel, a.head.runs);
  failures(a.failures);
  outcomes(a.outcomes);
  stuck(a.stuck);
  trends(a.trends);
  skills(a.skills);
}}

/* ------------------------------------------------------------ is it healthy */
function head(h) {{
  if (!h.runs) {{
    $('head').innerHTML = metric('Runs', '0', 'Nothing has run in this period yet');
    return;
  }}
  const yieldTone = h.first_pass_yield === null ? '' : h.first_pass_yield >= 0.8 ? 'good' : h.first_pass_yield >= 0.5 ? 'warn' : 'bad';
  $('head').innerHTML =
    metric('Runs', esc(h.runs), plural(h.finished, 'has finished', 'have finished')) +
    metric('First-pass yield', pct(h.first_pass_yield),
           'Delivered with no guard failure', yieldTone) +
    metric('To first reviewable',
           h.time_to_first_reviewable_min === null ? '&mdash;' : esc(h.time_to_first_reviewable_min) + '<small> min</small>',
           'Median, from the file landing') +
    metric('Review items per run', num(h.review_items_per_run, '0'),
           'Median. What a person is asked to look at') +
    metric('Spend per engagement', money(h.model_spend_per_engagement_usd),
           'Median model cost') +
    metric('Released then corrected', esc(h.released_then_corrected),
           h.released_then_corrected ? 'Went out and had to be changed' : 'Nothing went out and came back',
           h.released_then_corrected ? 'bad' : 'good');
}}

/* ------------------------------------------------------------ where they stop */
function funnel(rows, runs) {{
  if (!rows.length || !runs) {{
    $('funnel').innerHTML = '<div class="empty"><b>No runs in this period</b>Each stage will show how many runs reached it, and how many stopped there.</div>';
    return;
  }}
  $('funnel').innerHTML = rows.map(f => {{
    const share = runs ? (f.reached / runs * 100) : 0;
    return `<div style="padding:9px 0;border-bottom:1px solid var(--line-soft)">
      <div class="r" style="border:0;padding:0 0 7px">
       <span class="lbl">${{esc(f.stage)}}</span>
       <span class="val">${{f.reached}}<span class="sub" style="font-weight:400"> of ${{runs}}</span></span>
       ${{f.dropped ? `<span class="pill warn">&minus;${{f.dropped}} here</span>` : ''}}
      </div>
      <div class="bar ${{f.dropped ? 'warn' : 'good'}}"><i style="width:${{share.toFixed(1)}}%"></i></div>
     </div>`;
  }}).join('');
}}

/* ------------------------------------------------------------ what to fix */
const OWNER_TONE = {{'client-data': '', 'config': 'warn', 'model': 'warn', 'system': 'bad', 'policy': 'accent', 'process': ''}};

function failures(rows) {{
  if (!rows.length) {{
    $('failures').innerHTML = '<div class="empty"><b>Nothing has failed</b>Codes appear here ranked by how often they came up.</div>';
    return;
  }}
  const top = rows[0].count || 1;
  $('failures').innerHTML = rows.slice(0, 12).map(f => `
    <details><summary style="padding:0">
      <div class="r" style="border:0;padding:7px 0;display:inline-flex;width:calc(100% - 22px)">
       <span class="lbl mono" style="color:var(--ink)">${{esc(f.code)}}</span>
       <span class="pill ${{OWNER_TONE[f.owner] ?? ''}}">${{esc(f.owner)}}</span>
       <span class="val">${{f.count}}</span>
      </div></summary>
     <div class="bar" style="margin:0 0 8px"><i style="width:${{(f.count / top * 100).toFixed(0)}}%"></i></div>
     <p class="note" style="margin:0 0 10px">${{esc(f.what_now || 'No guidance recorded for this code.')}}</p>
    </details>`).join('') +
    (rows.length > 12 ? `<p class="note">${{rows.length - 12}} more, less often.</p>` : '');
}}

/* ------------------------------------------------------------ outcomes */
function outcomes(rows) {{
  if (!rows.length) {{
    $('outcomes').innerHTML = '<div class="empty"><b>Nothing has finished yet</b>Weeks appear here as runs end.</div>';
    return;
  }}
  $('outcomes').innerHTML =
    '<div class="r head"><span class="lbl">Week</span><span class="sub">Clean</span><span class="sub">Reviewed</span><span class="sub">Blocked</span><span class="sub">Halted</span></div>' +
    rows.map(o => {{
      const total = o.clean + o.released_with_review + o.blocked + o.halted || 1;
      const seg = (n, colour) => n ? `<i style="display:block;height:100%;float:left;width:${{(n / total * 100).toFixed(1)}}%;background:${{colour}}"></i>` : '';
      return `<div style="padding:8px 0;border-bottom:1px solid var(--line-soft)">
        <div class="r" style="border:0;padding:0 0 6px">
         <span class="lbl mono">${{esc(o.week)}}</span>
         <span class="sub" style="color:var(--good)">${{o.clean}}</span>
         <span class="sub">${{o.released_with_review}}</span>
         <span class="sub" style="color:var(--warn)">${{o.blocked}}</span>
         <span class="sub" style="color:var(--bad)">${{o.halted}}</span>
        </div>
        <div class="bar">${{seg(o.clean, 'var(--good)')}}${{seg(o.released_with_review, 'var(--accent)')}}${{seg(o.blocked, 'var(--warn)')}}${{seg(o.halted, 'var(--bad)')}}</div>
       </div>`;
    }}).join('');
}}

/* ------------------------------------------------------------ stuck */
function stuck(s) {{
  const lines = [
    ['Quarantined steps', s.quarantined_steps, 'A step whose output a guard rejected'],
    ['Review items past SLA', s.review_items_past_sla, 'Somebody was asked and has not answered'],
    ['Of those, unassigned', s.review_owners_unassigned, 'Nobody has been asked in particular'],
    ['Stalled runs', s.stalled_runs, 'Silent for longer than expected'],
  ];
  const total = lines.reduce((n, l) => n + (l[1] || 0), 0);
  const flagged = s.skills_flagged_by_drift || [];
  $('stuck').innerHTML =
    `<div class="r" style="border:0;padding:0 0 10px"><span class="lbl">
      <span class="pill ${{total || flagged.length ? 'warn' : 'good'}}"><i class="dot"></i>${{total || flagged.length ? 'Needs attention' : 'Nothing is stuck'}}</span>
     </span></div>` +
    lines.map(([k, v, why]) => `<div class="r">
      <span class="lbl">${{k}}<span class="d" style="display:block;color:var(--ink-3);font-size:12.5px;margin-top:2px">${{why}}</span></span>
      <span class="val" style="color:${{v ? 'var(--bad)' : 'var(--ink-3)'}}">${{v}}</span></div>`).join('') +
    `<div class="r"><span class="lbl">Skills flagged by drift
       <span class="d" style="display:block;color:var(--ink-3);font-size:12.5px;margin-top:2px">Behaving differently from the version that was approved</span></span>
      <span class="val">${{flagged.length
        ? '<span class="pill bad">' + flagged.map(esc).join('</span> <span class="pill bad">') + '</span>'
        : '<span style="color:var(--ink-3)">none</span>'}}</span></div>`;
}}

/* ------------------------------------------------------------ trends */
function trends(t) {{
  const baseline = t.override_rate_human_baseline;
  const measured = baseline !== 'unmeasured' && baseline !== null && baseline !== undefined;
  let verdict = '';
  if (measured && t.override_rate !== null) {{
    const delta = (t.override_rate - baseline) * 100;
    verdict = `<span class="pill ${{delta <= 0 ? 'good' : 'warn'}}">${{delta <= 0 ? '' : '+'}}${{delta.toFixed(1)}} pts vs people</span>`;
  }}
  $('trends').innerHTML =
    `<div class="r"><span class="lbl">Auto-accept rate
       <span class="d" style="display:block;color:var(--ink-3);font-size:12.5px;margin-top:2px">Items the system was confident enough to decide</span></span>
      <span class="val">${{pct(t.auto_accept_rate)}}</span></div>
     <div class="r"><span class="lbl">Override rate
       <span class="d" style="display:block;color:var(--ink-3);font-size:12.5px;margin-top:2px">Proposals a reviewer changed or rejected</span></span>
      <span class="val">${{pct(t.override_rate)}}</span>${{verdict}}</div>
     <div class="r"><span class="lbl">Human baseline
       <span class="d" style="display:block;color:var(--ink-3);font-size:12.5px;margin-top:2px">How often two analysts disagree with each other on the same work</span></span>
      <span class="val">${{measured ? pct(baseline)
        : '<span class="pill warn">unmeasured</span>'}}</span></div>
     ${{measured ? '' : '<p class="note">Until two analysts have measured it on 200 real line items, there is no honest number to compare the override rate against &mdash; so the dashboard says so rather than inventing one.</p>'}}
     <div class="r"><span class="lbl">Tie-out failure rate
       <span class="d" style="display:block;color:var(--ink-3);font-size:12.5px;margin-top:2px">Proposals whose figures did not foot to the source</span></span>
      <span class="val">${{pct(t.tieout_failure_rate)}}</span></div>
     <div class="r"><span class="lbl">Cost per engagement</span>
      <span class="val">${{money(t.cost_per_engagement_usd)}}</span></div>`;
}}

/* ------------------------------------------------------------ by skill */
function skills(rows) {{
  if (!rows.length) {{
    $('skills').innerHTML = '<div class="empty"><b>No skill has been routed yet</b>Each will appear here with its scope once a run reaches it.</div>';
    return;
  }}
  $('skills').innerHTML =
    '<div class="r head"><span class="lbl">Skill</span><span class="sub">Runs</span><span class="sub">Auto</span><span class="sub">Override</span></div>' +
    rows.map(k => `<div class="r">
      <span class="lbl"><b>${{esc(k.skill)}}</b>
       <span class="d" style="display:block;color:var(--ink-3);font-size:12.5px;margin-top:2px">${{esc(k.scope)}} &middot; ${{plural(k.items, 'item', 'items')}}</span></span>
      <span class="sub">${{k.runs}}</span>
      <span class="sub">${{pct(k.auto_accept_rate)}}</span>
      <span class="sub">${{pct(k.override_rate)}}</span>
      ${{k.drift_flags.length ? `<span class="pill bad">drift: ${{k.drift_flags.map(esc).join(', ')}}</span>` : ''}}
     </div>`).join('');
}}

refresh();
setInterval(refresh, 60000);
</script>
"""
