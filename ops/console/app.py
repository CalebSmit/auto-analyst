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
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from ops.analytics import Analytics
from ops.console.trace import Trace, TraceReducer
from ops.cost import CostMeter
from ops.drift import DriftMonitor
from ops.events import EventBus
from ops.run_store import EventRecord, RunRecord, RunStore
from ops.scorecard import RunScorecard
from ops.stall import StallDetector
from registries.constraints import ConstraintRegistry

__all__ = ["Console", "create_app"]

KEEPALIVE_S = 1.0
TERMINAL_TYPES = frozenset({"run.manifest.written"})


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
    ) -> None:
        self.store = store
        self.bus = bus
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
        }

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


PAGE = """<!doctype html>
<meta charset="utf-8"><title>Automated Analyst - ops console</title>
<style>
body{font:13px/1.45 system-ui,sans-serif;margin:0;background:#0f1216;color:#d7dbe0}
header{padding:12px 18px;border-bottom:1px solid #262b33;display:flex;gap:18px;align-items:baseline}
h1{font-size:15px;margin:0}main{display:grid;grid-template-columns:320px 1fr;gap:14px;padding:14px}
section{border:1px solid #262b33;border-radius:6px;padding:10px 12px;margin-bottom:14px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#8b93a1;margin:0 0 8px}
.mono{font-family:ui-monospace,monospace;font-size:12px}.row{display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-bottom:1px solid #1a1f26}
.passed{color:#5fcf8a}.failed{color:#ff6b6b}.active{color:#f0b64a}.used{color:#8b93a1}.notreached{color:#4a515c}
.pass{color:#5fcf8a}.fail{color:#ff6b6b}.not_measured{color:#4a515c}
#feed{max-height:52vh;overflow:auto}a{color:#7cb7ff}
</style>
<header><h1>Ops console</h1><span id="status" class="mono">reader of the event bus - console down, runs continue</span></header>
<main>
<div>
<section><h2>Runs</h2><div id="runs"></div></section>
<section><h2>Review inbox</h2><div id="inbox"></div></section>
<section><h2>Alerts</h2><div id="alerts"></div></section>
</div>
<div>
<section><h2>Run scorecard</h2><div id="card"></div></section>
<section><h2>Node state <span class="mono" id="trace-src"></span></h2><div id="nodes" class="mono"></div></section>
<section><h2>Live activity</h2><div id="feed" class="mono"></div></section>
</div>
</main>
<script>
const $=id=>document.getElementById(id);let source=null;
async function j(u){const r=await fetch(u);return r.json()}
function esc(s){return String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
async function refresh(){
 const runs=await j('/api/runs');$('runs').innerHTML=runs.map(r=>`<div class="row"><a href="#" onclick="open_('${r.run_id}');return false">${r.run_id}</a><span>${r.engagement_id}</span><span class="${r.state==='halted'?'failed':r.state==='delivered'?'passed':'active'}">${r.state}</span></div>`).join('')||'<i>no runs</i>';
 const inbox=await j('/api/review');$('inbox').innerHTML=inbox.map(i=>`<div class="row"><span>${esc(i.item_id)}</span><span>${esc(i.owner||'unassigned')}</span><span>${esc(i.due_at||'')}</span></div>`).join('')||'<i>nothing waiting</i>';
 const alerts=await j('/api/alerts');$('alerts').innerHTML=alerts.map(a=>`<div class="row failed"><span>${esc(a.kind)}</span><span>${esc(a.run_id)}/${esc(a.subject)}</span><span>${esc(a.code)}</span></div>`).join('')||'<i>none</i>';
}
function paint(trace){$('nodes').innerHTML=Object.entries(trace.nodes).map(([n,s])=>`<div class="row"><span>${esc(n)}</span><span class="${s}">${s}</span></div>`).join('')}
async function open_(id){
 if(source){source.close()}
 const run=await j('/api/runs/'+id);
 const c=run.scorecard;$('card').innerHTML=`<div class="row"><b>${c.in_progress?'IN PROGRESS':esc(c.verdict).toUpperCase()}</b><span class="mono">${esc(c.criteria_version)}</span></div>`+c.criteria.map(x=>`<div class="row"><span class="${x.status}">${x.status==='pass'?'&#10003;':x.status==='fail'?'&#10007;':'&middot;'} ${esc(x.label)}</span><span class="mono">${esc(x.measured)}</span></div>`).join('');
 $('feed').innerHTML='';$('trace-src').textContent='replaying '+id+' from the event stream';paint(run.trace);
 source=new EventSource('/api/runs/'+id+'/stream');
 source.onmessage=null;
 source.addEventListener('replayed',e=>{$('trace-src').textContent='replayed through seq '+JSON.parse(e.data).event.through+(run.ended_at?' - run ended':' - following live')});
 for(const t of ['step','skill','guard','hitl','run','release','model','loop','alert','budget','tool','policy','intake','context','lock']){}
 source.onerror=()=>{$('status').textContent='stream closed - the run ended or the console lost the bus; runs continue either way'};
 const handler=e=>{const d=JSON.parse(e.data);const ev=d.event;if(!ev.type)return;const line=document.createElement('div');line.className='row';line.innerHTML=`<span>${esc(ev.ts||'')}</span><span>${esc(ev.node_id||'')}</span><span class="${ev.type.endsWith('fail')||ev.type.startsWith('alert.')?'failed':''}">${esc(ev.type)}</span><span>${esc(ev.message||'')}</span>`;$('feed').prepend(line);paint(d.trace)};
 const es=source;const orig=es.addEventListener.bind(es);
 fetch('/api/runs/'+id+'/events').then(r=>r.json()).then(list=>{const types=new Set(list.map(e=>e.type));for(const t of types)orig(t,handler);for(const t of ['step.started','step.completed','skill.dispatched','skill.completed','hitl.item.queued','hitl.item.decided','release.written','run.scored','run.manifest.written','budget.ceiling_crossed','alert.run_silent','alert.review_overdue','alert.step_overdue','alert.guard_repeating'])if(!types.has(t))orig(t,handler)});
}
refresh();setInterval(refresh,5000);
</script>
"""
