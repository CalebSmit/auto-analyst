"""Releasing a run: the window said yes, so exactly one run starts over the whole set.

What happens, in order, and each step is on the record:

1. A run is registered, queued.
2. The Engagement Lock is taken, or the run stays queued behind the holder.
3. Every file in the current set becomes a `sources` row on the run - the manifest's
   own shape - and every missing required type becomes a coverage gap with a review
   item, because "we are still waiting on the client" is a fact a person should see.
4. The pending files are marked consumed by this run.
5. Any earlier run that consumed an older version of a file in this set is marked
   superseded by this one. Its manifest is retained, never overwritten; a run still in
   flight is marked and left to finish.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from graph.recipes import Recipe
from intake.lock import EngagementLock, LockResult
from intake.store import IntakeStore
from intake.window import Verdict
from ops.events import EventBus
from ops.run_store import SqlRunStore

__all__ = ["Launched", "RunLauncher"]

NODE = "intake_window"


@dataclass(frozen=True)
class Launched:
    run_id: str
    engagement_id: str
    lock: LockResult
    sources: int
    gaps: tuple[str, ...] = ()
    superseded: tuple[str, ...] = ()
    review_item_id: str | None = None

    @property
    def queued(self) -> bool:
        return not self.lock.acquired


class RunLauncher:
    def __init__(
        self,
        store: SqlRunStore,
        bus: EventBus,
        lock: EngagementLock,
        intake_store: IntakeStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.bus = bus
        self.lock = lock
        self.intake_store = intake_store
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    def launch(
        self,
        engagement_id: str,
        recipe: Recipe,
        verdict: Verdict,
        *,
        plan_hash: str,
        versions: dict[str, Any],
        run_id: str | None = None,
        tieout_tolerance: float | None = None,
    ) -> Launched:
        if not verdict.release:
            raise ValueError(f"the window did not release {engagement_id}: {verdict.reason}")
        run_id = run_id or f"run_{uuid4().hex[:12]}"
        self.store.start_run(
            run_id=run_id,
            engagement_id=engagement_id,
            plan_hash=plan_hash,
            versions=versions,
            tieout_tolerance=tieout_tolerance,
        )
        lock = self.lock.acquire(engagement_id, run_id)

        for row in verdict.current_set:
            self.store.record_source(run_id, row.as_source())
        for missing in verdict.missing_types:
            self.store.record_gap(
                run_id,
                what=f"required document type {missing}",
                why=(
                    f"not received before max_wait; {recipe.key} proceeds with an explicit "
                    f"gap rather than treating what arrived as what exists"
                ),
            )
        item_id: str | None = None
        if verdict.missing_types:
            item_id = f"coverage_gap:{run_id}"
            self.store.open_review_item(
                run_id,
                item_id,
                kind="coverage_gap",
                subject=(
                    f"{engagement_id}: the intake set never completed - missing "
                    f"{', '.join(verdict.missing_types)}"
                ),
                detail={
                    "missing_types": list(verdict.missing_types),
                    "present": [r.filename for r in verdict.current_set],
                    "held": [r.filename for r in verdict.held],
                    "waited_hours": round(verdict.waiting_for.total_seconds() / 3600, 2),
                },
            )
            self.bus.emit(
                run_id=run_id,
                engagement_id=engagement_id,
                node_id=NODE,
                type="hitl.item.queued",
                message=f"{engagement_id}: intake set never completed; run proceeds with a gap",
                level="warn",
                payload={"item_id": item_id, "missing_types": list(verdict.missing_types)},
            )

        self.intake_store.mark_consumed(
            engagement_id, [r.source_id for r in verdict.pending], run_id
        )
        superseded = self._supersede(engagement_id, verdict, run_id)

        self.bus.emit(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type="run.launched",
            message=f"{engagement_id}: {verdict.reason}",
            payload={
                "recipe": recipe.key,
                "sources": len(verdict.current_set),
                "new_this_run": len(verdict.pending),
                "gaps": list(verdict.missing_types),
                "held": [r.filename for r in verdict.held],
                "superseded": list(superseded),
                "lock": "acquired" if lock.acquired else f"queued at {lock.position}",
            },
        )
        return Launched(
            run_id=run_id,
            engagement_id=engagement_id,
            lock=lock,
            sources=len(verdict.current_set),
            gaps=verdict.missing_types,
            superseded=superseded,
            review_item_id=item_id,
        )

    def _supersede(self, engagement_id: str, verdict: Verdict, run_id: str) -> tuple[str, ...]:
        """Every earlier run that consumed an older version of a file now in the set."""
        older: set[str] = set()
        for row in verdict.current_set:
            for version, consumer in self.intake_store.runs_that_consumed(
                engagement_id, row.filename
            ):
                if version < row.source_version and consumer != run_id:
                    older.add(consumer)
        for old in sorted(older):
            record = self.store.run(old)
            if record.superseded_by:
                continue
            self.store.mark_superseded_by(old, run_id)
            self.bus.emit(
                run_id=old,
                engagement_id=engagement_id,
                node_id=NODE,
                type="run.superseded",
                message=f"{old}: a newer source version is covered by {run_id}; manifest retained",
                payload={"superseded_by": run_id, "was_finished": record.ended_at is not None},
            )
        return tuple(sorted(older))
