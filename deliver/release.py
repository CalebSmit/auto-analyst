"""The Single Release Gate and the Idempotency Ledger: one node, one way out.

The sole release point for client work. Its one inbound edge is the Deliverable QC
Gate: nothing is handed to the Delivery Port that QC did not pass, and a failure routes
to the Fixed Notice rather than to a partially valid deliverable. The run manifest is
the one thing that bypasses this gate, deliberately - it is a record, not client work,
and it must be written even when a run halts.

The ledger records run id, artifact hash and destination in the same transaction as the
release event. A repeat release with the same key is a no-op that returns the original
location rather than creating a second file. It covers the case that actually happens:
a delivery succeeds, the acknowledgement is lost, and the step is retried. Exactly-once
delivery over an at-least-once transport is a ledger, not a hope.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from deliver.qc import DeliverableQC
from guards import GuardFailed
from harness.notice import Notice, notice
from ops.events import EventBus
from ops.run_store import ReleaseRecord, SqlRunStore
from ports.delivery import DeliveryPort
from registries.errors import QC_FAILED, DiagnosticError, diagnose

__all__ = ["ReleaseGate", "ReleaseRefused", "Released", "release_path"]

NODE = "release_gate"


class ReleaseRefused(DiagnosticError):
    """QC did not pass. Nothing was delivered, and the notice says so."""

    def __init__(self, diagnostic: Any, fixed_notice: Notice) -> None:
        super().__init__(diagnostic)
        self.notice = fixed_notice


@dataclass(frozen=True)
class Released:
    run_id: str
    name: str
    path: str
    content_hash: str
    version: int
    already_released: bool
    """True when the ledger already held this key: the original location is returned
    and the port was not asked to write again."""


def release_path(engagement_id: str, run_id: str, name: str) -> str:
    return f"{engagement_id}/{run_id}/{name}"


class ReleaseGate:
    def __init__(
        self,
        store: SqlRunStore,
        bus: EventBus,
        delivery: DeliveryPort,
        qc: DeliverableQC | None = None,
    ) -> None:
        self.store = store
        self.bus = bus
        self.delivery = delivery
        self.qc = qc or DeliverableQC(bus)

    def release(
        self,
        run_id: str,
        engagement_id: str,
        name: str,
        data: bytes,
        *,
        template_version: str | None = None,
        expected: Mapping[str, Any] | None = None,
        owner: str = "the engagement owner",
    ) -> Released:
        """QC, then the ledger, then the port - and the ledger decides whether the port
        is asked at all."""
        try:
            result = self.qc.run(
                data,
                run_id,
                engagement_id,
                "release",
                template_version=template_version,
                expected=expected,
            )
        except GuardFailed as failed:
            result = failed.result
        if not result.passed:
            fixed = notice(
                "blocked_release",
                deliverable=name,
                engagement=engagement_id,
                check="deliverable_qc",
                owner=owner,
            )
            self.bus.emit(
                run_id=run_id,
                engagement_id=engagement_id,
                node_id=NODE,
                type="release.blocked",
                level="error",
                message=f"{name}: QC failed, nothing released",
                step_id="release",
                diagnostic_code=QC_FAILED,
                payload={"artifact": name, "reasons": list(result.reasons), "notice": fixed.text},
            )
            raise ReleaseRefused(
                diagnose(
                    QC_FAILED,
                    f"{name}: {'; '.join(result.reasons)}",
                    locator=f"{run_id}/{name}",
                    step_id="release",
                ),
                fixed,
            )

        digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
        prior = self.store.release_for(run_id, digest)
        if prior is not None:
            self.bus.emit(
                run_id=run_id,
                engagement_id=engagement_id,
                node_id="idempotency_ledger",
                type="release.replayed",
                message=f"{name}: already released to {prior.path}; not written again",
                step_id="release",
                payload={"artifact": name, "content_hash": digest, "path": prior.path},
            )
            return Released(
                run_id=run_id,
                name=name,
                path=prior.path,
                content_hash=digest,
                version=prior.version,
                already_released=True,
            )

        path = release_path(engagement_id, run_id, name)
        self.delivery.ensure_folder(f"{engagement_id}/{run_id}")
        written = self.delivery.put(path, data)
        event = self.bus.draft(
            run_id=run_id,
            engagement_id=engagement_id,
            node_id=NODE,
            type="release.written",
            message=f"{name} released to {written.path} ({digest[:19]}...)",
            step_id="release",
            payload={
                "artifact": name,
                "content_hash": digest,
                "path": written.path,
                "version": written.version,
                "template_version": template_version,
            },
        )
        record: ReleaseRecord = self.store.record_release(
            run_id, digest, written.path, written.version, name, event
        )
        self.store.record_artifact(run_id, name, digest, path=written.path)
        return Released(
            run_id=run_id,
            name=name,
            path=record.path,
            content_hash=digest,
            version=record.version,
            already_released=False,
        )
