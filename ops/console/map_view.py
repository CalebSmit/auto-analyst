# ruff: noqa: E501 - a browser view held in strings; wrapping it makes it harder to read.
"""The whole design, painted with what one run did.

The Run trace panel lists the nodes a run touched, grouped, without their edges - which
answers "what did it do" and not "where in the system did it happen". This is the other
view: every node of the blueprint, in the blueprint's own positions, with the edges between
them, and each node bordered by what happened there on this run.

**The positions are the blueprint's.** `graph/architecture.json` carries the x and y the
design of record puts each node at, exported from the same file the assertions run over, and
covered by the same digest - so this is the design's own picture rather than a second
drawing of it that has to be kept in step by hand. A node moved in the blueprint moves here
on the next export, and a blueprint edited without one fails a test.

**What it is for.** Standing in front of a halted run and asking where it stopped, what it
had already passed, and what never ran at all. The border carries that: mint for passed,
plum for failed, the accent for running, a hairline for touched, and a dashed outline for
the hundred-odd nodes a given run never reaches. Clicking one says what happened there, in
the events the run recorded against it.
"""

from __future__ import annotations

__all__ = ["MAP_HTML", "MAP_JS", "MAP_STYLE"]

MAP_STYLE = """
/* ---------------------------------------------------------------- the map */
#dmap{position:fixed;inset:0;z-index:70;display:none;flex-direction:column;
 background:var(--bg);background-image:linear-gradient(180deg,#f6f5f0 0,var(--bg) 22rem)}
#dmap.on{display:flex}
#dmap .map-top{flex:none;display:flex;align-items:center;gap:var(--s4);flex-wrap:wrap;
 padding:var(--s3) var(--s6);border-bottom:1px solid var(--line);background:var(--surface);
 box-shadow:var(--shadow)}
#dmap .map-top h2{font:400 1.16rem/1.2 var(--serif);margin:0;color:var(--navy);letter-spacing:-.012em}
#dmap .map-top h2 .of{font:600 var(--t-label)/1 var(--sans);letter-spacing:.1em;color:var(--ink-3);
 margin-left:.6rem;vertical-align:.12em;font-variant-numeric:tabular-nums}
#dmap .map-top .why{margin:.15rem 0 0;font-size:var(--t-xs);color:var(--ink-3)}
#dmap .map-tools{margin-left:auto;display:flex;align-items:center;gap:var(--s2);flex-wrap:wrap}
#dmap .zoom{display:inline-flex;align-items:center;gap:.15rem;border:1px solid var(--line-strong);
 border-radius:var(--radius-sm);background:var(--surface);overflow:hidden}
#dmap .zoom button{border:0;border-radius:0;box-shadow:none;padding:.4rem .6rem;background:transparent}
#dmap .zoom button:hover{background:var(--surface-2)}
#dmap .zoom .lvl{padding:0 .5rem;font-size:var(--t-xs);color:var(--ink-3);min-width:3.4rem;
 text-align:center;font-variant-numeric:tabular-nums}

#dmap .map-body{flex:1;min-height:0;display:flex}
#dmap .stage{flex:1;min-width:0;position:relative;overflow:hidden;cursor:grab;
 background:var(--bg)}
#dmap .stage.dragging{cursor:grabbing}
#dmap .pan{position:absolute;top:0;left:0;transform-origin:0 0}
#dmap .pan svg{position:absolute;top:0;left:0;pointer-events:none;overflow:visible}

/* A node of the design, as the blueprint places it. */
#dmap .mn{position:absolute;width:178px;padding:.45rem .55rem;border-radius:var(--radius-sm);
 background:var(--surface);border:1px solid var(--line);color:var(--ink-3);
 font-size:.82rem;line-height:1.3;text-align:left;box-shadow:none;
 transition:border-color .16s var(--ease),background .16s var(--ease),box-shadow .16s var(--ease)}
#dmap .mn .nm{display:block;color:var(--ink-2);font-weight:600;font-size:.84rem}
#dmap .mn .id{display:block;font-family:var(--mono);font-size:.7rem;color:var(--ink-4);
 margin-top:.1rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* Never reached: drawn as an outline, because a node a run did not touch is not a node
   that passed - the one distinction this whole view exists to make. */
#dmap .mn.notreached,#dmap .mn.pending{border-style:dashed;border-color:var(--line-soft);
 background:transparent;color:var(--ink-4)}
#dmap .mn.notreached .nm,#dmap .mn.pending .nm{color:var(--ink-4);font-weight:400}
#dmap .mn.used{border-color:var(--line-strong);background:var(--surface)}
#dmap .mn.used .nm{color:var(--ink)}
#dmap .mn.passed{border-color:var(--good);background:var(--good-soft);box-shadow:0 1px 2px rgba(47,107,98,.14)}
#dmap .mn.passed .nm{color:var(--good)}
#dmap .mn.failed{border-color:var(--bad);background:var(--bad-soft);box-shadow:0 1px 3px rgba(81,42,68,.2)}
#dmap .mn.failed .nm{color:var(--bad)}
#dmap .mn.active{border-color:var(--accent);background:var(--accent-soft)}
#dmap .mn.active .nm{color:var(--accent-ink)}
#dmap .mn.on{box-shadow:0 0 0 2px var(--accent),var(--shadow-lift)}
/* The order the run touched it in. A run is a sequence, and this is the only place the
   picture can say so. */
#dmap .mn .ord{position:absolute;top:-.55rem;left:-.55rem;min-width:1.25rem;height:1.25rem;
 padding:0 .25rem;border-radius:99px;background:var(--navy);color:#fff;font-size:.68rem;
 font-weight:700;display:none;place-items:center;font-variant-numeric:tabular-nums;
 box-shadow:0 1px 2px rgba(12,46,63,.3)}
#dmap .mn[data-ord] .ord{display:grid}
#dmap .mn.failed .ord{background:var(--bad)}
/* What a picked node is joined to, and what it is not. */
#dmap .mn.near{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent-line)}
#dmap.focused .mn:not(.on):not(.near){opacity:.4}
#dmap .mn.hit{box-shadow:0 0 0 2px var(--gold)}
/* The legend is how the colours are used, not a picture of them. */
#dmap .map-legend{display:flex;gap:.1rem;flex-wrap:wrap}
#dmap .map-legend button{display:inline-flex;align-items:center;gap:.4rem;border:0;
 background:transparent;box-shadow:none;padding:.3rem .5rem;font-weight:400;
 font-size:var(--t-xs);color:var(--ink-3)}
#dmap .map-legend button:hover{background:var(--surface-2);color:var(--navy)}
#dmap .map-legend button i{width:.6rem;height:.6rem;border-radius:2px;display:inline-block}
#dmap .map-legend button[aria-pressed="false"]{color:var(--ink-4);text-decoration:line-through}
#dmap.hide-passed .mn.passed,#dmap.hide-failed .mn.failed,#dmap.hide-active .mn.active,
#dmap.hide-used .mn.used,#dmap.hide-notreached .mn.notreached,#dmap.hide-notreached .mn.pending{
 opacity:.12}
#dmap .find{width:11rem;margin:0;padding:.4rem .6rem;font-size:var(--t-xs)}
#dmap .found{font-size:var(--t-xs);color:var(--ink-3);min-width:4.5rem}
#dmap .step{display:inline-flex;align-items:center;gap:.15rem;border:1px solid var(--line-strong);
 border-radius:var(--radius-sm);background:var(--surface);overflow:hidden}
#dmap .step button{border:0;border-radius:0;box-shadow:none;padding:.4rem .55rem;background:transparent}
#dmap .step button:hover{background:var(--surface-2)}
#dmap .step .at{padding:0 .5rem;font-size:var(--t-xs);color:var(--ink-3);min-width:4.6rem;
 text-align:center;font-variant-numeric:tabular-nums}
#dmap .chips{display:flex;flex-wrap:wrap;gap:.3rem;margin:.1rem 0 var(--s3)}
#dmap .chips button{padding:.25rem .5rem;font-size:var(--t-xs);font-weight:400;
 color:var(--accent-ink);border-color:var(--line)}
#dmap .chips button:hover{border-color:var(--accent);background:var(--accent-soft)}
#dmap .chips .none{font-size:var(--t-xs);color:var(--ink-4)}
#dmap .said{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);
 white-space:nowrap}
#dmap .mn:hover{box-shadow:var(--shadow-lift)}
/* Far out, a two-line label is a smudge: the id alone, in type that survives the scale. */
#dmap.far .mn{padding:.3rem .45rem}
#dmap.far .mn .nm{display:none}
#dmap.far .mn .id{font-size:1.45rem;line-height:1.15;color:var(--ink-2);margin:0;
 font-family:var(--sans);letter-spacing:-.01em}
#dmap.far .mn.notreached .id,#dmap.far .mn.pending .id{color:var(--ink-4)}
#dmap.far .mn.passed .id{color:var(--good)}
#dmap.far .mn .ord{min-width:2.1rem;height:2.1rem;font-size:1.2rem;top:-1rem;left:-1rem}
#dmap.far .mn.failed .id{color:var(--bad)}


#dmap.focused #dmap-edges path:not(.on){opacity:.12}
#dmap #dmap-edges path.on{stroke:var(--accent);stroke-width:2.4;stroke-opacity:.95}

#dmap .band{position:absolute;height:1px;background:var(--line);pointer-events:none}
#dmap .band.priv{background:var(--bad-line);height:2px}
#dmap .band-t{position:absolute;font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;
 color:var(--ink-4);pointer-events:none;white-space:nowrap;font-weight:600}
#dmap .band-t.priv{color:var(--bad)}

/* What happened in the node you picked. */
#dmap .side{flex:none;width:23rem;border-left:1px solid var(--line);background:var(--surface);
 display:flex;flex-direction:column;min-height:0}
#dmap .side .side-in{overflow:auto;padding:var(--s4) var(--s5) var(--s5)}
#dmap .side h3{font:400 1.05rem/1.25 var(--serif);margin:0;color:var(--navy)}
#dmap .side .idline{font-family:var(--mono);font-size:var(--t-xs);color:var(--ink-3);margin:.15rem 0 var(--s3)}
#dmap .side .ev{border-left:2px solid var(--line);padding:.35rem 0 .35rem .7rem;margin-bottom:.35rem}
#dmap .side .ev.bad{border-left-color:var(--bad)}
#dmap .side .ev .t{font-family:var(--mono);font-size:.74rem;color:var(--navy)}
#dmap .side .ev .m{display:block;font-size:var(--t-xs);color:var(--ink-3);line-height:1.45;margin-top:.1rem}
#dmap .side .when{float:right;font-size:.72rem;color:var(--ink-4);font-variant-numeric:tabular-nums}
@media (max-width:1100px){
 #dmap .side{display:none}
 #dmap.picked .side{display:flex;position:absolute;inset:auto 0 0 0;width:auto;max-height:55%;
  border-left:0;border-top:1px solid var(--line)}
}
"""

MAP_HTML = """
<div id="dmap" aria-hidden="true" role="dialog" aria-modal="true" aria-label="The whole design, painted with one run">
 <p class="said" id="dmap-said" role="status" aria-live="polite"></p>
 <div class="map-top">
  <div>
   <h2>The whole design<span class="of" id="dmap-count"></span></h2>
   <p class="why" id="dmap-why">Every node of the blueprint, in the blueprint's own positions, bordered by what this run did there.</p>
  </div>
  <div class="map-tools">
   <span class="map-legend" role="group" aria-label="Show or hide by what happened">
    <button data-act="mapFilter" data-state="passed" aria-pressed="true"><i style="background:var(--good-soft);box-shadow:inset 0 0 0 1px var(--good)"></i>passed</button>
    <button data-act="mapFilter" data-state="failed" aria-pressed="true"><i style="background:var(--bad-soft);box-shadow:inset 0 0 0 1px var(--bad)"></i>failed</button>
    <button data-act="mapFilter" data-state="active" aria-pressed="true"><i style="background:var(--accent-soft);box-shadow:inset 0 0 0 1px var(--accent)"></i>running</button>
    <button data-act="mapFilter" data-state="used" aria-pressed="true"><i style="background:var(--surface);box-shadow:inset 0 0 0 1px var(--line-strong)"></i>touched</button>
    <button data-act="mapFilter" data-state="notreached" aria-pressed="true"><i style="background:transparent;box-shadow:inset 0 0 0 1px var(--line-soft)"></i>never reached</button>
   </span>
   <input class="find" id="dmap-find" type="search" placeholder="Find a node" aria-label="Find a node by name or id">
   <span class="found" id="dmap-found"></span>
   <span class="step" role="group" aria-label="Step through what this run did">
    <button data-act="mapStep" data-by="-1" title="The step before (p)" aria-label="Previous node this run touched">&lsaquo;</button>
    <span class="at" id="dmap-at">step</span>
    <button data-act="mapStep" data-by="1" title="The next step (n)" aria-label="Next node this run touched">&rsaquo;</button>
   </span>
   <span class="zoom">
    <button data-act="mapZoom" data-by="-1" title="Zoom out" aria-label="Zoom out">&minus;</button>
    <span class="lvl" id="dmap-lvl">100%</span>
    <button data-act="mapZoom" data-by="1" title="Zoom in" aria-label="Zoom in">+</button>
   </span>
   <button data-act="mapFocus" title="Zoom to the part of the design this run went through">Where it ran</button>
   <button data-act="mapFit" title="The whole design at once">Fit all</button>
   <button class="primary" data-act="mapClose">Close</button>
  </div>
 </div>
 <div class="map-body">
  <div class="stage" id="dmap-stage">
   <div class="pan" id="dmap-pan"><svg id="dmap-edges"></svg></div>
  </div>
  <aside class="side" id="dmap-side"><div class="side-in" id="dmap-side-in"></div></aside>
 </div>
</div>
"""

MAP_JS = """
/* The whole design, painted with what one run did.

   Positions come from the blueprint through /api/graph, so this draws the design of record
   rather than a second layout of the same graph. What a run did comes from the trace it
   already has, and what happened inside a node is the events it recorded against it. */
let MAP_RUN = null, MAP_STATES = {}, MAP_EVENTS = {}, MAP_PICKED = null;
let MAP_K = 1, MAP_X = 0, MAP_Y = 0, MAP_BUILT = false, MAP_CAME_FROM = null;
/* The order the run touched things in, and what each node is joined to. */
let MAP_ORDER = [], MAP_SEQ = {};
const MAP_IN = {}, MAP_OUT = {}, MAP_LABEL = {}, MAP_NAME = {};
const MAP_PAD = 120;

async function openMap(runId, nodeId) {
  const g = await loadGraph();
  if (!g.nodes.length || g.nodes[0].x === null || g.nodes[0].x === undefined) {
    return say('The blueprint has no positions in this build - re-export it with tools/export_architecture.py.', 'bad');
  }
  MAP_RUN = runId;
  const run = RUNS.find(r => r.run_id === runId) || {};
  $('dmap-why').textContent = (run.client ? run.client + ' — ' : '') + runId
    + ': every node of the design, bordered by what this run did there.';
  const trace = LAST_TRACE && LAST_TRACE.nodes ? LAST_TRACE
    : await get(`/api/runs/${encodeURIComponent(runId)}/trace`).catch(() => ({nodes: {}}));
  MAP_STATES = trace.nodes || {};
  MAP_EVENTS = {};
  const events = await get(`/api/runs/${encodeURIComponent(runId)}/events`).catch(() => []);
  for (const e of events) (MAP_EVENTS[e.node_id] = MAP_EVENTS[e.node_id] || []).push(e);
  // The order it went through them: first time each node was written against. A run is a
  // sequence and the drawing is not, so this is the only place the picture can say so.
  MAP_ORDER = Object.keys(MAP_EVENTS)
    .filter(id => id && (MAP_STATES[id] || 'notreached') !== 'notreached')
    .sort((a, b) => String(MAP_EVENTS[a][0].ts).localeCompare(String(MAP_EVENTS[b][0].ts)));
  MAP_SEQ = {};
  MAP_ORDER.forEach((id, i) => { MAP_SEQ[id] = i + 1; });
  if (!MAP_BUILT) buildMap(g);
  paintMap(trace);
  $('dmap').classList.add('on');
  $('dmap').setAttribute('aria-hidden', 'false');
  history.replaceState(null, '', mapHash(runId, nodeId));
  document.addEventListener('keydown', mapKeys);
  MAP_CAME_FROM = document.activeElement;
  const find = $('dmap-find');
  if (find) { find.value = ''; mapFind(); find.focus(); }
  // Not the whole canvas: the part this run actually went through, at a size its labels
  // can be read at. "Fit all" is the other question, and it is one button away.
  mapFocus();
  pickNode(nodeId && $('mn-' + nodeId) ? nodeId : null);
}

/* A link to a run's map, or to one node of it: what somebody pastes into a message when
   the question is "look at where this stopped". */
function mapHash(runId, nodeId) {
  return '#map=' + encodeURIComponent(runId) + (nodeId ? '/' + encodeURIComponent(nodeId) : '');
}

function closeMap() {
  $('dmap').classList.remove('on');
  $('dmap').setAttribute('aria-hidden', 'true');
  document.removeEventListener('keydown', mapKeys);
  // Back where it came from: a reader who opened this from the keyboard is otherwise left
  // at the top of the page with nothing selected.
  if (MAP_CAME_FROM && MAP_CAME_FROM.focus) MAP_CAME_FROM.focus();
  if (MAP_RUN) history.replaceState(null, '', '#' + encodeURIComponent(MAP_RUN));
}

function mapKeys(e) {
  if (e.key === 'Escape') return closeMap();
  if (e.target && e.target.closest('input,textarea,select')) return;
  const step = e.shiftKey ? 240 : 80;
  const moves = {ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step]};
  if (moves[e.key]) { e.preventDefault(); MAP_X += moves[e.key][0]; MAP_Y += moves[e.key][1]; mapApply(); }
  if (e.key === '+' || e.key === '=') { e.preventDefault(); mapZoom(1); }
  if (e.key === '-') { e.preventDefault(); mapZoom(-1); }
  if (e.key === '0') { e.preventDefault(); mapFit(); }
  if (e.key === 'n' || e.key === ']') { e.preventDefault(); mapStep(1); }
  if (e.key === 'p' || e.key === '[') { e.preventDefault(); mapStep(-1); }
  if (e.key === '/') { e.preventDefault(); $('dmap-find').focus(); }
  if (e.key === 'Tab') mapTrap(e);
}

/* The map covers the screen, so Tab belongs in it: tabbing out lands on a page nobody can
   see, which is worse than having no focus at all. */
function mapTrap(e) {
  const stops = [...$('dmap').querySelectorAll(
    'button:not([tabindex="-1"]),input,[tabindex="0"]')].filter(el => el.offsetParent !== null);
  if (!stops.length) return;
  const first = stops[0], last = stops[stops.length - 1];
  if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
}

/* Through the run, in the order it happened. The whole point of a sequence is being able
   to walk it. */
function mapStep(by) {
  if (!MAP_ORDER.length) return say('This run touched nothing to step through.', 'warn');
  const at = MAP_PICKED ? MAP_ORDER.indexOf(MAP_PICKED) : -1;
  const next = at === -1 ? (by > 0 ? 0 : MAP_ORDER.length - 1)
    : (at + by + MAP_ORDER.length) % MAP_ORDER.length;
  pickNode(MAP_ORDER[next]);
}

/* One of 118 nodes, by name, id or group. */
function mapFind() {
  const q = ($('dmap-find').value || '').trim().toLowerCase();
  let hits = 0;
  document.querySelectorAll('#dmap .mn').forEach(el => {
    const hit = Boolean(q) && el.dataset.search.includes(q);
    el.classList.toggle('hit', hit);
    if (hit) hits++;
  });
  $('dmap-found').textContent = q ? (hits ? hits + ' found' : 'none') : '';
  return hits;
}

function mapFindEnter() {
  const first = document.querySelector('#dmap .mn.hit');
  if (first) pickNode(first.dataset.node);
}

/* Built once: 118 nodes and 240 edges do not change between runs - only their colours do. */
function buildMap(g) {
  const pan = $('dmap-pan'), svg = $('dmap-edges');
  const at = {};
  g.nodes.forEach(n => { at[n.id] = n; });
  const width = Math.max(...g.nodes.map(n => n.x)) + 178 + MAP_PAD;
  const height = Math.max(...g.nodes.map(n => n.y)) + 90 + MAP_PAD;
  pan.style.width = width + 'px';
  pan.style.height = height + 'px';
  svg.setAttribute('width', width);
  svg.setAttribute('height', height);
  MAP_SIZE.w = width;
  MAP_SIZE.h = height;

  const layout = g.layout || {};
  (layout.bands || []).forEach(b => {
    const rule = document.createElement('div');
    rule.className = 'band' + (b.privacy ? ' priv' : '');
    rule.style.cssText = `left:20px;top:${b.y}px;width:${width - 60}px`;
    pan.appendChild(rule);
    const label = document.createElement('div');
    label.className = 'band-t' + (b.privacy ? ' priv' : '');
    label.style.cssText = `left:262px;top:${b.y + 6}px`;
    label.textContent = b.label;
    pan.appendChild(label);
  });
  (layout.columns || []).forEach(c => {
    const label = document.createElement('div');
    label.className = 'band-t';
    label.style.cssText = `left:${c.x}px;top:${c.y + 6}px`;
    label.textContent = c.label;
    pan.appendChild(label);
  });

  /* An edge leaves the side of a box when the two are mostly apart, and the top or bottom
     when one is mostly above the other - the blueprint's own rule, so the picture reads
     the same way in both places. */
  const NH = 52;
  (g.edges || []).forEach((e, i) => {
    const a = at[e.from], b = at[e.to];
    if (!a || !b) return;
    const ax = a.x + 89, ay = a.y + NH / 2, bx = b.x + 89, by = b.y + NH / 2;
    const dx = bx - ax, dy = by - ay;
    let d;
    if (Math.abs(dx) > Math.abs(dy) * 1.15 || Math.abs(dx) > 430) {
      const x1 = dx > 0 ? a.x + 178 : a.x, x2 = dx > 0 ? b.x : b.x + 178, m = (x1 + x2) / 2;
      d = `M${x1},${ay} C${m},${ay} ${m},${by} ${x2},${by}`;
    } else if (dy > 0) {
      const y1 = a.y + NH, y2 = b.y, m = (y1 + y2) / 2;
      d = `M${ax},${y1} C${ax},${m} ${bx},${m} ${bx},${y2}`;
    } else {
      const y1 = a.y, y2 = b.y + NH, m = (y1 + y2) / 2;
      d = `M${ax},${y1} C${ax},${m} ${bx},${m} ${bx},${y2}`;
    }
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', d);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke-linecap', 'round');
    path.id = 'me-' + i;
    path.dataset.from = e.from;
    path.dataset.to = e.to;
    if (e.kind === 'port' || e.kind === 'gov') path.setAttribute('stroke-dasharray', '5 5');
    svg.appendChild(path);
    (MAP_OUT[e.from] = MAP_OUT[e.from] || []).push(e.to);
    (MAP_IN[e.to] = MAP_IN[e.to] || []).push(e.from);
    MAP_LABEL[e.from + '>' + e.to] = e.label || '';
  });

  g.nodes.forEach(n => {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = 'mn';
    el.id = 'mn-' + n.id;
    el.style.cssText = `left:${n.x}px;top:${n.y}px`;
    el.dataset.act = 'mapPick';
    el.dataset.node = n.id;
    el.title = n.plain || n.label;
    el.dataset.search = `${n.label} ${n.id} ${n.group || ''}`.toLowerCase();
    el.innerHTML = `<span class="ord" aria-hidden="true"></span>`
      + `<span class="nm">${esc(n.label)}</span><span class="id">${esc(n.id)}</span>`;
    pan.appendChild(el);
    MAP_NAME[n.id] = n.label;
  });
  MAP_BUILT = true;
}

const MAP_SIZE = {w: 2600, h: 2900};

/* The colours, from the trace this run recorded. Everything else stays outlined. */
function paintMap(trace) {
  const states = (trace && trace.nodes) || {};
  let touched = 0;
  const says = {passed: 'passed', failed: 'failed', active: 'running',
    used: 'went through', notreached: 'never reached', pending: 'not reached yet'};
  document.querySelectorAll('#dmap .mn').forEach(el => {
    const id = el.id.slice(3);
    const state = states[id] || 'notreached';
    const went = state !== 'notreached' && state !== 'pending';
    el.className = 'mn ' + state + (MAP_PICKED === id ? ' on' : '');
    if (MAP_SEQ[id]) el.dataset.ord = MAP_SEQ[id]; else delete el.dataset.ord;
    el.querySelector('.ord').textContent = MAP_SEQ[id] || '';
    // A hundred and eighteen tab stops is not navigation. The keyboard goes to what the
    // run touched; the rest are reachable by the find box.
    el.tabIndex = went ? 0 : -1;
    el.setAttribute('aria-label',
      `${MAP_NAME[id] || id}, ${says[state] || state}` + (MAP_SEQ[id] ? `, step ${MAP_SEQ[id]}` : ''));
    if (went) touched++;
  });
  document.querySelectorAll('#dmap-edges path').forEach(p => {
    const a = states[p.dataset.from], b = states[p.dataset.to];
    const live = a && b && a !== 'notreached' && b !== 'notreached' && a !== 'pending' && b !== 'pending';
    const failed = a === 'failed' || b === 'failed';
    p.setAttribute('stroke', failed ? 'var(--bad)' : live ? 'var(--accent)' : 'var(--line)');
    p.setAttribute('stroke-width', live ? 1.8 : 1);
    p.setAttribute('stroke-opacity', live ? .75 : .32);
  });
  const drawn = document.querySelectorAll('#dmap .mn').length;
  const off = Object.entries(states).filter(([id, st]) =>
    st !== 'notreached' && st !== 'pending' && !$('mn-' + id)).length;
  $('dmap-count').textContent = touched + ' of ' + drawn + ' touched'
    + (off ? ' \u00b7 ' + off + ' not on this map' : '');
}

/* What happened in one node: the state the trace gave it, what the blueprint says it is
   for, and every event this run recorded against it. */
async function pickNode(id) {
  MAP_PICKED = id;
  const near = new Set([...(MAP_IN[id] || []), ...(MAP_OUT[id] || [])]);
  document.querySelectorAll('#dmap .mn').forEach(el => {
    el.classList.toggle('on', el.id === 'mn-' + id);
    el.classList.toggle('near', near.has(el.id.slice(3)));
  });
  // The hairball is 240 edges at one weight. Picking a node draws the ones it is on and
  // lets the rest fall back, which is the only way to read what feeds what.
  $('dmap').classList.toggle('focused', Boolean(id));
  document.querySelectorAll('#dmap-edges path').forEach(path => {
    path.classList.toggle('on', Boolean(id) && (path.dataset.from === id || path.dataset.to === id));
  });
  const said = $('dmap-said');
  if (said && id) {
    said.textContent = `${MAP_NAME[id] || id}, ${MAP_STATES[id] || 'never reached'}`
      + (MAP_SEQ[id] ? `, step ${MAP_SEQ[id]} of ${MAP_ORDER.length}` : '');
  }
  const at = $('dmap-at');
  if (at) at.textContent = id && MAP_SEQ[id] ? `${MAP_SEQ[id]} of ${MAP_ORDER.length}`
    : (MAP_ORDER.length ? `${MAP_ORDER.length} steps` : 'step');
  if (MAP_RUN) history.replaceState(null, '', mapHash(MAP_RUN, id));
  const chosen = id ? $('mn-' + id) : null;
  if (chosen) {
    // Bring it under the eye rather than leaving the reader to find it on a canvas the
    // size of a wall.
    const stage = $('dmap-stage').getBoundingClientRect();
    const x = parseFloat(chosen.style.left), y = parseFloat(chosen.style.top);
    MAP_X = stage.width / 2 - (x + 89) * MAP_K;
    MAP_Y = stage.height / 2 - (y + 26) * MAP_K;
    mapApply();
  }
  $('dmap').classList.toggle('picked', Boolean(id));
  const box = $('dmap-side-in');
  if (!id) {
    const g0 = await loadGraph();
    const named = {};
    (g0.nodes || []).forEach(n => { named[n.id] = n.label; });
    const onCanvas = new Set((g0.nodes || []).map(n => n.id));
    // In the order it happened, not in the order a dictionary put them: the first
    // question of a run is what it did, then, and then.
    const ordered = MAP_ORDER.map(nodeId => [nodeId, MAP_STATES[nodeId]]);
    const rest = Object.entries(MAP_STATES)
      .filter(([nodeId, state]) => state !== 'notreached' && state !== 'pending' && !MAP_SEQ[nodeId]);
    // The numbers run across everything the run recorded, so a number missing from the
    // list below is one of the names further down, not a hole.
    const reached = [...ordered, ...rest];
    const went = reached.filter(([nodeId]) => onCanvas.has(nodeId));
    // Recorded against a node the design of record does not have. Not dropped: dropping it
    // is how a drawing and a system come to disagree without anybody noticing.
    const stray = reached.filter(([nodeId]) => !onCanvas.has(nodeId));
    box.innerHTML = went.length
      ? `<h3>Where this run went</h3>
         <p class="idline">${went.length} of ${(g0.nodes || []).length} nodes &middot; pick one for what happened there</p>`
        + went.map(([nodeId, state]) => `<div class="r pick" data-act="mapPick" data-node="${esc(nodeId)}" role="button" tabindex="0">
            <span class="lbl"><b>${MAP_SEQ[nodeId] ? esc(MAP_SEQ[nodeId]) + '. ' : ''}${esc(named[nodeId] || nodeId)}</b><span class="sub" style="display:block">${esc(nodeId)}${
              (MAP_EVENTS[nodeId] || []).length ? ' &middot; ' + esc(String(MAP_EVENTS[nodeId][0].ts).slice(11, 19)) : ''}</span></span>
            <span class="pill ${state === 'passed' ? 'good' : state === 'failed' ? 'bad' : state === 'active' ? 'accent' : ''}"><i class="dot"></i>${esc(state)}</span>
           </div>`).join('')
      : `<div class="empty"><b>Nothing ran</b>This run touched no node of the design - it was
         refused or replaced before it started. Every box is still here, outlined.</div>`;
    if (stray.length) {
      box.innerHTML += `<div class="section-label">Not on this map</div>
        <p class="note" style="margin-top:0">This run recorded work against
         ${plural(stray.length, 'name', 'names')} the design of record has no node for.
         That is a difference between the system and its blueprint, not a gap in the drawing.</p>`
        + stray.map(([nodeId, state]) => `<div class="r">
            <span class="lbl"><b class="mono">${MAP_SEQ[nodeId] ? esc(MAP_SEQ[nodeId]) + '. ' : ''}${esc(nodeId)}</b></span>
            <span class="pill ${state === 'failed' ? 'bad' : ''}"><i class="dot"></i>${esc(state)}</span>
           </div>`).join('');
    }
    return;
  }
  const g = await loadGraph();
  const node = (g.nodes || []).find(n => n.id === id) || {id, label: id};
  const state = MAP_STATES[id] || 'notreached';
  const says = {passed: 'passed here', failed: 'failed here', active: 'running here',
    used: 'went through here', notreached: 'never reached this', pending: 'has not reached this yet'};
  const events = MAP_EVENTS[id] || [];
  const diagnostic = ((LAST_TRACE || {}).diagnostics || {})[id];
  box.innerHTML = `<h3>${esc(node.label)}</h3>
    <p class="idline">${esc(node.id)}${node.exec ? ' &middot; ' + esc(node.exec) : ''}${node.group ? ' &middot; ' + esc(node.group) : ''}</p>
    <div class="r" style="border:0;padding:0 0 .6rem"><span class="pill ${
      state === 'passed' ? 'good' : state === 'failed' ? 'bad' : state === 'active' ? 'accent' : ''
    }"><i class="dot"></i>${esc(says[state] || state)}</span></div>
    ${node.plain ? `<p class="note" style="margin-top:0">${esc(node.plain)}</p>` : ''}
    ${events.length ? `<p class="idline" style="margin:.4rem 0 0">${plural(events.length, 'event', 'events')}
      &middot; ${esc(String(events[0].ts).slice(11, 19))}${events.length > 1
        ? '&ndash;' + esc(String(events[events.length - 1].ts).slice(11, 19)) : ''}${
        MAP_SEQ[id] ? ' &middot; step ' + esc(MAP_SEQ[id]) + ' of ' + esc(MAP_ORDER.length) : ''}</p>` : ''}
    <div class="section-label">What it is joined to</div>
    <div class="chips">${
      (MAP_IN[id] || []).length
        ? (MAP_IN[id] || []).map(from => `<button data-act="mapPick" data-node="${esc(from)}"
            title="${esc(MAP_LABEL[from + '>' + id] || 'feeds this node')}">&larr; ${esc(MAP_NAME[from] || from)}</button>`).join('')
        : '<span class="none">nothing feeds this node</span>'}</div>
    <div class="chips">${
      (MAP_OUT[id] || []).length
        ? (MAP_OUT[id] || []).map(to => `<button data-act="mapPick" data-node="${esc(to)}"
            title="${esc(MAP_LABEL[id + '>' + to] || 'this node feeds it')}">&rarr; ${esc(MAP_NAME[to] || to)}</button>`).join('')
        : '<span class="none">this node feeds nothing</span>'}</div>
    ${diagnostic ? `<div class="diag"><div class="d-row"><span class="code">${esc(diagnostic.code || '')}</span>
      <span class="msg">${esc(diagnostic.message || diagnostic.detail || '')}</span></div></div>` : ''}
    <div class="section-label">What happened here</div>
    ${events.length ? events.map(e => `<div class="ev${String(e.type).endsWith('fail') ? ' bad' : ''}">
        <span class="when">${esc((e.ts || '').slice(11, 19))}</span>
        <span class="t">${esc(e.type)}</span>
        ${e.message ? `<span class="m">${esc(e.message)}</span>` : ''}</div>`).join('')
      : `<p class="note" style="margin-top:0">This run recorded nothing against this node.</p>`}`;
}

/* Pan, zoom, fit. */
function mapApply() {
  $('dmap-pan').style.transform = `translate(${MAP_X}px,${MAP_Y}px) scale(${MAP_K})`;
  $('dmap-lvl').textContent = Math.round(MAP_K * 100) + '%';
  $('dmap').classList.toggle('far', MAP_K < .52);
}

function mapZoom(by, at) {
  const stage = $('dmap-stage').getBoundingClientRect();
  const cx = at ? at.x - stage.left : stage.width / 2;
  const cy = at ? at.y - stage.top : stage.height / 2;
  const next = Math.min(2.4, Math.max(.12, MAP_K * (by > 0 ? 1.22 : 1 / 1.22)));
  // Keep whatever is under the pointer (or the middle) where it is while the scale changes.
  MAP_X = cx - (cx - MAP_X) * (next / MAP_K);
  MAP_Y = cy - (cy - MAP_Y) * (next / MAP_K);
  MAP_K = next;
  mapApply();
}

/* The bounding box of everything this run touched, with room around it. A run that
   touched nothing - one that never started - falls back to the whole design. */
function mapFocus() {
  const touched = [];
  document.querySelectorAll('#dmap .mn').forEach(el => {
    const state = MAP_STATES[el.id.slice(3)];
    if (state && state !== 'notreached' && state !== 'pending') {
      touched.push({x: parseFloat(el.style.left), y: parseFloat(el.style.top)});
    }
  });
  if (touched.length < 2) return mapFit();
  const pad = 140;
  const x0 = Math.min(...touched.map(n => n.x)) - pad;
  const y0 = Math.min(...touched.map(n => n.y)) - pad;
  const x1 = Math.max(...touched.map(n => n.x)) + 178 + pad;
  const y1 = Math.max(...touched.map(n => n.y)) + 52 + pad;
  const stage = $('dmap-stage').getBoundingClientRect();
  MAP_K = Math.min(1.15, Math.max(.3, Math.min(stage.width / (x1 - x0), stage.height / (y1 - y0))));
  MAP_X = (stage.width - (x1 - x0) * MAP_K) / 2 - x0 * MAP_K;
  MAP_Y = (stage.height - (y1 - y0) * MAP_K) / 2 - y0 * MAP_K;
  mapApply();
}

function mapFit() {
  const stage = $('dmap-stage').getBoundingClientRect();
  MAP_K = Math.min(stage.width / MAP_SIZE.w, stage.height / MAP_SIZE.h) * .96;
  MAP_X = (stage.width - MAP_SIZE.w * MAP_K) / 2;
  MAP_Y = (stage.height - MAP_SIZE.h * MAP_K) / 2;
  mapApply();
}

ACTIONS.map = d => openMap(d.run);
ACTIONS.mapClose = () => closeMap();
ACTIONS.mapFit = () => mapFit();
ACTIONS.mapFocus = () => mapFocus();
ACTIONS.mapZoom = d => mapZoom(Number(d.by));
ACTIONS.mapPick = d => pickNode(d.node);
ACTIONS.mapStep = d => mapStep(Number(d.by));
ACTIONS.mapFilter = (d, el) => {
  const showing = el.getAttribute('aria-pressed') !== 'false';
  el.setAttribute('aria-pressed', showing ? 'false' : 'true');
  $('dmap').classList.toggle('hide-' + d.state, showing);
};

(function mapFindBox() {
  const box = $('dmap-find');
  if (!box) return;
  box.addEventListener('input', mapFind);
  box.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); mapFindEnter(); }
    if (e.key === 'Escape') { box.value = ''; mapFind(); box.blur(); }
  });
})();

(function mapDrag() {
  const stage = $('dmap-stage');
  if (!stage) return;
  let from = null, moved = false;
  stage.addEventListener('pointerdown', e => {
    if (e.target.closest('.mn')) return;
    from = {x: e.clientX - MAP_X, y: e.clientY - MAP_Y};
    moved = false;
    stage.classList.add('dragging');
    stage.setPointerCapture(e.pointerId);
  });
  stage.addEventListener('pointermove', e => {
    if (!from) return;
    if (Math.abs(e.clientX - from.x - MAP_X) > 3 || Math.abs(e.clientY - from.y - MAP_Y) > 3) moved = true;
    MAP_X = e.clientX - from.x;
    MAP_Y = e.clientY - from.y;
    mapApply();
  });
  const done = () => {
    // A click on the paper rather than on a node: back to the whole run, which is what
    // "nothing in particular" means here.
    if (from && !moved && MAP_PICKED) pickNode(null);
    from = null;
    moved = false;
    stage.classList.remove('dragging');
  };
  stage.addEventListener('pointerup', done);
  stage.addEventListener('pointercancel', done);
  stage.addEventListener('wheel', e => {
    e.preventDefault();
    mapZoom(e.deltaY < 0 ? 1 : -1, {x: e.clientX, y: e.clientY});
  }, {passive: false});
})();
"""
