"""Five guards: each passes clean input, fails its own kind of bad input, and emits both.

Three exit criteria are here by name - the 0.4% total, the "derived" source, the writer
that rounds to the nearest thousand. The fourth, the eleven fixtures, has its own file.
"""

from __future__ import annotations

import pytest

from guards import GuardFailed, figures_in
from guards.numeric_lock import NumericLock, as_text
from guards.provenance import ProvenanceGate
from guards.reconcile import Reconcile
from guards.schema import SchemaGate
from guards.tieout import TieoutGate
from ops.run_store import SqlRunStore
from tests.p13.conftest import (
    ENGAGEMENT,
    ROWS_LOCATOR,
    SOURCE,
    TOTAL_LOCATOR,
    TRUE_TOTAL,
    addback,
    ebitda_output,
    figure,
)

CONTRACT = "skills/ebitda-normalization@1.0.0"


def summed(value: float = TRUE_TOTAL) -> dict:
    return figure(value, TOTAL_LOCATOR, {"op": "sum", "of": [ROWS_LOCATOR]})


def guard_events(store: SqlRunStore, run_id: str, guard: str) -> list:
    return [e for e in store.events(run_id) if e.type.startswith(f"guard.{guard}.")]


# ----------------------------------------------------------------- schema


def test_schema_passes_a_valid_output_and_says_so(
    schema_gate: SchemaGate, started: str, store: SqlRunStore
) -> None:
    result = schema_gate.run(
        ebitda_output(addback(summed())), CONTRACT, started, ENGAGEMENT, "ebitda"
    )
    assert result.passed
    events = guard_events(store, started, "schema")
    assert [e.type for e in events] == ["guard.schema.pass"]


def test_schema_refuses_a_field_that_should_not_exist(
    schema_gate: SchemaGate, started: str, store: SqlRunStore
) -> None:
    """Forbidden fields are part of the schema. A conclusion written into a field that
    does not exist is caught structurally."""
    output = ebitda_output(addback(summed()))
    output["conclusion"] = "approved"
    with pytest.raises(GuardFailed) as raised:
        schema_gate.run(output, CONTRACT, started, ENGAGEMENT, "ebitda")
    assert raised.value.diagnostic.code == "SKILL.SCHEMA_INVALID"
    assert guard_events(store, started, "schema")[0].type == "guard.schema.fail"


def test_schema_refuses_a_fabricated_source_as_a_provenance_failure(
    schema_gate: SchemaGate, started: str
) -> None:
    """The envelope's own `not` rule. The schema gate reports it under the provenance
    code, because that is what it is."""
    output = ebitda_output(addback(figure(1.0, source_id="derived")))
    with pytest.raises(GuardFailed) as raised:
        schema_gate.run(output, CONTRACT, started, ENGAGEMENT)
    assert raised.value.diagnostic.code == "SKILL.FABRICATED_SOURCE"


# ------------------------------------------------------------- provenance


def test_provenance_passes_a_figure_the_run_actually_read(
    provenance_gate: ProvenanceGate, started: str, sources: dict, store: SqlRunStore
) -> None:
    result = provenance_gate.run(ebitda_output(addback(summed())), started, ENGAGEMENT, sources)
    assert result.passed and result.checked == 1
    assert guard_events(store, started, "provenance")[0].type == "guard.provenance.pass"


def test_a_figure_citing_source_id_derived_fails_provenance(
    provenance_gate: ProvenanceGate, started: str, sources: dict, store: SqlRunStore
) -> None:
    """The exit criterion. Fabricated provenance is rejected as hard as a missing one."""
    output = {"figures": [figure(331000.0, source_id="derived")]}
    with pytest.raises(GuardFailed) as raised:
        provenance_gate.run(output, started, ENGAGEMENT, sources)
    assert raised.value.diagnostic.code == "SKILL.FABRICATED_SOURCE"
    assert (
        guard_events(store, started, "provenance")[0].diagnostic_code == "SKILL.FABRICATED_SOURCE"
    )


@pytest.mark.parametrize("source_id", ["model", "analysis", "estimated", "n/a", "sha256:internal"])
def test_every_spelling_of_fabricated_is_refused(
    provenance_gate: ProvenanceGate, started: str, sources: dict, source_id: str
) -> None:
    result = provenance_gate.check({"f": figure(1.0, source_id=source_id)}, started, sources)
    assert not result.passed
    assert result.code in ("SKILL.FABRICATED_SOURCE", "SKILL.NO_PROVENANCE")


def test_a_well_formed_hash_not_in_the_manifest_fails(
    provenance_gate: ProvenanceGate, started: str, sources: dict
) -> None:
    """The second half of the blueprint's provenance fixture: the hash is fine and the
    document is not here."""
    stray = "sha256:" + "cd" * 32
    result = provenance_gate.check({"f": figure(1.0, source_id=stray)}, started, sources)
    assert not result.passed
    assert result.code == "SKILL.UNKNOWN_SOURCE"
    assert "not in this run's intake" in result.reasons[0]


def test_a_locator_that_is_not_in_the_parse_store_fails(
    provenance_gate: ProvenanceGate, started: str, sources: dict
) -> None:
    result = provenance_gate.check({"f": figure(1.0, locator="TB_FY25!Z99")}, started, sources)
    assert not result.passed
    assert "parse store" in result.reasons[0]


def test_a_source_version_the_run_does_not_hold_fails(
    provenance_gate: ProvenanceGate, started: str, sources: dict
) -> None:
    result = provenance_gate.check({"f": figure(1.0, source_version=2)}, started, sources)
    assert not result.passed
    assert "version 2" in result.reasons[0]


def test_provenance_walks_every_figure_wherever_it_sits(
    provenance_gate: ProvenanceGate, started: str, sources: dict
) -> None:
    nested = {
        "a": {"b": [{"c": figure(TRUE_TOTAL)}, {"d": {"e": figure(2.0, source_id="derived")}}]}
    }
    assert len(list(figures_in(nested))) == 2
    result = provenance_gate.check(nested, started, sources)
    assert result.checked == 2 and result.failed == 1


# ----------------------------------------------------------------- tie-out


def test_tieout_passes_a_total_the_rows_add_up_to(
    tieout_gate: TieoutGate, started: str, store: SqlRunStore
) -> None:
    result = tieout_gate.run(ebitda_output(addback(summed())), started, ENGAGEMENT, "ebitda")
    assert result.passed and result.checked == 1
    assert guard_events(store, started, "tieout")[0].type == "guard.tieout.pass"


def test_a_total_altered_by_0_4_percent_fails_tieout(
    tieout_gate: TieoutGate, started: str, store: SqlRunStore
) -> None:
    """The exit criterion. 332,324 against rows that sum to 331,000: plausible on sight,
    $1,324 outside a $1 tolerance. Both values, the delta and the rows are recorded."""
    altered = round(TRUE_TOTAL * 1.004, 2)
    with pytest.raises(GuardFailed) as raised:
        tieout_gate.run(ebitda_output(addback(summed(altered))), started, ENGAGEMENT, "ebitda")

    assert raised.value.diagnostic.code == "GUARD.TIEOUT_MISMATCH"
    mismatch = raised.value.result.detail["mismatches"][0]
    assert mismatch["stated"] == altered
    assert mismatch["recomputed"] == TRUE_TOTAL
    assert mismatch["delta"] == pytest.approx(1324.0)
    assert mismatch["rows"] == [ROWS_LOCATOR]
    fail = guard_events(store, started, "tieout")[0]
    assert fail.type == "guard.tieout.fail"
    assert fail.diagnostic_code == "GUARD.TIEOUT_MISMATCH"


def test_a_total_inside_tolerance_passes(tieout_gate: TieoutGate, started: str) -> None:
    assert tieout_gate.check(ebitda_output(addback(summed(TRUE_TOTAL + 0.99))), started).passed


def test_a_figure_may_tighten_the_tolerance_but_never_loosen_it(
    tieout_gate: TieoutGate, started: str
) -> None:
    """A repair loop may change the input to a step. Never the guard, the tolerance or
    the schema."""
    tight = figure(
        TRUE_TOTAL + 0.5, TOTAL_LOCATOR, {"op": "sum", "of": [ROWS_LOCATOR], "tolerance": 0.1}
    )
    assert not tieout_gate.check({"f": tight}, started).passed
    loose = figure(
        TRUE_TOTAL + 50, TOTAL_LOCATOR, {"op": "sum", "of": [ROWS_LOCATOR], "tolerance": 100.0}
    )
    assert not tieout_gate.check({"f": loose}, started).passed


def test_a_figure_read_off_the_page_is_not_tied_out(tieout_gate: TieoutGate, started: str) -> None:
    """No derivation, no arithmetic to check. Provenance's business."""
    result = tieout_gate.check({"f": figure(TRUE_TOTAL, derivation=None)}, started)
    assert result.passed and result.checked == 0


def test_a_derivation_over_rows_the_store_does_not_hold_fails(
    tieout_gate: TieoutGate, started: str
) -> None:
    result = tieout_gate.check(
        {"f": figure(1.0, derivation={"op": "sum", "of": ["TB_FY25!Z1:Z9"]})}, started
    )
    assert not result.passed and result.code == "SKILL.UNKNOWN_SOURCE"


def test_tieout_proves_arithmetic_not_selection(tieout_gate: TieoutGate, started: str) -> None:
    """Eight wrong rows added correctly still pass here. The note on the phase, as a
    test, so nobody later reads a tie-out pass as more than it is."""
    wrong_rows_right_sum = figure(TRUE_TOTAL, TOTAL_LOCATOR, {"op": "sum", "of": [ROWS_LOCATOR]})
    assert tieout_gate.check({"f": wrong_rows_right_sum}, started).passed


# --------------------------------------------------------------- reconcile


def test_reconcile_passes_outputs_that_agree(
    reconcile: Reconcile, started: str, store: SqlRunStore
) -> None:
    outputs = {
        "line-item-tagging": {"items": [{"line_item_ref": "li_1", "category": "owner_related"}]},
        "ebitda-normalization": ebitda_output(
            addback(summed(), ref="li_1", category="owner_related")
        ),
    }
    result = reconcile.run(outputs, started, ENGAGEMENT)
    assert result.passed
    assert guard_events(store, started, "reconcile")[0].type == "guard.reconcile.pass"


def test_two_skills_categorising_one_item_differently_is_a_conflict(
    reconcile: Reconcile, started: str, store: SqlRunStore
) -> None:
    outputs = {
        "line-item-tagging": {"items": [{"line_item_ref": "li_1", "category": "rent"}]},
        "ebitda-normalization": ebitda_output(
            addback(summed(), ref="li_1", category="owner_related")
        ),
    }
    with pytest.raises(GuardFailed) as raised:
        reconcile.run(outputs, started, ENGAGEMENT)
    assert raised.value.diagnostic.code == "GUARD.RECONCILE_CONFLICT"
    conflict = raised.value.result.detail["conflicts"][0]
    assert conflict["kind"] == "category" and conflict["subject"] == "li_1"
    assert {p["skill"]: p["claim"] for p in conflict["positions"]} == {
        "line-item-tagging": "rent",
        "ebitda-normalization": "owner_related",
    }


def test_the_same_figure_stated_two_ways_is_a_conflict(reconcile: Reconcile) -> None:
    outputs = {
        "timing-normalization": {"f": figure(331000.0)},
        "ebitda-normalization": {"f": figure(330000.0)},
    }
    result = reconcile.check(outputs)
    assert not result.passed
    assert result.detail["conflicts"][0]["kind"] == "figure"


def test_a_period_one_skill_has_and_another_lacks_is_a_conflict(reconcile: Reconcile) -> None:
    fy24 = figure(1.0, period={"type": "FY", "end": "2024-12-31"})
    fy25 = figure(2.0, period={"type": "FY", "end": "2025-12-31"})
    outputs = {"timing-normalization": {"a": fy24, "b": fy25}, "ebitda-normalization": {"a": fy25}}
    result = reconcile.check(outputs)
    assert not result.passed
    assert any(c["kind"] == "period" for c in result.detail["conflicts"])


def test_a_conflict_is_never_resolved_by_preferring_the_later_writer(reconcile: Reconcile) -> None:
    """Both positions are on the record. Nothing here picks one."""
    outputs = {
        "first": {"items": [{"line_item_ref": "li_1", "category": "a"}]},
        "later": {"items": [{"line_item_ref": "li_1", "category": "b"}]},
    }
    result = reconcile.check(outputs)
    positions = result.detail["conflicts"][0]["positions"]
    assert {p["claim"] for p in positions} == {"a", "b"}
    for forbidden in ("resolve", "prefer", "winner", "pick"):
        assert not hasattr(reconcile, forbidden)


# ------------------------------------------------------------ numeric lock


def test_the_lock_passes_when_nothing_numeric_changed(
    numeric_lock: NumericLock, started: str, store: SqlRunStore
) -> None:
    before = as_text(ebitda_output(addback(summed())))
    after = before.replace("[[", "").replace("]]", "")  # unmasking changes no number
    result = numeric_lock.run(before, after, started, ENGAGEMENT, "release")
    assert result.passed and result.checked > 5
    assert guard_events(store, started, "numeric_lock")[0].type == "guard.numeric_lock.pass"


def test_a_template_writer_that_rounds_to_the_nearest_thousand_fails_the_lock(
    numeric_lock: NumericLock, started: str, store: SqlRunStore
) -> None:
    """The exit criterion. 18,400 written as 18,000 is a different number, and the lock
    does not care that it is a rounder one."""
    before = "auto allowance 18,400.00; health 12,600.00; total EBITDA 1,284,317.55"
    after = "auto allowance 18,000.00; health 13,000.00; total EBITDA 1,284,000.00"
    with pytest.raises(GuardFailed) as raised:
        numeric_lock.run(before, after, started, ENGAGEMENT, "model")
    assert raised.value.diagnostic.code == "GUARD.NUMERIC_DRIFT"
    assert set(raised.value.result.detail["missing"]) == {"18400", "12600", "1.28432e+06"}
    assert guard_events(store, started, "numeric_lock")[0].diagnostic_code == "GUARD.NUMERIC_DRIFT"


def test_the_lock_reads_values_not_typography(numeric_lock: NumericLock) -> None:
    """1,234.50 and 1234.5 are the same figure. (2,500) and -2500 are the same figure."""
    assert numeric_lock.check("1,234.50 and (2,500)", "1234.5 and -2500").passed


def test_a_dropped_citation_fails_the_lock(numeric_lock: NumericLock) -> None:
    before = f"331,000.00 from {SOURCE} at TB_FY25!B48"
    after = "331,000.00 from the trial balance"
    result = numeric_lock.check(before, after)
    assert not result.passed
    assert SOURCE in result.detail["missing"]
    assert "TB_FY25!B48" in result.detail["missing"]


def test_a_number_that_appeared_from_nowhere_fails_the_lock(numeric_lock: NumericLock) -> None:
    result = numeric_lock.check("total 331,000.00", "total 331,000.00 (rounded from 331,417)")
    assert not result.passed
    assert result.detail["extra"] == ["331417"]


def test_the_lock_is_its_own_node(numeric_lock: NumericLock) -> None:
    """Two strings in, a verdict out. It can be tested independently of either transform
    it sits between, which is why it is a module and not a line in the writer."""
    import inspect

    assert set(inspect.signature(NumericLock.check).parameters) == {"before", "after"}
