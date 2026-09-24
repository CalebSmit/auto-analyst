"""P110 - the timing payload, and the question it did not include.

`payload()` sent `{"files": [...]}` and nothing else. The model was handed twelve client
documents, asked to type and date every period in them, and never told when this company's
fiscal year ends - although a person had recorded exactly that at setup, in
`fiscal_calendar.year_end_month` and `year_end_day`.

Then a guard refused the answer, because FY2023 came back with two ends. The guard is
right and stays exactly as strict as it is: a fiscal year has one end, and a table where it
has two is a table nobody can foot. But the question was unanswerable as asked. A June year
end on one statement and a bare "2023" printed on another page cannot be reconciled by
anybody who has not been told which one this company uses.

The first real client folder quarantined there, and a real model would have had no more to
go on than the stand-in did.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.inputs import RunFacts, _calendar_of, build_inputs
from harness.procedures.timing_normalization import (
    NO_CALENDAR,
    FiscalCalendar,
    SourceFile,
    TimingInputs,
    TimingNormalization,
)

ROOT = Path(__file__).resolve().parents[2]
JUNE = FiscalCalendar(basis="fiscal", year_end_month=6, year_end_day=30)


def source(name: str = "IS.xlsx", **over: Any) -> SourceFile:
    fields: dict[str, Any] = {
        "source_id": "sha256:" + "b" * 64,
        "filename": name,
        "document_type": "financial_statements",
        "blocks": {"Sheet1!A1:D9": [{"label": "Revenue", "value": 1.0, "ordinal": 1}]},
        "scale": 1,
        "currency": "USD",
        "period_type": "FY",
        "period_ends": ("2023-06-30",),
        "block_periods": {"Sheet1!A1:D9": "FY2023"},
    }
    fields.update(over)
    return SourceFile(**fields)


def payload_of(inputs: TimingInputs) -> dict[str, Any]:
    return json.loads(TimingNormalization().payload(inputs))


# ============================================================ the payload says it


def test_the_payload_states_the_year_end() -> None:
    body = payload_of(TimingInputs(files=(source(),), calendar=JUNE))
    assert body["fiscal_calendar"]["fiscal_year_ends"] == "06-30"
    assert body["fiscal_calendar"]["year_end_month"] == 6
    assert body["fiscal_calendar"]["year_end_day"] == 30


def test_the_payload_says_the_basis_too() -> None:
    """A 52/53-week retailer's "year end" is a weekday, not a date, and a model that is
    told the basis can say so instead of rounding to the 31st."""
    body = payload_of(TimingInputs(files=(source(),), calendar=JUNE))
    assert body["fiscal_calendar"]["basis"] == "fiscal"


def test_a_silence_is_said_out_loud_rather_than_filled_in_with_december() -> None:
    """The failure this whole phase is about is a year end nobody stated. Substituting
    December here would put the system's guess where the guard expects a fact - right for
    most clients and silently wrong for exactly the ones whose year does not end then."""
    body = payload_of(TimingInputs(files=(source(),), calendar=None))
    assert body["fiscal_calendar"] == {"recorded": False, "note": NO_CALENDAR}
    assert "12-31" not in json.dumps(body["fiscal_calendar"])


def test_the_files_are_still_all_of_it() -> None:
    """The calendar is an addition, not a replacement. Everything the model matched on
    before is still in front of it."""
    body = payload_of(TimingInputs(files=(source(),), calendar=JUNE))
    assert [f["filename"] for f in body["files"]] == ["IS.xlsx"]
    assert body["files"][0]["blocks"]["Sheet1!A1:D9"]["rows"]


def test_no_values_reach_the_model() -> None:
    """Unchanged and load-bearing: the model matches labels, it does not read figures."""
    body = payload_of(TimingInputs(files=(source(),), calendar=JUNE))
    assert "1.0" not in json.dumps(body["files"])


# ============================================================ the profile reaches it


def facts(profile: dict[str, Any]) -> RunFacts:
    return RunFacts(
        profile=profile,
        policy=None,
        taxonomy_version="coa-taxonomy@1.0.0",
        sources=(source(),),
        blocks={},
    )


def test_the_profile_reaches_the_skill() -> None:
    """The seam. It is the whole defect: the fact was recorded, and the one step that
    needed it was never handed it."""
    built = build_inputs(
        "timing-normalization@0.1.0",
        "timing",
        {},
        facts({"fiscal_calendar": {"basis": "fiscal", "year_end_month": 6, "year_end_day": 30}}),
        None,  # type: ignore[arg-type]
    )
    assert built.calendar == JUNE
    assert payload_of(built)["fiscal_calendar"]["fiscal_year_ends"] == "06-30"


def test_a_profile_without_a_calendar_reaches_it_as_a_silence() -> None:
    built = build_inputs(
        "timing-normalization@0.1.0",
        "timing",
        {},
        facts({}),
        None,  # type: ignore[arg-type]
    )
    assert built.calendar is None


def test_a_half_recorded_calendar_is_a_silence_rather_than_half_a_date() -> None:
    assert _calendar_of({"fiscal_calendar": {"year_end_month": 6}}) is None
    assert _calendar_of({"fiscal_calendar": "December"}) is None
    assert _calendar_of(None) is None


def test_the_end_of_a_year_is_derivable_from_it() -> None:
    """What the whole thing is for: one label, one end, computed rather than read off
    whichever page happened to come first."""
    assert JUNE.end_of(2023) == "2023-06-30"
    assert FiscalCalendar("calendar", 12, 31).end_of(2024) == "2024-12-31"


# ============================================================ the stand-in


def stand_in_periods(calendar: dict[str, Any] | None, hints: list[str]) -> list[dict[str, Any]]:
    from ports.llm.scripted import ScriptedAnalyst

    body: dict[str, Any] = {
        "files": [
            {
                "source_id": "sha256:" + "c" * 64,
                "period_ends": [],
                "blocks": {
                    f"S!A{i}": {"period_hint": hint, "rows": [f"S!A{i}r1: Revenue"]}
                    for i, hint in enumerate(hints)
                },
            }
        ]
    }
    if calendar is not None:
        body["fiscal_calendar"] = calendar
    return list(ScriptedAnalyst().timing(body)["periods"])


def test_the_stand_in_gives_one_end_per_label() -> None:
    """Two pages spelling the same year differently used to become two ends for FY2023,
    which quarantined the run. A stand-in that contradicts itself can never reach the
    deliverable, so nothing past timing could be rehearsed without a key at all."""
    periods = stand_in_periods(
        {"fiscal_year_ends": "06-30"}, ["FY2023", "2023-06-30", "year ended 2023"]
    )
    assert {p["label"] for p in periods} == {"FY2023"}
    assert {p["end"] for p in periods} == {"2023-06-30"}


def test_the_stand_in_takes_the_year_end_from_the_payload() -> None:
    """Not from December. The calendar is stated now, so a stand-in that ignored it would
    be testing the wrong thing."""
    assert stand_in_periods({"fiscal_year_ends": "03-31"}, ["FY2024"])[0]["end"] == "2024-03-31"


def test_the_stand_in_falls_back_to_december_only_on_a_silence() -> None:
    assert stand_in_periods(None, ["FY2024"])[0]["end"] == "2024-12-31"
    assert stand_in_periods({"recorded": False}, ["FY2024"])[0]["end"] == "2024-12-31"


def test_a_block_with_no_year_keeps_a_real_date() -> None:
    """The `P1`, `P2` fallback has no year to substitute into, and building one produced
    `0000-06-30` - which the date parser refused with "year 0 is out of range", five steps
    into a run. A label with nothing to derive from keeps what was read."""
    periods = stand_in_periods({"fiscal_year_ends": "06-30"}, ["a header with no year in it"])
    assert not periods[0]["end"].startswith("0000")
    assert periods[0]["end"][:4].isdigit() and int(periods[0]["end"][:4]) > 1900


# ============================================================ the guard is untouched


def test_two_genuinely_different_ends_are_still_refused() -> None:
    """The point of this phase is to make the question answerable, not to make the answer
    acceptable. A proposal that really does date FY2023 two ways is still a table nobody
    can foot, and the normalizer still refuses it."""
    import pytest

    from tools.normalize import _check_periods

    with pytest.raises(ValueError, match="typed or ended two ways"):
        _check_periods(
            [
                {"label": "FY2023", "type": "FY", "end": "2023-06-30"},
                {"label": "FY2023", "type": "FY", "end": "2023-12-31"},
            ]
        )


def test_two_different_types_for_one_label_are_still_refused() -> None:
    """The other half of the same guard. FY2023 and LTM2023 are not the same period even
    when they end on the same day."""
    import pytest

    from tools.normalize import _check_periods

    with pytest.raises(ValueError, match="typed or ended two ways"):
        _check_periods(
            [
                {"label": "FY2023", "type": "FY", "end": "2023-06-30"},
                {"label": "FY2023", "type": "LTM", "end": "2023-06-30"},
            ]
        )


def test_one_end_for_one_label_passes() -> None:
    """What the stand-in now produces, and what a model told the year end can produce."""
    from tools.normalize import _check_periods

    _check_periods(
        [
            {"label": "FY2023", "type": "FY", "end": "2023-06-30"},
            {"label": "FY2023", "type": "FY", "end": "2023-06-30"},
            {"label": "FY2024", "type": "FY", "end": "2024-06-30"},
        ]
    )
