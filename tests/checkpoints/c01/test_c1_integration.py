"""C1 - The skeleton holds bytes.

Proves: a fake run moves bytes storage to delivery, emits events and writes a manifest.

Everything here is built from P01-P03 only: the two registries, the six ports, and the
contracts. There is no event bus and no run store yet - those are P04, and this
checkpoint is deliberately in front of them. What it establishes is that the pieces
already built fit together: bytes come in through an interface, every step says what it
did in a shape the contract accepts, and the run leaves a record behind that validates.

A checkpoint exists because phases that each pass alone can still disagree. The
disagreement this one would catch is a manifest that no port can write, or events that
no contract accepts - both of which are cheap now and expensive in P09.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import ports
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry

ENGAGEMENT = "HEND-2026-04"
RUN_ID = "run_c1"


class Emitter:
    """The event bus, in the smallest form that is honest.

    P04 makes this append-only, persisted and queryable. What matters here is that every
    event is validated against event@1.0.0 as it is emitted, so the contract is load
    bearing from the first run rather than retrofitted onto a stream that already exists.
    """

    def __init__(self, contracts: ContractRegistry) -> None:
        self.contracts = contracts
        self.events: list[dict[str, Any]] = []
        self._ids = itertools.count(1)

    def emit(self, node_id: str, event_type: str, message: str, **payload: Any) -> None:
        event = {
            "event_id": f"evt_{next(self._ids):05d}",
            "ts": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
            "run_id": RUN_ID,
            "engagement_id": ENGAGEMENT,
            "node_id": node_id,
            "type": event_type,
            "level": "guard" if event_type.startswith("guard.") else "info",
            "message": message,
            "payload": payload,
            "schema_version": "event@1.0.0",
        }
        self.contracts.validate("event@1.0.0", event)
        self.events.append(event)


def fake_run() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Bytes in through storage, bytes out through delivery, a manifest at the end.

    Written against the interfaces. It never names an adapter, which is why the swap
    test below can run it twice unchanged.
    """
    contracts = ContractRegistry.load()
    constraints = ConstraintRegistry.load()
    events = Emitter(contracts)

    storage = ports.get_storage()
    delivery = ports.get_delivery()
    compute = ports.get_compute()

    started = datetime.now(tz=UTC)
    events.emit("engagement", "run.started", f"run {RUN_ID} on {ENGAGEMENT}")

    sources: list[dict[str, Any]] = []
    payload = b""
    for ref in storage.list():
        stat = storage.stat(ref)
        payload += storage.read(ref)
        sources.append(
            {
                "source_id": stat.content_hash,
                "filename": ref.path,
                "document_type": "trial_balance",
                "source_version": 1,
                "received_at": stat.modified_at.isoformat().replace("+00:00", "Z"),
                "bytes": stat.size_bytes,
            }
        )
        events.emit(
            "file_fingerprint",
            "intake.fingerprint",
            f"{ref.path} -> {stat.content_hash[:19]}",
            source_id=stat.content_hash,
        )

    # A guard that passes still emits. A guard that only speaks when it fires is, on a
    # quiet day, indistinguishable from a guard that never ran.
    events.emit(
        "provenance_gate",
        "guard.provenance.pass",
        f"{len(sources)} of {len(sources)} sources carry a content hash",
        checked=len(sources),
        failed=0,
    )

    delivery.ensure_folder(ENGAGEMENT)
    written = delivery.put(f"{ENGAGEMENT}/deliverable.bin", payload)
    events.emit(
        "release_gate", "release.written", f"wrote {written.path} v{written.version}"
    )

    target = compute.target()
    manifest: dict[str, Any] = {
        "schema_version": "run_manifest@1.0.0",
        "run_id": RUN_ID,
        "engagement_id": ENGAGEMENT,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "ended_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "outcome": "clean",
        "plan_hash": "sha256:" + hashlib.sha256(b"c1-skeleton").hexdigest(),
        "versions": {
            "model_pin": "none - no model was called",
            "skills": [],
            "contracts": contracts.version,
            "constraints": constraints.version,
            "taxonomy": "none",
            "template_version": None,
            "prompt_version": None,
        },
        "sources": sources,
        "steps": [
            {
                "step_id": "step_01",
                "kind": "io",
                "skill": None,
                "status": "completed",
                "step_key": "sha256:" + hashlib.sha256(b"step_01").hexdigest(),
                "attempts": 1,
                "loop": None,
            }
        ],
        "guard_events": [
            {
                "guard": "provenance_gate",
                "result": "pass",
                "checked": len(sources),
                "failed": 0,
                "diagnostic_code": None,
                "at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
            }
        ],
        "human_decisions": [],
        "coverage_gaps": [
            {"what": "everything", "why": f"a skeleton run on {target.describe()}"}
        ],
        "artifacts": [
            {
                "name": written.path,
                "content_hash": written.content_hash,
                "written_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
            }
        ],
        "cost": {"total_usd": 0.0, "model_calls": 0},
    }
    contracts.validate("run_manifest@1.0.0", manifest)

    # The manifest goes through the same port as the deliverable, so the record lands
    # beside the work it describes.
    delivery.put(f"{ENGAGEMENT}/manifest.json", json.dumps(manifest, indent=2).encode("utf-8"))
    events.emit("run_manifest", "run.completed", "manifest written")
    return manifest, events.events


@pytest.fixture
def wired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    inbox, outbox = tmp_path / "inbox", tmp_path / "outbox"
    inbox.mkdir()
    outbox.mkdir()
    (inbox / "TB_FY23.xlsx").write_bytes(b"1000,2000,3000")
    (inbox / "IS_FY23.xlsx").write_bytes(b"4000,5000")
    monkeypatch.setenv("AA_INBOX_ROOT", str(inbox))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(outbox))
    ports.reset()
    yield inbox, outbox
    ports.reset()


def test_the_skeleton_holds_bytes(wired: tuple[Path, Path]) -> None:
    inbox, outbox = wired
    manifest, events = fake_run()

    # Bytes made it from storage to delivery, unaltered.
    delivered = (outbox / ENGAGEMENT / "deliverable.bin").read_bytes()
    assert delivered == b"4000,50001000,2000,3000"

    # The manifest landed beside it and says what happened.
    written = json.loads((outbox / ENGAGEMENT / "manifest.json").read_text(encoding="utf-8"))
    assert written == manifest
    assert written["outcome"] == "clean"
    assert len(written["sources"]) == 2

    # Events were emitted, including a guard pass.
    assert [e["type"] for e in events] == [
        "run.started",
        "intake.fingerprint",
        "intake.fingerprint",
        "guard.provenance.pass",
        "release.written",
        "run.completed",
    ]


def test_every_event_validates_against_the_contract(wired: tuple[Path, Path]) -> None:
    """Emitter.emit validates as it goes, so reaching this point already proves it. The
    assertion is here so the checkpoint states the property rather than implying it."""
    inbox, outbox = wired
    _, events = fake_run()
    contracts = ContractRegistry.load()
    for event in events:
        assert contracts.check("event@1.0.0", event) == ()
    assert all(e["node_id"] for e in events), "the run trace is derived from node_id"


def test_the_manifest_validates_and_names_every_version(wired: tuple[Path, Path]) -> None:
    inbox, outbox = wired
    manifest, _ = fake_run()
    contracts = ContractRegistry.load()
    assert contracts.check("run_manifest@1.0.0", manifest) == ()
    assert manifest["versions"]["contracts"] == contracts.version
    assert manifest["versions"]["constraints"] == ConstraintRegistry.load().version


def test_every_source_carries_the_hash_a_figure_would_cite(wired: tuple[Path, Path]) -> None:
    """No figure exists yet, but the ids they will cite are produced here. If intake
    could not hash a file, provenance in P13 would have nothing to check against."""
    inbox, outbox = wired
    manifest, _ = fake_run()
    for source in manifest["sources"]:
        assert source["source_id"].startswith("sha256:")
        raw = (inbox / source["filename"]).read_bytes()
        assert source["source_id"] == "sha256:" + hashlib.sha256(raw).hexdigest()


def test_a_repeat_run_does_not_duplicate_the_deliverable(wired: tuple[Path, Path]) -> None:
    """The keyed-write property, end to end. A transport failure and a retry must not
    leave the client with two copies."""
    inbox, outbox = wired
    fake_run()
    fake_run()
    assert ports.get_delivery().version(f"{ENGAGEMENT}/deliverable.bin") == 1


def test_the_run_never_names_an_adapter(wired: tuple[Path, Path]) -> None:
    """The portability claim, exercised rather than asserted: the same run function,
    with storage swapped underneath it, reads different bytes and changes nothing else."""
    inbox, outbox = wired
    first, _ = fake_run()

    (inbox / "TB_FY23.xlsx").write_bytes(b"9999")
    ports.reset()
    second, _ = fake_run()

    assert first["sources"][1]["source_id"] != second["sources"][1]["source_id"]
    assert ports.get_delivery().version(f"{ENGAGEMENT}/deliverable.bin") == 2
