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
import dataclasses
import hashlib
import json
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

import ports
from deliver.audit import AUDITED_SUFFIXES, audit_workbook
from ops.analytics import Analytics
from ops.blobs import ContentRef, ContentStore
from ops.console.analytics_page import PAGE as ANALYTICS_PAGE
from ops.console.help_page import PAGE as HELP_PAGE
from ops.console.map_view import MAP_HTML, MAP_JS, MAP_STYLE
from ops.console.trace import Trace, TraceReducer
from ops.cost import CostMeter
from ops.drift import DriftMonitor
from ops.events import EventBus
from ops.models import Outcome, RunState
from ops.run_store import EventRecord, RunRecord, RunStore
from ops.scorecard import RunScorecard
from ops.stall import StallDetector
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from review.surface import ReviewRefused, ReviewSurface, StaleDecision
from ui import CSS, SHELL
from ui.theme import shell
from ui.who import install_identity, who

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
        label_of: Callable[[str], Mapping[str, str] | None] | None = None,
    ) -> None:
        """`label_of` names an engagement for a person - its client and scope path - so the
        runs list reads as work rather than as hashes. Optional: the console reads the run
        store, and the roster that knows a client's name is the composition root's."""
        self.label_of = label_of
        self.store = store
        self.bus = bus
        self.queue = queue
        self.blobs = blobs
        constraints = constraints or ConstraintRegistry.load()
        self.constraints = constraints
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
                    **self._label(run.engagement_id),
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

    def engagements(self) -> list[dict[str, Any]]:
        """The runs, folded by the thing an analyst actually thinks in.

        Everything else on this console is indexed by run, which is the system's unit and
        not the work's: a repeat client has several runs behind one engagement, and asking
        "where does Northgate stand" meant reading every row. This folds the same rows the
        runs panel already reads - no second source, so the two cannot disagree.

        What a line carries is what the console knows. There is deliberately no valuation
        date: the engagement profile's two `as_of` fields belong to `size_band` and
        `fiscal_calendar`, neither of which is one, and a date on the screen that nothing
        in the system means is worse than no date. It is an interview question
        (BUILD/OPEN.md).
        """
        by_engagement: dict[str, list[dict[str, Any]]] = {}
        for row in self.runs():
            by_engagement.setdefault(str(row["engagement_id"]), []).append(row)

        lines = []
        for engagement_id, rows in by_engagement.items():
            rows.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)
            newest = rows[0]
            lines.append(
                {
                    "engagement_id": engagement_id,
                    **self._label(engagement_id),
                    "runs": len(rows),
                    "run_ids": [str(r["run_id"]) for r in rows],
                    "state": newest["state"],
                    "latest_run_id": str(newest["run_id"]),
                    "last_ts": max(str(r.get("last_ts") or "") for r in rows),
                    "open_review_items": sum(int(r.get("open_review_items") or 0) for r in rows),
                    "needs_attention": sum(1 for r in rows if str(r["state"]) in NEEDS_ATTENTION),
                }
            )
        lines.sort(key=lambda line: str(line["last_ts"]), reverse=True)
        return lines

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
            "budget_usd": self._ceiling_usd(),
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

    def decisions(self, run_id: str) -> list[dict[str, Any]]:
        """Every decision made on this run, with the proposal it was made against.

        The queue shows what is outstanding; this is what was settled, which is the part a
        reviewer, an associate or a challenge letter asks for a year later. `revealed_at`
        comes from the `hitl.proposal.revealed` event the surface records precisely so that
        "accepted without ever looking" is answerable - here it is answered on the page
        rather than only in the database.
        """
        revealed: dict[str, dict[str, Any]] = {}
        for event in self.store.events(run_id):
            if event.type == "hitl.proposal.revealed":
                item = str((event.payload or {}).get("item_id") or "")
                if item and item not in revealed:
                    revealed[item] = {
                        "at": event.ts,
                        "viewer": (event.payload or {}).get("viewer"),
                    }
        rows = []
        for d in self.store.decisions(run_id):
            seen = revealed.get(d.item_id)
            rows.append(
                {
                    "item_id": d.item_id,
                    "skill": d.skill,
                    "decision": str(d.decision),
                    "decided_by": d.decided_by,
                    "decided_at": d.decided_at,
                    "rationale": d.rationale,
                    "writes_precedent": d.writes_precedent,
                    "proposal": d.proposal,
                    "answer": d.answer,
                    "revealed_at": seen["at"] if seen else None,
                    "revealed_to": seen["viewer"] if seen else None,
                    "seconds_looking": _between(seen["at"], d.decided_at) if seen else None,
                }
            )
        return rows

    def _ceiling_usd(self) -> float | None:
        """What one run may spend. A spend with no ceiling beside it is a number nobody
        can judge, and the first anybody hears of a budget problem is a halted run."""
        try:
            return float(self.constraints.ceilings["per_run"]["usd_max"])
        except (KeyError, TypeError, ValueError):
            return None

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

    def _label(self, engagement_id: str) -> dict[str, str]:
        found = self.label_of(engagement_id) if self.label_of else None
        if not found:
            return {"client": "", "scope_path": ""}
        return {
            "client": str(found.get("client") or ""),
            "scope_path": str(found.get("scope_path") or ""),
        }

    def inbox(self, engagement_id: str | None = None) -> list[dict[str, Any]]:
        engagements: dict[str, str] = {}

        def engagement_of(run_id: str) -> str:
            if run_id not in engagements:
                engagements[run_id] = self.store.run(run_id).engagement_id
            return engagements[run_id]

        return [
            {
                "engagement_id": engagement_of(i.run_id),
                **self._label(engagement_of(i.run_id)),
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
        """What has stopped, read rather than raised.

        `open_alerts` is `scan` without the emit: the page says it drives nothing, and a
        page that wrote alert events would be the only thing raising them - so a weekend
        with nobody watching would raise none. The sweep loop emits them instead.
        """
        return [a.as_dict() for a in self.stall.open_alerts(engagement_id)]

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
            {
                "name": a.name,
                "content_hash": a.content_hash,
                "written_at": a.written_at,
                "path": a.path,
            }
            for a in self.store.artifacts(run_id)
        ]


class Claimed(BaseModel):
    who: str | None = None


class Decision(BaseModel):
    decision: str
    expected_version: int
    rationale: str = ""
    answer: dict[str, Any] | None = None
    who: str | None = None


class Ask(BaseModel):
    reason: str = ""
    who: str | None = None


def create_app(console: Console, surface: ReviewSurface | None = None, pool: Any = None) -> FastAPI:
    """The ops console's routes. `surface` is the review surface a person answers through;
    without one the reading routes work and the writing ones say so."""
    app = FastAPI(title="Chartwell Automated Analyst - ops console", docs_url=None, redoc_url=None)
    # On this app as well as on the combined one. `tools/serve.py` installs it on the app it
    # serves - a router does not carry its application's middleware - but this factory is
    # public, and an entry point that served it alone would have no check at all: every run,
    # every review excerpt and every released workbook, to anything that asked.
    install_identity(app)

    def _surface() -> ReviewSurface:
        if surface is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "refused": [
                        {
                            "code": "REVIEW.NOT_WIRED",
                            "message": "no review surface is wired on this server",
                        }
                    ]
                },
            )
        return surface

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return PAGE

    @app.get("/api/runs")
    def runs(engagement_id: str | None = None) -> list[dict[str, Any]]:
        return console.runs(engagement_id)

    @app.get("/api/engagements")
    def engagements() -> list[dict[str, Any]]:
        return console.engagements()

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
        import json as _json  # noqa: PLC0415

        from graph.architecture_assertions import (
            GRAPH_FILE,  # noqa: PLC0415
            load_graph,
        )

        loaded = load_graph()
        raw = _json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
        return {
            "nodes": [
                {
                    "id": n["id"],
                    "label": n.get("label", n["id"]),
                    "group": n.get("group", ""),
                    "plain": n.get("plain", ""),
                    "runtime": n.get("runtime", ""),
                    "exec": n.get("exec", ""),
                    # Where the blueprint puts it. The console draws the design of record
                    # rather than laying the same graph out a second time and hoping the
                    # two agree.
                    "x": n.get("x"),
                    "y": n.get("y"),
                }
                for n in loaded.nodes.values()
            ],
            "edges": [
                {"from": e.src, "to": e.dst, "kind": e.kind, "label": e.label}
                for e in loaded.edges
            ],
            "layout": raw.get("layout", {}),
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

    def _released(run_id: str, name: str) -> tuple[bytes, Path]:
        """The bytes of a delivered artifact, from where it was delivered, checked against
        the digest the release recorded - so what is read is what was released, not
        whatever is at that path now.

        Shared by the download and the audit, deliberately. Two routes reading the same
        file through two copies of this check is two chances for one of them to stop
        checking, and the one that stopped would be the one serving a file nobody
        released."""
        found = next((a for a in console.store.artifacts(run_id) if a.name == name), None)
        if found is None or not found.path:
            raise HTTPException(status_code=404, detail=f"no delivered file {name!r} on {run_id}")
        delivery = ports.get_delivery()
        base = getattr(delivery, "root", None)
        if base is None or getattr(delivery, "name", "") != "local_folder":
            raise HTTPException(status_code=409, detail="deliverables are not in a local folder here")
        target = (Path(base) / found.path).resolve()
        if Path(base).resolve() not in target.parents or not target.is_file():
            raise HTTPException(status_code=404, detail=f"{found.path} is not in the delivery folder")
        data = target.read_bytes()
        if found.content_hash and "sha256:" + hashlib.sha256(data).hexdigest() != found.content_hash:
            raise HTTPException(
                status_code=409,
                detail=f"{found.path} has changed since it was released; it is not the deliverable",
            )
        return data, target

    @app.get("/api/runs/{run_id}/artifacts/{name:path}/download")
    def download(run_id: str, name: str) -> Response:
        """A deliverable, from where it was delivered, when that is a folder on this machine."""
        _known(console, run_id)
        data, target = _released(run_id, name)
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
        )

    @app.get("/api/runs/{run_id}/artifacts/{name:path}/audit")
    def audit_artifact(run_id: str, name: str, convention: bool = False) -> dict[str, Any]:
        """What is wrong with the formulas in a delivered workbook.

        Re-derived from the released bytes rather than read back off the event the
        release wrote, so this answers for the file as it stands - including the cached
        totals Excel fills in the first time somebody opens and saves it, which is
        exactly when the footing check becomes able to run at all."""
        _known(console, run_id)
        if not name.lower().endswith(AUDITED_SUFFIXES):
            raise HTTPException(
                status_code=409,
                detail=f"{name} is not a workbook; there are no formulas in it to audit",
            )
        data, _ = _released(run_id, name)
        return audit_workbook(data, include_convention=convention).as_dict()

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

    @app.get("/api/runs/{run_id}/decisions")
    def decisions(run_id: str) -> list[dict[str, Any]]:
        """What was settled on this run, as against what is outstanding.

        The queue empties as items are answered, and before this route nothing could say
        afterwards who answered them, against what proposal, or whether they revealed it
        before deciding. That is the question a reviewer, an associate or a challenge
        letter asks, and the record has always held the answer.
        """
        _known(console, run_id)
        return console.decisions(run_id)

    # -- one review item: read it, reveal the proposal, answer it. The order is the
    # surface's: the question first, the proposal only on request and on the record, and
    # the decision once, at the version the reviewer saw.

    @app.get("/api/runs/{run_id}/review/{item_id}")
    def review_item(run_id: str, item_id: str) -> dict[str, Any]:
        try:
            return dataclasses.asdict(_surface().show(run_id, item_id))
        except KeyError as missing:
            raise HTTPException(status_code=404, detail=str(missing)) from missing

    @app.post("/api/runs/{run_id}/review/{item_id}/reveal")
    def reveal(
        run_id: str, item_id: str, request: Request, body: Claimed | None = None
    ) -> dict[str, Any]:
        viewer = who(request, body.who if body else None)
        try:
            return dataclasses.asdict(_surface().reveal(run_id, item_id, viewer=viewer))
        except KeyError as missing:
            raise HTTPException(status_code=404, detail=str(missing)) from missing

    @app.post("/api/runs/{run_id}/review/{item_id}/decide")
    def decide(run_id: str, item_id: str, body: Decision, request: Request) -> dict[str, Any]:
        decided_by = who(request, body.who)
        try:
            record = _surface().decide(
                run_id,
                item_id,
                decided_by=decided_by,
                decision=body.decision,  # type: ignore[arg-type]
                expected_version=body.expected_version,
                rationale=body.rationale,
                answer=body.answer,
            )
        except StaleDecision as stale:
            raise HTTPException(
                status_code=409, detail={"refused": [stale.diagnostic.as_dict()]}
            ) from stale
        except ReviewRefused as refused:
            raise HTTPException(
                status_code=422, detail={"refused": [refused.diagnostic.as_dict()]}
            ) from refused
        except KeyError as missing:
            raise HTTPException(status_code=404, detail=str(missing)) from missing
        except ValueError as bad:
            raise HTTPException(
                status_code=422,
                detail={"refused": [{"code": "REVIEW.INVALID", "message": str(bad)}]},
            ) from bad
        out = dataclasses.asdict(record)
        out["decision"] = str(record.decision)
        out["run_state"] = str(console.store.run(run_id).state)
        out["open_items"] = sum(1 for i in console.store.review_items(run_id) if i.state == "open")
        return out

    # -- a stuck run: picked back up, or ended by a person with a reason. Both on the
    # record with who asked. Neither touches a run a worker is holding.

    def _stuck(run_id: str) -> Any:
        try:
            run = console.store.run(run_id)
        except KeyError as missing:
            raise HTTPException(status_code=404, detail=str(missing)) from missing
        if run.is_finished:
            raise HTTPException(
                status_code=409,
                detail={
                    "refused": [
                        {
                            "code": "RUN.ENDED",
                            "message": f"{run_id} has ended ({run.state}); nothing to do",
                        }
                    ]
                },
            )
        if getattr(run, "superseded_by", None):
            raise HTTPException(
                status_code=409,
                detail={
                    "refused": [
                        {
                            "code": "RUN.SUPERSEDED",
                            "message": f"{run_id} was superseded by {run.superseded_by}; "
                            f"act on that run instead",
                        }
                    ]
                },
            )
        if (
            run.state is RunState.RUNNING
            and pool is not None
            and not any(s.run_id == run_id for s in pool.stranded(emit=False))
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "refused": [
                        {"code": "RUN.HELD", "message": f"{run_id} is running under a worker"}
                    ]
                },
            )
        return run

    @app.post("/api/runs/{run_id}/resume")
    def resume_run(run_id: str, body: Ask, request: Request) -> dict[str, Any]:
        by = who(request, body.who)
        if pool is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "refused": [{"code": "POOL.NOT_WIRED", "message": "no pool on this server"}]
                },
            )
        if not (body.reason or "").strip():
            # As halting one does. A quarantined run is one a guard refused; restarting it
            # is a judgement - "the client sent a corrected trial balance", "the
            # methodology was cleared" - and that belongs beside the refusal.
            raise HTTPException(
                status_code=422,
                detail={
                    "refused": [
                        {
                            "code": "REVIEW.RATIONALE_REQUIRED",
                            "message": "resuming a run needs a reason: what changed",
                        }
                    ]
                },
            )
        run = _stuck(run_id)
        console.bus.emit(
            run_id=run_id,
            engagement_id=run.engagement_id,
            node_id="ops_console",
            type="run.resume.requested",
            message=f"{by}: {body.reason or 'resume'}"[:400],
            payload={"who": by, "reason": body.reason},
        )
        placement = pool.resume(run_id)
        return {
            "run_id": run_id,
            "waiting_on": getattr(placement, "waiting_on", None),
            "state": str(console.store.run(run_id).state),
        }

    @app.post("/api/runs/{run_id}/halt")
    def halt_run(run_id: str, body: Ask, request: Request) -> dict[str, Any]:
        by = who(request, body.who)
        if not body.reason.strip():
            raise HTTPException(
                status_code=422,
                detail={
                    "refused": [
                        {
                            "code": "REVIEW.RATIONALE_REQUIRED",
                            "message": "ending a run needs a reason",
                        }
                    ]
                },
            )
        _stuck(run_id)
        from ops.manifest import close_out  # noqa: PLC0415
        from ops.scorecard import RunScorecard, Verdict  # noqa: PLC0415

        # The outcome is what the record supports, not what the caller claims: a run
        # something refused ended halted; one that only ever waited on a person ended
        # blocked. The close-out would refuse a claim the scorecard contradicts.
        verdict = (
            RunScorecard(console.store, console.bus)
            .score(run_id, ending=(RunState.HALTED, Outcome.HALTED))
            .verdict
        )
        outcome = Outcome.HALTED if verdict is Verdict.HALTED else Outcome.BLOCKED
        close_out(
            console.store,
            run_id,
            RunState.HALTED,
            outcome,
            ports.get_delivery(),
            bus=console.bus,
            contracts=ContractRegistry.load(),
            reason=f"{by}: {body.reason.strip()}"[:400],
        )
        run = console.store.run(run_id)
        return {"run_id": run_id, "state": str(run.state), "outcome": str(run.outcome), "by": by}

    @app.get("/api/alerts")
    def alerts(engagement_id: str | None = None) -> list[dict[str, Any]]:
        return console.alerts(engagement_id)

    @app.get("/api/cost/{engagement_id}")
    def cost(engagement_id: str) -> dict[str, Any]:
        return console.meter.rollup(engagement_id).as_dict()

    @app.get("/help", response_class=HTMLResponse)
    def help_page() -> str:
        """What a person does, in order, and what the words on the other pages mean."""
        return HELP_PAGE

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


FRAME = "aa"
"""The one frame name. A browser delivers a named SSE frame only to a listener registered for
that exact name, and a page cannot know every event type this system will ever emit - so a
type it had not seen before was dropped without a word. The type rides in the body, which is
where the page reads it from anyway."""

NEEDS_ATTENTION = ("quarantined", "waiting")
"""The run states that want a person. Named once here because the page counts them for its
chrome and `engagements()` counts them per engagement; two lists would drift, and the one
that drifted would be the one nobody was reading. A test pins the page's literal to this.

`blocked` was on this list until C36 asked whether every name on it was a state the store
can produce. It is not: `blocked` is an `Outcome`, carried by a *halted* run, and no run is
ever in it. Nothing counted it, because nothing could - which is why it survived. A list
naming a state that cannot occur reads as coverage it has not got."""


def _frame(event_type: str, event_id: str, data: dict[str, Any], reducer: TraceReducer) -> bytes:
    body = {
        "type": event_type,
        "event": data,
        "trace": {
            "nodes": {k: str(v) for k, v in reducer.trace.nodes.items()},
            "steps": {k: str(v) for k, v in reducer.trace.steps.items()},
            "active_step": reducer.trace.active_step,
            "diagnostics": reducer.trace.diagnostics,
        },
    }
    return (
        f"event: {FRAME}\nid: {event_id}\ndata: {json.dumps(body, sort_keys=True)}\n\n"
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


def _between(earlier: str, later: str) -> float | None:
    """Seconds between two recorded timestamps, or None if either is unreadable. Used for
    how long a proposal was on screen before it was decided - a number that only means
    anything beside the decision it belongs to."""
    try:
        start = datetime.fromisoformat(earlier.replace("Z", "+00:00"))
        end = datetime.fromisoformat(later.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    return round((end - start).total_seconds(), 1)


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

PAGE = (
    f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Activity - Automated Analyst</title>
<style>{CSS}
/* The run and the list of runs get two rows of the three: the detail is what a person
   reads, and it was being cut at its fifth line while the map of the architecture - the
   least actionable panel on the page - had the largest share of the screen. */
{MAP_STYLE}
.board{{grid-template-columns:minmax(0,1.05fr) minmax(0,1fr) minmax(0,.95fr);
 grid-template-rows:repeat(3,min-content);
 grid-template-areas:"runs detail inbox" "runs detail alerts" "trace trace feed"}}
</style>
{OPS_SHELL}
<div class="wrap">
 <div id="offline"></div>
 <div class="page-head">
  <h1>Activity</h1>
  <p>What is happening right now. This reads the event log and drives nothing &mdash;
   console down, runs continue.</p>
 </div>

 <div class="board">
  <!-- A stream: one row per run, for as long as the firm keeps running them. -->
  <section class="card stream" style="grid-area:runs">
   <header><h2>Runs<span class="of" id="n-runs"></span></h2>
    <p class="why">Grouped by engagement, newest first, because a repeat client is one
     job with several runs. Pick one to see what it did, step by step, as it happened.</p>
    <div class="filter">
     <input id="q" type="search" placeholder="Find a client, engagement or scope"
      autocomplete="off" spellcheck="false" aria-label="Filter runs by client, engagement or scope"
      data-act="filterRuns">
     <button class="btn small" id="q-needs" data-act="onlyNeedsAPerson" hidden
      aria-pressed="false">Needs a person</button>
     <button class="btn small" id="q-clear" data-act="clearFilter" hidden>Clear</button>
    </div>
    <p class="why" id="q-says" hidden></p></header>
   <div class="body"><div id="runs"><div class="skel"></div><div class="skel"></div></div></div>
  </section>

  <section class="card" style="grid-area:detail">
   <!-- The title is the run, once there is one. "Run detail" named the box rather than
        the thing in it: the client was set in the smallest type on the page, below a
        heading three sizes larger that said nothing a reader did not know from having
        clicked. A panel about one thing is titled with that thing. -->
   <header><h2 id="detail-title">Run detail</h2>
    <p class="why" id="detail-why">Nothing selected.</p></header>
   <div class="body">
    <div id="card"><div class="empty"><b>Choose a run</b>Its scorecard, its trace and its live activity appear here.</div></div>
   </div>
  </section>

  <!-- A stream: one per question a run has stopped on, and nothing bounds how many. -->
  <section class="card stream" style="grid-area:inbox">
   <header><h2>Waiting on a person<span class="of" id="n-inbox"></span></h2>
    <p class="why">What the system was not sure enough about to decide alone. Open one to read the source first, then the proposal.</p></header>
   <div class="body"><div id="inbox"><div class="skel"></div></div></div>
  </section>

  <!-- A stream: a hundred and eighteen nodes, however many the run touched. -->
  <section class="card stream" style="grid-area:trace">
   <header><h2>Run trace</h2>
    <p class="why">Every node in the design, painted with what this run actually did.
     Mint passed, plum failed with its diagnostic below, a ring on whatever is running,
     and everything the run never touched left neutral &mdash; because <i>never ran</i>
     and <i>passed</i> are the two answers it matters most not to confuse.</p></header>
   <div class="body">
    <div class="legend">
     <span class="node passed"><span class="id">passed</span></span>
     <span class="node failed"><span class="id">failed</span></span>
     <span class="node active"><i class="ring"></i><span class="id">running</span></span>
     <span class="node used"><span class="id">touched</span></span>
     <span class="legend-note">and a name with no box at all is a node this run never reached</span>
     <label class="toggle" style="margin-left:auto"><input type="checkbox" id="touched-only" data-act="onlyTouched">only what this run touched</label>
     <span id="map-count"></span>
    </div>
    <div class="diag" id="diag"></div>
    <div id="map"><div class="empty"><b>Choose a run</b>The graph is painted from its event stream.</div></div>
   </div>
  </section>

  <!-- A stream: one per run gone quiet or review past its SLA. -->
  <section class="card stream" style="grid-area:alerts">
   <header><h2>Alerts<span class="of" id="n-alerts"></span></h2>
    <p class="why">Runs that have gone quiet, reviews past their SLA, guards repeating.</p></header>
   <div class="body"><div id="alerts"><div class="skel"></div></div></div>
  </section>

  <!-- A stream: the event log, which only ever grows. -->
  <section class="card stream" style="grid-area:feed">
   <header><h2>Live activity</h2>
    <p class="why" id="feed-src">Events arrive as they happen, newest first.</p></header>
   <div class="body"><div id="feed"></div></div>
  </section>
 </div>
</div>
<div id="toast"></div>
{MAP_HTML}
{SHELL}
"""
    + """<script>
let source = null;
let current = null;
let RUNS = [];
let LAST_TRACE = null;
/* The SSE frame name. One name for every event, so a type this page has never seen still
   reaches the feed. It must match `FRAME` in ops/console/app.py, and a test says so. */
const FRAME = 'aa';

/* What a row does, by name. Registered once; the rows themselves carry only data, so a
   client's apostrophe cannot break a handler and a client's file cannot write one. */
ACTIONS.open = d => open_(d.run);
ACTIONS.review = d => { open_(d.run); review(d.run, d.item); };
ACTIONS.runAction = d => runAction(d.run, d.do);
ACTIONS.reveal = d => revealProposal(d.run, d.item);
ACTIONS.clearFilter = () => {
  const q = $('q'); if (q) { q.value = ''; q.focus(); }
  ONLY_NEEDS = false; paintRuns();
};
/* The phrase, with its verb, in one place.

   Two surfaces counted the same thing and each wrote the sentence itself, so the
   engagement header read **"1 need a person"** on a real engagement with one halted run.
   `plural()` inflects the noun and this phrase inflects the verb, which is not something a
   caller should be expected to remember at each site.

   Found by looking at a console with three real runs on it, not by reading the source. */
const needAPerson = n => n + (n === 1 ? ' needs' : ' need') + ' a person';

/* The count in the chrome is the filter. Somebody reads "12 need a person", and the
   next thing they want is those twelve - so the number they read is the control they
   press, rather than a fact they then have to act on somewhere else. */
ACTIONS.onlyNeedsAPerson = () => { ONLY_NEEDS = !ONLY_NEEDS; paintRuns(); };
/* The two controls that are fields rather than buttons. They reach their handler the
   same way every other control does; what is different is only which event carries it. */
ACTIONS.filterRuns = () => applyFilter();
ACTIONS.onlyTouched = () => repaint();
/* The questions count goes to the questions, rather than filtering the runs: an item is
   answered in the review panel, and sending somebody to a filtered run list would be one
   more click away from the thing they read the number for. */
ACTIONS.toReview = () => {
  const panel = $('inbox');
  if (!panel) return;
  panel.scrollIntoView({behavior: 'smooth', block: 'center'});
  const first = panel.querySelector('[data-act="review"]');
  if (first) first.focus();
};
ACTIONS.auditFile = d => auditFile(d.run, d.name, d.box);

/* Narrowing is a redraw of what the page already has, not a request: the answer is in
   RUNS, and asking the server again would make a person wait to be told something the
   browser knew. Nothing here is interpolated into script - the rows are rebuilt by
   runRow, which reads data through esc() exactly as the unfiltered list does. */
function applyFilter() { paintRuns(); }

/* The run states, in the three colours that carry meaning: fine, attention, problem.
   Every key is a state `RunState` can actually hold - `released` and `blocked` sat here
   for a while and are neither (the first is called `delivered`, the second is an outcome),
   so both were dead entries reading as coverage. C36 asks that of every key. */
const STATE_TONE = {delivered: 'good', halted: 'bad', quarantined: 'warn',
  waiting: 'warn', queued: '', running: 'accent', superseded: ''};
const STATE_SAYS = {
  quarantined: 'stopped on itself - a step failed in a way retrying will not fix',
  waiting: 'stopped on a person - it resumes when the review items are answered',
  halted: 'ended without delivering - nothing partial left the system',
  running: 'working now', queued: 'waiting for a worker', superseded: 'replaced by a newer run',
};
/* The states that want a person. It must match `NEEDS_ATTENTION` in ops/console/app.py,
   and a test says so: the page counts them for its chrome and `engagements()` counts them
   per engagement, and two lists would drift. Not 'blocked' - that is an outcome a halted
   run carries, never a state a run is in. */
const NEEDS_ATTENTION = new Set(['quarantined', 'waiting']);
/* The scorecard's verdicts, which are not the run's states: pass, pass_with_exceptions,
   partial, blocked, halted. Coloured here so the two vocabularies cannot drift apart. */
const VERDICT_TONE = {pass: 'good', pass_with_exceptions: 'good', partial: 'warn',
  blocked: 'warn', halted: 'bad'};
const VERDICT_SAYS = {
  pass: 'every criterion measured was met',
  pass_with_exceptions: 'met, with exceptions recorded against the criteria',
  partial: 'some criteria were never measured - the run did not reach them',
  blocked: 'a criterion was not met and the run could not deliver',
  halted: 'the run ended without delivering',
};

/* The states a run is in when nothing is happening to it. Derived from STATE_SAYS rather
   than listed again: each of these sentences begins by saying the run stopped. */
const STOPPED = new Set(['quarantined', 'waiting', 'halted', 'superseded']);

/* The second pill: what the scorecard says, beside what the run is.

   `in_progress` on a scorecard means **no verdict yet**, and the pill rendered that as
   "in progress" with the tooltip "still running". On a quarantined run that put
   `quarantined` and `in progress` side by side - a run that has stopped, labelled as
   running, with the tooltip insisting on it. Seen on a console with three real runs.

   The scorecard's vocabulary is not the run's and was never meant to be read as it. When
   the run has stopped, a scorecard with no verdict says exactly that. */
function scorecardPill(c, state) {
  const stopped = STOPPED.has(state);
  const label = c.in_progress ? (stopped ? 'no verdict' : 'in progress') : c.verdict;
  if (label === state) return '';   // one word, said once
  const says = c.in_progress
    ? (stopped ? 'the run stopped before the scorecard reached a verdict' : 'still running')
    : (VERDICT_SAYS[c.verdict] || "the scorecard's verdict");
  const tone = c.in_progress ? (stopped ? '' : 'accent') : (VERDICT_TONE[c.verdict] ?? '');
  return `<span class="pill ${tone}" title="${esc(says)}">${esc(label)}</span>`;
}

/* A count beside a panel's title, or nothing at all when there is nothing to count. */
function count(id, n) {
  const box = $(id);
  if (box) box.textContent = n ? String(n) : '';
}

function runName(r) {
  return r.client ? esc(r.client) : esc(r.engagement_id);
}

async function refresh() {
  let runs, inbox, alerts;
  try {
    [runs, inbox, alerts] = await Promise.all(
      ['/api/runs', '/api/review', '/api/alerts'].map(u => get(u)));
  } catch (e) {
    // Not an empty dashboard: an empty dashboard is a claim that there is nothing to do.
    return offline(e);
  }
  online();
  RUNS = runs;
  // What each panel holds, in its own title: a list cut off by the fold is a known length
  // rather than a surprise, and the number is the one thing you would count by hand.
  count('n-runs', runs.length);
  count('n-inbox', inbox.length);
  count('n-alerts', alerts.length);
  RUNS.sort((a, b) => String(b.started_at || '').localeCompare(String(a.started_at || '')));

  /* The two numbers say what they count, and they are not the same kind of thing.
     `attention` counts *runs* that have stopped on somebody; `inbox` counts *questions*
     waiting to be answered - and a question sits on a run that is already in the first
     number. Written as "12 need attention . 2 waiting on you" the two read as disjoint
     buckets of one thing, and on the battery store that was twelve runs beside two items
     that belonged to them. Naming the unit is the whole fix. */
  const attention = RUNS.filter(r => NEEDS_ATTENTION.has(r.state)).length;
  $('chrome-right').innerHTML = RUNS.length
    ? `<span class="attention">${plural(RUNS.length, 'run', 'runs')}`
      + (attention ? ` &middot; <b class="chip" role="button" tabindex="0" data-act="onlyNeedsAPerson"`
         + ` title="Show only these. A run stops on itself when a step failed in a way retrying`
         + ` will not fix, or on a person when it has a question.">${needAPerson(attention)}</b>` : '')
      + (inbox.length ? ` &middot; <b class="chip" role="button" tabindex="0" data-act="toReview"`
         + ` title="Open questions waiting for an answer. Each sits on one of the runs above.">`
         + `${plural(inbox.length, 'question', 'questions')} waiting</b>` : '')
      + `</span>`
    : '';

  paintRuns();
  paintRest(inbox, alerts);
}

/* One run, as a row. Pulled out of the panel so the grouped list and the filtered list
   are the same row rather than two that have to be kept looking alike. */
function runRow(r) {
  return `<div class="r pick${r.run_id === current ? ' on' : ''}" role="button" tabindex="0" data-act="open" data-run="${esc(r.run_id)}">
     <span class="lbl"><b>${runName(r)}</b>
      <span class="sub" style="display:block;white-space:normal">${esc(r.engagement_id)}${r.scope_path ? ' &middot; ' + esc(r.scope_path) : ''} &middot; <span class="mono" title="run id">${esc(r.run_id)}</span></span>
      ${r.state_reason && r.state !== 'delivered' ? `<span class="why-line" title="${esc(r.state_reason)}">${esc(r.state_reason)}</span>` : ''}
     </span>
     <span style="display:flex;flex-direction:column;align-items:flex-end;gap:.3rem">
      <span class="pill ${STATE_TONE[r.state] ?? ''}" title="${esc(STATE_SAYS[r.state] || '')}"><i class="dot"></i>${esc(r.state)}</span>
      <span class="sub">${esc(ago(r.last_ts || r.started_at))}${r.open_review_items ? ` &middot; <span class="count" title="open review items">${r.open_review_items}</span>` : ''}</span>
      ${r.queue && r.queue.waiting_on ? `<span class="sub">#${r.queue.position} behind ${esc(r.queue.waiting_on)}</span>` : ''}
     </span>
    </div>`;
}

/* What the find box matches on: the words a person would type looking for one job -
   the client's name, the engagement, the scope, the run id. Never the state, because
   "waiting" is a pill you can already see and matching it would hide the rest. */
function haystack(r) {
  return [r.client, r.engagement_id, r.scope_path, r.run_id].join(' ').toLowerCase();
}

/* Narrowed to the runs that have stopped on somebody. Off by default: the list is
   ordered newest-first because that is how an analyst finds the job they were just
   working on, and reordering it by state would answer a different question than the one
   somebody usually arrives with. This answers the other one - *what do I do now* - on a
   button, and leaves the default alone. */
let ONLY_NEEDS = false;

function matching() {
  const q = ($('q') ? $('q').value : '').trim().toLowerCase();
  let rows = q ? RUNS.filter(r => haystack(r).includes(q)) : RUNS.slice();
  if (ONLY_NEEDS) rows = rows.filter(r => NEEDS_ATTENTION.has(r.state));
  return rows;
}

/* Runs, folded by engagement. An analyst thinks in clients: a repeat client is one job
   with several runs behind it, and before this the only way to see that was to read
   every row and notice the ids repeating. Groups sort by their newest run, runs within
   a group by their own - so what moved last is at the top at both levels. */
function paintRuns() {
  const rows = matching();
  const q = ($('q') ? $('q').value : '').trim();
  const narrowed = !!q || ONLY_NEEDS;
  const clear = $('q-clear'); const says = $('q-says'); const needs = $('q-needs');
  if (clear) clear.hidden = !narrowed;
  if (needs) {
    // Offered only when there is something to narrow to. A button that filters to
    // nothing is a button that reads as broken.
    const waiting = RUNS.filter(r => NEEDS_ATTENTION.has(r.state)).length;
    needs.hidden = !waiting;
    needs.setAttribute('aria-pressed', ONLY_NEEDS ? 'true' : 'false');
    needs.classList.toggle('primary', ONLY_NEEDS);
    needs.textContent = ONLY_NEEDS ? 'All runs' : `Needs a person (${waiting})`;
  }
  if (says) {
    says.hidden = !narrowed;
    const what = ONLY_NEEDS ? 'needing a person' : '';
    const quoted = q ? `matching “${q}”` : '';
    const both = [quoted, what].filter(Boolean).join(' and ');
    says.textContent = narrowed
      ? (rows.length
          ? `${plural(rows.length, 'run', 'runs')} ${both}.`
          : `No run ${both}. ${plural(RUNS.length, 'run', 'runs')} in all.`)
      : '';
  }

  const groups = new Map();
  for (const r of rows) {
    const key = r.engagement_id;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r);
  }
  const ordered = [...groups.entries()].sort((a, b) =>
    String(b[1][0].started_at || '').localeCompare(String(a[1][0].started_at || '')));

  $('runs').innerHTML = rows.length ? ordered.map(([id, rs]) => {
    // An engagement with one run is one row. The header and the run row carried the
    // client's name, the scope path and the same timestamp each, so a single-run
    // engagement - which is every engagement until a client comes back - printed all
    // three twice and said nothing the second time. The fold earns its line when it is
    // summarising more than one thing; folding one run is indenting it under itself.
    if (rs.length === 1) return runRow(rs[0]);

    const open = rs.reduce((n, r) => n + (r.open_review_items || 0), 0);
    const attention = rs.filter(r => NEEDS_ATTENTION.has(r.state)).length;
    const last = rs.map(r => r.last_ts || r.started_at).sort().pop();
    return `<div class="grp">
      <div class="grp-head">
       <b>${esc(rs[0].client || id)}</b>
       <span class="sub">${esc(rs[0].scope_path || '')}</span>
       <span class="sub">${plural(rs.length, 'run', 'runs')}${open ? ` &middot; <span class="count" title="questions waiting for an answer on this engagement">${open}</span> ${open === 1 ? 'question' : 'questions'}` : ''}${attention ? ` &middot; <b class="wants-a-person">${needAPerson(attention)}</b>` : ''} &middot; ${esc(ago(last))}</span>
      </div>
      <div class="grp-runs">${rs.map(runRow).join('')}</div>
     </div>`;
  }).join('')
   : (RUNS.length ? `<div class="empty"><b>No run matches</b>Nothing here matches what you typed. Clear the box to see all ${RUNS.length}.</div>`
   : `<div class="empty" style="text-align:left;padding:.6rem .2rem"><b>No runs yet - here is how one starts</b>
      <div class="steps" style="margin-top:.6rem">
       <div class="step"><span class="mark">1</span><span><span class="t">Set up an engagement</span><span class="d">On <a href="/admin">Setup</a>: the client, its practice group and its profile.</span></span></div>
       <div class="step"><span class="mark">2</span><span><span class="t">Add the client&rsquo;s files</span><span class="d">The engagement&rsquo;s <b>files</b> button on Setup takes them by drag and drop.</span></span></div>
       <div class="step"><span class="mark">3</span><span><span class="t">Activate it</span><span class="d">When the files stop changing, a run starts and appears here.</span></span></div>
       <div class="step"><span class="mark">4</span><span><span class="t">Answer what it asks</span><span class="d">Items it is not sure about wait for you in <b>Waiting on a person</b>.</span></span></div>
      </div></div>`);
}

function paintRest(inbox, alerts) {
  $('inbox').innerHTML = inbox.length ? inbox.map(i => `<div class="r pick" role="button" tabindex="0" data-act="review" data-run="${esc(i.run_id)}" data-item="${esc(i.item_id)}">
     <span class="lbl"><b>${esc(i.subject || i.item_id)}</b>
      <span class="sub" style="display:block;white-space:normal">${i.client ? esc(i.client) + ' &middot; ' : ''}${esc(i.skill || i.kind || '')}${i.due_at ? ' &middot; due ' + esc(i.due_at.slice(0, 16).replace('T', ' ')) : ''}</span></span>
     <span style="display:flex;flex-direction:column;align-items:flex-end;gap:.3rem">
      ${i.severity ? `<span class="pill ${i.severity === 'high' ? 'bad' : 'warn'}">${esc(i.severity)}</span>` : ''}
      <span class="sub">${esc(i.owner || 'unassigned')}</span>
      <button class="small" data-act="review" data-run="${esc(i.run_id)}" data-item="${esc(i.item_id)}">Review</button>
     </span></div>`).join('')
   : (RUNS.length
      ? '<div class="empty"><b>Nothing waiting</b>Nothing is open for a person on the runs so far.</div>'
      : '<div class="empty"><b>Nothing waiting</b>No run has reached a proposal yet.</div>');

  $('alerts').innerHTML = alerts.length ? alerts.map(a => `<div class="r pick" role="button" tabindex="0" data-act="open" data-run="${esc(a.run_id)}">
     <span class="lbl"><b>${esc(a.kind.replace(/_/g, ' '))}</b><br>
      <span class="sub mono">${esc(a.run_id)} &middot; ${esc(a.subject)}</span></span>
     <span class="pill bad">${esc(a.code || 'alert')}</span></div>`).join('')
   : (RUNS.length
      ? '<div class="empty"><b>Nothing raised</b>No run is silent and no review is overdue.</div>'
      : '<div class="empty"><b>Nothing raised</b>Nothing has run yet.</div>');

  if (current) {
    const run = RUNS.find(r => r.run_id === current);
    if (run) actions(run);
  }
}

/* The run's own actions, beside what it is doing. A quarantined run stopped on itself:
   resume replays it from the frontier; halt ends it, with a reason, and writes its
   manifest. Both are recorded against whoever asked. */
function actions(run) {
  const box = $('run-actions');
  if (!box) return;
  box.innerHTML =
    `<button class="small" data-act="map" data-run="${esc(run.run_id)}" title="Every node of the design, painted with what this run did">See the whole design</button>`
    // Neither of these is primary, and that is the point. The line directly above them
    // says a quarantined run "stopped on itself - a step failed in a way retrying will
    // not fix", and the first version of this made **Resume** the dark button - so the
    // design pointed at the one action the sentence had just said would not work.
    // Resume is right *after* somebody has fixed the cause, which is why it is still
    // here and why it says so.
    + (run.state === 'quarantined'
      ? ` <button class="small" data-act="runAction" data-run="${esc(run.run_id)}" data-do="resume"
          title="Replays from where it stopped. Only useful once whatever stopped it has been fixed - on its own, it stops again.">Resume</button>
       <button class="small ghost" data-act="runAction" data-run="${esc(run.run_id)}" data-do="halt"
          title="End it, with a reason. Nothing partial is delivered and the manifest is written.">Halt</button>`
      : '');
}

async function runAction(runId, action) {
  let reason = '';
  if (action === 'halt') {
    const answer = await ask({
      title: 'End this run', ok: 'Halt the run', danger: true,
      why: 'The run ends without delivering, and its manifest is written. Nothing partial leaves the system.',
      fields: [{name: 'reason', label: 'Why', kind: 'textarea', required: true,
        placeholder: 'e.g. the client sent a corrected trial balance; a new run will pick it up'}],
    });
    if (!answer) return;
    reason = answer.reason;
  } else {
    const answer = await ask({
      title: 'Resume this run', ok: 'Resume',
      why: 'It replays from where it stopped. Whatever made it stop should be fixed first, or it will stop again in the same place.',
      fields: [{name: 'reason', label: 'What changed', kind: 'textarea', required: true}],
    });
    if (!answer) return;
    reason = answer.reason;
  }
  try {
    const r = await post(`/api/runs/${runId}/${action}`, {reason});
    say(`${runId}: ${action === 'halt' ? 'halted' : 'resuming'} (${r.state})`, 'good');
  } catch (e) { say(e.text || String(e), 'bad', e.code); }
  refresh();
}

/* One review item, in the surface's order: the question and the source first; the
   proposal and its confidence only when asked for, and that asking is recorded; then
   the decision, once, at the version the reviewer saw. A reason is required for
   anything but accepting, and a correction carries the corrected value. */
async function review(runId, itemId) {
  let item;
  try { item = await get(`/api/runs/${runId}/review/${itemId}`); }
  catch (e) { return say(e.text || String(e), 'bad', e.code); }
  const run = RUNS.find(r => r.run_id === runId) || {};
  const box = document.createElement('div');
  box.className = 'modal';
  box.innerHTML = `<section class="card" role="dialog" aria-modal="true" aria-label="Review">
    <header><h2>${esc(item.question || item.item_id)}</h2>
     <p class="why">${run.client ? esc(run.client) + ' &middot; ' : ''}${esc(run.engagement_id || '')} &middot; ${esc(item.skill || item.kind)}${item.due_at ? ' &middot; due ' + esc(item.due_at.slice(0, 16).replace('T', ' ')) : ''}</p></header>
    <div class="body">
     ${item.source_excerpt ? `<div class="section-label">What the source says${item.locator ? ' &middot; <span class="mono aside">' + esc(item.locator) + '</span>' : ''}</div>
      <div class="excerpt">${esc(item.source_excerpt)}</div>` : ''}
     ${(item.reasons || []).length ? `<div class="section-label">Why it came to a person</div>
      <ul style="margin:.2rem 0 .8rem 1.1rem;padding:0;font-size:.9rem;color:var(--ink-2)">${item.reasons.map(x => '<li>' + esc(x) + '</li>').join('')}</ul>` : ''}
     <div id="rv-proposal"><div class="reveal"><p>${item.source_excerpt
       ? `Read the source first.`
       : `No excerpt was recorded for this one, so there is nothing above to read - open the file itself before you answer.`} The system's proposal and its confidence are shown when you ask, and the asking is recorded - so an answer given without looking is visible later.</p>
      <button data-act="reveal" data-run="${esc(runId)}" data-item="${esc(itemId)}">Show the proposal</button></div></div>
     <div class="section-label">Your decision</div>
     <div class="decide" id="rv-choices">
      <button data-d="accepted" disabled title="Show the proposal first">Accept</button>
      <button data-d="corrected" disabled title="Show the proposal first">Correct it</button>
      <button data-d="rejected">Reject</button>
      <button data-d="escalated">Escalate</button>
     </div>
     <div id="rv-reason" style="display:none;margin-top:.7rem">
      <label for="rv-rationale">Why</label>
      <textarea id="rv-rationale" rows="3" placeholder="Recorded with the decision"></textarea>
     </div>
    </div>
    <div class="foot"><span class="spacer">Version ${esc(item.version)} &middot; <a href="#review=${encodeURIComponent(runId)}/${encodeURIComponent(itemId)}" title="A link to this item, to send to whoever should answer it">link to this item</a></span>
     <button class="quiet" data-close>Cancel</button>
     <button class="primary" id="rv-submit" disabled>Record decision</button></div>
  </section>`;
  // One dialog at a time, focus moved in and handed back, Escape and the listener handled
  // in the one place any of that is written.
  const close = openModal(box);
  let decision = null;
  let sending = false;
  // Inside this dialog only: two review items open at once carry the same ids, and the
  // second one's fields would otherwise answer the first one's buttons.
  const mine = sel => box.querySelector(sel);
  box.addEventListener('click', e => { if (e.target === box || e.target.dataset.close !== undefined) close(); });
  box.querySelectorAll('#rv-choices button').forEach(b => b.addEventListener('click', () => {
    decision = b.dataset.d;
    box.querySelectorAll('#rv-choices button').forEach(x => x.classList.toggle('on', x === b));
    mine('#rv-reason').style.display = decision === 'accepted' ? 'none' : '';
    box.querySelectorAll('.pv').forEach(i => { i.disabled = decision !== 'corrected'; });
    mine('#rv-submit').disabled = false;
    if (decision !== 'accepted') mine('#rv-rationale').focus();
  }));
  mine('#rv-submit').addEventListener('click', async () => {
    // A second click while the first is in flight sends the same decision at the same
    // version: the surface refuses it as stale, and the person is shown a red refusal for
    // work that succeeded.
    if (sending) return;
    const rationale = mine('#rv-rationale').value;
    if (decision !== 'accepted' && !rationale.trim()) {
      mine('#rv-rationale').focus();
      return say('A ' + decision + ' decision needs a reason - there is no silent override.', 'bad');
    }
    let answer = null;
    if (decision === 'corrected') {
      answer = {};
      box.querySelectorAll('.pv').forEach(i => {
        const raw = i.value, was = i.dataset.type;
        answer[i.dataset.key] = was === 'number' && raw.trim() !== '' && !isNaN(Number(raw)) ? Number(raw)
          : was === 'boolean' ? raw === 'true' : was === 'json' ? JSON.parse(raw || 'null') : raw;
      });
    }
    sending = true;
    mine('#rv-submit').disabled = true;
    try {
      const r = await post(`/api/runs/${encodeURIComponent(runId)}/review/${encodeURIComponent(itemId)}/decide`,
        {decision, expected_version: item.version, rationale, answer});
      close();
      say(`${decision}: ${item.question || itemId}` + (r.open_items ? ` (${r.open_items} still open)` : ' - the run resumes on the next sweep'), 'good');
    } catch (e) {
      sending = false;
      mine('#rv-submit').disabled = false;
      say(e.text || String(e), 'bad', e.code);
    }
    refresh();
  });
}

async function revealProposal(runId, itemId) {
  let p;
  try { p = await post(`/api/runs/${runId}/review/${itemId}/reveal`, {}); }
  catch (e) { return say(e.text || String(e), 'bad', e.code); }
  const entries = Object.entries(p.proposal || {});
  const typeOf = v => typeof v === 'number' ? 'number' : typeof v === 'boolean' ? 'boolean' : (v !== null && typeof v === 'object') ? 'json' : 'text';
  const open = document.querySelector('.modal');
  const into = open ? open.querySelector('#rv-proposal') : null;
  if (!into) return;
  into.innerHTML = `<div class="section-label">What the system proposes${p.confidence !== null && p.confidence !== undefined ? ' &middot; confidence ' + Math.round(p.confidence * 100) + '%' : ''}</div>
    ${entries.length ? `<dl class="kv">${entries.map(([k, v]) => `<dt>${esc(k.replace(/_/g, ' '))}</dt><dd>
      <input class="pv" data-key="${esc(k)}" data-type="${typeOf(v)}" disabled
       value="${esc(typeOf(v) === 'json' ? JSON.stringify(v) : v)}"></dd>`).join('')}</dl>`
      : '<p class="note" style="margin-top:0">The item carries no proposal - it is a question for you to answer.</p>'}`;
  document.querySelectorAll('#rv-choices button').forEach(b => { b.disabled = false; b.title = ''; });
}

/* The 118 nodes of the design, loaded once. The trace says what a run did to some of
   them; the rest are the ones it never touched, which is most of what a trace tells you. */
let GRAPH = null;
const GROUP_ORDER = ['entry', 'intake', 'source', 'privacy', 'orch', 'skill', 'tool',
  'guard', 'hitl', 'out', 'data', 'pref', 'gov', 'ops', 'notice', 'port'];
const GROUP_NAME = {
  entry: 'The engagement', intake: 'Files come in', source: 'Reading them',
  privacy: 'Masking', orch: 'Planning the work', skill: 'Skills', tool: 'Tools',
  guard: 'Guards', hitl: 'People', out: 'Deliverables', data: 'What it knows',
  pref: 'Precedent', gov: 'Governance', ops: 'Watching it work', notice: 'Notices',
  port: 'Ports',
};

let GRAPH_LOADING = null;
async function loadGraph() {
  if (GRAPH) return GRAPH;
  // The promise is cached, not the answer: concurrent callers share one request, and a
  // failure is thrown rather than remembered, so the next attempt is a fresh one.
  if (!GRAPH_LOADING) {
    GRAPH_LOADING = get('/api/graph').then(g => { GRAPH = g; return g; })
      .finally(() => { GRAPH_LOADING = null; });
  }
  return GRAPH_LOADING;
}

function repaint() { if (LAST_TRACE) paint(LAST_TRACE); }

async function paint(trace) {
  LAST_TRACE = trace;
  const g = await loadGraph();
  const seen = trace.nodes || {};
  const onlyTouched = $('touched-only') && $('touched-only').checked;
  const groups = new Map();
  for (const n of g.nodes) {
    if (onlyTouched && !seen[n.id]) continue;
    if (!groups.has(n.group)) groups.set(n.group, []);
    groups.get(n.group).push(n);
  }
  const ordered = GROUP_ORDER.filter(k => groups.has(k))
    .concat([...groups.keys()].filter(k => !GROUP_ORDER.includes(k)));

  $('map').innerHTML = ordered.length ? '<div class="map-groups">' + ordered.map(key => `
    <div class="map-group"><h3>${esc(GROUP_NAME[key] || key)}</h3><div class="map">` +
    groups.get(key).map(n => {
      const state = seen[n.id] || '';
      const running = state === 'active';
      return `<span class="node ${esc(state)}" title="${esc(n.plain || n.label)}">
        ${running ? '<i class="ring"></i>' : ''}<span class="id">${esc(n.id)}</span></span>`;
    }).join('') + '</div></div>').join('') + '</div>'
    : '<div class="empty"><b>Nothing touched yet</b>This run has not reached any node of the design.</div>';

  const touched = Object.keys(seen).length;
  $('map-count').textContent = touched + ' of ' + g.nodes.length + ' touched';

  const failed = Object.entries(trace.diagnostics || {});
  $('diag').innerHTML = failed.length ? failed.map(([node, d]) => `<div class="d-row">
     <span class="code">${esc(node)} &mdash; ${esc(d.code || d.type || 'failed')}</span>
     <span class="msg">${esc(d.message || '')}${d.step_id ? ' <span class="quiet-note">at step ' + esc(d.step_id) + '</span>' : ''}</span>
    </div>`).join('') : '';
}

/* The step statuses the record uses - completed, failed, skipped, quarantined,
   not_reached. `not_reached` is neutral on purpose: a step the run never got to is not a
   step that passed, and it is not a step that failed either. */
const STEP_TONE = {completed: 'good', failed: 'bad', quarantined: 'warn', skipped: '',
  not_reached: ''};

/* The steps of the plan, in order, with what each one cost in attempts. A step that was
   tried twice and a step that ran once are not the same event. */
function steps(run) {
  const box = $('steps');
  if (!box) return;
  const rows = run.steps || [];
  box.innerHTML = rows.length ? `<div class="section-label">Steps</div>` + rows.map(x => `<div class="r">
     <span class="lbl"><b style="font-size:var(--t-sm)">${esc(x.step_id)}</b>
      <span class="sub" style="margin-left:.45rem">${esc(x.skill || x.kind)}</span></span>
     ${x.attempts > 1 ? `<span class="sub" title="attempts">&times;${esc(x.attempts)}</span>` : ''}
     <span class="pill ${STEP_TONE[x.status] ?? ''}">${esc(String(x.status).replace('_', ' '))}</span>
    </div>`).join('') : '';
}

/* What a person settled, against what the system proposed - and whether they revealed the
   proposal before deciding. The queue shows what is outstanding; this is the record of what
   was answered, which is what a reviewer asks for afterwards. */
async function decisions(id) {
  const box = $('decisions');
  if (!box) return;
  const rows = await get(`/api/runs/${encodeURIComponent(id)}/decisions`).catch(() => []);
  box.innerHTML = rows.length ? `<div class="section-label">Decided on this run</div>` + rows.map(d => `<div class="r">
     <span class="lbl"><b>${esc(d.item_id)}</b>
      <span class="d" style="display:block;white-space:normal">${esc(d.decision)} by ${esc(d.decided_by)} &middot; ${esc(ago(d.decided_at))}${d.rationale ? ' &middot; ' + esc(d.rationale) : ''}</span>
      <span class="sub" style="display:block;white-space:normal">${d.revealed_at
        ? 'proposal revealed' + (d.seconds_looking !== null && d.seconds_looking !== undefined ? ` ${esc(d.seconds_looking)}s before the decision` : '')
        : 'decided without the proposal being revealed'}${d.writes_precedent ? ' &middot; written to precedent' : ''}</span></span>
     <span class="pill ${d.decision === 'accepted' ? 'good' : d.decision === 'rejected' ? 'bad' : 'warn'}">${esc(d.decision)}</span>
    </div>`).join('') : '';
}

/* What the run delivered, where it went, and a download of exactly what was released. */
async function deliverables(id) {
  const box = $('deliverables');
  if (!box) return;
  const all = await get(`/api/runs/${encodeURIComponent(id)}/artifacts`).catch(() => []);
  const files = all.filter(a => a.path && !/manifest|\\.json$/i.test(a.name));
  const record = all.filter(a => a.path && /manifest/i.test(a.name));
  box.innerHTML = files.length ? `<div class="section-label" style="margin-top:.2rem">Delivered</div>` + files.map((a, i) => `<div class="r">
     <span class="lbl"><b>${esc(a.name)}</b><span class="sub" style="display:block;white-space:normal">${esc(a.path)} &middot; ${esc(ago(a.written_at))}</span></span>
     ${/\\.xls[xm]$/i.test(a.name) ? `<button class="btn small"${data({act: 'auditFile', run: id, name: a.name, box: 'audit-' + i})}>Check formulas</button>` : ''}
     <a class="btn small" href="/api/runs/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(a.name)}/download">Download</a></div>
     <div id="audit-${i}" class="sub" style="display:none;white-space:normal;padding:.1rem 0 .6rem .2rem"></div>`).join('') : '';
  box.innerHTML += record.length ? `<div class="section-label" style="margin-top:.2rem">Record</div>` + record.map(a => `<div class="r">
     <span class="lbl"><b>Run manifest</b><span class="sub" style="display:block;white-space:normal">what was in context, which model, which skill versions, what each guard said</span></span>
     <a class="btn small" href="/api/runs/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(a.name)}/download">Download</a></div>`).join('') : '';
}

/* What is wrong with the formulas in a workbook this run released.

   Asked for rather than painted on load: reading a workbook's every formula is work, and
   the answer changes the first time somebody opens the file in Excel and saves it - that
   is when the cached totals appear and the footing check becomes able to run at all. So
   the button is the honest shape: press it when you want the current answer. */
async function auditFile(id, name, boxId) {
  const box = $(boxId);
  if (!box) return;
  box.style.display = 'block';
  box.textContent = 'Reading the formulas...';
  let a;
  try { a = await get(`/api/runs/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(name)}/audit`); }
  catch (e) { box.textContent = e.text || String(e); return; }
  const groups = [
    ['wrong', 'Wrong - the file disagrees with itself', 'bad'],
    ['suspect', 'Suspect - worth an eye', 'warn'],
  ];
  let html = `<div>${esc(a.formulas)} formula(s) over ${esc((a.sheets || []).join(', ') || 'no sheets')}</div>`;
  let found = 0;
  for (const [severity, heading, tone] of groups) {
    const rows = (a.findings || []).filter(f => f.severity === severity);
    if (!rows.length) continue;
    found += rows.length;
    html += `<div style="margin-top:.35rem"><span class="pill ${tone}">${esc(heading)}</span></div>`;
    html += rows.map(f => `<div style="margin:.2rem 0 0 .2rem"><b>${esc(f.sheet)}!${esc(f.cell)}</b> ${esc(f.says)}<br><span class="quiet-note">${esc(f.check)}: ${esc(f.formula)}</span></div>`).join('');
  }
  if (!found) html += '<div style="margin-top:.35rem"><span class="pill good">Nothing found</span></div>';
  if ((a.skipped || []).length) {
    html += `<div class="quiet-note" style="margin-top:.35rem">Did not run: ` + a.skipped.map(esc).join(' ') + `</div>`;
  }
  box.innerHTML = html;
}

let OPENING = 0;
async function open_(id) {
  // Two clicks in quick succession used to leave the first run's stream open for ever - the
  // second closed nothing, because the first had not assigned it yet - and could paint the
  // first run's spend beside the second run's name.
  const mine = ++OPENING;
  if (source) { source.close(); source = null; }
  current = id;
  history.replaceState(null, '', '#' + encodeURIComponent(id));
  // By the id the row carries, not by the text of a handler that no longer exists - and
  // an id with an `&` in it used to match nothing, so the selection never moved.
  document.querySelectorAll('#runs .r').forEach(el => el.classList.toggle('on', el.dataset.run === id));
  let run;
  try { run = await get('/api/runs/' + encodeURIComponent(id)); }
  catch (e) { return say(e.text || String(e), 'bad', e.code); }
  const row = RUNS.find(r => r.run_id === id) || {};

  if (mine !== OPENING) return;
  const c = run.scorecard;
  $('detail-title').textContent = row.client || run.engagement_id || 'Run detail';
  $('detail-why').textContent = (run.engagement_id || '') + (run.engagement_id ? ' · ' : '') + id;
  $('card').innerHTML =
    `<div class="r" style="border:0;padding:0 0 .4rem">
      <span class="lbl"><span class="pill ${STATE_TONE[run.state] ?? ''}"><i class="dot"></i>${esc(run.state)}</span>
       ${scorecardPill(c, run.state)}</span>
      <span id="run-actions"></span></div>
     ${run.state_reason ? `<p class="note" style="margin:.1rem 0 .2rem">${esc(STATE_SAYS[run.state] ? STATE_SAYS[run.state] + '.' : '')}</p>
      ${run.state_reason.length > 160
        ? `<details style="margin:0 0 .6rem"><summary><b style="color:var(--navy)">${esc(run.state_reason.slice(0, 150))}&hellip;</b></summary><p class="note" style="margin:.2rem 0 0">${esc(run.state_reason)}</p></details>`
        : `<p style="margin:0 0 .6rem;font-size:.9rem;color:var(--navy);font-weight:600">${esc(run.state_reason)}</p>`}` : ''}
     <dl class="kv" style="margin-bottom:.4rem">
      <dt>Started</dt><dd>${esc((run.started_at || '').slice(0, 16).replace('T', ' '))} <span class="sub">(${esc(ago(run.started_at))})</span></dd>
      ${run.ended_at ? `<dt>Ended</dt><dd>${esc(run.ended_at.slice(0, 16).replace('T', ' '))}</dd>` : ''}
      ${(run.versions || {}).model_pin ? `<dt>Model</dt><dd class="mono" title="the pin this run holds">${esc(run.versions.model_pin)}</dd>` : ''}
      <dt>Model spend</dt><dd>${esc(usd(run.spend ? run.spend.usd : run.cost_usd))}${run.budget_usd ? ` <span class="sub">of ${esc(usd(run.budget_usd))}</span>` : ''} <span class="sub">&middot; ${esc(run.spend ? run.spend.model_calls : run.model_calls)} calls</span></dd>
      ${run.superseded_by ? `<dt>Replaced by</dt><dd><a href="#${encodeURIComponent(run.superseded_by)}" data-act="open" data-run="${esc(run.superseded_by)}">${esc(run.superseded_by)}</a> <span class="sub">&middot; a newer file covers this work</span></dd>` : ''}
      <!-- "Questions waiting", the chrome's words for the same count. P132 retired
           "waiting on you" and replaced it in the two places it was looking; this is the
           fourth, on the panel somebody reads *after* clicking the chrome's number, so the
           two were a click apart and spelled differently. -->
      ${row.open_review_items ? `<dt>Questions waiting</dt><dd><span class="count">${row.open_review_items}</span></dd>` : ''}
     </dl>
     <div id="steps"></div>
     <div id="decisions"></div>
     <div id="deliverables"></div>
     <details><summary>Scorecard &mdash; ${esc(c.criteria.filter(x => x.status === 'pass').length)} passed &middot; ${esc(c.criteria.filter(x => x.status === 'fail').length)} failed &middot; ${esc(c.criteria.filter(x => x.status !== 'pass' && x.status !== 'fail').length)} never measured <span class="mono">(${esc(c.criteria_version)})</span></summary>` +
    c.criteria.map(x => `<div class="r">
      <span class="lbl">${esc(x.label)}
       ${(x.exceptions || []).length ? `<span class="d" style="display:block;white-space:normal">${(x.exceptions || []).map(e => esc(typeof e === 'string' ? e : JSON.stringify(e))).join('<br>')}</span>` : ''}</span>
      <span class="sub mono">${esc(x.measured)}</span>
      <span class="pill ${x.status === 'pass' ? 'good' : x.status === 'fail' ? 'bad' : 'warn'}">${esc(x.status.replace('_', ' '))}</span>
     </div>`).join('') + '</details>';
  actions(row.run_id ? row : run);
  steps(run);
  decisions(id);
  deliverables(id);

  $('feed').innerHTML = '';
  $('feed-src').textContent = 'Replaying ' + id + ' from the event stream.';
  paint(run.trace);

  // The stream replays the record, then follows the bus while the run is live. A run
  // that has ended closes its stream - and a browser reconnects a closed EventSource on
  // its own, replaying the whole history into the feed again. So the page closes it.
  const seen = new Set();
  const ended = () => Boolean(run.ended_at) || ['halted', 'delivered', 'released', 'superseded'].includes(run.state);
  let through = 0, attempts = 0;

  const handler = stream => e => {
    if (source !== stream || mine !== OPENING) return;
    const d = JSON.parse(e.data), ev = d.event;
    if (d.type === 'replayed') {
      through = ev.through || through;
      $('feed-src').textContent = 'Replayed through event ' + through +
        (ended() ? ' — the run has ended.' : ' — following live.');
      // A browser reconnects a closed EventSource by itself and replays the whole history
      // into the feed again, so a run that has ended closes its own stream.
      if (ended() && source) source.close();
      return;
    }
    attempts = 0;
    if (!ev.type || seen.has(ev.event_id || ev.seq)) return;
    seen.add(ev.event_id || ev.seq);
    if (ev.seq) through = Math.max(through, ev.seq);
    const bad = ev.type.endsWith('fail') || ev.type.startsWith('alert.');
    const line = document.createElement('div');
    line.className = 'r';
    line.innerHTML = `<span class="sub mono">${esc((ev.ts || '').slice(11, 19))}</span>
      <span class="lbl"><span class="mono" style="color:${bad ? 'var(--bad)' : 'var(--navy)'}">${esc(ev.type)}</span>
       ${ev.node_id ? `<span class="sub">&middot; ${esc(ev.node_id)}</span>` : ''}
       ${ev.message ? `<span class="d">${esc(ev.message)}</span>` : ''}</span>`;
    $('feed').prepend(line);
    // A long run emits thousands of events; the feed is what is happening now, not a log.
    while ($('feed').childElementCount > 300) $('feed').lastElementChild.remove();
    paint(d.trace);
  };

  const connect = () => {
    const stream = new EventSource('/api/runs/' + encodeURIComponent(id) + '/stream?since=' + through);
    source = stream;
    stream.addEventListener(FRAME, handler(stream));
    stream.onerror = () => {
      stream.close();
      if (source !== stream || mine !== OPENING) return;
      if (ended()) {
        $('feed-src').textContent = 'The run has ended; the feed is what it did.';
        return;
      }
      // A restart, a sleeping laptop or a dropped connection. Resuming from the last event
      // seen, rather than replaying the run from the top or going quietly still.
      if (++attempts > 5) {
        $('feed-src').textContent = 'Lost the live feed after ' + attempts +
          ' attempts. The run carries on; reopen it to try again.';
        return;
      }
      $('feed-src').textContent = 'Lost the live feed — trying again (' + attempts + ')…';
      setTimeout(() => { if (source === stream && mine === OPENING) connect(); },
        Math.min(1000 * Math.pow(2, attempts - 1), 10000));
    };
  };
  connect();
}

/* A link to a run is a link to this page with the run in the fragment, so one can be
   pasted into a message and open on the right run. With no link, the page opens on the
   run most likely to need somebody: one that has stopped, or else the newest. */
refresh().then(() => {
  const wanted = decodeURIComponent(location.hash.slice(1));
  const first = RUNS.find(r => NEEDS_ATTENTION.has(r.state)) || RUNS[0];
  if (wanted.startsWith('map=')) {
    // `#map=run_x` is the whole design for that run; `#map=run_x/node_id` opens it on one
    // node, which is what a person sends when the question is about that node.
    const [runId, ...rest] = wanted.slice(4).split('/');
    open_(runId).then(() => openMap(runId, rest.join('/') || null));
  }
  else if (wanted.startsWith('review=')) {
    // A link to one review item - what a person pastes into a message asking for an answer.
    const [runId, ...rest] = wanted.slice(7).split('/');
    open_(runId);
    review(runId, rest.join('/'));
  }
  else if (wanted) open_(wanted);
  else if (first) open_(first.run_id);
});
poll(refresh, 5000);
</script>
"""
    # Last, and in a block of its own: the map registers its actions on the shell's table
    # and calls functions the page's own script declares, so both have to exist by the time
    # it runs.
    + "<script>"
    + MAP_JS
    + "</script>\n"
)
