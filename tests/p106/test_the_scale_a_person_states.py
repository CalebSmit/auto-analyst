"""P106 - the scale a person states.

The analyst's rule, 2026-09-22: *"the client could give us their financials in any form, we
always put it in thousands no matter what they give us."* P105 made the deliverable declare
thousands. This is the other half: establishing what arrived.

**The livelock it ends.** `escalate()` in the timing procedure refuses a source whose scale
is unsettled - correctly, because thousands read as units is a figure out by a factor of a
thousand and it passes every other check on the way through. But it reads the *source's*
scale, and no review decision changes that. So on the first real client folder a person
answered the item, the step re-ran, and asked again. Thirty passes, thirty items, no
progress. A question that answering cannot resolve is worse than no question.

**The shape is not new.** `_settle_currency` sits directly above it and solves the same
problem the same way: a US file rarely says "USD", the readers leave it unsettled rather
than guess, and the engagement profile is where a person declared it. Scale needed the same
thing and had never been given it - a gap that only shows on a folder whose statements
state no scale, which is most of them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
#: The version the field lives at. It was added to 1.0.0 in place first, and
#: `tools/surfaces.py` caught it by the schema's hash - "a contract edited in place" is the
#: first accident that snapshot exists to find.
PROFILE_CONTRACT = ROOT / "contracts" / "engagement_profile@1.1.0.schema.json"
WAS_THERE_BEFORE = ROOT / "contracts" / "engagement_profile.schema.json"


class Bus:
    def __init__(self) -> None:
        self.emitted: list[dict[str, Any]] = []

    def emit(self, **kwargs: Any) -> None:
        self.emitted.append(kwargs)


class Source:
    """The fields `_settle_scale` reads and writes, as `dataclasses.replace` needs them."""

    def __init__(self, filename: str, scale: int | None, ambiguous: tuple[str, ...] = ()) -> None:
        self.filename = filename
        self.source_id = f"sha256:{filename}"
        self.scale = scale
        self.ambiguous = ambiguous


def settle(sources: tuple[Any, ...], profile: dict[str, Any]) -> tuple[tuple[Any, ...], Bus]:
    """`_settle_scale` against a driver built with nothing but a bus."""
    import dataclasses

    from workers.driver import RunDriver

    bus = Bus()
    driver = RunDriver.__new__(RunDriver)
    driver.wiring = type("W", (), {"bus": bus})()

    # The real sources are frozen dataclasses; these stand-ins are not, so `replace` is
    # given something it can copy.
    @dataclasses.dataclass(frozen=True)
    class Frozen:
        filename: str
        source_id: str
        scale: int | None
        ambiguous: tuple[str, ...]

    frozen = tuple(
        Frozen(s.filename, s.source_id, s.scale, s.ambiguous) for s in sources
    )
    return driver._settle_scale("r1", "E1", frozen, profile), bus  # noqa: SLF001


# ============================================================ the contract


def test_the_profile_may_declare_what_arrived() -> None:
    doc = json.loads(PROFILE_CONTRACT.read_text(encoding="utf-8"))
    field = doc["properties"]["statements_arrive_in"]
    assert field["enum"] == [1, 1000, 1000000]
    assert "no default" in field["description"]


def test_the_contract_says_why_it_cannot_be_assumed() -> None:
    """The reason belongs beside the field. Somebody reading the profile schema and
    wondering why this is not optional-with-a-sensible-default should find the answer
    there rather than in a phase file."""
    doc = json.loads(PROFILE_CONTRACT.read_text(encoding="utf-8"))
    said = doc["properties"]["statements_arrive_in"]["description"]
    assert "factor of a thousand" in said
    assert "cue on the page always wins" in said


def test_it_is_optional_so_an_existing_profile_is_still_valid() -> None:
    """Every engagement already has a profile. A required field would invalidate all of
    them at once, which is a migration rather than a setting."""
    doc = json.loads(PROFILE_CONTRACT.read_text(encoding="utf-8"))
    assert "statements_arrive_in" not in doc.get("required", [])


def test_the_version_that_shipped_without_it_still_does_not_have_it() -> None:
    """The registry's own rule: adding to a contract bumps the version and leaves the old
    one listed, because a recorded run may cite it. The field was added to 1.0.0 in place
    first and the surface snapshot caught it - which is the whole reason that snapshot
    records a hash per schema rather than a list of names."""
    older = json.loads(WAS_THERE_BEFORE.read_text(encoding="utf-8"))
    assert "statements_arrive_in" not in older["properties"]
    assert older["$id"].endswith("engagement_profile@1.0.0")


def test_both_versions_are_registered_and_the_new_one_says_why() -> None:
    import yaml

    registry = yaml.safe_load(
        (ROOT / "contracts" / "registry.yaml").read_text(encoding="utf-8")
    )
    versions = {
        c["version"]: c for c in registry["contracts"] if c["id"] == "engagement_profile"
    }
    assert set(versions) == {"1.0.0", "1.1.0"}
    assert "statements_arrive_in" in versions["1.1.0"]["note"]


# ============================================================ what it settles


def test_a_source_with_no_scale_takes_the_declared_one() -> None:
    settled, bus = settle(
        (Source("Consolidated Income Statements.xlsx", None, ("scale: no cue in the headers",)),),
        {"statements_arrive_in": 1},
    )
    assert settled[0].scale == 1
    assert settled[0].ambiguous == (), "and the flag that stopped the run is gone"
    assert [e["type"] for e in bus.emitted] == ["intake.scale.assumed"]


def test_the_substitution_is_recorded_rather_than_quietly_made() -> None:
    """A figure's scale decides its magnitude. Changing one silently is the single most
    expensive quiet edit available on this path, so it is an event naming the file, the
    source and the number."""
    _, bus = settle((Source("FS.xlsx", None),), {"statements_arrive_in": 1000})
    (event,) = bus.emitted
    assert event["payload"] == {"source_id": "sha256:FS.xlsx", "scale": 1000}
    assert "FS.xlsx" in event["message"]
    assert "the engagement profile declares 1000" in event["message"]


def test_a_source_that_stated_its_own_scale_is_left_alone() -> None:
    """A cue on the page always wins. The profile fills a silence; it does not overrule a
    statement that says `($000s)` in its own header."""
    settled, bus = settle(
        (Source("Says thousands.xlsx", 1000),), {"statements_arrive_in": 1}
    )
    assert settled[0].scale == 1000
    assert bus.emitted == [], "nothing was assumed, so nothing is recorded"


def test_without_a_declaration_nothing_is_settled() -> None:
    """No default, at any level. A scale is settled by a person or not at all - and a run
    that stops is the correct outcome of nobody having said."""
    settled, bus = settle((Source("FS.xlsx", None, ("scale: no cue",)),), {})
    assert settled[0].scale is None
    assert settled[0].ambiguous == ("scale: no cue",), "the run still stops, naming the file"
    assert bus.emitted == []


def test_only_the_scale_flag_is_cleared() -> None:
    """A source ambiguous about its periods as well is still ambiguous about those. The
    settlement answers one question and must not look like it answered the others."""
    settled, _ = settle(
        (Source("FS.xlsx", None, ("scale: no cue", "period_type: no period cue")),),
        {"statements_arrive_in": 1},
    )
    assert settled[0].ambiguous == ("period_type: no period cue",)


# ============================================================ how it sits beside currency


def test_it_follows_the_currency_settlement_rather_than_inventing_a_second_shape() -> None:
    """Two settlements with different rules would be two things to learn and one to get
    wrong. Both leave a cue alone, both fill a silence from the profile, both emit."""
    source = (ROOT / "workers" / "driver.py").read_text(encoding="utf-8")
    scale = source[source.index("def _settle_scale") : source.index("def _read_sources")]
    currency = source[source.index("def _settle_currency") : source.index("def _read_sources")]
    for both in ("if not declared:", "return sources", "dataclasses.replace("):
        assert both in scale and both in currency, both
    assert "intake.scale.assumed" in scale


def test_both_run_before_anything_reads_a_source() -> None:
    """Settled once, where the facts are built, rather than by each caller remembering."""
    source = (ROOT / "workers" / "driver.py").read_text(encoding="utf-8")
    facts = source[source.index("def _facts") : source.index("def _settle_scale")]
    assert "self._settle_scale(" in facts
    assert "self._settle_currency(" in facts


def test_the_timing_skill_still_refuses_an_unsettled_scale() -> None:
    """What P106 changes is that the question can be answered, not that it stopped being
    asked. A source nobody settled still stops the run before a model sees it."""
    from harness.procedures.timing_normalization import (
        SourceFile,
        TimingInputs,
        TimingNormalization,
    )

    unsettled = SourceFile(
        source_id="s1",
        filename="FS.xlsx",
        document_type="financial_statements",
        blocks={},
        scale=None,
        currency="USD",
        period_type="annual",
        period_ends=("2025-12-31",),
        ambiguous=("scale: no cue in the headers",),
    )
    said = TimingNormalization().escalate(TimingInputs(files=(unsettled,)))
    assert said is not None
    assert "FS.xlsx" in said
    assert "scale" in said


@pytest.mark.parametrize("declared", [1, 1000, 1_000_000])
def test_the_three_forms_a_client_sends(declared: int) -> None:
    """Units, thousands and millions. The firm restates all three to thousands, so all
    three have to be statable - and nothing else is, because a scale that is not a power of
    a thousand is a typo rather than a convention."""
    settled, _ = settle((Source("FS.xlsx", None),), {"statements_arrive_in": declared})
    assert settled[0].scale == declared
