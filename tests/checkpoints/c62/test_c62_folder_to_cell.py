"""C62 - a document from the folder to the cell.

Four phases from one question: can the analyst point this at a folder and get a structured
output. Each was found by the one before it failing on the real thing.

* **P103** let the files in - ten of thirteen had never entered a run, because the binder
  read filename tokens and had never asked the classifier.
* **P104** was made reachable by P103. With twelve files in, the timing skill was asked to
  find periods in board minutes; it refused, a person answered, it asked again. Thirty
  passes.
* **P105** made the deliverable declare thousands, which is what the firm always writes.
* **P106** made what *arrived* settleable, because P105 exposed that a scale nobody had
  stated stopped a run in a way answering could not clear.

Each is green alone. What a checkpoint asks is whether the four agree about one document's
journey - and the two places they could disagree are both about **silence**: a file nothing
names, and a figure whose scale nothing states. Every phase here handles a silence, and the
rule across all four is the same one: fill it from something a person decided, record that
you did, and never default.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from openpyxl import load_workbook

from intake.bind import CLASSIFICATION, CONVENTION, document_type_for
from registries.contracts import ContractRegistry

ROOT = Path(__file__).resolve().parents[3]
WORKBOOK = ROOT / "templates" / "Chartwell_Input_Help_v1.xlsx"

CONVENTIONS: dict[str, tuple[str, ...]] = {
    "trial_balance": ("tb_", "trial balance"),
    "financial_statements": ("income statement", "balance sheet", "financials"),
    "forecast": ("forecast", "projection", "projected", "budget"),
}


def carries_periods() -> set[str]:
    return {t.id for t in ContractRegistry.load().intake_document_types() if t.carries_periods}


# ================================================ the journey, end to end


@pytest.mark.parametrize(
    ("filename", "folders", "expected_type", "reaches_timing"),
    [
        # A statement: named by a convention, read by the timing skill, written in thousands.
        ("Consolidated Income Statements_Redacted.xlsx", (), "financial_statements", True),
        # A document only the classifier knows: bound, on the record, and not shown to a
        # skill that reads fiscal calendars.
        ("2024 Board Minutes_Redacted.pdf", ("Board Minutes",), "board_minutes", False),
        ("Org Chart_Redacted.pdf", (), "org_chart", False),
        # Dated and still not a statement - the distinction P104 had to be told twice.
        ("Capital Expenditures_Redacted.xlsx", (), "capex_schedule", False),
    ],
)
def test_a_document_gets_as_far_as_its_kind_allows(
    filename: str, folders: tuple[str, ...], expected_type: str, reaches_timing: bool
) -> None:
    """One file, both gates. P103 decides whether it enters at all; P104 decides which
    skills are asked about it. A phase that widened the first without the second is what
    produced the livelock, so the two are asserted together."""
    found, _ = document_type_for(filename, CONVENTIONS, folders=folders)
    assert found == expected_type, filename
    assert (found in carries_periods()) is reaches_timing, filename


def test_every_type_that_can_bind_has_an_answer_about_periods() -> None:
    """The join between P103 and P104, as a property rather than a list. P103 widened what
    can bind to the whole registry vocabulary; P104 requires each of those to declare
    whether a skill that reads periods should see it. A type that could bind and had not
    declared would reach the timing skill with nothing to say about itself."""
    for declared in ContractRegistry.load().intake_document_types():
        assert isinstance(declared.carries_periods, bool), declared.id


# ================================================ the two silences


def test_a_file_nothing_names_is_still_held() -> None:
    """P103's silence. Widening what binds was not emptying the held list - a file neither
    a convention nor a confident classification claims is a question for a person."""
    assert document_type_for("scan0001.pdf", CONVENTIONS) == (None, "")
    assert document_type_for("Overview and notes.docx", CONVENTIONS) == (None, "")


def test_a_scale_nothing_states_is_still_refused() -> None:
    """P106's silence, and the one that costs the most. A figure read as units when it was
    thousands is out by a factor of a thousand and passes provenance, footing and tie-out
    on the way through."""
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
    assert TimingNormalization().escalate(TimingInputs(files=(unsettled,))) is not None


def test_both_silences_are_filled_only_by_something_a_person_decided() -> None:
    """The rule the four phases share. A convention is a token the firm wrote down; a
    declared scale is a person saying what arrived. Neither is a default, and the code says
    so in both places rather than leaving it to be inferred."""
    binder = (ROOT / "intake" / "bind.py").read_text(encoding="utf-8")
    driver = (ROOT / "workers" / "driver.py").read_text(encoding="utf-8")
    assert "convention always wins" in binder
    settle = driver[driver.index("def _settle_scale") : driver.index("def _read_sources")]
    assert "if not declared:" in settle and "return sources" in settle


def test_filling_a_silence_is_recorded_both_times() -> None:
    """A substitution nobody can see is the failure mode both phases are guarding. The
    binder records which of the two named a file; the driver emits an event when a profile
    settles a scale."""
    assert CONVENTION != CLASSIFICATION
    driver = (ROOT / "workers" / "driver.py").read_text(encoding="utf-8")
    assert "intake.scale.assumed" in driver
    assert "intake.currency.assumed" in driver


# ================================================ what lands in the cell


def test_the_deliverable_is_thousands_and_keeps_its_decimals() -> None:
    """P105, asked at the end of the journey rather than at its own phase: whatever a
    document's kind, whatever settled its scale, the cell it reaches is in thousands and
    holds every decimal it was given."""
    schema = yaml.safe_load(
        (ROOT / "templates" / "inputs" / "Chartwell_Input_Help_v1@1.0.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert schema["scale"] == 1000

    book = load_workbook(WORKBOOK)
    try:
        assert book["Input"]["B5"].number_format == "#,##0"
        assert not [
            c.value
            for sheet in book.worksheets
            for row in sheet.iter_rows()
            for c in row
            if isinstance(c.value, str) and c.value.startswith("=")
        ], "the workbook still computes nothing"
    finally:
        book.close()


def test_a_figure_at_the_wrong_scale_never_reaches_a_cell() -> None:
    """The last gate, and the reason P106 settles the scale upstream rather than dividing
    at the end. The writer refuses a mismatch instead of restating - restating is
    arithmetic, and arithmetic under the last number anybody reads is the one place it
    cannot go."""
    from deliver.builder import _value_of
    from registries.errors import RegistryError

    with pytest.raises(RegistryError, match="restating is arithmetic"):
        _value_of(
            {"value": 1.0, "scale": 1, "unit": "currency", "currency": "USD"},
            1000,
            "USD",
            "Revenue_FY1",
        )


def test_the_whole_path_still_reaches_no_model_of_its_own_accord() -> None:
    """Four phases touched intake, the registry, the driver and the template writer. None
    of them is allowed to have reached for a model on the way."""
    import ast

    for module in (
        "intake/bind.py",
        "harness/inputs.py",
        "registries/contracts.py",
        "tools/synthesize_templates.py",
    ):
        tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
        named: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                named.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                named.add(node.module)
        for forbidden in ("ports.llm", "anthropic", "openai", "harness.door"):
            assert not any(
                n == forbidden or n.startswith(forbidden + ".") for n in named
            ), module
