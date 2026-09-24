"""P105 - thousands on the page, cents in the cell.

The analyst gave the firm's convention on 2026-09-22: *"The statements always need to be
put into thousands in the output, but it usually doesn't come in as thousands, it comes in
as normal. But don't round to zero decimal points before putting in the output, have Excel
round it for visual affect to zero decimal points, but keep all the decimals in there."*

Two rules, and the second is the one worth being careful about.

**Thousands.** The workbook declares `scale: 1000`. What arrives is usually units, so a
figure has to be restated before it can be written - and `deliver/builder.py` refuses to do
that itself: *"restating is arithmetic and does not happen in the writer"*. Dividing by a
thousand in the last step before a cell would put the one operation nobody can see
underneath the one number everybody reads.

**Round for the eye, never for the file.** A number format changes what is drawn and
nothing about what is stored. Rounding before the write would bake the rounding into the
figure a model is built on, and forty rounded rows do not re-add to the total they came
from - which is the same arithmetic P99 spent a phase proving holds.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
import yaml
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
WORKBOOK = ROOT / "templates" / "Chartwell_Input_Help_v1.xlsx"
SCHEMA = ROOT / "templates" / "inputs" / "Chartwell_Input_Help_v1@1.0.yaml"


def schema() -> dict:
    return yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))


# ============================================================ thousands


def test_the_workbook_declares_thousands() -> None:
    assert schema()["scale"] == 1000


def test_it_says_so_where_somebody_will_read_it() -> None:
    """On the first sheet, which is the one that opens. A workbook of figures whose scale is
    only in a YAML file is a workbook somebody reads in units."""
    book = load_workbook(WORKBOOK)
    try:
        said = " ".join(
            str(c.value)
            for row in book["Not the model"].iter_rows()
            for c in row
            if c.value
        )
        assert "THOUSANDS" in said.upper()
        # The claim, not the sentence. This used to assert the literal words "stored to
        # the cent", which were P105's own and which P108 made false: the cell holds every
        # decimal the restatement produced. An assertion precise about wording and wrong
        # about the fact keeps a wrong claim on the page that an analyst actually reads.
        assert "decimal" in said.lower(), "the page says what precision is kept"
        assert "stored to the cent" not in said, "a rounding nobody does"
    finally:
        book.close()


def test_the_model_template_beside_it_is_still_in_units() -> None:
    """The scale is a property of each template rather than a setting somebody changed
    globally - and a phase that quietly restated the firm's own model would be the kind of
    change nobody notices until a figure is out by a thousand."""
    master = yaml.safe_load(
        (ROOT / "templates" / "inputs" / "Chartwell_Master_Model_v14@14.2.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert master["scale"] == 1


# ============================================================ round for the eye


def test_every_value_cell_displays_whole_dollars() -> None:
    book = load_workbook(WORKBOOK)
    try:
        sheet = book["Input"]
        formats = {
            sheet.cell(row=r, column=2).number_format
            for r in range(5, 5 + len(schema()["required"]))
        }
        assert formats == {"#,##0"}
    finally:
        book.close()


def test_the_format_changes_what_is_drawn_and_not_what_is_stored() -> None:
    """The whole rule in one assertion. `#,##0` is a display instruction; the cell keeps
    every decimal, so `=B5*2` uses the cents and a total built on these rows re-adds to what
    the statements say."""
    book = load_workbook(WORKBOOK)
    try:
        book["Input"]["B5"] = 37_559.55936
        saved = BytesIO()
        book.save(saved)
    finally:
        book.close()

    again = load_workbook(BytesIO(saved.getvalue()))
    try:
        cell = again["Input"]["B5"]
        assert cell.value == pytest.approx(37_559.55936), "the cents survived the round trip"
        assert cell.number_format == "#,##0", "and Excel still draws it whole"
    finally:
        again.close()


def test_nothing_rounds_the_value_on_its_way_to_the_cell() -> None:
    """Held on the writer's source. A `round()` between a figure and a cell would satisfy
    every test above - the format would still be right and the stored value would already
    have lost its decimals."""
    for module in ("deliver/builder.py", "tools/synthesize_templates.py"):
        source = (ROOT / module).read_text(encoding="utf-8")
        assert "round(" not in source, f"{module} rounds something on the way to a cell"


def test_the_display_format_is_named_rather_than_written_inline() -> None:
    """`#,##0` twice in two files is how the two drift. It is one constant with the reason
    beside it."""
    source = (ROOT / "tools" / "synthesize_templates.py").read_text(encoding="utf-8")
    assert 'SHOWN_TO_THE_DOLLAR = "#,##0"' in source
    assert source.count('"#,##0"') == 1


# ============================================================ what is still refused


def test_the_writer_still_refuses_a_figure_at_the_wrong_scale() -> None:
    """Restating is arithmetic. A writer that divided by a thousand to make a figure fit
    would be doing the one operation nobody can see underneath the one number everybody
    reads - so it refuses, and names both scales."""
    from deliver.builder import _value_of
    from registries.errors import RegistryError

    with pytest.raises(RegistryError) as refused:
        _value_of({"value": 1.0, "scale": 1, "unit": "currency", "currency": "USD"},
                  1000, "USD", "Revenue_FY1")
    said = str(refused.value)
    assert "scale 1" in said and "1000" in said
    assert "restating is arithmetic" in said


def test_the_restatement_has_somewhere_to_happen() -> None:
    """Not built here, and not nowhere: the recompute engine already carries a
    `restate_scale` operation, so a skill can derive the restated figure and the tie-out
    can check it. This asserts the hook exists, because "the writer refuses" is only a
    tolerable answer while something else can do it."""
    from tools.recompute import OPERATIONS

    assert "restate_scale" in OPERATIONS


def test_the_schema_says_why_the_writer_will_not_restate() -> None:
    """Written beside the declaration, because the next person to see a units figure
    refused by a thousands template will look there first."""
    # Flattened with the comment markers removed: the sentence wraps mid-phrase, so a
    # naive join leaves a `#` between "restating is" and "arithmetic". A test that depended
    # on where a comment wrapped would fail on a reflow that changed nothing.
    said = " ".join(
        line.lstrip("# ").strip()
        for line in SCHEMA.read_text(encoding="utf-8").splitlines()
    )
    said = " ".join(said.split())
    assert "restating is arithmetic" in said
    assert "in thousands" in said
