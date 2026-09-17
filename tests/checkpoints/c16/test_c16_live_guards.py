"""Checkpoint C16 - a citation is checked where it points.

Proves: the system a person starts calls every output guard the blueprint says runs on a
skill step, and the eleven adversarial fixtures still each fire their own guard.

The finding behind P39 was not a bug in a guard. It was that two guards were built, tested
and passed, and the composition root never handed them to the dispatcher - so every test of
the guard was green and no live run was guarded. A checkpoint that asks the guard again would
pass again. This one asks the assembled system.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from cryptography.fernet import Fernet

from harness.dispatch import SkillDispatcher
from tools.serve import build

ROOT = Path(__file__).resolve().parents[3]

# The blueprint's output guards and the dispatcher attribute that carries each. The Policy
# Gate, Budget Governor, Untrusted Boundary and Payload Scan are wired through the runtime,
# the door and the context builder, and C06/C13 already prove those on a live path.
OUTPUT_GUARDS = {
    "schema_gate": "schema",
    "provenance_gate": "provenance",
    "tieout_gate": "recompute",
}


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c16.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    (tmp_path / "inbox").mkdir()
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    system = build()
    yield system
    system.close()
    ports.reset()


def test_the_blueprints_output_guards_are_step_guards_that_exist_now() -> None:
    nodes = {
        n["id"]: n
        for n in json.loads((ROOT / "graph/architecture.json").read_text("utf-8"))["nodes"]
    }
    for node_id in OUTPUT_GUARDS:
        node = nodes[node_id]
        assert node["runtime"] == "step" and node["now"] and node["failClosed"], node_id


def test_the_system_a_person_starts_hands_every_output_guard_to_the_dispatcher(served: Any) -> None:
    assert served.pool is not None, "the driver was built; readiness() says why if not"
    dispatcher = served.pool.passes.wiring.dispatcher_for("run_c16")
    assert isinstance(dispatcher, SkillDispatcher)
    unwired = [
        node for node, attr in OUTPUT_GUARDS.items() if getattr(dispatcher, attr, None) is None
    ]
    assert unwired == [], (
        f"guards the blueprint runs on every step that no live run calls: {unwired}"
    )
    assert dispatcher.sources_for is not None and dispatcher.tolerance_for is not None


def test_every_adversarial_fixture_names_a_distinct_failure() -> None:
    table = yaml.safe_load((ROOT / "fixtures/guards/fixtures.yaml").read_text(encoding="utf-8"))
    rows = table["fixtures"]
    assert len(rows) == 11
    provenance = {r["fires"] for r in rows if r["guard"] == "provenance"}
    assert provenance == {"SKILL.FABRICATED_SOURCE", "SKILL.CITED_VALUE_ABSENT"}
