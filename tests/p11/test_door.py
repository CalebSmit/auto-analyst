"""The one door: one turn, scanned, budgeted, pinned, metered - in that order.

Three of the four exit criteria pass through here. The fourth, the ceilings, has its own
file because each of the four needs its own test.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from harness.door import ModelDoor
from ops.run_store import SqlRunStore
from ports.llm import Message, Usage
from privacy.payload_scan import IdentifierList, ScanFailed
from registries.errors import RegistryError
from tests.p11.conftest import ENGAGEMENT, Answers, masked_request

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- one turn


def test_a_single_turn_request_is_sent(
    door: ModelDoor, identifiers: IdentifierList, started: str, port: Answers
) -> None:
    call = door.send(masked_request(), identifiers, started, step_id="tagging")
    assert call.response.text == "ok"
    assert len(port.requests) == 1
    assert call.request_hash.startswith("sha256:")


def test_a_request_carrying_an_assistant_turn_raises_before_it_is_sent(
    door: ModelDoor, identifiers: IdentifierList, started: str, port: Answers
) -> None:
    """The exit criterion. A conversation with a prior assistant message is turn two of
    something, and a skill does not have one of those."""
    second_turn = masked_request(messages=(
        Message("user", "[[ACCOUNT_17]] categorise."),
        Message("assistant", "owner_compensation"),
        Message("user", "are you sure?"),
    ))
    with pytest.raises(RegistryError) as raised:
        door.send(second_turn, identifiers, started)
    assert raised.value.diagnostic.code == "POLICY.MULTI_TURN_STEP"
    assert "turn 2" in str(raised.value)
    assert port.requests == [], "it was sent anyway"


def test_two_user_messages_is_also_not_one_turn(
    door: ModelDoor, identifiers: IdentifierList, started: str, port: Answers
) -> None:
    with pytest.raises(RegistryError, match="MULTI_TURN_STEP"):
        door.send(masked_request(messages=(
            Message("user", "[[ACCOUNT_17]]"), Message("user", "[[PERSON_1]]"),
        )), identifiers, started)
    assert port.requests == []


def test_the_turn_check_runs_before_the_scan(
    door: ModelDoor, identifiers: IdentifierList, started: str, store: SqlRunStore
) -> None:
    """Order matters for the record: a multi-turn request with raw names in it should
    fail as multi-turn, and no scan event should claim it was checked."""
    with pytest.raises(RegistryError, match="MULTI_TURN_STEP"):
        door.send(masked_request(messages=(
            Message("user", "Bob Henderson"), Message("assistant", "x"), Message("user", "y"),
        )), identifiers, started)
    assert not [e for e in store.events(started) if e.type.startswith("guard.payload_scan")]


# ---------------------------------------------------------------- the scan


def test_every_outbound_payload_passes_the_scan(
    door: ModelDoor, identifiers: IdentifierList, started: str, store: SqlRunStore
) -> None:
    """The exit criterion, first half. A pass is recorded, so silence is never
    ambiguous."""
    call = door.send(masked_request(), identifiers, started, step_id="tagging")
    passes = [e for e in store.events(started) if e.type == "guard.payload_scan.pass"]
    assert len(passes) == 1
    assert passes[0].payload["checked"] == call.scan_checked == 6
    assert passes[0].payload["tokens_seen"] == 3


def test_a_no_op_masker_is_caught_at_the_door(
    door: ModelDoor, identifiers: IdentifierList, started: str, port: Answers,
    store: SqlRunStore,
) -> None:
    """The exit criterion, second half. The masker did nothing: the names are still in
    the payload and the tokens it was meant to write are absent. Nothing leaves."""
    unmasked = masked_request(
        system="You are tagging line items for Henderson Manufacturing.",
        messages=(Message("user", "Bob's LLC Checking 48,231.00 — categorise."),),
    )
    with pytest.raises(ScanFailed) as raised:
        door.send(unmasked, identifiers, started, step_id="tagging")

    assert raised.value.diagnostic.code == "PRIVACY.UNMASKED_IDENTIFIER"
    assert port.requests == [], "the payload left"
    fails = [e for e in store.events(started) if e.type == "guard.payload_scan.fail"]
    assert len(fails) == 1
    assert fails[0].diagnostic_code == "PRIVACY.UNMASKED_IDENTIFIER"
    assert fails[0].payload["hits"] == 2
    assert fails[0].payload["missing_tokens"] == ["[[ACCOUNT_17]]", "[[CLIENT_1]]", "[[PERSON_1]]"]


def test_the_scan_never_echoes_the_identifier(
    door: ModelDoor, identifiers: IdentifierList, started: str, store: SqlRunStore
) -> None:
    """An error that quoted the name would be the leak the scan exists to prevent, one
    level up."""
    with pytest.raises(ScanFailed) as raised:
        door.send(masked_request(system="Bob Henderson"), identifiers, started)
    for name in ("Henderson", "Bob"):
        assert name not in str(raised.value)
        for event in store.events(started):
            assert name not in event.message
            assert name not in str(event.payload)


def test_the_system_prompt_is_scanned_too(
    door: ModelDoor, identifiers: IdentifierList, started: str
) -> None:
    with pytest.raises(ScanFailed):
        door.send(masked_request(system="Henderson Manufacturing"), identifiers, started)


# ------------------------------------------------------------------ the pin


def test_a_response_from_a_different_model_is_refused(
    identifiers: IdentifierList, started: str, bus, governor, meter
) -> None:
    """A provider substituting a model is the most common way reproducibility is lost
    without anyone choosing it. The answer is not used."""
    from privacy.payload_scan import PayloadScan

    substituted = Answers(model="claude-haiku-4-5")
    door = ModelDoor(substituted, PayloadScan(bus), governor, meter, bus)
    with pytest.raises(RegistryError) as raised:
        door.send(masked_request(), identifiers, started)
    assert raised.value.diagnostic.code == "SCOPE.MODEL_PIN_UNAVAILABLE"


def test_a_dated_model_id_still_matches_its_pin(
    identifiers: IdentifierList, started: str, bus, governor, meter
) -> None:
    """The API may answer with a dated id for the pinned alias. That is the pin."""
    from privacy.payload_scan import PayloadScan

    dated = Answers(model="claude-sonnet-5-20260401")
    door = ModelDoor(dated, PayloadScan(bus), governor, meter, bus)
    assert door.send(masked_request(), identifiers, started).response.model.startswith(
        "claude-sonnet-5"
    )


# -------------------------------------------------------------- the meter


def test_the_cost_meter_agrees_with_the_usage_the_api_reports(
    identifiers: IdentifierList, started: str, bus, governor, meter, store: SqlRunStore
) -> None:
    """The exit criterion. 1,200 in and 300 out on Sonnet at $2/$10 per MTok is
    $0.0024 + $0.0030. The meter has no other input to disagree with."""
    from privacy.payload_scan import PayloadScan

    port = Answers(usage=Usage(input_tokens=1200, output_tokens=300))
    door = ModelDoor(port, PayloadScan(bus), governor, meter, bus)
    call = door.send(masked_request(), identifiers, started)

    assert call.charge.usd == pytest.approx(0.0054)
    assert call.charge.input_tokens == 1200
    assert call.charge.output_tokens == 300
    run = store.run(started)
    assert run.cost_usd == pytest.approx(0.0054)
    assert (run.input_tokens, run.output_tokens, run.model_calls) == (1200, 300, 1)


def test_the_record_carries_the_call_and_the_answer(
    door: ModelDoor, identifiers: IdentifierList, started: str, store: SqlRunStore
) -> None:
    door.send(masked_request(), identifiers, started, step_id="tagging")
    types = [e.type for e in store.events(started)]
    assert types.index("guard.payload_scan.pass") < types.index("model.called")
    assert types.index("model.called") < types.index("model.answered")
    answered = next(e for e in store.events(started) if e.type == "model.answered")
    assert answered.node_id == "cost_meter"
    assert answered.cost_usd == pytest.approx(0.0054)


# ------------------------------------------------------ structurally the only way


def test_nothing_outside_the_door_calls_a_port(
) -> None:
    """The one door, as a property of the code. Outside harness/door.py, the ports
    package and the tests, no module calls `.complete(` on anything."""
    offenders: list[str] = []
    for package in ("harness", "graph", "privacy", "guards", "ops", "registries", "skills"):
        for path in sorted((ROOT / package).rglob("*.py")):
            if path == ROOT / "harness" / "door.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "complete"
                ):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, f"{offenders} reach a model around the door"


def test_the_door_has_one_method() -> None:
    public = [
        n for n in dir(ModelDoor) if not n.startswith("_") and callable(getattr(ModelDoor, n))
    ]
    assert public == ["send"]


def test_the_engagement_on_the_record_is_the_identifier_lists(
    door: ModelDoor, identifiers: IdentifierList, started: str, store: SqlRunStore
) -> None:
    door.send(masked_request(), identifiers, started)
    assert {e.engagement_id for e in store.events(started)} == {ENGAGEMENT}
