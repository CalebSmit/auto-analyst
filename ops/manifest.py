"""The Run Manifest: what the run did, assembled at the end and written every time.

The one rule in this module is the one worth reading the code to check: **there is no
branch on outcome anywhere in the write path.** A run that halted needs its manifest more
than a run that delivered, because it is the halted run somebody will ask about - what
did the system check, on what sources, and what stopped it. A record that only exists
when things went well is not a record.

So `close_out` is the single door out of a run. It ends the run in the store, assembles
the manifest from what the store holds, validates it against `run_manifest@1.0.0`, and
writes it through the Delivery Port beside the deliverable. Every terminal state goes
through here, which is enforced upstream: `SqlRunStore.transition` refuses a terminal
target and tells the caller to use `end_run`, and `end_run` is what this wraps.

Assembled rather than maintained: it is written once, at the end, so it is a clean
artifact rather than live mutable state that can be caught half-updated. Immutability
comes from destination versioning, not from everyone remembering not to overwrite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ops.events import EventBus
from ops.models import Outcome, RunState, RunStoreError
from ops.run_store import RunRecord, RunStore
from registries.contracts import ContractRegistry
from registries.errors import MANIFEST_INCOMPLETE, ContractViolation, diagnose

MANIFEST_CONTRACT = "run_manifest@1.0.0"
MANIFEST_NAME = "run_manifest.json"

# What `versions` has to be able to name for a run to be reproducible. Exported so
# preflight can check it at second zero rather than discovering it at close-out.
REQUIRED_VERSIONS = ("model_pin", "skills", "contracts", "constraints", "taxonomy")

__all__ = [
    "MANIFEST_CONTRACT",
    "MANIFEST_NAME",
    "REQUIRED_VERSIONS",
    "ManifestIncomplete",
    "ManifestResult",
    "assemble",
    "check_versions",
    "close_out",
    "manifest_path",
]


class ManifestIncomplete(RunStoreError):
    """The assembled manifest does not satisfy run_manifest@1.0.0."""


@dataclass(frozen=True)
class ManifestResult:
    """What close-out produced. Enough to prove the record landed."""

    run: RunRecord
    manifest: dict[str, Any]
    path: str
    content_hash: str
    version: int
    already_present: bool


def manifest_path(engagement_id: str, run_id: str) -> str:
    """Beside the work it describes, not somewhere else entirely."""
    return f"{engagement_id}/{run_id}/{MANIFEST_NAME}"


def check_versions(versions: dict[str, Any]) -> tuple[str, ...]:
    """Which required version pins are missing. Empty means the run can be closed out."""
    return tuple(name for name in REQUIRED_VERSIONS if not versions.get(name))


def assemble(store: RunStore, run_id: str, bus: EventBus | None = None) -> dict[str, Any]:
    """Build the manifest from the run store. Reads only; writes nothing.

    `guard_events` comes from the event stream rather than from a table of its own,
    which is what makes "every guard result, passes included" a property of the record
    instead of a second thing to remember to write.
    """
    run = store.run(run_id)
    reader = bus or EventBus(store)

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_CONTRACT,
        "run_id": run.run_id,
        "engagement_id": run.engagement_id,
        "started_at": run.started_at,
        "ended_at": run.ended_at or run.started_at,
        "outcome": str(run.outcome) if run.outcome else str(Outcome.BLOCKED),
        "plan_hash": run.plan_hash,
        "versions": dict(run.versions),
        "sources": [dict(source) for source in run.sources],
        "steps": [
            {
                "step_id": step.step_id,
                "kind": step.kind,
                "skill": step.skill,
                "status": str(step.status),
                "step_key": step.step_key,
                "attempts": step.attempts,
                "loop": step.loop,
            }
            for step in store.steps(run_id)
        ],
        "guard_events": [
            {
                "guard": result.guard,
                "result": result.result,
                "checked": result.checked,
                "failed": result.failed,
                "diagnostic_code": result.diagnostic_code,
                "at": result.at,
            }
            for result in reader.guard_results(run_id)
        ],
        "human_decisions": [
            {
                "item_id": decision.item_id,
                "decided_by": decision.decided_by,
                "decided_at": decision.decided_at,
                "decision": str(decision.decision),
                "rationale": decision.rationale,
                "writes_precedent": decision.writes_precedent,
            }
            for decision in store.decisions(run_id)
        ],
        "coverage_gaps": [dict(gap) for gap in run.coverage_gaps],
        "artifacts": [
            {
                "name": artifact.name,
                "content_hash": artifact.content_hash,
                "written_at": artifact.written_at,
            }
            for artifact in store.artifacts(run_id)
        ],
        "cost": {
            "total_usd": run.cost_usd,
            "model_calls": run.model_calls,
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
        },
    }
    if run.tieout_tolerance is not None:
        manifest["tieout_tolerance"] = run.tieout_tolerance
    return manifest


def close_out(
    store: RunStore,
    run_id: str,
    state: RunState,
    outcome: Outcome,
    delivery: Any,
    *,
    bus: EventBus | None = None,
    contracts: ContractRegistry | None = None,
    reason: str | None = None,
) -> ManifestResult:
    """End the run and write its manifest. The only way a run ends.

    The order is: end the run, then assemble - so `ended_at` and `outcome` are in the
    record rather than predicted. If the delivery write fails, that failure propagates:
    the run is over either way, and a close-out that quietly produced no manifest would
    be the one kind of silence this system is built to not have.
    """
    run = store.end_run(run_id, state, outcome, reason=reason)
    reader = bus or EventBus(store, contracts=contracts)
    registry = contracts or ContractRegistry.load()

    manifest = assemble(store, run_id, bus=reader)
    _require_valid(registry, manifest)

    body = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    path = manifest_path(run.engagement_id, run.run_id)
    delivery.ensure_folder(f"{run.engagement_id}/{run.run_id}")
    written = delivery.put(path, body)

    store.record_artifact(run_id, MANIFEST_NAME, written.content_hash, path=written.path)
    reader.emit(
        run_id=run_id,
        engagement_id=run.engagement_id,
        node_id="run_manifest",
        type="run.manifest.written",
        message=f"manifest written for a {state} run ({outcome})",
        payload={
            "path": written.path,
            "content_hash": written.content_hash,
            "version": written.version,
            "guard_events": len(manifest["guard_events"]),
            "steps": len(manifest["steps"]),
        },
    )
    return ManifestResult(
        run=run,
        manifest=manifest,
        path=written.path,
        content_hash=written.content_hash,
        version=written.version,
        already_present=written.already_present,
    )


def _require_valid(contracts: ContractRegistry, manifest: dict[str, Any]) -> None:
    missing = check_versions(manifest.get("versions", {}))
    if missing:
        raise ManifestIncomplete(
            diagnose(
                MANIFEST_INCOMPLETE,
                f"versions is missing {', '.join(missing)}; a run that cannot name "
                f"what produced a figure cannot defend it",
                locator=f"{manifest.get('run_id')}.versions",
            )
        )
    try:
        contracts.validate(MANIFEST_CONTRACT, manifest)
    except ContractViolation as violation:
        raise ManifestIncomplete(
            diagnose(
                MANIFEST_INCOMPLETE,
                str(violation.diagnostic),
                locator=str(manifest.get("run_id")),
            )
        ) from violation
