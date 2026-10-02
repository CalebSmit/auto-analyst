"""Build the synthetic model templates under templates/ from their input schemas.

The firm's real templates are Chartwell's and arrive at the P24 pilot. Until then the
registry, the writer and the QC gate need workbooks with the declared shape: an Inputs
sheet with one named range per declared input, a Historicals sheet of formulas over
those names, a DCF sheet with more formulas, and the two stamp cells. No client data,
no values - a template is empty by definition.

    python tools/synthesize_templates.py            # writes both templates
    python tools/synthesize_templates.py --check    # exit 1 if either differs from disk

Deterministic: the same schema produces the same workbook.
"""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.workbook.defined_name import DefinedName

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # this is run as a script, from wherever somebody is standing
    sys.path.insert(0, str(ROOT))

from tools._environment import needs  # noqa: E402

# What this tool cannot run without. Called here, before the first project import, because
# that import is where a bare `python tools/synthesize_templates.py` fails - and what it
# fails with is a traceback about somebody else's library rather than the line to
# type. P58 was written about that failure for `serve.py`; six more tools had it, and
# this is one of them.
needs("openpyxl", "yaml", script="tools/synthesize_templates.py")

# The word the writer puts in a waived input's cell. Imported rather than repeated: this
# front page describes what the writer does, and two copies of one string drift apart.
from deliver.builder import NOT_FOUND  # noqa: E402
from deliver.registry import SOURCE_SUFFIX  # noqa: E402

TEMPLATES = ROOT / "templates"
INPUTS = TEMPLATES / "inputs"

LINES = [
    ("Revenue", "Revenue"),
    ("COGS", "Cost of sales"),
    ("Officer_Comp", "Officer compensation"),
    ("Wages", "Wages"),
    ("Payroll_Taxes", "Payroll taxes"),
    ("Rent", "Rent"),
    ("Repairs", "Repairs and maintenance"),
    ("Utilities", "Utilities"),
    ("Insurance", "Insurance"),
    ("Professional_Fees", "Professional fees"),
    ("Depreciation", "Depreciation"),
    ("Travel", "Travel"),
    ("Office", "Office supplies"),
    ("Other_Opex", "Other operating expense"),
]


NOT_THE_MODEL = "This workbook is not the Chartwell model."

SHOWN_TO_THE_DOLLAR = "#,##0"
"""Excel's display format for the value column: thousands separated, no decimals.

A format and not a rounding. `#,##0` changes what is drawn and nothing about what
is stored, which is the whole point - `=B7*2` still uses the cents."""

WHAT_IT_IS = [
    "It is a worksheet of inputs, laid out the way the model's Input tab expects them, for",
    "you to copy from. Nothing here is a valuation and nothing here has been concluded.",
    "",
    "FIGURES ARE IN THOUSANDS, whatever the client's own statements were stated in. They are",
    "shown to the nearest dollar and stored exactly as they were restated - not rounded to",
    "the cent, not rounded at all. What you see is Excel rounding for the eye; the cell",
    "underneath keeps every decimal, so a total you build on these adds up to what the",
    "statements say rather than to the rounding.",
    "",
    "Every figure was read out of a document in the engagement's folder. The Source column",
    "says which file and which row, so any one of them can be checked in a click rather than",
    "taken on trust.",
    "",
    f"A Value reading {NOT_FOUND.upper()!r} is an input nothing in the folder answered. It says",
    "so in words rather than being left blank, because a blank cell among filled ones reads",
    "as a",
    "zero, and a zero is a number. Nothing here is guessed: a wrong figure that looks like a",
    "reading is the one failure this whole build exists to prevent. Every one of them is also",
    "listed by name in the run's review queue, beside the person who said to write without it.",
]


def build_input_help(schema: dict) -> bytes:  # type: ignore[type-arg]
    """The version 1 deliverable: an Input tab and a page saying what this is not.

    Deliberately not the same shape as the model templates above. Those carry Historicals
    and DCF sheets of formulas over their named ranges, which is what makes them models. A
    workbook that computed anything would be the thing version 1 is defined against - the
    analyst runs the model, and this fills in front of him.

    The first sheet is the disclaimer rather than the data, because the first sheet is what
    opens, and a file that looks like the firm's model until you read the second tab is one
    filename away from being used as it.
    """
    wb = Workbook()
    front = wb.active
    front.title = "Not the model"
    front["A1"] = NOT_THE_MODEL
    front["A1"].font = Font(bold=True, size=14)
    for n, line in enumerate(WHAT_IT_IS, start=3):
        front.cell(row=n, column=1, value=line)
    front.column_dimensions["A"].width = 96

    sheet = wb.create_sheet("Input")
    sheet["A1"] = "Input"
    sheet["B1"] = "Value"
    sheet["C1"] = "Source"
    for cell in ("A1", "B1", "C1"):
        sheet[cell].font = Font(bold=True)
    sheet["A2"] = "Template version"
    sheet["A3"] = "Run id"
    wb.defined_names["Template_Version"] = DefinedName("Template_Version", attr_text="Input!$B$2")
    wb.defined_names["Run_Id"] = DefinedName("Run_Id", attr_text="Input!$B$3")

    row = 5
    for entry in [*schema["required"], *schema.get("optional", [])]:
        sheet.cell(row=row, column=1, value=f"{entry['line']} ({entry['period']})")
        # Zero decimals on the *display* and every decimal in the cell. The analyst's rule,
        # and it is the right way round: rounding before the write would bake a rounding
        # error into the number a model is built on, and a schedule of forty rounded
        # figures does not re-add to the total it came from. Excel rounds for the eye.
        sheet.cell(row=row, column=2).number_format = SHOWN_TO_THE_DOLLAR
        wb.defined_names[entry["name"]] = DefinedName(entry["name"], attr_text=f"Input!$B${row}")
        # And the cell beside it, which says which document and which row the figure came
        # from. A named range because everything written into this workbook is bound by
        # name - `C7` is not a contract - and a stamp rather than an input because the
        # writer owns it and the mapping may never name one.
        if schema.get("sources_beside_values"):
            source = f"{entry['name']}{SOURCE_SUFFIX}"
            wb.defined_names[source] = DefinedName(source, attr_text=f"Input!$C${row}")
        row += 1
    sheet.column_dimensions["A"].width = 44
    sheet.column_dimensions["B"].width = 18
    sheet.column_dimensions["C"].width = 52

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def build(schema: dict) -> bytes:  # type: ignore[type-arg]
    wb = Workbook()
    inputs = wb.active
    inputs.title = "Inputs"
    inputs["A1"] = "Input"
    inputs["B1"] = "Value"
    inputs["A2"] = "Template version"
    inputs["A3"] = "Run id"
    wb.defined_names["Template_Version"] = DefinedName("Template_Version", attr_text="Inputs!$B$2")
    wb.defined_names["Run_Id"] = DefinedName("Run_Id", attr_text="Inputs!$B$3")

    row = 5
    for entry in [*schema["required"], *schema["optional"]]:
        inputs.cell(row=row, column=1, value=f"{entry['line']} ({entry['period']})")
        wb.defined_names[entry["name"]] = DefinedName(entry["name"], attr_text=f"Inputs!$B${row}")
        row += 1

    hist = wb.create_sheet("Historicals")
    hist["A1"] = "Line"
    for n, fy in enumerate(("FY1", "FY2", "FY3"), start=2):
        hist.cell(row=1, column=n, value=fy)
    r = 2
    for key, label in LINES:
        hist.cell(row=r, column=1, value=label)
        for n, fy in enumerate(("FY1", "FY2", "FY3"), start=2):
            hist.cell(row=r, column=n, value=f"={key}_{fy}")
        r += 1
    hist.cell(row=r, column=1, value="Gross profit")
    for n, fy in enumerate(("FY1", "FY2", "FY3"), start=2):
        hist.cell(row=r, column=n, value=f"=Revenue_{fy}-COGS_{fy}")
    gross = r
    r += 1
    hist.cell(row=r, column=1, value="Operating expenses")
    for n, fy in enumerate(("FY1", "FY2", "FY3"), start=2):
        names = "+".join(f"{key}_{fy}" for key, _ in LINES[2:])
        hist.cell(row=r, column=n, value=f"={names}")
    opex = r
    r += 1
    hist.cell(row=r, column=1, value="EBITDA (reported)")
    for n, _ in enumerate(("FY1", "FY2", "FY3"), start=2):
        col = hist.cell(row=1, column=n).column_letter
        hist.cell(row=r, column=n, value=f"={col}{gross}-{col}{opex}+{col}{2 + 10}")
    r += 1
    hist.cell(row=r, column=1, value="Officer comp over benchmark")
    for n, fy in enumerate(("FY1", "FY2", "FY3"), start=2):
        hist.cell(row=r, column=n, value=f"=Officer_Comp_{fy}-Owner_Comp_Benchmark")

    dcf = wb.create_sheet("DCF")
    dcf["A1"] = "Terminal WACC"
    dcf["B1"] = "=WACC_Terminal"
    dcf["A2"] = "Target NWC"
    dcf["B2"] = "=NWC_Target"
    dcf["A3"] = "Selected multiple"
    dcf["B3"] = "=EV_EBITDA_Multiple"
    dcf["A4"] = "Template"
    dcf["B4"] = "=Template_Version"

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def main(argv: list[str]) -> int:
    check = "--check" in argv
    status = 0
    for schema_path in sorted(INPUTS.glob("*.yaml")):
        schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
        target = TEMPLATES / schema["template"]
        # `kind` chooses the shape. A model template carries formulas; the input-help
        # workbook carries none, which is the difference between the thing the analyst
        # runs and the thing this build fills in front of him.
        data = (
            build_input_help(schema) if schema.get("kind") == "input_help" else build(schema)
        )
        if check:
            if not target.is_file() or _cells(target.read_bytes()) != _cells(data):
                print(f"differs: {target.name}")
                status = 1
            continue
        target.write_bytes(data)
        print(f"wrote {target.name}: {len(schema['required'])} required inputs")
    return status


def _cells(data: bytes) -> list[tuple[str, str, object]]:
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(data))
    found = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    found.append((ws.title, cell.coordinate, cell.value))
    found.append(("names", "", sorted(wb.defined_names.keys())))
    return found


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
