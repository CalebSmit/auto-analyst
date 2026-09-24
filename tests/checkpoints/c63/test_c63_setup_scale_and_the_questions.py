"""C63 - the four things between a real folder and a run that gets anywhere.

* **P107** made "Ready to run" mean a machine could actually mask and actually ask.
* **P108** did the multiplication nobody did: a figure at the client's scale, restated to
  the template's, once, outside the writer so the Numeric Integrity Lock still means what
  it says.
* **P109** pointed the system at the contract version that carries the arrival scale,
  which had been registered and wired to nothing - so the one field the settlement reads
  was the one field a person was refused for sending.
* **P110** told the skill that dates periods when this company's year ends, which the
  profile had recorded and nobody had passed on.

Each is green alone. What a checkpoint asks is whether they agree, and here they have one
seam in common: **a fact a person recorded at setup, travelling to the place that needs
it.** The arrival scale (P109, P106) and the fiscal calendar (P110) both start on the same
form, both reach different steps, and both are read by code that must not substitute a
default when they are silent. P108 is what the first of them is *for*, and P107 is the page
that says whether any of it would happen.

So the question across the four: can one profile, filled in once, be followed all the way
to a restated figure - and does every step still refuse to guess when the profile says
nothing?
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from deliver.builder import _value_of
from harness.inputs import _calendar_of
from harness.procedures.timing_normalization import (
    NO_CALENDAR,
    SourceFile,
    TimingInputs,
    TimingNormalization,
)
from harness.restate import restated
from intake.config import PROFILE_CONTRACT, PROFILES_SUPPORTED
from registries.contracts import ContractRegistry
from registries.errors import RegistryError

ROOT = Path(__file__).resolve().parents[3]


def profile(**over: Any) -> dict[str, Any]:
    """A profile as the Setup page would hand it back, at the version the store takes."""
    body: dict[str, Any] = {
        "schema_version": PROFILE_CONTRACT,
        "engagement_id": "KSPW-2026-01",
        "practice": "valuation",
        "segment": "non-esop",
        "disposition": "non-repeat",
        "industry_classification": {
            "system": "NAICS",
            "code": "332710",
            "description": "Machine shops",
        },
        "size_band": {"metric": "revenue", "band": "10-50M", "as_of": "2024-06-30"},
        "fiscal_calendar": {"basis": "fiscal", "year_end_month": 6, "year_end_day": 30},
        "scale_convention": 1000,
        "statements_arrive_in": 1,
        "owner_compensation_baseline": {
            "amount": 265000,
            "currency": "USD",
            "basis": "survey_median",
            "source": "ERI 2025",
            "as_of": "2025-06-30",
        },
        "materiality_threshold": {"amount": 5000, "currency": "USD"},
        "checkpoint_policy": {
            "owner": "reviewer@chartwell.invalid",
            "sla_hours": 24,
            "auto_accept_confidence": 0.9,
            "always_review_categories": [],
        },
        "recorded_by": "Caleb",
        "recorded_at": "2026-09-22T09:00:00Z",
    }
    body.update(over)
    return body


def envelope(value: float, scale: int) -> dict[str, Any]:
    return {
        "value": value,
        "unit": "currency",
        "currency": "USD",
        "scale": scale,
        "period": {"type": "FY", "end": "2023-06-30"},
        "source_id": "sha256:" + "e" * 64,
        "locator": "IS!B7",
        "source_version": 1,
        "derivation": None,
        "masked": True,
        "confidence": 0.9,
        "produced_by": "timing-normalization@0.1.0",
        "model_pin": "claude-sonnet-5 @ effort=high",
    }


def source() -> SourceFile:
    return SourceFile(
        source_id="sha256:" + "f" * 64,
        filename="Consolidated Income Statements.xlsx",
        document_type="financial_statements",
        blocks={"IS!A1:D9": [{"label": "Revenue", "value": 1.0, "ordinal": 1}]},
        scale=None,
        currency=None,
        period_type="FY",
        period_ends=("2023-06-30",),
        block_periods={"IS!A1:D9": "FY2023"},
    )


# ============================================================ one profile, both facts


def test_the_profile_a_person_fills_in_validates_at_the_version_in_use() -> None:
    """The whole of P109 in one line. Before it, this exact document - the one the Setup
    page hands back, carrying the arrival scale - was refused with SKILL.SCHEMA_INVALID
    and the engagement would not activate."""
    ContractRegistry.load().validate(PROFILE_CONTRACT, profile())


def test_the_same_document_still_validates_without_the_new_field() -> None:
    """An engagement set up before P109 is not migrated and is not broken."""
    older = profile()
    older.pop("statements_arrive_in")
    older["schema_version"] = "engagement_profile@1.0.0"
    assert older["schema_version"] in PROFILES_SUPPORTED
    ContractRegistry.load().validate(older["schema_version"], older)


def test_both_facts_leave_the_same_form_for_different_steps() -> None:
    """The seam these four phases share. One form, two facts, two destinations: the
    arrival scale is read by the driver's settlement and the calendar by the timing
    payload, and neither step can see the other's."""
    body = profile()
    assert body["statements_arrive_in"] == 1
    calendar = _calendar_of(body)
    assert calendar is not None
    assert calendar.end_of(2023) == "2023-06-30"


# ============================================================ the calendar arrives


def test_the_timing_payload_carries_the_year_end_from_that_profile() -> None:
    payload = json.loads(
        TimingNormalization().payload(
            TimingInputs(files=(source(),), calendar=_calendar_of(profile()))
        )
    )
    assert payload["fiscal_calendar"]["fiscal_year_ends"] == "06-30"


def test_a_profile_that_records_no_calendar_says_so_rather_than_guessing() -> None:
    """The rule the four share. A silence is filled from something a person decided, or it
    is said out loud - never defaulted."""
    quiet = profile()
    quiet.pop("fiscal_calendar")
    payload = json.loads(
        TimingNormalization().payload(
            TimingInputs(files=(source(),), calendar=_calendar_of(quiet))
        )
    )
    assert payload["fiscal_calendar"] == {"recorded": False, "note": NO_CALENDAR}


# ============================================================ the scale arrives, and moves


def test_the_arrival_scale_is_what_the_restatement_moves_from() -> None:
    """P106 settles what arrived from the profile; P108 moves it to what the template
    declares. This is the join: the number the person typed is the number the
    multiplication starts from."""
    arrived = profile()["statements_arrive_in"]
    out, moves = restated({"timing:Revenue:FY1": envelope(4_200_000.0, arrived)}, 1000)
    assert out["timing:Revenue:FY1"]["value"] == pytest.approx(4200.0)
    assert moves[0].from_scale == arrived
    assert moves[0].to_scale == 1000


def test_a_client_who_sends_thousands_is_not_restated_twice() -> None:
    """The failure the two phases could have had between them: the profile says thousands,
    the template says thousands, and a restatement that ran anyway would divide a correct
    figure by a thousand."""
    body = profile(statements_arrive_in=1000)
    out, moves = restated({"a": envelope(4200.0, body["statements_arrive_in"])}, 1000)
    assert out["a"]["value"] == 4200.0
    assert moves == ()


def test_the_writer_accepts_what_the_restatement_produced() -> None:
    """End of the chain. The builder refuses a scale mismatch and that refusal is what
    makes the lock evidence - so the two phases agree exactly when a restated figure walks
    through it without complaint."""
    out, _ = restated({"a": envelope(4_200_000.0, 1)}, 1000)
    assert _value_of(out["a"], 1000, "USD", "Revenue_FY1") == pytest.approx(4200.0)


def test_the_writer_still_refuses_an_unrestated_one() -> None:
    with pytest.raises(RegistryError, match="does not happen in the writer"):
        _value_of(envelope(4_200_000.0, 1), 1000, "USD", "Revenue_FY1")


# ============================================================ and the page that says so


def test_the_setup_page_checks_the_machine_and_not_a_flag() -> None:
    """P107. Everything above is about a profile a person filled in; this is the screen
    that tells them whether filling it in would lead to any work at all. It reads the live
    system - the vault is opened, the model adapter is asked what it is - because the one
    thing a checklist may never do is report done on a machine that cannot."""
    console = (ROOT / "admin" / "console.py").read_text(encoding="utf-8")
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")
    assert '"environment_ready": self._environment(),' in console
    assert "sqlite:///:memory:" in console, "the vault is opened, not counted"
    assert "SETUP.environment_ready" in page
    assert "A run would mask, ask a model and write a workbook." in page


def test_the_page_asks_the_two_scale_questions_separately() -> None:
    """Where P107 and P109 meet. Both facts are on one form and they are different
    questions - how the firm keeps its own papers, and what the client sent - and a form
    that labelled them the same is a form that gets one of them wrong."""
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")
    assert "Our working papers are kept in" in page
    assert "The client's statements arrive in" in page
