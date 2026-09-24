"""P115 - the column that was promised and never written.

The delivered workbook had a Source column with a header and forty-four empty cells, and
the page in front of it said: *"The Source column says which file and which row, so any one
of them can be checked in a click rather than taken on trust."* Nothing had ever written it.
I found it by opening the file the first real client folder produced.

Every figure envelope already carries its `source_id` and its `locator`. The whole
provenance chain existed and stopped one cell short of the person who needs it - and the
blueprint's rule is that *a figure is proved by arithmetic, or it is seen*. This column is
the seeing.

The first real folder makes the point better than any argument: with the column filled, the
stand-in's nonsense mapping is visible at a glance - "Revenue" sourced from the Balance
Sheet is obviously wrong. With it empty, a wrong figure looked exactly like a right one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook

from deliver.builder import FROM_THE_PROFILE, source_of
from deliver.registry import SOURCE_SUFFIX, TemplateInputs
from registries.errors import RegistryError
from tests.p21.conftest import mapping_for
from tools.write_template import read_named

ROOT = Path(__file__).resolve().parents[2]
HELP = ROOT / "templates" / "Chartwell_Input_Help_v1.xlsx"
DOCS = {"sha256:" + "a" * 64: "Consolidated Income Statements.xlsx"}


def envelope(**over: Any) -> dict[str, Any]:
    figure = {
        "value": 1.0,
        "unit": "currency",
        "currency": "USD",
        "scale": 1000,
        "period": {"type": "FY", "end": "2023-12-31"},
        "source_id": "sha256:" + "a" * 64,
        "locator": "IS!B7",
        "source_version": 1,
        "derivation": None,
        "masked": True,
        "confidence": 0.9,
        "produced_by": "timing-normalization@0.1.0",
        "model_pin": "claude-sonnet-5 @ effort=high",
    }
    figure.update(over)
    return figure


# ============================================================ what a source cell says


def test_it_names_the_document_and_the_row() -> None:
    """Both halves. The document alone sends somebody to a forty-page workbook; the row
    alone is a cell reference to nothing."""
    said = source_of(envelope(), DOCS)
    assert "Consolidated Income Statements.xlsx" in said
    assert "IS!B7" in said


def test_it_uses_the_name_rather_than_the_hash() -> None:
    """A content hash is provenance a machine can check and a person cannot. The point of
    this column is that a person can."""
    assert "sha256" not in source_of(envelope(), DOCS)


def test_an_unknown_hash_falls_back_to_the_hash() -> None:
    """Worse to read and still true. A source cell that gave up and said nothing would be
    indistinguishable from a figure nobody could trace."""
    said = source_of(envelope(), {})
    assert said.startswith("sha256:")
    assert "IS!B7" in said


def test_a_figure_from_the_profile_says_so() -> None:
    """The owner-compensation benchmark is a number a person recorded at setup. There is
    no page to point at, and a blank cell there would read as an oversight beside forty
    filled ones."""
    assert source_of(265000.0, DOCS) == FROM_THE_PROFILE


def test_an_envelope_with_no_locator_says_where_it_came_from_anyway() -> None:
    assert source_of(envelope(source_id="", locator=""), DOCS) == FROM_THE_PROFILE


# ============================================================ the template declares it


def test_the_input_help_workbook_has_a_cell_for_every_input() -> None:
    schema = TemplateInputs.load("Chartwell_Input_Help_v1@1.0")
    assert schema.sources_beside_values
    assert len(schema.sources) == len(schema.inputs)
    names = set(load_workbook(HELP).defined_names)
    for name in schema.sources:
        assert name in names, f"{name} has no named range"


def test_the_firm_s_own_model_does_not() -> None:
    """Not ours to add. The Input Help workbook exists to be copied from and therefore to
    be checked; `Chartwell_Master_Model_v14` stands in for a workbook Chartwell maintains,
    and putting a column in it that this build invented would be this build editing
    somebody else's model."""
    master = TemplateInputs.load("Chartwell_Master_Model_v14@14.2")
    assert master.sources_beside_values is False
    assert master.sources == ()


def test_the_names_follow_the_inputs_rather_than_being_listed() -> None:
    """Forty-four names written out by hand is forty-three names written out by hand and
    one forgotten - and the forgotten one is an input whose figure looks as checkable as
    the others and is not."""
    schema = TemplateInputs.load("Chartwell_Input_Help_v1@1.0")
    assert schema.sources == tuple(f"{i.name}{SOURCE_SUFFIX}" for i in schema.inputs)
    import yaml as _yaml

    raw = _yaml.safe_load(
        (ROOT / "templates" / "inputs" / "Chartwell_Input_Help_v1@1.0.yaml").read_text(
            encoding="utf-8"
        )
    )
    # The file says `sources_beside_values: true` and names not one of them. The comment
    # above it explains the suffix, so this reads the parsed document rather than the text.
    assert raw["sources_beside_values"] is True
    listed = [str(name) for name in raw.get("stamps", [])]
    assert not any(SOURCE_SUFFIX in name for name in listed), "declared by rule, not by list"


def test_they_are_stamps_rather_than_inputs() -> None:
    """The rule that stops a model writing its own provenance: a stamp is the writer's and
    the mapping may never name one. `write_template` refuses a write to a stamp."""
    schema = TemplateInputs.load("Chartwell_Input_Help_v1@1.0")
    assert set(schema.sources) <= set(schema.stamps)
    assert not set(schema.sources) & schema.declared


def test_the_mapping_cannot_write_one() -> None:
    """The refusal itself, not just the arrangement that should produce it."""
    from tools.write_template import write_template

    schema = TemplateInputs.load("Chartwell_Input_Help_v1@1.0")
    name = schema.sources[0]
    with pytest.raises(RegistryError, match="is a stamp"):
        write_template(HELP.read_bytes(), {name: 1.0}, {*schema.declared, name}, {name: "x"})


# ============================================================ in a real workbook


def build(world: Any, **over: Any) -> Any:
    return world["builder"].build(
        mapping_for(world),
        world["inputs"].figures(),
        world["template"],
        run_id="run_p115",
        engagement_id="ENG-P115",
        step_id="release",
        **over,
    )


def test_a_template_without_the_column_is_written_exactly_as_before(world: Any) -> None:
    """The P21 world builds into the master template. Nothing about this phase may change
    what goes into the firm's own model."""
    built = build(world, documents=DOCS)
    assert built.lock.passed
    assert not any(SOURCE_SUFFIX in name for name in built.writes)


# ============================================================ read back, or refuse


def test_the_provenance_is_read_back_after_the_write() -> None:
    """The numeric lock covers the figures. A source cell pointing at the wrong row is
    worse than an empty one, because it is an invitation to check and be reassured by the
    wrong page - so the writer reads these back too."""
    source = (ROOT / "deliver" / "builder.py").read_text(encoding="utf-8")
    body = source[source.index("        before = _lock_text") : source.index("        lock = ")]
    assert "read_named(data, list(stamps))" in body
    assert "did not read back as written" in body


def test_a_source_cell_that_does_not_read_back_stops_the_delivery(
    world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal, exercised. A workbook whose provenance did not survive the write is a
    workbook whose figures cannot be checked, and it does not leave."""
    import deliver.builder as builder

    real = builder.read_named

    def lying(data: bytes, names: Any) -> dict[str, Any]:
        out = real(data, names)
        return {k: ("something else" if k == "Run_Id" else v) for k, v in out.items()}

    monkeypatch.setattr(builder, "read_named", lying)
    with pytest.raises(RegistryError, match="did not read back as written"):
        build(world, documents=DOCS)


def test_the_stamps_a_template_already_had_are_still_written(world: Any) -> None:
    built = build(world, documents=DOCS)
    back = read_named(built.data, ["Template_Version", "Run_Id"])
    assert back["Run_Id"] == "run_p115"
    assert back["Template_Version"] == world["template"].template_version


# ============================================================ the workbook people open


def input_help() -> Any:
    """The Input Help template, registered straight off disk."""
    import hashlib

    from deliver.registry import RegisteredTemplate

    schema = TemplateInputs.load("Chartwell_Input_Help_v1@1.0")
    data = HELP.read_bytes()
    return RegisteredTemplate(
        file=schema.file,
        template_version=schema.template_version,
        content_hash=f"sha256:{hashlib.sha256(data).hexdigest()}",
        named_ranges=frozenset(load_workbook(HELP).defined_names),
        inputs=schema,
        path=HELP,
    )


def filled(waived: tuple[str, ...] = ()) -> Any:
    """Build the Input Help workbook with every input bound to one figure."""
    from deliver.builder import ModelBuilder, waiver_for

    template = input_help()
    bound = [n for n in template.inputs.required if n not in waived]
    figures = {f"timing:{n}": envelope(value=float(i)) for i, n in enumerate(bound, start=1)}
    mapping = {
        "template_mapping": {
            "template_version": template.template_version,
            "bindings": [{"named_range": n, "figure_ref": f"timing:{n}"} for n in bound],
            "unmapped_template_inputs": [
                {"named_range": n, "why": "nothing in the folder answered it"} for n in waived
            ],
        }
    }
    return ModelBuilder().build(
        mapping,
        figures,
        template,
        run_id="run_p115",
        engagement_id="ENG-P115",
        step_id="release",
        waived=(waiver_for("release", waived),) if waived else (),
        documents=DOCS,
    )


def test_every_written_figure_has_its_document_beside_it() -> None:
    """The exit criterion, in the workbook itself. Before this phase the column had a
    header and forty-four empty cells under a page promising it was filled."""
    built = filled()
    schema = input_help().inputs
    back = read_named(built.data, list(schema.sources))
    for name in schema.required:
        said = back[f"{name}{SOURCE_SUFFIX}"]
        assert said, f"{name} has no source"
        assert "Consolidated Income Statements.xlsx" in str(said)
        assert "IS!B7" in str(said)


def test_a_waived_input_has_no_source_because_there_is_none() -> None:
    """Its Value cell already says `not found`. A source cell repeating that would be two
    statements of one fact; an invented one would be worse."""
    name = input_help().inputs.required[0]
    built = filled(waived=(name,))
    back = read_named(built.data, [f"{name}{SOURCE_SUFFIX}"])
    assert not back[f"{name}{SOURCE_SUFFIX}"]


def test_the_figures_are_still_written_and_locked() -> None:
    """The column is an addition. If it cost the lock anything it would not be worth it."""
    built = filled()
    assert built.lock.passed
    back = read_named(built.data, list(built.writes))
    assert back == built.writes
