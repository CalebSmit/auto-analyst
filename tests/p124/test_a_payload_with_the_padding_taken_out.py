"""P124 - a payload with the padding taken out.

Every procedure serialized its payload with `indent=1`, which spends a newline and a
space on every key of every row. Nothing reads those payloads but a model, and the
context assembler measures the whole in bytes against a declared ceiling before the call
is allowed - so the indentation was being paid for twice, once in tokens and once in
headroom, for a reader that does not exist.

On a catalogue shaped like the first real client folder that was 52 KB of whitespace
inside 269 KB, and model-load's assembled context was 305 KB against a ceiling of 400 KB.
The step most likely to refuse a real client was carrying a fifth of its bulk as padding.

**What this is not.** Dropping the repeated key names as well - 56 KB of `"figure_ref"`
written out eleven hundred times - would change the shape the model has to understand,
and that is a change to what is asked rather than to how it is spelled. It is recorded as
B-083, behind an eval that can say whether the answers got worse. The whole reason this
change is safe is that the same object parses out the other side.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from harness.procedures.model_load import (
    FigureRef,
    ModelLoad,
    ModelLoadInputs,
    TemplateInput,
)
from harness.procedures.payload import as_payload

ROOT = Path(__file__).resolve().parents[2]
PROCEDURES = ROOT / "harness" / "procedures"

SLOTS = ("FY1", "FY2", "FY3")


def a_catalogue(lines: int) -> ModelLoadInputs:
    """Model-load's inputs, shaped like the real client folder: a few hundred line items,
    three slots each, every row repeating the same `source_output`."""
    named = [f"Line item number {n} as the client spelled it" for n in range(lines)]
    return ModelLoadInputs(
        template_key="Chartwell_Input_Help_v1@1.0",
        template_version="1.0",
        inputs=tuple(
            TemplateInput(name=f"{line[:20]}_{slot}", line=line[:20], period=slot, required=True)
            for line in named[:60]
            for slot in SLOTS
        ),
        catalogue=tuple(
            FigureRef(
                figure_ref=f"timing:{line}:FY202{3 + n}",
                source_output="timing.normalized_historicals",
                description=line,
                period=SLOTS[n],
                figure=1.0,
            )
            for line in named
            for n in range(3)
        ),
        periods=SLOTS,
        period_slots=(("FY2023", "FY1"), ("FY2024", "FY2"), ("FY2025", "FY3")),
    )


# ============================================================ the same object, still


def test_the_compact_form_parses_to_what_the_indented_one_did() -> None:
    """The whole safety of this change, stated once. Nothing about the payload's meaning
    is a function of how it was spaced."""
    body = {"a": [1, 2, {"b": "c"}], "d": {"e": None, "f": True}, "g": "", "h": []}
    assert json.loads(as_payload(body)) == json.loads(json.dumps(body, indent=1))


def test_and_that_holds_for_a_real_model_load_payload() -> None:
    """Through the procedure rather than through the helper, because the procedure is what
    a run calls and the helper is only how it is spelled."""
    inputs = a_catalogue(40)
    parsed = json.loads(ModelLoad().payload(inputs))
    assert parsed["period_slots"] == {"FY1": "FY2023", "FY2": "FY2024", "FY3": "FY2025"}
    assert len(parsed["catalogue"]) == 120
    assert parsed["catalogue"][0]["figure_ref"].startswith("timing:")
    assert set(parsed) == {"template", "periods", "period_slots", "catalogue"}


def test_no_key_and_no_value_changed() -> None:
    """Field by field against the indented serialization of the same inputs, so a helper
    that quietly dropped or renamed something could not pass."""
    inputs = a_catalogue(40)
    sent = json.loads(ModelLoad().payload(inputs))
    as_it_was = json.loads(
        json.dumps(
            {
                "template": {
                    "key": inputs.template_key,
                    "template_version": inputs.template_version,
                    "inputs": [
                        {"name": i.name, "line": i.line, "period": i.period, "required": i.required}
                        for i in inputs.inputs
                    ],
                },
                "periods": list(inputs.periods),
                "period_slots": {slot: label for label, slot in inputs.period_slots},
                "catalogue": [f.as_row() for f in inputs.catalogue],
            },
            indent=1,
        )
    )
    assert sent == as_it_was


# ============================================================ and it is smaller


def test_a_real_sized_catalogue_serializes_appreciably_smaller() -> None:
    """The measurement the phase exists for, on the shape that nearly refused: about
    eleven hundred catalogue rows, which is what the first real client folder produced."""
    inputs = a_catalogue(370)
    sent = ModelLoad().payload(inputs)
    padded = json.dumps(json.loads(sent), indent=1)

    assert len(inputs.catalogue) > 1000, "the shape under test is a real-sized one"
    saved = 1 - len(sent) / len(padded)
    assert saved > 0.10, f"only {saved:.0%} smaller; the padding is still being sent"


def test_the_saving_is_headroom_on_the_step_that_has_least() -> None:
    """Not a cost story - at Sonnet's input rate the whitespace was worth pennies. The
    reason it matters is that `_refuse_if_it_will_not_fit` measures bytes, and model-load
    is the step closest to the ceiling that refuses a run outright."""
    from registries.constraints import ConstraintRegistry

    ceiling = ConstraintRegistry.load().context_ceiling()
    sent = len(ModelLoad().payload(a_catalogue(370)))
    padded = len(json.dumps(json.loads(ModelLoad().payload(a_catalogue(370))), indent=1))
    assert padded - sent > 0.05 * ceiling, (
        "the padding removed is worth less than a twentieth of the ceiling, which is not "
        "the headroom this phase claimed"
    )


# ============================================================ nowhere is it still padded


def test_no_procedure_pretty_prints_a_payload() -> None:
    """Walked as code rather than grepped, because the module explaining why it must not
    happen contains the phrase that would satisfy the grep - `tests/reading.py`'s rule,
    which this build has now broken four times."""
    for module in sorted(PROCEDURES.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr != "dumps":
                continue
            given = {kw.arg for kw in node.keywords}
            assert "indent" not in given, (
                f"{module.name} still pretty-prints a payload; use as_payload()"
            )


def test_every_procedure_that_sends_a_payload_goes_through_the_one_helper() -> None:
    """Five call sites had each decided independently how to serialize, and all five had
    decided the same wrong thing - which is what a copied default looks like from the
    inside. Derived from the procedure register rather than from a list typed here, so a
    new skill cannot be added without this noticing (B-066)."""
    from harness.procedures import PROCEDURES as REGISTERED

    modules = {type(p()).__module__ for p in REGISTERED.values()}
    assert modules, "the procedure register is empty"
    for name in sorted(modules):
        source = (ROOT / Path(*name.split("."))).with_suffix(".py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        returns_payload = [
            fn for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef) and fn.name == "payload"
        ]
        assert returns_payload, f"{name} has no payload()"
        for fn in returns_payload:
            calls = {
                node.func.id
                for node in ast.walk(fn)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            assert "as_payload" in calls, f"{name}.payload does not use the shared helper"
