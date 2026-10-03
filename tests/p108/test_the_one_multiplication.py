"""P108 - restating to the template's scale, and the place it is allowed to happen.

The analyst's rule: *"the client could give us their financials in any form, we always put
it in thousands no matter what they give us."* P105 made the template declare thousands and
P106 made what arrived settleable, and between them nothing multiplied - so a run that got
all the way to the writer was refused there, correctly, with *"restating is arithmetic and
does not happen in the writer"*.

That refusal has to survive this phase. It is not fastidiousness: the Numeric Integrity
Lock brackets the write and is evidence only because the code inside the bracket does no
arithmetic. So the multiplication goes in front of the mapping, and the writer keeps
refusing, and a test here fails if anybody ever moves it back.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from harness.restate import BARE_NUMBERS_ARE_AT, restated
from registries.errors import RegistryError

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "deliver" / "builder.py"


def envelope(value: float, scale: int, **over: Any) -> dict[str, Any]:
    figure = {
        "value": value,
        "unit": "currency",
        "currency": "USD",
        "scale": scale,
        "period": {"type": "FY", "end": "2023-12-31"},
        "source_id": "sha256:" + "a" * 64,
        "locator": "Sheet1!B4",
        "source_version": 1,
        "derivation": None,
        "masked": True,
        "confidence": 0.9,
        "produced_by": "timing-normalization@0.1.0",
        "model_pin": "claude-sonnet-5 @ effort=high",
    }
    figure.update(over)
    return figure


# ============================================================ the arithmetic


def test_units_become_thousands() -> None:
    """What the client sends and what the firm delivers, which is the whole phase."""
    out, moves, _ = restated({"a": envelope(1_234_567.89, 1)}, 1000)
    assert out["a"]["value"] == pytest.approx(1234.56789)
    assert out["a"]["scale"] == 1000
    assert [m.figure_ref for m in moves] == ["a"]
    assert (moves[0].from_scale, moves[0].to_scale) == (1, 1000)


def test_millions_become_thousands_as_well() -> None:
    """The rule is the template's scale, not "divide by a thousand". A client sending
    millions is restated up, and the same code does it."""
    out, moves, _ = restated({"a": envelope(1.5, 1_000_000)}, 1000)
    assert out["a"]["value"] == pytest.approx(1500.0)
    assert out["a"]["scale"] == 1000
    assert moves[0].factor == 1000


def test_every_decimal_survives() -> None:
    """The analyst, on the output: don't round before writing, let Excel round for visual
    effect, keep all the decimals in there. The template's number format does the
    rounding; this must not."""
    out, _, _ = restated({"a": envelope(123_456_789.01, 1)}, 1000)
    assert out["a"]["value"] == pytest.approx(123456.78901, abs=1e-9)
    assert out["a"]["value"] != round(out["a"]["value"])


def test_it_is_one_operation_rather_than_two() -> None:
    """`value * from / to` rounds twice and is not the same number. A restatement that
    introduces its own error is not keeping the decimals it was asked to keep."""
    source = (ROOT / "harness" / "restate.py").read_text(encoding="utf-8")
    body = source[source.index("def _moved") : source.index("def restated")]
    assert "from_scale // to_scale" in body
    assert "to_scale // from_scale" in body
    assert "value * from_scale / to_scale" not in body


def test_a_figure_already_at_the_template_scale_is_untouched() -> None:
    """Identity, not a multiply by one - and nothing is recorded, because there is nothing
    to tell anybody about a number nobody moved."""
    already = envelope(42.0, 1000)
    out, moves, _ = restated({"a": already}, 1000)
    assert out["a"] is already
    assert moves == ()


def test_everything_else_in_the_envelope_is_carried_through() -> None:
    """A restated figure is the same figure. Its locator, its source and its period are
    how anyone checks the restatement was right."""
    out, _, _ = restated({"a": envelope(1000.0, 1, locator="IS!C7")}, 1000)
    assert out["a"]["locator"] == "IS!C7"
    assert out["a"]["source_id"] == "sha256:" + "a" * 64
    assert set(out["a"]) == set(envelope(0.0, 1))


# ============================================================ what it refuses


def test_a_ratio_that_is_not_a_power_of_ten_is_refused() -> None:
    """The figure contract allows 1, 1000 and 1000000, so today every ratio is a power of
    ten. The guard is for the template that one day declares something else: a fractional
    factor would be a wrong number in every cell and nothing downstream would notice."""
    with pytest.raises(RegistryError) as refused:
        restated({"a": envelope(100.0, 1000)}, 512)
    assert "power of ten" in str(refused.value)


def test_a_scale_of_zero_is_refused_rather_than_dividing() -> None:
    with pytest.raises(RegistryError):
        restated({"a": envelope(100.0, 1000)}, 0)


# ============================================================ the bare number


def test_a_bare_number_is_treated_as_units_and_restated_too() -> None:
    """The profile's owner-compensation benchmark reaches the catalogue as a plain float,
    and `_value_of` returns a plain number without checking its scale at all. So a
    benchmark of 250,000 dollars was being written into a thousands cell as 250,000
    thousand - a quarter of a billion - and no guard in the build said a word."""
    out, moves, _ = restated({"profile:owner_compensation_baseline": 250_000.0}, 1000)
    assert out["profile:owner_compensation_baseline"] == pytest.approx(250.0)
    assert moves[0].from_scale == BARE_NUMBERS_ARE_AT == 1


def test_the_profile_still_states_its_benchmark_in_units() -> None:
    """The assumption the line above rests on. The profile gives `amount` a currency and
    no scale, which is what makes units the right reading. The day it gains a scale field
    this test fails, which is the only warning anybody would get."""
    schema = json.loads(
        (ROOT / "contracts" / "engagement_profile@1.1.0.schema.json").read_text(encoding="utf-8")
    )
    baseline = schema["properties"]["owner_compensation_baseline"]["properties"]
    assert "amount" in baseline and "currency" in baseline
    assert "scale" not in baseline


# ============================================================ where it may not happen


def test_the_writer_still_refuses_a_mismatch() -> None:
    """Nothing downstream may come to rely on the builder restating, because the moment it
    does, the arithmetic is inside the lock's bracket."""
    from deliver.builder import _value_of

    with pytest.raises(RegistryError) as refused:
        _value_of(envelope(5.0, 1), 1000, "USD", "Revenue_FY1")
    assert "does not happen in the writer" in str(refused.value)


def test_the_builder_does_no_arithmetic() -> None:
    """The reason the Numeric Integrity Lock is evidence rather than decoration. Walk the
    module and fail on a multiplication or a division - the lock brackets this code, and
    arithmetic inside the bracket is arithmetic the lock cannot see."""
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    hits = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult | ast.Div | ast.FloorDiv)
    ]
    assert not hits, f"arithmetic in deliver/builder.py at line(s) {[h.lineno for h in hits]}"


class Bus:
    """A bus that keeps what it was told."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, **event: Any) -> None:
        self.events.append(event)


def driver_figures(figures: dict[str, Any], *, template_scale: int) -> tuple[Any, Bus]:
    """Run the driver's real `_figures` over a catalogue, with the template and the model
    step stood in for.

    This is a behavioural test and it replaced two source scans that read the driver for
    an import line and a string. Both of those stayed green with the restatement call
    itself cut out, which is the exact defect this build keeps finding: a test that
    matches the shape of a fix rather than its effect.
    """
    from types import SimpleNamespace

    import harness.inputs
    from workers.driver import RunDriver

    bus = Bus()
    driver = RunDriver.__new__(RunDriver)
    driver.wiring = SimpleNamespace(bus=bus, blobs=None)  # type: ignore[attr-defined]
    template = SimpleNamespace(
        key="Chartwell_Input_Help_v1", inputs=SimpleNamespace(scale=template_scale)
    )
    context = SimpleNamespace(
        run_id="run-1", engagement_id="eng-1", facts=SimpleNamespace(template=template)
    )
    attempt = SimpleNamespace(step=SimpleNamespace(id="model-load"), inputs={})

    original = harness.inputs.build_inputs
    harness.inputs.build_inputs = lambda *a, **k: SimpleNamespace(figures=lambda: figures)  # type: ignore[assignment]
    try:
        return driver._figures(attempt, context), bus  # noqa: SLF001
    finally:
        harness.inputs.build_inputs = original  # type: ignore[assignment]


def test_the_driver_hands_the_builder_figures_at_the_template_scale() -> None:
    """The whole phase, at the seam where it has to be true. The builder refuses a
    mismatch, so a run only finishes if this step did the restating."""
    out, _ = driver_figures({"timing:Revenue:FY1": envelope(4_200_000.0, 1)}, template_scale=1000)
    assert out["timing:Revenue:FY1"]["value"] == pytest.approx(4200.0)
    assert out["timing:Revenue:FY1"]["scale"] == 1000


def test_the_driver_restates_the_profile_benchmark_too() -> None:
    """The bare float, through the real step rather than the pure function."""
    out, _ = driver_figures({"profile:owner_compensation_baseline": 250_000.0}, template_scale=1000)
    assert out["profile:owner_compensation_baseline"] == pytest.approx(250.0)


# ============================================================ the record


def test_the_driver_records_one_event_listing_every_figure() -> None:
    """Thirty lines over three years is ninety restatements. One event per figure is a
    flood that hides the one question worth asking, so the payload is a list."""
    _, bus = driver_figures(
        {"a": envelope(1_000.0, 1), "b": envelope(2_000.0, 1), "c": envelope(7.0, 1000)},
        template_scale=1000,
    )
    assert len(bus.events) == 1
    event = bus.events[0]
    assert event["type"] == "model.figures.restated"
    rows = event["payload"]["restated"]
    assert [r["figure_ref"] for r in rows] == ["a", "b"], "c was already at scale"
    assert rows[0] == {
        "figure_ref": "a",
        "from_scale": 1,
        "to_scale": 1000,
        "before": 1_000.0,
        "after": 1.0,
    }
    assert event["payload"]["to_scale"] == 1000


def test_the_driver_says_nothing_when_nothing_moved() -> None:
    """A run whose client already sent thousands did not restate anything, and an event
    saying so would be an event about an operation that did not happen."""
    _, bus = driver_figures({"a": envelope(5.0, 1000)}, template_scale=1000)
    assert bus.events == []


def test_the_row_says_what_moved_and_where_to() -> None:
    """Enough to redo the multiplication by hand, which is the only form of "recorded"
    worth anything."""
    _, moves, _ = restated({"Revenue": envelope(2_500_000.0, 1)}, 1000)
    assert moves[0].as_row() == {
        "figure_ref": "Revenue",
        "from_scale": 1,
        "to_scale": 1000,
        "before": 2_500_000.0,
        "after": 2_500.0,
    }


# ============================================================ the lock, after all this


def test_the_lock_text_keeps_every_digit_of_a_restated_figure() -> None:
    """`:g` is six significant digits. Before this phase every figure was a whole number
    off a statement and that was harmless; a restated figure has decimals, and a lock that
    cannot see them is not locking the thing the analyst asked to keep."""
    from deliver.builder import _plain

    near = 1234.56789
    other = 1234.5678912
    assert f"{near:g}" == f"{other:g}", "the old format could not tell these apart"
    assert _plain(near) != _plain(other)
    assert float(_plain(near)) == near


def test_the_lock_text_still_reads_back_as_the_same_number() -> None:
    from deliver.builder import _plain

    for value in (0.1, 1e-7, 123456789.01 / 1000, -2.5, 0.0):
        assert float(_plain(value)) == float(value)
