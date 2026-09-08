"""FastAPI plus server-sent events over the event bus.

`Console` is the reader: every surface on it is a pure function of the run store and
the bus, computed on request, so the process holds nothing a run needs. `create_app`
mounts it. The stream endpoint replays a run's recorded events from `since` and then,
if the run is still going, follows the bus live; a completed run replays and closes. Both
halves go through the same `TraceReducer`, which is what "replays a completed run from
the event stream alone" means in code.

A subscriber that raises is dropped by the bus, and a client that goes away is detected
on the next tick. Neither reaches the run.
"""

# ruff: noqa: E501 - the one-page browser client at the foot of this file is a string.
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from ops.analytics import Analytics
from ops.blobs import ContentRef, ContentStore
from ops.console.analytics_page import PAGE as ANALYTICS_PAGE
from ops.console.trace import Trace, TraceReducer
from ops.cost import CostMeter
from ops.drift import DriftMonitor
from ops.events import EventBus
from ops.run_store import EventRecord, RunRecord, RunStore
from ops.scorecard import RunScorecard
from ops.stall import StallDetector
from registries.constraints import ConstraintRegistry
from ui import CSS, SHELL
from ui.theme import shell

__all__ = ["Console", "create_app"]

KEEPALIVE_S = 1.0
TERMINAL_TYPES = frozenset({"run.manifest.written"})


class QueueView(Protocol):
    """What the console asks the worker pool: where a run stands, and how full the
    pool is. A Protocol so `ops/` never imports `workers/`; the pool satisfies it."""

    def placement(self, run_id: str) -> Any | None: ...
    def placements(self) -> list[Any]: ...
    def pressure(self) -> Any: ...


class Console:
    """Everything the dashboard shows, computed from the record on request."""

    def __init__(
        self,
        store: RunStore,
        bus: EventBus,
        *,
        constraints: ConstraintRegistry | None = None,
        clock: Callable[[], datetime] | None = None,
        scope_of: Callable[[str], str | None] | None = None,
        human_baseline_override_rate: float | None = None,
        queue: QueueView | None = None,
        blobs: ContentStore | None = None,
    ) -> None:
        self.store = store
        self.bus = bus
        self.queue = queue
        self.blobs = blobs
        constraints = constraints or ConstraintRegistry.load()
        self.scorecard = RunScorecard(store, bus, constraints)
        self.meter = CostMeter(store)
        self.stall = StallDetector(store, bus, constraints=constraints, clock=clock)
        self.drift = DriftMonitor(store, scope_of=scope_of)
        self.analytics = Analytics(
            store,
            meter=self.meter,
            drift=self.drift,
            stall=self.stall,
            scope_of=scope_of,
            human_baseline_override_rate=human_baseline_override_rate,
            clock=clock,
        )

    # -- the live feed

    def runs(self, engagement_id: str | None = None) -> list[dict[str, Any]]:
        rows = []
        for run in self.store.runs(engagement_id):
            events = self.store.events(run.run_id)
            rows.append(
                {
                    **_run_row(run),
                    "events": len(events),
                    "last_event": events[-1].type if events else None,
                    "last_ts": events[-1].ts if events else run.started_at,
                    "open_review_items": sum(
                        1 for i in self.store.review_items(run.run_id) if i.state == "open"
                    ),
                    "queue": self._placement(run.run_id),
                }
            )
        return rows

    def run(self, run_id: str) -> dict[str, Any]:
        record = self.store.run(run_id)
        card = self.scorecard.score(run_id)
        spend = self.meter.spend(run_id)
        return {
            **_run_row(record),
            "scorecard": {**card.as_dict(), "in_progress": card.in_progress},
            "spend": {
                "usd": spend.usd,
                "model_calls": spend.model_calls,
                "tokens": spend.tokens,
                "active_seconds": spend.active_seconds,
                "loop_iterations": spend.loop_iterations,
            },
            "cost": self.meter.breakdown(run_id).as_dict(),
            "steps": [
                {
                    "step_id": s.step_id,
                    "kind": s.kind,
                    "skill": s.skill,
                    "status": str(s.status),
                    "attempts": s.attempts,
                }
                for s in self.store.steps(run_id)
            ],
            "trace": self.replay(run_id).as_dict(),
            "queue": self._placement(run_id),
        }

    def queue_view(self) -> dict[str, Any]:
        """The pool: how full it is, and every run that is waiting with its position.
        Without a pool attached the console can only say so."""
        if self.queue is None:
            return {"pressure": None, "waiting": [], "attached": False}
        waiting = [p.as_dict() for p in self.queue.placements() if p.waiting_on]
        waiting.sort(key=lambda p: (p["waiting_on"], p["position"]))
        return {"pressure": self.queue.pressure().as_dict(), "waiting": waiting, "attached": True}

    def _placement(self, run_id: str) -> dict[str, Any] | None:
        if self.queue is None:
            return None
        placed = self.queue.placement(run_id)
        return placed.as_dict() if placed is not None else None

    def events(self, run_id: str, since: int = 0) -> tuple[EventRecord, ...]:
        return self.bus.stream(run_id, since)

    def replay(self, run_id: str, since: int = 0) -> Trace:
        """The trace from the recorded stream and nothing else."""
        planned = (s.step_id for s in self.store.steps(run_id))
        return TraceReducer(run_id, planned).fold(self.bus.stream(run_id, since))

    def finished(self, run_id: str) -> bool:
        run = self.store.run(run_id)
        return run.is_finished and any(
            e.type in TERMINAL_TYPES for e in self.store.events(run.run_id)
        )

    # -- the strips and the inbox

    def guard_strip(self) -> list[dict[str, Any]]:
        """The latest verdict of every guard on every unfinished run."""
        rows = []
        for run in self.store.runs():
            if run.is_finished:
                continue
            latest: dict[str, EventRecord] = {}
            for e in self.store.events(run.run_id):
                if e.level == "guard":
                    latest[e.type.split(".", 1)[1].rsplit(".", 1)[0]] = e
            for guard, e in sorted(latest.items()):
                rows.append(
                    {
                        "run_id": run.run_id,
                        "guard": guard,
                        "result": e.type.rsplit(".", 1)[1],
                        "checked": e.payload.get("checked"),
                        "failed": e.payload.get("failed"),
                        "at": e.ts,
                        "diagnostic_code": e.diagnostic_code,
                    }
                )
        return rows

    def inbox(self, engagement_id: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "run_id": i.run_id,
                "item_id": i.item_id,
                "kind": i.kind,
                "subject": i.subject,
                "owner": i.owner,
                "due_at": i.due_at,
                "created_at": i.created_at,
                "skill": i.detail.get("skill"),
                "severity": i.detail.get("severity"),
            }
            for i in self.store.open_review_items(engagement_id)
        ]

    def alerts(self, engagement_id: str | None = None) -> list[dict[str, Any]]:
        return [a.as_dict() for a in self.stall.scan(engagement_id)]

    def run_plan(self, run_id: str) -> dict[str, Any] | None:
        """The Run Plan artifact, read back from the content store.

        The plan is written down before execution begins, so this answers "what is it
        about to do" as well as "what did it do". None when no plan was recorded, or when
        the console was built without a content store to read it from - the console holds
        nothing itself, here as everywhere.
        """
        if self.blobs is None:
            return None
        found = [a for a in self.store.artifacts(run_id) if a.name == "run_plan"]
        if not found:
            return None
        ref = ContentRef(
            content_hash=found[-1].content_hash, media_type="application/json", name="run_plan"
        )
        return json.loads(self.blobs.get(ref).decode("utf-8"))  # type: ignore[no-any-return]

    def artifacts(self, run_id: str) -> list[dict[str, Any]]:
        return [
            {"name": a.name, "content_hash": a.content_hash, "written_at": a.written_at}
            for a in self.store.artifacts(run_id)
        ]


def create_app(console: Console) -> FastAPI:
    app = FastAPI(title="Chartwell Automated Analyst - ops console", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return PAGE

    @app.get("/api/runs")
    def runs(engagement_id: str | None = None) -> list[dict[str, Any]]:
        return console.runs(engagement_id)

    @app.get("/api/runs/{run_id}")
    def run(run_id: str) -> dict[str, Any]:
        _known(console, run_id)
        return console.run(run_id)

    @app.get("/api/runs/{run_id}/events")
    def events(run_id: str, since: int = 0) -> list[dict[str, Any]]:
        _known(console, run_id)
        return [_event_dict(e) for e in console.events(run_id, since)]

    @app.get("/api/graph")
    def graph() -> dict[str, Any]:
        """The nodes a trace refers to, so the console can paint all of them.

        Read from `graph/architecture.json`, which is exported from the blueprint - so the
        picture is of the design of record rather than of a diagram somebody kept beside
        it. Labels and plain-language descriptions only: the console draws what a run did,
        and the reasoning behind each node lives in the blueprint.
        """
        from graph.architecture_assertions import load_graph

        loaded = load_graph()
        return {
            "nodes": [
                {
                    "id": n["id"],
                    "label": n.get("label", n["id"]),
                    "group": n.get("group", ""),
                    "plain": n.get("plain", ""),
                    "runtime": n.get("runtime", ""),
                }
                for n in loaded.nodes.values()
            ]
        }

    @app.get("/api/runs/{run_id}/trace")
    def trace(run_id: str) -> dict[str, Any]:
        _known(console, run_id)
        return console.replay(run_id).as_dict()

    @app.get("/api/runs/{run_id}/scorecard")
    def scorecard(run_id: str) -> dict[str, Any]:
        _known(console, run_id)
        card = console.scorecard.score(run_id)
        return {**card.as_dict(), "in_progress": card.in_progress, "report": card.report()}

    @app.get("/api/runs/{run_id}/artifacts")
    def artifacts(run_id: str) -> list[dict[str, Any]]:
        _known(console, run_id)
        return console.artifacts(run_id)

    @app.get("/api/runs/{run_id}/stream")
    async def stream(
        run_id: str, request: Request, since: int = 0, follow: bool = True
    ) -> StreamingResponse:
        _known(console, run_id)
        return StreamingResponse(
            _sse(console, run_id, request, since, follow),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/runs/{run_id}/plan")
    def run_plan(run_id: str) -> dict[str, Any]:
        _known(console, run_id)
        plan = console.run_plan(run_id)
        if plan is None:
            raise HTTPException(status_code=404, detail=f"no run plan recorded for {run_id!r}")
        return plan

    @app.get("/api/queue")
    def queue() -> dict[str, Any]:
        return console.queue_view()

    @app.get("/api/guards")
    def guards() -> list[dict[str, Any]]:
        return console.guard_strip()

    @app.get("/api/review")
    def review(engagement_id: str | None = None) -> list[dict[str, Any]]:
        return console.inbox(engagement_id)

    @app.get("/api/alerts")
    def alerts(engagement_id: str | None = None) -> list[dict[str, Any]]:
        return console.alerts(engagement_id)

    @app.get("/api/cost/{engagement_id}")
    def cost(engagement_id: str) -> dict[str, Any]:
        return console.meter.rollup(engagement_id).as_dict()

    @app.get("/analytics", response_class=HTMLResponse)
    def analytics_page() -> str:
        """The four questions that decide whether the project continues.

        A second page rather than a tab: the live console answers "what is happening now"
        and this answers "across every run, is it working". They are read at different
        times, by people asking different things.
        """
        return ANALYTICS_PAGE

    @app.get("/api/analytics")
    def analytics(days: int = 30) -> dict[str, Any]:
        return console.analytics.overview(days=days).as_dict()

    @app.get("/api/drift")
    def drift() -> dict[str, Any]:
        return console.drift.report().as_dict()

    return app


async def _sse(
    console: Console, run_id: str, request: Request, since: int, follow: bool
) -> AsyncIterator[bytes]:
    """Replay from the record, then follow the bus. One reducer, both halves."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    reducer = TraceReducer(run_id, (s.step_id for s in console.store.steps(run_id)))

    def on_event(event: dict[str, Any]) -> None:
        if event.get("run_id") == run_id:
            loop.call_soon_threadsafe(queue.put_nowait, event)

    following = follow and not console.finished(run_id)
    if following:
        console.bus.subscribe(on_event)
    try:
        last = since
        for record in console.events(run_id, since):
            reducer.apply(record)
            yield _frame(record.type, str(record.seq), _event_dict(record), reducer)
            last = record.seq
        yield _frame("replayed", str(last), {"run_id": run_id, "through": last}, reducer)
        if not following:
            return
        while True:
            if await request.is_disconnected():
                return
            try:
                event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_S)
            except TimeoutError:
                yield b": keepalive\n\n"
                continue
            reducer.apply(event)
            yield _frame(str(event["type"]), str(event["event_id"]), event, reducer)
            if event["type"] in TERMINAL_TYPES:
                return
    finally:
        if following:
            console.bus.unsubscribe(on_event)


def _frame(event_type: str, event_id: str, data: dict[str, Any], reducer: TraceReducer) -> bytes:
    body = {
        "event": data,
        "trace": {
            "nodes": {k: str(v) for k, v in reducer.trace.nodes.items()},
            "steps": {k: str(v) for k, v in reducer.trace.steps.items()},
            "active_step": reducer.trace.active_step,
            "diagnostics": reducer.trace.diagnostics,
        },
    }
    return (
        f"event: {event_type}\nid: {event_id}\ndata: {json.dumps(body, sort_keys=True)}\n\n"
    ).encode()


def _event_dict(e: EventRecord) -> dict[str, Any]:
    return {
        "seq": e.seq,
        "event_id": e.event_id,
        "ts": e.ts,
        "run_id": e.run_id,
        "engagement_id": e.engagement_id,
        "node_id": e.node_id,
        "step_id": e.step_id,
        "type": e.type,
        "level": e.level,
        "message": e.message,
        "payload": dict(e.payload),
        "diagnostic_code": e.diagnostic_code,
        "cost_usd": e.cost_usd,
    }


def _run_row(run: RunRecord) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "engagement_id": run.engagement_id,
        "state": str(run.state),
        "state_reason": run.state_reason,
        "outcome": str(run.outcome) if run.outcome else None,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
        "plan_hash": run.plan_hash,
        "versions": dict(run.versions),
        "cost_usd": run.cost_usd,
        "model_calls": run.model_calls,
        "active_seconds": run.active_seconds,
        "superseded_by": run.superseded_by,
    }


def _known(console: Console, run_id: str) -> None:
    try:
        console.store.run(run_id)
    except Exception as unknown:  # noqa: BLE001 - one shape for the client
        raise HTTPException(status_code=404, detail=f"no run {run_id!r}") from unknown


OPS_SHELL = shell("Activity", "/")

PAGE = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Activity - Automated Analyst</title>
<style>{CSS}</style>
{OPS_SHELL}
<div class="wrap">
 <div class="page-head">
  <h1>Activity</h1>
  <p>What is happening right now. This reads the event log and drives
   nothing &mdash; console down, runs continue.</p>
 </div>

 <div class="cols side">
  <div>
   <section class="card">
    <header><h2>Runs</h2>
     <p class="why">Pick one to see what it did, step by step, as it happened.</p></header>
    <div class="body"><div id="runs"><div class="skel"></div><div class="skel"></div></div></div>
   </section>

   <section class="card">
    <header><h2>Run detail</h2>
     <p class="why" id="detail-why">Nothing selected.</p></header>
    <div class="body">
     <div id="card"><div class="empty"><b>Choose a run</b>Its scorecard, its trace and its live activity appear here.</div></div>
    </div>
   </section>

   <section class="card">
    <header><h2>Run trace</h2>
     <p class="why">Every node in the design, painted with what this run actually did.
      Green passed, red failed with its diagnostic below, a ring on whatever is running,
      and everything the run never touched left neutral &mdash; because <i>never ran</i>
      and <i>passed</i> are the two answers it matters most not to confuse.</p></header>
    <div class="body">
     <div class="legend">
      <span><i style="background:var(--good)"></i>passed</span>
      <span><i style="background:var(--bad)"></i>failed</span>
      <span><i style="background:var(--accent)"></i>running</span>
      <span><i style="background:var(--ink-3)"></i>touched</span>
      <span><i style="box-shadow:inset 0 0 0 1px var(--line)"></i>never reached</span>
      <span style="margin-left:auto" id="map-count"></span>
     </div>
     <div id="map"><div class="empty"><b>Choose a run</b>The graph is painted from its event stream.</div></div>
     <div class="diag" id="diag"></div>
    </div>
   </section>

   <section class="card">
    <header><h2>Live activity</h2>
     <p class="why" id="feed-src">Events arrive as they happen, newest first.</p></header>
    <div class="body"><div id="feed" style="max-height:44vh;overflow:auto"></div></div>
   </section>
  </div>

  <div>
   <section class="card">
    <header><h2>Waiting on a person</h2>
     <p class="why">Anything the system was not sure enough about to decide alone.</p></header>
    <div class="body"><div id="inbox"><div class="skel"></div></div></div>
   </section>

   <section class="card">
    <header><h2>Alerts</h2>
     <p class="why">Runs that have gone quiet, reviews past their SLA, guards repeating.</p></header>
    <div class="body"><div id="alerts"><div class="skel"></div></div></div>
   </section>
  </div>
 </div>
</div>
<div id="toast"></div>
{SHELL}
<script>
let source = null, current = null;

const STATE_TONE = {{delivered: 'good', halted: 'bad', blocked: 'warn', queued: '', running: 'accent'}};

async function refresh() {{
  const runs = await get('/api/runs').catch(() => []);
  $('chrome-right').textContent = runs.length ? plural(runs.length, 'run', 'runs') : '';
  $('runs').innerHTML = runs.length ? runs.map(r => `<div class="r link" onclick="open_('${{r.run_id}}')">
     <span class="lbl"><b class="mono">${{esc(r.run_id)}}</b><br>
      <span class="sub">${{esc(r.engagement_id)}}</span></span>
     <span class="pill ${{STATE_TONE[r.state] ?? ''}}"><i class="dot"></i>${{esc(r.state)}}</span>
     ${{r.queue && r.queue.waiting_on
        ? `<span class="sub">#${{r.queue.position}} behind ${{esc(r.queue.waiting_on)}}</span>` : ''}}
    </div>`).join('')
   : '<div class="empty"><b>No runs yet</b>A run starts when a complete set of files settles in a watched folder.</div>';

  const inbox = await get('/api/review').catch(() => []);
  $('inbox').innerHTML = inbox.length ? inbox.map(i => `<div class="r">
     <span class="lbl mono">${{esc(i.item_id)}}</span>
     <span class="sub">${{esc(i.owner || 'unassigned')}}</span>
     <span class="sub">${{esc(i.due_at || '')}}</span></div>`).join('')
   : '<div class="empty"><b>Nothing waiting</b>Everything the system proposed was inside its confidence bar.</div>';

  const alerts = await get('/api/alerts').catch(() => []);
  $('alerts').innerHTML = alerts.length ? alerts.map(a => `<div class="r">
     <span class="lbl"><b>${{esc(a.kind.replace(/_/g, ' '))}}</b><br>
      <span class="sub mono">${{esc(a.run_id)}} &middot; ${{esc(a.subject)}}</span></span>
     <span class="pill bad">${{esc(a.code || 'alert')}}</span></div>`).join('')
   : '<div class="empty"><b>Nothing raised</b>No run is silent and no review is overdue.</div>';
}}

/* The 118 nodes of the design, loaded once. The trace says what a run did to some of
   them; the rest are the ones it never touched, which is most of what a trace tells you. */
let GRAPH = null;
const GROUP_ORDER = ['entry', 'intake', 'source', 'privacy', 'orch', 'skill', 'tool',
  'guard', 'hitl', 'out', 'data', 'pref', 'gov', 'ops', 'notice', 'port'];
const GROUP_NAME = {{
  entry: 'The engagement', intake: 'Files come in', source: 'Reading them',
  privacy: 'Masking', orch: 'Planning the work', skill: 'Skills', tool: 'Tools',
  guard: 'Guards', hitl: 'People', out: 'Deliverables', data: 'What it knows',
  pref: 'Precedent', gov: 'Governance', ops: 'Watching it work', notice: 'Notices',
  port: 'Ports',
}};

async function loadGraph() {{
  if (!GRAPH) GRAPH = await get('/api/graph').catch(() => ({{nodes: []}}));
  return GRAPH;
}}

async function paint(trace) {{
  const g = await loadGraph();
  const seen = trace.nodes || {{}};
  const groups = new Map();
  for (const n of g.nodes) {{
    if (!groups.has(n.group)) groups.set(n.group, []);
    groups.get(n.group).push(n);
  }}
  const ordered = GROUP_ORDER.filter(k => groups.has(k))
    .concat([...groups.keys()].filter(k => !GROUP_ORDER.includes(k)));

  $('map').innerHTML = '<div class="map-groups">' + ordered.map(key => `
    <div class="map-group"><h3>${{esc(GROUP_NAME[key] || key)}}</h3><div class="map">` +
    groups.get(key).map(n => {{
      const state = seen[n.id] || '';
      const running = state === 'active';
      return `<span class="node ${{esc(state)}}" title="${{esc(n.plain || n.label)}}">
        ${{running ? '<i class="ring"></i>' : ''}}<span class="id">${{esc(n.id)}}</span></span>`;
    }}).join('') + '</div></div>').join('') + '</div>';

  const touched = Object.keys(seen).length;
  $('map-count').textContent = touched + ' of ' + g.nodes.length + ' touched';

  const failed = Object.entries(trace.diagnostics || {{}});
  $('diag').innerHTML = failed.length ? failed.map(([node, d]) => `<div class="d-row">
     <span class="code">${{esc(node)}} &mdash; ${{esc(d.code || d.type || 'failed')}}</span>
     <span class="msg">${{esc(d.message || '')}}${{d.step_id ? ' <span style="color:var(--ink-4)">at step ' + esc(d.step_id) + '</span>' : ''}}</span>
    </div>`).join('') : '';
}}

async function open_(id) {{
  if (source) source.close();
  current = id;
  let run;
  try {{ run = await get('/api/runs/' + id); }}
  catch (e) {{ return say(e.text || String(e), 'bad', e.code); }}

  const c = run.scorecard;
  $('detail-why').textContent = id + ' \u2014 ' + (run.engagement_id || '');
  $('card').innerHTML =
    `<div class="r" style="border:0;padding:0 0 10px">
      <span class="lbl"><span class="pill ${{c.in_progress ? 'accent' : c.verdict === 'clean' ? 'good' : c.verdict === 'halted' ? 'bad' : 'warn'}}">
       <i class="dot"></i>${{c.in_progress ? 'in progress' : esc(c.verdict)}}</span></span>
      <span class="sub mono">${{esc(c.criteria_version)}}</span></div>` +
    c.criteria.map(x => `<div class="r">
      <span class="lbl">${{esc(x.label)}}</span>
      <span class="sub mono">${{esc(x.measured)}}</span>
      <span class="pill ${{x.status === 'pass' ? 'good' : x.status === 'fail' ? 'bad' : ''}}">${{esc(x.status.replace('_', ' '))}}</span>
     </div>`).join('');

  $('feed').innerHTML = '';
  $('feed-src').textContent = 'Replaying ' + id + ' from the event stream.';
  paint(run.trace);

  source = new EventSource('/api/runs/' + id + '/stream');
  source.addEventListener('replayed', e => {{
    $('feed-src').textContent = 'Replayed through event ' + JSON.parse(e.data).event.through +
      (run.ended_at ? ' \u2014 the run has ended.' : ' \u2014 following live.');
  }});
  source.onerror = () => {{
    $('feed-src').textContent = 'Stream closed. The run ended, or the console lost the bus \u2014 runs continue either way.';
  }};
  const handler = e => {{
    const d = JSON.parse(e.data), ev = d.event;
    if (!ev.type) return;
    const bad = ev.type.endsWith('fail') || ev.type.startsWith('alert.');
    const line = document.createElement('div');
    line.className = 'r';
    line.innerHTML = `<span class="sub mono">${{esc((ev.ts || '').slice(11, 19))}}</span>
      <span class="lbl mono" style="color:${{bad ? 'var(--bad)' : 'var(--ink-2)'}}">${{esc(ev.type)}}</span>
      <span class="sub">${{esc(ev.node_id || '')}}</span>
      <span class="sub">${{esc(ev.message || '')}}</span>`;
    $('feed').prepend(line);
    paint(d.trace);
  }};
  const known = ['step.started', 'step.completed', 'skill.dispatched', 'skill.completed',
    'hitl.item.queued', 'hitl.item.decided', 'release.written', 'run.scored',
    'run.manifest.written', 'budget.ceiling_crossed', 'alert.run_silent',
    'alert.review_overdue', 'alert.step_overdue', 'alert.guard_repeating'];
  const events = await get('/api/runs/' + id + '/events').catch(() => []);
  const types = new Set(events.map(e => e.type).concat(known));
  for (const t of types) source.addEventListener(t, handler);
}}

refresh();
setInterval(refresh, 5000);
</script>
"""
